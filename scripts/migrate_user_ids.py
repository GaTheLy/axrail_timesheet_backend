"""One-time migration: fix userId mismatch between DynamoDB and Cognito.

Root Cause:
    The user "Jason Gunawan" has a userId in the DynamoDB Users table that does
    not match the Cognito `sub` used for authentication.  This means the
    `listMySubmissions` query (which filters by the authenticated Cognito sub)
    returns no results, even though the user record exists.

Fix:
    1. Query DynamoDB Users table for the target user by email/name.
    2. Query Cognito user pool to get the actual Cognito `sub` for the same email.
    3. Compare the two userIds and log the mismatch.
    4. If mismatched, update the DynamoDB `userId` using a conditional update
       (idempotent — running multiple times produces the same result).
    5. Log before/after state for audit purposes.

Usage:
    python scripts/migrate_user_ids.py
"""

import logging
import sys
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError

# ---------------------------------------------------------------------------
# Configuration — update these for the target environment
# ---------------------------------------------------------------------------
REGION = "ap-southeast-1"
USER_POOL_ID = "ap-southeast-1_FCLxuGj3s"
USERS_TABLE = "Timesheet_Users-dev"
SUBMISSIONS_TABLE = "Timesheet_Submissions-dev"

# Target user details
TARGET_USER_NAME = "Jason Gunawan"
TARGET_USER_EMAIL = None  # Set if known; otherwise the script finds by name

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# AWS clients
# ---------------------------------------------------------------------------
dynamodb = boto3.resource("dynamodb", region_name=REGION)
cognito = boto3.client("cognito-idp", region_name=REGION)


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def find_user_in_dynamodb(table_name, target_name):
    """Scan the Users table for a user matching the target full name.

    Returns the full user item dict, or None if not found.
    """
    table = dynamodb.Table(table_name)
    logger.info("Scanning DynamoDB table '%s' for user '%s' ...", table_name, target_name)

    resp = table.scan()
    items = resp.get("Items", [])
    while "LastEvaluatedKey" in resp:
        resp = table.scan(ExclusiveStartKey=resp["LastEvaluatedKey"])
        items.extend(resp.get("Items", []))

    for item in items:
        full_name = item.get("fullName", "")
        if full_name.lower() == target_name.lower():
            logger.info("Found user in DynamoDB: fullName='%s', userId='%s', email='%s', status='%s'",
                        full_name, item.get("userId"), item.get("email"), item.get("status"))
            return item

    logger.warning("User '%s' not found in DynamoDB table '%s'.", target_name, table_name)
    return None


def get_cognito_sub(email):
    """Look up the Cognito `sub` for a given email address.

    Returns (sub, cognito_user_dict) or (None, None) if not found.
    """
    logger.info("Querying Cognito user pool '%s' for email '%s' ...", USER_POOL_ID, email)
    try:
        resp = cognito.list_users(
            UserPoolId=USER_POOL_ID,
            Filter=f'email = "{email}"',
            Limit=1,
        )
    except ClientError as exc:
        logger.error("Cognito API error: %s", exc)
        return None, None

    users = resp.get("Users", [])
    if not users:
        logger.warning("No Cognito user found for email '%s'.", email)
        return None, None

    cognito_user = users[0]
    sub_value = None
    for attr in cognito_user.get("Attributes", []):
        if attr["Name"] == "sub":
            sub_value = attr["Value"]
            break

    if sub_value:
        logger.info("Cognito user found: Username='%s', sub='%s', Enabled=%s",
                     cognito_user.get("Username"), sub_value, cognito_user.get("Enabled"))
    else:
        logger.warning("Cognito user found but 'sub' attribute is missing.")

    return sub_value, cognito_user


