# Implementation Plan: TimeFlow Frontend

## Overview

Build the TimeFlow employee portal as a Laravel application in the `frontend/` directory. The implementation follows an incremental approach: project scaffolding → auth → layout/sidebar → core services → dashboard → timesheet CRUD → history → settings → final wiring. Each task builds on the previous, ensuring no orphaned code.

## Tasks

- [x] 1. Scaffold Laravel project and configure environment
  - [x] 1.1 Create Laravel project in `frontend/` directory with required dependencies
    - Run `composer create-project laravel/laravel frontend`
    - Add `aws/aws-sdk-php` and `guzzlehttp/guzzle` to `composer.json`
    - Configure `.env` with `APPSYNC_ENDPOINT`, `COGNITO_USER_POOL_ID`, `COGNITO_CLIENT_ID`, `AWS_REGION`
    - Create `config/aws.php` to read these env vars into Laravel config
    - _Requirements: 14.1, 14.2, 14.3_

  - [x] 1.2 Set up directory structure for views, components, assets, and services
    - Create `resources/views/layouts/`, `resources/views/pages/`, `resources/views/components/`
    - Create `public/css/`, `public/js/`, `public/images/`
    - Create `app/Services/` directory for GraphQLClient, CognitoAuthService, TimesheetEntryMapper
    - _Requirements: 14.4_

- [x] 2. Implement authentication system
  - [x] 2.1 Create `CognitoAuthService` in `app/Services/CognitoAuthService.php`
    - Implement `authenticate(email, password, rememberDevice)` using Cognito `InitiateAuth` with `USER_PASSWORD_AUTH` flow
    - Implement `refreshTokens(refreshToken)` using Cognito `InitiateAuth` with `REFRESH_TOKEN_AUTH` flow
    - Implement `forgotPassword(email)` using Cognito `ForgotPassword` API
    - Implement `confirmForgotPassword(email, code, newPassword)` using Cognito `ConfirmForgotPassword` API
    - Implement `changePassword(accessToken, oldPassword, newPassword)` using Cognito `ChangePassword` API
    - Implement `globalSignOut(accessToken)` using Cognito `GlobalSignOut` API
    - Parse ID token JWT to extract `custom:userType`, `custom:role`, `sub`, `email`, `name` claims
    - _Requirements: 1.2, 1.4, 1.6, 1.7, 11.2_

  - [x] 2.2 Create `AuthController` in `app/Http/Controllers/AuthController.php`
    - Implement `showLogin()` → render `pages/login.blade.php`
    - Implement `login(Request)` → validate credentials, call `CognitoAuthService::authenticate`, store tokens and user info in session, redirect to `/dashboard`
    - Implement `logout()` → call `CognitoAuthService::globalSignOut`, flush session, redirect to `/login`
    - Implement `showForgotPassword()` → render forgot password form
    - Implement `forgotPassword(Request)` → call `CognitoAuthService::forgotPassword`
    - Implement `resetPassword(Request)` → call `CognitoAuthService::confirmForgotPassword`
    - Handle authentication errors with generic error messages (not revealing which field is incorrect)
    - _Requirements: 1.1, 1.2, 1.3, 1.5, 1.7_

  - [x] 2.3 Create `CognitoAuth` middleware in `app/Http/Middleware/CognitoAuth.php`
    - Check session for valid access token on every authenticated route
    - If token expired, attempt refresh using stored refresh token via `CognitoAuthService::refreshTokens`
    - If refresh fails or no session, redirect to `/login`
    - Extract `custom:userType` and `custom:role` from ID token and store in session
    - Set session lifetime based on "Remember this device" flag (30-day refresh token vs standard)
    - _Requirements: 1.4, 1.6, 11.2, 11.4, 11.5_

  - [x] 2.4 Create login page view `resources/views/pages/login.blade.php`
    - Email input, password input, "Remember this device" checkbox, "Forgot password?" link, "Sign In" button
    - TimeFlow branding and logo
    - "© 2026 Team Alpha" footer
    - Error message display area
    - _Requirements: 1.1, 1.5, 12.1_

  - [x] 2.5 Register auth routes in `routes/web.php`
    - `GET /login`, `POST /login`, `POST /logout`, `GET /forgot-password`, `POST /forgot-password`, `POST /reset-password`
    - Apply `CognitoAuth` middleware to all routes except auth routes
    - _Requirements: 1.1, 1.7, 11.4_

  - [ ]* 2.6 Write unit tests for `CognitoAuthService`
    - Test token parsing extracts correct claims
    - Test error handling for invalid credentials
    - Test refresh token flow
    - _Requirements: 1.2, 1.3, 1.4_

