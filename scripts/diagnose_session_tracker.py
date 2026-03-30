"""Diagnostic script to test the SessionTracker DynamoDB table.

Simulates the single-device login flow:
1. Write session token A for a user (device 1 login)
2. Read it back and verify
3. Write session token B for the same user (device 2 login)
4. Read it back — should return token B, not token A
5. This proves the table is working and tokens get overwritten

Usage: python scripts/diagnose_session_tracker.py
"""

import boto3
import uuid
import time

TABLE_NAME = "Timesheet_SessionTracker-dev"
REGION = "ap-southeast-1"

dynamodb = boto3.client("dynamodb", region_name=REGION)


def put_session(user_id, session_token):
    """Simulate SessionTrackerService::putSession"""
    now = int(time.time())
    ttl = now + (30 * 24 * 60 * 60)

    dynamodb.put_item(
        TableName=TABLE_NAME,
        Item={
            "userId": {"S": user_id},
            "sessionToken": {"S": session_token},
            "loginTimestamp": {"S": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())},
            "ttl": {"N": str(ttl)},
        },
    )
    print(f"  PUT: userId={user_id}, token={session_token[:16]}...")


def get_session_token(user_id):
    """Simulate SessionTrackerService::getSessionToken"""
    result = dynamodb.get_item(
        TableName=TABLE_NAME,
        Key={"userId": {"S": user_id}},
    )
    item = result.get("Item")
    if not item:
        return None
    return item.get("sessionToken", {}).get("S")


def main():
    print("=== SessionTracker DynamoDB Diagnostic ===\n")

    # Step 0: Check if table exists
    print("Step 0: Checking if table exists...")
    try:
        desc = dynamodb.describe_table(TableName=TABLE_NAME)
        status = desc["Table"]["TableStatus"]
        print(f"  Table '{TABLE_NAME}' exists, status: {status}\n")
    except dynamodb.exceptions.ResourceNotFoundException:
        print(f"  ERROR: Table '{TABLE_NAME}' does NOT exist!")
        print("  You need to deploy: cdk deploy ColabsTimesheetDynamoDBStack-dev")
        return
    except Exception as e:
        print(f"  ERROR: {e}")
        return

    # Use a test user ID
    test_user_id = "diagnostic-test-" + str(uuid.uuid4())[:8]

    # Step 1: Device 1 logs in
    token_a = uuid.uuid4().hex + uuid.uuid4().hex  # 64-char hex
    print(f"Step 1: Device 1 logs in (token A)")
    put_session(test_user_id, token_a)

    # Step 2: Read back
    print(f"Step 2: Read back token for user")
    stored = get_session_token(test_user_id)
    if stored == token_a:
        print(f"  OK: Token matches device 1's token\n")
    elif stored is None:
        print(f"  FAIL: No token found! PutItem may have failed silently.\n")
        return
    else:
        print(f"  FAIL: Token mismatch! Expected {token_a[:16]}..., got {stored[:16]}...\n")
        return

    # Step 3: Device 2 logs in (overwrites token)
    token_b = uuid.uuid4().hex + uuid.uuid4().hex  # 64-char hex
    print(f"Step 3: Device 2 logs in (token B)")
    put_session(test_user_id, token_b)

    # Step 4: Read back — should be token B
    print(f"Step 4: Read back token — should be device 2's token")
    stored = get_session_token(test_user_id)
    if stored == token_b:
        print(f"  OK: Token matches device 2's token")
    elif stored == token_a:
        print(f"  FAIL: Token still matches device 1! Overwrite didn't work.")
        return
    else:
        print(f"  FAIL: Unexpected token: {stored[:16]}...")
        return

    # Step 5: Simulate middleware check for device 1
    print(f"\nStep 5: Simulating middleware check for device 1 (stale session)")
    if stored != token_a:
        print(f"  OK: Tokens mismatch — device 1 would be logged out")
        print(f"       Device 1 token: {token_a[:16]}...")
        print(f"       Stored token:   {stored[:16]}...")
    else:
        print(f"  FAIL: Tokens still match — device 1 would NOT be logged out")

    # Cleanup
    print(f"\nCleaning up test data...")
    dynamodb.delete_item(
        TableName=TABLE_NAME,
        Key={"userId": {"S": test_user_id}},
    )
    print("  Done.")

    print("\n=== CONCLUSION ===")
    print("DynamoDB SessionTracker table is working correctly.")
    print("If single-device login still doesn't work, the issue is in the")
    print("Laravel app (EB environment config, IAM permissions, or code path).")
    print("\nCheck these on your EB environment:")
    print("  1. Is SESSION_TRACKER_TABLE env var set?")
    print("  2. Does the EB instance role have dynamodb:PutItem/GetItem/DeleteItem")
    print("     permissions on the Timesheet_SessionTracker-dev table?")
    print("  3. Check storage/logs/laravel.log for 'Session token stored' or")
    print("     'Failed to store session token' messages.")


if __name__ == "__main__":
    main()