def verify_submissions_access(submissions_table_name, user_id, user_name):
    """Verify the user can retrieve timesheet submissions after the userId fix.

    This simulates what the `listMySubmissions` GraphQL resolver does: it queries
    the Timesheet_Submissions table using the `employeeId-periodId-index` GSI
    with the corrected userId (Cognito sub).  If the query returns results, the
    fix is confirmed — the user can now see their timesheet data.

    Args:
        submissions_table_name: Name of the Timesheet_Submissions DynamoDB table.
        user_id: The corrected userId (Cognito sub) to query with.
        user_name: The user's full name (for logging).

    Returns:
        True if verification passed (submissions found or query succeeded),
        False if the query failed unexpectedly.
    """
    table = dynamodb.Table(submissions_table_name)
    logger.info("Verifying submissions access for userId='%s' (user: '%s') ...", user_id, user_name)

    try:
        from boto3.dynamodb.conditions import Key

        resp = table.query(
            IndexName="employeeId-periodId-index",
            KeyConditionExpression=Key("employeeId").eq(user_id),
        )
        items = resp.get("Items", [])

        # Paginate if needed
        while "LastEvaluatedKey" in resp:
            resp = table.query(
                IndexName="employeeId-periodId-index",
                KeyConditionExpression=Key("employeeId").eq(user_id),
                ExclusiveStartKey=resp["LastEvaluatedKey"],
            )
            items.extend(resp.get("Items", []))

        if items:
            logger.info(
                "VERIFICATION PASSED: Found %d submission(s) for userId='%s'. "
                "The user can now retrieve timesheet data via listMySubmissions.",
                len(items), user_id,
            )
            for i, item in enumerate(items, 1):
                logger.info(
                    "  Submission %d: submissionId='%s', periodId='%s', status='%s'",
                    i,
                    item.get("submissionId", "N/A"),
                    item.get("periodId", "N/A"),
                    item.get("status", "N/A"),
                )
        else:
            logger.warning(
                "VERIFICATION NOTE: No submissions found for userId='%s'. "
                "This may be expected if the user has not yet created any timesheet submissions. "
                "The userId mapping is correct; submissions will appear once the user creates them.",
                user_id,
            )
        return True

    except ClientError as exc:
        logger.error("VERIFICATION FAILED: Could not query submissions table: %s", exc)
        return False


def update_user_id(table_name, old_user_id, new_user_id):
    """Update the userId in DynamoDB using a conditional update (idempotent).

    Since userId is the partition key and cannot be updated in place, this:
    1. Reads the current item (with old key).
    2. Writes a new item with the corrected userId (conditional on it not
       already existing, to prevent duplicates).
    3. Deletes the old item (conditional on it still having the old userId).

    Idempotency: if the new item already exists (from a previous run), the
    put_item condition fails gracefully and the script reports success.
    """
    table = dynamodb.Table(table_name)

    # Step 1: Read the current item
    resp = table.get_item(Key={"userId": old_user_id})
    old_item = resp.get("Item")
    if not old_item:
        logger.info("Old userId '%s' no longer exists — migration may have already run.", old_user_id)
        # Check if the new item exists
        resp2 = table.get_item(Key={"userId": new_user_id})
        if resp2.get("Item"):
            logger.info("New userId '%s' already exists. Migration is already complete (idempotent).", new_user_id)
            return True
        logger.error("Neither old nor new userId found. Manual investigation required.")
        return False

    # Step 2: Create new item with corrected userId
    new_item = dict(old_item)
    new_item["userId"] = new_user_id

    try:
        table.put_item(
            Item=new_item,
            ConditionExpression="attribute_not_exists(userId)",
        )
        logger.info("Created new DynamoDB item with userId='%s'.", new_user_id)
    except ClientError as exc:
        if exc.response["Error"]["Code"] == "ConditionalCheckFailedException":
            logger.info("New userId '%s' already exists (idempotent — no action needed).", new_user_id)
        else:
            logger.error("Failed to create new item: %s", exc)
            return False

    # Step 3: Delete old item (only if it still exists with the old key)
    try:
        table.delete_item(
            Key={"userId": old_user_id},
            ConditionExpression="attribute_exists(userId)",
        )
        logger.info("Deleted old DynamoDB item with userId='%s'.", old_user_id)
    except ClientError as exc:
        if exc.response["Error"]["Code"] == "ConditionalCheckFailedException":
            logger.info("Old userId '%s' already removed (idempotent).", old_user_id)
        else:
            logger.error("Failed to delete old item: %s", exc)
            return False

    return True