- [x] 3. Implement GraphQL client and shared layout
  - [x] 3.1 Create `GraphQLClient` service in `app/Services/GraphQLClient.php`
    - Implement `query(string $query, array $variables): array` using Guzzle HTTP client
    - Implement `mutate(string $mutation, array $variables): array`
    - Attach Cognito JWT access token from session to `Authorization` header
    - Handle GraphQL error responses and extract error messages
    - Detect 401/403 responses and throw an `AuthenticationException` to trigger redirect to login
    - Implement retry logic for transient network failures (max 2 retries with exponential backoff)
    - _Requirements: 13.1, 13.2, 13.3, 13.5_

  - [x] 3.2 Create main layout `resources/views/layouts/app.blade.php`
    - HTML skeleton with responsive meta viewport tag
    - CSS includes (app.css)
    - JS includes (app.js)
    - Sidebar component inclusion
    - Main content area with `@yield('content')`
    - Loading spinner overlay for AJAX requests
    - _Requirements: 12.1, 12.2, 12.3, 13.4_

  - [x] 3.3 Create sidebar component `resources/views/components/sidebar.blade.php`
    - Navigation links: Dashboard (`/dashboard`), Timesheet (`/timesheet`), Settings (`/settings`)
    - Highlight active page link based on current route
    - Display authenticated user's full name and role at bottom
    - Hamburger menu toggle for viewports < 768px
    - TimeFlow logo at top
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 12.4_

  - [x] 3.4 Create base CSS in `public/css/app.css`
    - TimeFlow brand colors, typography, and consistent styling
    - Responsive layout: sidebar + main content grid
    - Sidebar collapse to hamburger menu at < 768px
    - Desktop (≥1024px), tablet (768–1023px), and mobile breakpoints
    - Summary card, table, modal, button, and form styles
    - Loading spinner and skeleton UI styles
    - _Requirements: 12.1, 12.2, 12.3, 12.4, 13.4_

  - [ ]* 3.5 Write unit tests for `GraphQLClient`
    - Test Authorization header attachment
    - Test error response handling
    - Test 401/403 detection triggers exception
    - _Requirements: 13.1, 13.2, 13.3_

- [x] 4. Checkpoint — Ensure auth flow and layout work
  - Ensure all tests pass, ask the user if questions arise.

