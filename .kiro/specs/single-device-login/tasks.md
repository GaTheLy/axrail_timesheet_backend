# Implementation Plan: Single-Device Login

## Overview

Enforce single-device login by tracking active sessions in a DynamoDB table. On login, a cryptographic session token is stored in both the Laravel session and DynamoDB. The CognitoAuth middleware validates the token on every request, flushing stale sessions and redirecting to login with a notification. Infrastructure is provisioned via CDK.

## Tasks

- [ ] 1. Provision Session_Tracker DynamoDB table via CDK
  - [x] 1.1 Add Session_Tracker table to the existing DynamoDB CDK stack
    - Add a new DynamoDB table `Timesheet_SessionTracker_{env}` in `colabs_pipeline_cdk/stack/dynamodb_stack.py`
    - Partition key: `userId` (String)
    - Billing mode: PAY_PER_REQUEST
    - Enable TTL on attribute `ttl`
    - Removal policy: DESTROY for dev, RETAIN for staging/prod
    - _Requirements: 5.1, 5.2, 5.3, 5.4_

  - [x] 1.2 Add Session_Tracker table name to environment configuration
    - Add the table name pattern `Timesheet_SessionTracker_{env}` to `colabs_pipeline_cdk/environment.py`
    - Ensure the table name is available as an environment variable `SESSION_TRACKER_TABLE` for the frontend
    - _Requirements: 5.4_

- [ ] 2. Implement SessionTrackerService
  - [x] 2.1 Create `frontend/app/Services/SessionTrackerService.php`
    - Implement `putSession(string $userId, string $sessionToken): void` — PutItem with userId, sessionToken, loginTimestamp (ISO 8601), and ttl (30 days from now)
    - Implement `getSessionToken(string $userId): ?string` — GetItem by userId, return sessionToken or null
    - Implement `deleteSession(string $userId): void` — DeleteItem by userId
    - Read table name from `config('services.session_tracker.table')` mapped to `SESSION_TRACKER_TABLE` env var
    - Use the AWS SDK DynamoDB client consistent with existing service patterns
    - _Requirements: 1.2, 1.3, 2.2, 3.1, 4.1, 5.2, 5.3_

  - [x] 2.2 Write property test: Session token round-trip persistence (Property 2)
    - **Property 2: Session token round-trip persistence**
    - **Validates: Requirements 1.2, 2.2, 5.2, 5.3**
    - For random userId and sessionToken values, `putSession` then `getSessionToken` returns the same token

  - [x] 2.3 Write property test: Session token overwrite on re-login (Property 3)
    - **Property 3: Session token overwrite on re-login**
    - **Validates: Requirements 1.3**
    - For random userId and two random tokens, put both sequentially, verify only the second is retrievable

  - [x] 2.4 Write property test: Logout deletes session tracker entry (Property 6)
    - **Property 6: Logout deletes session tracker entry**
    - **Validates: Requirements 4.1**
    - For random userId, put a session then delete, verify getSessionToken returns null

- [ ] 3. Checkpoint — Ensure SessionTrackerService works
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 4. Integrate session token generation into AuthController
  - [x] 4.1 Modify `login()` method in `frontend/app/Http/Controllers/AuthController.php`
    - After successful Cognito authentication and storing tokens in session, generate a session token via `bin2hex(random_bytes(32))`
    - Store the token in the Laravel session under key `sessionToken`
    - Call `SessionTrackerService::putSession($userId, $sessionToken)`
    - Wrap the DynamoDB call in try/catch — log error and continue on failure
    - _Requirements: 1.1, 1.2, 1.3, 8.2_

  - [x] 4.2 Modify `forceChangePassword()` method in `frontend/app/Http/Controllers/AuthController.php`
    - After successful force-change-password challenge, generate a session token via `bin2hex(random_bytes(32))`
    - Store the token in the Laravel session under key `sessionToken`
    - Call `SessionTrackerService::putSession($userId, $sessionToken)`
    - Wrap the DynamoDB call in try/catch — log error and continue on failure
    - _Requirements: 2.1, 2.2_

  - [x] 4.3 Modify `logout()` method in `frontend/app/Http/Controllers/AuthController.php`
    - Before flushing the session, call `SessionTrackerService::deleteSession($userId)`
    - Wrap in try/catch — log error and continue with logout on failure
    - _Requirements: 4.1, 4.2_

  - [x] 4.4 Write property test: Session token generation on any auth flow (Property 1)
    - **Property 1: Session token generation on any auth flow**
    - **Validates: Requirements 1.1, 2.1**
    - For any successful authentication (login or force-change-password), the session contains a non-empty 64-character hex string

  - [x] 4.5 Write unit tests for AuthController session tracking
    - Test login stores a 64-char hex `sessionToken` in the session
    - Test login calls `SessionTrackerService::putSession()` with correct userId and token
    - Test force-change-password stores a `sessionToken` in the session
    - Test logout calls `SessionTrackerService::deleteSession()` with correct userId
    - Test logout succeeds even when `SessionTrackerService::deleteSession()` throws an exception
    - Test login succeeds when DynamoDB is unreachable (fail-open)
    - _Requirements: 1.1, 1.2, 2.1, 2.2, 4.1, 4.2, 8.2_

