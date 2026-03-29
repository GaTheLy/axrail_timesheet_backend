# Requirements Document

## Introduction

Single-Device Login Enforcement ensures that each TimeFlow user account can only maintain one active session at a time. When a user logs in on a new device or browser, any existing session on a previous device is invalidated. The user on the old device is logged out on their next request. This feature uses a server-side session token tracking mechanism backed by DynamoDB, integrated with the existing Cognito authentication flow and Laravel middleware.

## Glossary

- **Session_Tracker**: A DynamoDB table that stores the current active session token for each user, keyed by user ID.
- **Auth_Controller**: The Laravel controller (`AuthController`) that handles login, logout, and password flows via Cognito.
- **CognitoAuth_Middleware**: The Laravel middleware (`CognitoAuth`) that validates access tokens and refreshes expired tokens on each authenticated request.
- **Session_Token**: A unique, cryptographically random identifier generated at login time and stored both in the user's Laravel session and in the Session_Tracker.
- **Active_Session**: The single session whose Session_Token matches the value stored in the Session_Tracker for a given user.
- **Stale_Session**: A session whose Session_Token does not match the value stored in the Session_Tracker, indicating the user has logged in elsewhere.
- **Cognito_Service**: The Laravel service (`CognitoAuthService`) that wraps AWS Cognito SDK calls for authentication, token refresh, and sign-out operations.

## Requirements

### Requirement 1: Generate Session Token on Login

**User Story:** As a system administrator, I want each login to generate a unique session token, so that the system can track which device holds the active session.

#### Acceptance Criteria

1. WHEN a user successfully authenticates via the Auth_Controller, THE Auth_Controller SHALL generate a cryptographically random Session_Token and store it in the user's Laravel session.
2. WHEN a Session_Token is generated, THE Auth_Controller SHALL write the Session_Token and a login timestamp to the Session_Tracker, keyed by the authenticated user's ID.
3. WHEN a Session_Token is written to the Session_Tracker, THE Session_Tracker SHALL overwrite any previously stored Session_Token for that user ID.

### Requirement 2: Generate Session Token on Force Change Password

**User Story:** As a new user completing a forced password change, I want my session to be tracked, so that single-device enforcement applies from my first login.

#### Acceptance Criteria

1. WHEN a user successfully completes the force-change-password challenge via the Auth_Controller, THE Auth_Controller SHALL generate a cryptographically random Session_Token and store it in the user's Laravel session.
2. WHEN a Session_Token is generated after force-change-password, THE Auth_Controller SHALL write the Session_Token to the Session_Tracker, keyed by the authenticated user's ID.

### Requirement 3: Validate Session Token on Each Request

**User Story:** As a system administrator, I want every authenticated request to verify the session token, so that stale sessions are detected and terminated.

#### Acceptance Criteria

1. WHEN an authenticated request is received, THE CognitoAuth_Middleware SHALL retrieve the Session_Token from the user's Laravel session and compare it against the Session_Token stored in the Session_Tracker for that user ID.
2. WHEN the Session_Token in the Laravel session matches the Session_Token in the Session_Tracker, THE CognitoAuth_Middleware SHALL allow the request to proceed.
3. WHEN the Session_Token in the Laravel session does not match the Session_Token in the Session_Tracker, THE CognitoAuth_Middleware SHALL flush the Laravel session and redirect the user to the login page.
4. WHEN the Session_Token in the Laravel session does not match the Session_Token in the Session_Tracker, THE CognitoAuth_Middleware SHALL call the Cognito_Service globalSignOut method using the stale session's access token before flushing the session.

### Requirement 4: Clean Up Session Tracker on Logout

**User Story:** As a user, I want my session tracker entry to be removed when I log out, so that no stale references remain.

#### Acceptance Criteria

1. WHEN a user logs out via the Auth_Controller, THE Auth_Controller SHALL delete the Session_Tracker entry for that user's ID.
2. IF the Session_Tracker deletion fails, THEN THE Auth_Controller SHALL log the error and continue with the logout process without interrupting the user.

### Requirement 5: Session Tracker DynamoDB Table

**User Story:** As a DevOps engineer, I want the session tracker table provisioned via CDK, so that the infrastructure is managed as code.

#### Acceptance Criteria

1. THE Session_Tracker SHALL be a DynamoDB table with a partition key of `userId` (String type).
2. THE Session_Tracker SHALL store the following attributes: `userId`, `sessionToken`, and `loginTimestamp`.
3. THE Session_Tracker SHALL have a Time-To-Live (TTL) attribute named `ttl` set to expire records after 30 days.
4. THE Session_Tracker SHALL be provisioned using AWS CDK as part of the existing infrastructure stack.

### Requirement 6: Stale Session User Notification

**User Story:** As a user who has been logged out due to a login on another device, I want to see a clear message explaining why I was logged out, so that I understand what happened.

#### Acceptance Criteria

1. WHEN the CognitoAuth_Middleware detects a Stale_Session, THE CognitoAuth_Middleware SHALL redirect the user to the login page with a flash message indicating the account was logged in from another device.
2. WHEN the login page receives a stale-session flash message, THE login page SHALL display the message to the user.

### Requirement 7: Session Token Refresh Resilience

**User Story:** As a user with an expired access token, I want the session validation to work correctly after token refresh, so that I am not incorrectly logged out.

#### Acceptance Criteria

1. WHEN the CognitoAuth_Middleware refreshes an expired access token, THE CognitoAuth_Middleware SHALL retain the existing Session_Token in the Laravel session without modification.
2. WHEN the CognitoAuth_Middleware refreshes an expired access token, THE CognitoAuth_Middleware SHALL validate the Session_Token against the Session_Tracker after the token refresh completes.
3. IF the token refresh fails and the session is flushed, THEN THE CognitoAuth_Middleware SHALL skip the Session_Tracker validation since the user is already being redirected to login.

### Requirement 8: Error Handling for Session Tracker Unavailability

**User Story:** As a system administrator, I want the application to handle Session_Tracker outages gracefully, so that users are not locked out due to infrastructure issues.

#### Acceptance Criteria

1. IF the Session_Tracker is unreachable during session validation, THEN THE CognitoAuth_Middleware SHALL log the error and allow the request to proceed.
2. IF the Session_Tracker is unreachable during login, THEN THE Auth_Controller SHALL log the error and allow the login to proceed without writing the Session_Token.