- [x] 5. Implement TimesheetEntryMapper service
  - [x] 5.1 Create `TimesheetEntryMapper` in `app/Services/TimesheetEntryMapper.php`
    - Implement `flattenEntries(array $entries, string $weekStartDate): array` — convert weekly entry rows into per-day `FlattenedEntry` arrays (one row per day with hours > 0)
    - Implement `mapToEntryInput(string $projectCode, string $date, float $hours, array $existingEntries): array` — determine whether to call `addTimesheetEntry` or `updateTimesheetEntry`, map date to correct day-of-week field, build `TimesheetEntryInput`
    - Implement `calculateWeeklyTotal(array $entries): float` — sum all day fields across all entries
    - Implement `calculateDailyTotals(array $entries): array` — return hours per day (Mon–Fri) for chart data
    - Handle edge cases: date-to-day mapping, zeroing out a day field on delete, detecting when all days are zero to trigger `removeTimesheetEntry`
    - _Requirements: 4.3, 4.4, 5.3, 6.2, 7.2, 7.3_

  - [ ]* 5.2 Write unit tests for `TimesheetEntryMapper::flattenEntries`
    - Test flattening a single entry with hours on multiple days produces correct per-day rows
    - Test entries with zero hours on some days are excluded from flattened output
    - Test empty entries array returns empty result
    - _Requirements: 4.3_

  - [ ]* 5.3 Write unit tests for `TimesheetEntryMapper::mapToEntryInput`
    - Test adding hours for a new project creates an add operation with correct day-of-week field
    - Test adding hours for an existing project creates an update operation
    - Test date-to-day-of-week mapping for each weekday
    - Test zeroing a day when other days have hours returns update operation
    - Test zeroing the last day with hours returns remove operation
    - _Requirements: 5.3, 6.2, 7.2, 7.3_

- [x] 6. Implement Dashboard page
  - [x] 6.1 Create `DashboardController` in `app/Http/Controllers/DashboardController.php`
    - Fetch current period via `GraphQLClient::query` with `getCurrentPeriod`
    - Fetch current submission via `GraphQLClient::query` with `listMySubmissions` filtered by `periodId`
    - Compute deadline countdown (days, hours, minutes until `submissionDeadline`)
    - Use `TimesheetEntryMapper::flattenEntries` to prepare recent entries
    - Use `TimesheetEntryMapper::calculateDailyTotals` for weekly activity chart data
    - Use `TimesheetEntryMapper::calculateWeeklyTotal` for total hours summary card
    - Handle API errors with user-friendly messages and retry option
    - Pass `DashboardData` view model to Blade template
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.8_

  - [x] 6.2 Create dashboard view `resources/views/pages/dashboard.blade.php`
    - Welcome message with employee's full name
    - Three summary cards: Current Week Period, Submission Deadline (with countdown), Personal Summary (total hours)
    - Weekly Activity bar chart (Mon–Fri) using a lightweight JS chart library or CSS bars
    - Recent Time Entries table: Date, Project Code, Description, Charged Hours
    - "View Timesheet" link navigating to `/timesheet`
    - Error state with retry button
    - _Requirements: 3.1, 3.2, 3.5, 3.6, 3.7, 3.8_

  - [x] 6.3 Create summary card component `resources/views/components/summary-card.blade.php`
    - Reusable card with title, value, and optional icon/badge
    - _Requirements: 3.2_

  - [x] 6.4 Create countdown component `resources/views/components/countdown.blade.php`
    - Display days, hours, minutes remaining
    - JavaScript timer that updates every minute
    - _Requirements: 3.2_

  - [x] 6.5 Register dashboard route: `GET /dashboard` → `DashboardController@index`
    - _Requirements: 3.1_