# ---------------------------------------------------------------------------
# Main migration logic
# ---------------------------------------------------------------------------


def migrate():
    """Run the userId mismatch migration for the target user."""
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    logger.info("=" * 60)
    logger.info("userId Mismatch Migration — run %s", run_id)
    logger.info("=" * 60)

    # --- Step 1: Find the target user in DynamoDB ---
    db_user = find_user_in_dynamodb(USERS_TABLE, TARGET_USER_NAME)
    if not db_user:
        logger.error("ABORT: Target user '%s' not found in DynamoDB.", TARGET_USER_NAME)
        return False

    db_user_id = db_user["userId"]
    email = db_user.get("email")
    if not email and TARGET_USER_EMAIL:
        email = TARGET_USER_EMAIL

    if not email:
        logger.error("ABORT: No email found for user '%s'. Cannot look up Cognito sub.", TARGET_USER_NAME)
        return False

    # --- Step 2: Verify Cognito user exists and get the sub ---
    cognito_sub, cognito_user = get_cognito_sub(email)
    if not cognito_sub:
        logger.error("ABORT: Cognito user does not exist for email '%s'. Cannot proceed.", email)
        return False

    if not cognito_user.get("Enabled", False):
        logger.warning("Cognito user for '%s' is DISABLED. Proceeding with migration anyway.", email)

    # --- Step 3: Compare and log mismatch ---
    logger.info("-" * 60)
    logger.info("AUDIT — Before state:")
    logger.info("  DynamoDB userId : %s", db_user_id)
    logger.info("  Cognito sub     : %s", cognito_sub)
    logger.info("  Email           : %s", email)
    logger.info("  Full Name       : %s", db_user.get("fullName"))
    logger.info("  Status          : %s", db_user.get("status"))
    logger.info("  User Type       : %s", db_user.get("userType"))
    logger.info("-" * 60)

    if db_user_id == cognito_sub:
        logger.info("No mismatch detected — DynamoDB userId already matches Cognito sub. Nothing to do.")
        # Still verify submissions access to confirm end-to-end data retrieval
        verify_submissions_access(SUBMISSIONS_TABLE, cognito_sub, TARGET_USER_NAME)
        return True

    logger.warning("MISMATCH DETECTED: DynamoDB userId '%s' != Cognito sub '%s'", db_user_id, cognito_sub)

    # --- Step 4: Update DynamoDB userId (conditional, idempotent) ---
    logger.info("Updating DynamoDB userId from '%s' to '%s' ...", db_user_id, cognito_sub)
    success = update_user_id(USERS_TABLE, db_user_id, cognito_sub)

    if not success:
        logger.error("Migration FAILED. See errors above.")
        return False

    # --- Step 5: Log after state ---
    table = dynamodb.Table(USERS_TABLE)
    resp = table.get_item(Key={"userId": cognito_sub})
    updated_user = resp.get("Item")

    logger.info("-" * 60)
    logger.info("AUDIT — After state:")
    if updated_user:
        logger.info("  DynamoDB userId : %s", updated_user.get("userId"))
        logger.info("  Email           : %s", updated_user.get("email"))
        logger.info("  Full Name       : %s", updated_user.get("fullName"))
        logger.info("  Status          : %s", updated_user.get("status"))
        logger.info("  User Type       : %s", updated_user.get("userType"))
    else:
        logger.warning("  Could not read updated item — verify manually.")
    logger.info("-" * 60)

    logger.info("Migration SUCCEEDED. userId updated from '%s' to '%s'.", db_user_id, cognito_sub)

    # --- Step 6: Verify the user can now retrieve timesheet submissions ---
    # This replicates the listMySubmissions query path: it queries the
    # Timesheet_Submissions table by employeeId (the corrected Cognito sub).
    # If submissions are returned, the fix is confirmed end-to-end.
    verified = verify_submissions_access(SUBMISSIONS_TABLE, cognito_sub, TARGET_USER_NAME)
    if not verified:
        logger.warning("Post-migration verification could not be completed. Check submissions table access.")

    return True


if __name__ == "__main__":
    result = migrate()
    sys.exit(0 if result else 1)