- [ ] 5. Checkpoint — Ensure AuthController integration works
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 6. Add session validation to CognitoAuth Middleware
  - [x] 6.1 Modify `frontend/app/Http/Middleware/CognitoAuth.php` to validate session tokens
    - After token validation/refresh succeeds, retrieve `sessionToken` from the Laravel session and `userId` from `session('user.userId')`
    - Call `SessionTrackerService::getSessionToken($userId)`
    - If tokens match, allow request to proceed
    - If tokens mismatch: call `CognitoAuthService::globalSignOut()` with the access token, flush the session, redirect to `/login` with a `stale_session` flash message
    - If DynamoDB is unreachable (exception), log error and allow request to proceed (fail-open)
    - If session is missing `sessionToken` or `user.userId`, skip validation (handles legacy sessions)
    - If token refresh failed and session was already flushed, skip session tracker validation
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 6.1, 7.1, 7.2, 7.3, 8.1_

  - [x] 6.2 Write property test: Matching session token allows request (Property 4)
    - **Property 4: Matching session token allows request**
    - **Validates: Requirements 3.2**
    - For random matching token pairs, verify middleware passes request through

  - [x] 6.3 Write property test: Mismatched session token terminates session (Property 5)
    - **Property 5: Mismatched session token terminates session**
    - **Validates: Requirements 3.3, 3.4, 6.1**
    - For random non-matching token pairs, verify middleware flushes session and redirects with flash message

  - [x] 6.4 Write property test: Token refresh preserves session token (Property 7)
    - **Property 7: Token refresh preserves session token**
    - **Validates: Requirements 7.1**
    - For random session states with expired tokens, verify sessionToken is unchanged after refresh

  - [x] 6.5 Write property test: Fail-open on DynamoDB unavailability (Property 8)
    - **Property 8: Fail-open on DynamoDB unavailability**
    - **Validates: Requirements 8.1**
    - For random requests with simulated DynamoDB failures, verify request proceeds

  - [x] 6.6 Write unit tests for CognitoAuth Middleware session validation
    - Test middleware allows request when tokens match
    - Test middleware flushes session and redirects when tokens mismatch
    - Test middleware calls `globalSignOut` before flushing on mismatch
    - Test middleware redirects with `stale_session` flash message on mismatch
    - Test middleware allows request when DynamoDB throws an exception (fail-open)
    - Test middleware skips validation when `sessionToken` is missing from session (legacy session)
    - Test middleware skips validation when token refresh fails and session is already flushed
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 6.1, 7.1, 7.2, 7.3, 8.1_

- [ ] 7. Update login page to display stale session notification
  - [x] 7.1 Modify `frontend/resources/views/pages/login.blade.php`
    - Add a conditional block to display the `session('stale_session')` flash message
    - Use the existing `alert-error` styling consistent with the login page design
    - _Requirements: 6.1, 6.2_

- [ ] 8. Add Laravel service configuration
  - [x] 8.1 Register SessionTrackerService and add config entry
    - Add `session_tracker.table` to `config/services.php` mapped to `SESSION_TRACKER_TABLE` env var
    - Add `SESSION_TRACKER_TABLE` to `.env.example` with a placeholder value
    - _Requirements: 5.4_

- [x] 9. Final checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.
  - Verify all requirements are covered by implementation tasks

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document
- Unit tests validate specific examples and edge cases
- The fail-open strategy ensures DynamoDB outages don't lock users out