- [x] 7. Implement Timesheet page with CRUD operations
  - [x] 7.1 Create `TimesheetController` in `app/Http/Controllers/TimesheetController.php`
    - `index()`: Fetch current period, current submission with entries, flatten entries via `TimesheetEntryMapper`, render timesheet page
    - `storeEntry(Request)`: Validate input (projectCode, date, chargedHours), use `TimesheetEntryMapper::mapToEntryInput` to determine add vs update, execute GraphQL mutation, return JSON response
    - `updateEntry(Request, entryId)`: Validate input, use `TimesheetEntryMapper::mapToEntryInput`, execute `updateTimesheetEntry` mutation, return JSON response
    - `destroyEntry(entryId)`: Use `TimesheetEntryMapper` to determine if zeroing a day or removing entire row, execute appropriate mutation, return JSON response
    - `listProjects()`: Query `listProjects` with `approval_status: Approved` filter, return JSON for dropdown
    - Handle submission status check — disable edit/delete when status is "Submitted"
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.9, 5.1, 5.2, 5.3, 5.4, 5.5, 6.1, 6.2, 6.3, 6.4, 6.5, 7.1, 7.2, 7.3, 7.4, 7.5_

  - [x] 7.2 Create timesheet view `resources/views/pages/timesheet.blade.php`
    - Current week date range header (e.g., "Mon, Jun 16 – Fri, Jun 20")
    - Submission deadline countdown badge
    - Entries table: Date, Project Code, Description, Charged Hours, Actions (edit/delete icons)
    - Weekly Total display with 40-hour target
    - Search bar for filtering by project code or description
    - Project filter dropdown
    - "+ New Entry" button
    - "History" button linking to `/timesheet/history`
    - Disable edit/delete icons when submission status is "Submitted"
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 4.8, 6.5, 7.5_

  - [x] 7.3 Create entry modal component `resources/views/components/entry-modal.blade.php`
    - Project Code dropdown (populated via AJAX from `/timesheet/projects`)
    - Description text field
    - Date picker (constrained to current week Mon–Fri)
    - Charged Hours input (non-negative, max 2 decimal places)
    - "Save Changes" button (disabled until all required fields filled)
    - "Cancel" button
    - Error message display area
    - Pre-populate fields when editing an existing entry
    - _Requirements: 5.1, 5.2, 5.6, 5.7, 5.8, 6.1_

  - [x] 7.4 Create `public/js/timesheet.js` for AJAX interactions
    - Open modal for add/edit, populate fields
    - Submit entry form via `POST /timesheet/entry` or `PUT /timesheet/entry/{id}`
    - Delete entry via `DELETE /timesheet/entry/{id}` with confirmation dialog
    - Refresh entries table on success
    - Display error messages on failure
    - Client-side search/filter for entries table
    - Validate charged hours format before submission
    - _Requirements: 5.3, 5.4, 5.5, 5.6, 5.7, 5.8, 6.2, 6.3, 6.4, 7.1, 7.2, 7.3, 7.4_

  - [x] 7.5 Register timesheet routes in `routes/web.php`
    - `GET /timesheet` → `TimesheetController@index`
    - `POST /timesheet/entry` → `TimesheetController@storeEntry`
    - `PUT /timesheet/entry/{id}` → `TimesheetController@updateEntry`
    - `DELETE /timesheet/entry/{id}` → `TimesheetController@destroyEntry`
    - `GET /timesheet/projects` → `TimesheetController@listProjects`
    - _Requirements: 4.1, 5.1, 6.1, 7.1_

  - [ ]* 7.6 Write unit tests for `TimesheetController` CRUD operations
    - Test add entry calls correct GraphQL mutation based on mapper output
    - Test edit entry with submission status "Submitted" returns 403
    - Test delete entry that zeros last day triggers `removeTimesheetEntry`
    - _Requirements: 5.3, 6.2, 6.5, 7.2, 7.5_

- [x] 8. Checkpoint — Ensure dashboard and timesheet CRUD work
  - Ensure all tests pass, ask the user if questions arise.

- [x] 9. Implement History page
  - [x] 9.1 Create `HistoryController` in `app/Http/Controllers/HistoryController.php`
    - `index()`: Fetch all submissions via `listMySubmissions`, flatten entries, render history page
    - `filter(Request)`: Accept start/end date params, filter submissions by date range, return JSON with filtered flattened entries and count
    - _Requirements: 8.1, 8.2, 8.3, 8.6_

  - [x] 9.2 Create history view `resources/views/pages/history.blade.php`
    - Date range picker (start date, end date)
    - Entry count badge showing total entries in selected range
    - Entries table: Date, Project, Description, Charged Hours
    - Weekly Total for selected period
    - AJAX-based filtering on date range change
    - _Requirements: 8.2, 8.3, 8.4, 8.5_

  - [x] 9.3 Register history routes in `routes/web.php`
    - `GET /timesheet/history` → `HistoryController@index`
    - `GET /timesheet/history/filter` → `HistoryController@filter`
    - _Requirements: 8.1_

- [x] 10. Implement Settings page
  - [x] 10.1 Create `SettingsController` in `app/Http/Controllers/SettingsController.php`
    - `index()`: Fetch user profile via `getUser(userId)`, fetch departments via `listDepartments`, render settings page
    - `uploadAvatar(Request)`: Handle avatar image upload and storage
    - `changePassword(Request)`: Validate password fields (match check, policy check), call `CognitoAuthService::changePassword`, return JSON response
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 10.1, 10.2, 10.3, 10.4_

  - [x] 10.2 Create settings view `resources/views/pages/settings.blade.php`
    - Profile section: avatar display/upload, Full Name, Email (read-only), Department dropdown
    - Security section: Current Password, New Password, Confirm Password, "Save Changes" button
    - Client-side validation: password match check, password policy (min 8 chars, uppercase, lowercase, digit, symbol)
    - Success/error notifications
    - _Requirements: 9.1, 9.4, 9.5, 10.1, 10.5, 10.6_

  - [x] 10.3 Register settings routes in `routes/web.php`
    - `GET /settings` → `SettingsController@index`
    - `POST /settings/avatar` → `SettingsController@uploadAvatar`
    - `POST /settings/password` → `SettingsController@changePassword`
    - _Requirements: 9.1, 10.1_

  - [ ]* 10.4 Write unit tests for password change validation
    - Test password mismatch returns validation error
    - Test password not meeting policy returns specific error
    - Test successful password change returns success response
    - _Requirements: 10.4, 10.5, 10.6_

- [x] 11. Implement role-based access control
  - [x] 11.1 Create `RoleMiddleware` in `app/Http/Middleware/RoleMiddleware.php`
    - Read `userType` and `role` from session (set by `CognitoAuth` middleware)
    - Support role-based route restrictions via middleware parameter (e.g., `role:admin`)
    - Render navigation items conditionally based on role in sidebar
    - Redirect unauthorized access attempts to dashboard with error flash message
    - _Requirements: 11.1, 11.2, 11.3, 11.5_

  - [x] 11.2 Update sidebar component to conditionally render navigation items based on user role
    - Employee: Dashboard, Timesheet, Settings
    - Future roles (Tech_Lead_PM, Admin, Super_Admin) will add additional nav items
    - _Requirements: 11.3_

- [x] 12. Final integration and polish
  - [x] 12.1 Create `public/js/app.js` for shared JavaScript functionality
    - AJAX loading state management (show/hide spinner)
    - Global error notification handler
    - Sidebar hamburger menu toggle for mobile
    - CSRF token attachment for all AJAX requests
    - _Requirements: 13.4, 12.4_

  - [x] 12.2 Wire all routes together and verify navigation flow
    - Ensure login → dashboard → timesheet → history → settings navigation works
    - Ensure sidebar active state updates correctly on each page
    - Ensure logout clears session and redirects to login
    - Ensure unauthenticated access redirects to login
    - _Requirements: 2.1, 2.2, 2.4, 11.4_

  - [x] 12.3 Add GraphQL query/mutation string constants
    - Create `app/Services/GraphQLQueries.php` with all query and mutation strings used across controllers: `getCurrentPeriod`, `listMySubmissions`, `listProjects`, `getUser`, `listDepartments`, `addTimesheetEntry`, `updateTimesheetEntry`, `removeTimesheetEntry`
    - Ensure query fields match the GraphQL schema (`graphql/schema.graphql`)
    - _Requirements: 13.1_

- [x] 13. Final checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- The `TimesheetEntryMapper` (task 5) is the core complexity — it bridges the backend's weekly-row model with the UI's per-day display
- All GraphQL calls go through the server-side `GraphQLClient` (BFF pattern) — no AppSync endpoint exposed to browser
- Cognito tokens are stored server-side in Laravel session, never in browser storage
- The implementation targets the General Employee role first; other roles share the same infrastructure
