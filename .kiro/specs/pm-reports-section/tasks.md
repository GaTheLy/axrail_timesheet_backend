# Implementation Plan: PM Reports Section

## Overview

Add a Reports section to the TimeFlow frontend accessible to Tech_Lead, Project_Manager, admin, and superadmin users. The implementation extends the existing RoleMiddleware, adds a collapsible sidebar menu, creates a ReportsController with two report pages (Project Summary and Submission Summary), adds GraphQL query constants, implements client-side filtering/pagination, and wires up PDF export via pre-signed S3 URLs. Each task builds incrementally on the previous.

## Tasks

- [x] 1. Extend RoleMiddleware and add GraphQL query constants
  - [x] 1.1 Add `pm` role level to `RoleMiddleware::isAuthorized` in `frontend/app/Http/Middleware/RoleMiddleware.php`
    - Add a `'pm'` case to the match expression that permits users with userType `user` and role `Tech_Lead` or `Project_Manager`
    - Admin and superadmin access will be handled in a separate spec
    - _Requirements: 2.2, 2.3_

  - [ ]* 1.2 Write property test for RoleMiddleware pm role authorization
    - **Property 2: Route authorization permits only qualifying roles**
    - Generate random user role/userType combinations, assert that `isAuthorized` returns true only for userType `user` with role Tech_Lead or Project_Manager
    - **Validates: Requirements 2.2**

  - [x] 1.3 Add new GraphQL query constants to `frontend/app/Services/GraphQLQueries.php`
    - Add `LIST_ALL_SUBMISSIONS` query constant with fields: submissionId, periodId, employeeId, status, entries (entryId, projectCode, totalHours), totalHours, chargeableHours
    - Add `GET_PROJECT_SUMMARY_REPORT` query constant accepting `periodId` and returning url, expiresAt
    - Add `GET_TC_SUMMARY_REPORT` query constant accepting `techLeadId` and `periodId` and returning url, expiresAt
    - Add `LIST_USERS` query constant with fields: userId, fullName, role, status (with nextToken pagination)
    - _Requirements: 3.3, 4.3, 5.3, 5.4_

- [x] 2. Implement ReportsController and register routes
  - [x] 2.1 Create `ReportsController` in `frontend/app/Http/Controllers/ReportsController.php`
    - Inject `GraphQLClient` via constructor
    - Implement `projectSummary(Request)`: fetch current period via `getCurrentPeriod`, fetch all periods via `listTimesheetPeriods`, fetch projects via `listProjects`, fetch submissions via `listAllSubmissions` for selected period, compute utilization per project (chargedHours / plannedHours × 100, 0 when plannedHours is 0), compute totals row, return `pages.reports.project-summary` view
    - Implement `submissionSummary(Request)`: fetch current period, fetch all periods, fetch submissions via `listAllSubmissions`, fetch users via `listUsers` to resolve employee names, compute chargeability per employee (chargeableHours / totalHours × 100, 0 when totalHours is 0), compute totals row, return `pages.reports.submission-summary` view
    - Implement `exportProjectPdf(Request)`: accept `periodId`, call `getProjectSummaryReport` via GraphQL, return JSON with pre-signed URL or error
    - Implement `exportSubmissionPdf(Request)`: accept `periodId`, call `getTCSummaryReport` with user's ID and periodId, return JSON with pre-signed URL or error
    - Handle `AuthenticationException` by redirecting to `/login`, handle general exceptions by passing `$error` to view
    - _Requirements: 3.1, 3.3, 3.6, 3.8, 4.1, 4.3, 4.6, 4.8, 5.3, 5.4, 7.1, 7.3, 7.4, 7.5_

  - [ ]* 2.2 Write property test for utilization/chargeability percentage calculation
    - **Property 3: Utilization and chargeability percentage calculation**
    - Generate random non-negative (part, whole) float pairs, assert percentage equals (part/whole)*100 when whole > 0, and 0 when whole is 0
    - **Validates: Requirements 3.6, 4.6**

  - [ ]* 2.3 Write property test for totals row aggregation
    - **Property 5: Totals row equals sum of individual rows**
    - Generate random lists of report rows with random hour values, compute totals, assert totals equal sums of individual values
    - **Validates: Requirements 3.8, 4.8**

  - [x] 2.4 Register report routes in `frontend/routes/web.php`
    - Add a `Route::middleware('role:pm')` group inside the existing `cognito.auth` group
    - Register `GET /reports/project-summary` → `ReportsController@projectSummary`
    - Register `GET /reports/submission-summary` → `ReportsController@submissionSummary`
    - Register `GET /reports/project-summary/export` → `ReportsController@exportProjectPdf`
    - Register `GET /reports/submission-summary/export` → `ReportsController@exportSubmissionPdf`
    - _Requirements: 2.1, 2.3, 2.4_

- [x] 3. Checkpoint — Ensure controller and routes are wired correctly
  - Ensure all tests pass, ask the user if questions arise.

- [x] 4. Update sidebar with collapsible Reports menu
  - [x] 4.1 Add collapsible Reports menu group to `frontend/resources/views/components/sidebar.blade.php`
    - Inside the existing role conditional block, add a `<li class="nav-group">` between Timesheet and Settings links
    - Add a `<button class="nav-group-toggle">` with a document/chart SVG icon, "Reports" text, and a chevron SVG icon
    - Add a `<ul class="nav-group-items">` with two sub-items: "Project Summary" (`/reports/project-summary`) and "Submission Summary" (`/reports/submission-summary`)
    - Show the Reports menu only when user has userType `user` and role Tech_Lead or Project_Manager
    - Admin and superadmin access will be handled in a separate spec
    - Set `aria-expanded` attribute and chevron rotation based on whether the current URL starts with `/reports`
    - Add active class to the Reports group when on any report page, and to the specific sub-item matching the current URL
    - Hide the Reports menu for users with role Employee and userType user
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8_

  - [ ]* 4.2 Write property test for sidebar visibility by role
    - **Property 1: Sidebar visibility is determined by role**
    - Generate random user role/userType combinations, render sidebar partial, assert Reports menu presence matches the role predicate
    - **Validates: Requirements 1.1, 1.8**

  - [ ]* 4.3 Write property test for active sidebar state
    - **Property 8: Active sidebar state matches current URL**
    - Generate report URLs, render sidebar, assert correct active classes on menu group and sub-items
    - **Validates: Requirements 1.5, 1.6, 1.7**

- [x] 5. Create report page CSS styles
  - [x] 5.1 Add report-specific CSS to `frontend/public/css/app.css`
    - Add `.nav-group`, `.nav-group-toggle`, `.nav-group-items` styles for collapsible sidebar menu with CSS transition on expand/collapse
    - Add `.breadcrumb` styles for report page breadcrumb navigation
    - Add `.progress-bar`, `.progress-bar-fill` base styles for colored progress bars
    - Add `.progress-green` (#22c55e), `.progress-yellow` (#eab308), `.progress-red` (#ef4444) color variants
    - Add `.totals-row` bold styling for table totals row
    - Add `.pagination` styles for pagination controls below tables
    - Add `.btn-export` styles for the Export PDF button using primary blue style
    - Add `.filter-bar` styles for the filter bar layout between title and table
    - Ensure all styles use the existing dark theme color scheme and typography
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6_

  - [ ]* 5.2 Write property test for progress bar color assignment
    - **Property 4: Progress bar color assignment by threshold**
    - Generate random percentage values (0–200), apply the color function, assert yellow below 50, green 50–100, red above 100
    - **Validates: Requirements 3.7, 4.7, 6.3**

- [x] 6. Create Project Summary report page view
  - [x] 6.1 Create `frontend/resources/views/pages/reports/project-summary.blade.php`
    - Extend `layouts.app`
    - Render breadcrumb "Reports / Project Summary" at top
    - Render title "Project Summary Report" with "Export PDF" button (`.btn-export`) in top-right
    - Render filter bar: search input (placeholder "Search by project code or name"), period dropdown populated from `$periods`, status dropdown with "All Status" default
    - Render data table with columns: PROJECT CODE, PROJECT NAME, PLANNED HOURS, CHARGED HOURS, UTILIZATION (%)
    - Each utilization cell renders a `.progress-bar` with `.progress-bar-fill` using the correct color class based on percentage thresholds
    - Render totals row at bottom with aggregate planned hours, charged hours, and overall utilization
    - Render pagination controls showing "Showing X of Y projects" and page navigation
    - Show loading spinner while data loads, error message with retry button on API failure
    - Show "No data found for the selected period." when project list is empty
    - _Requirements: 3.1, 3.2, 3.4, 3.5, 3.7, 3.8, 3.11, 6.1, 6.2, 6.4, 7.4, 7.5_

- [x] 7. Create Submission Summary report page view
  - [x] 7.1 Create `frontend/resources/views/pages/reports/submission-summary.blade.php`
    - Extend `layouts.app`
    - Render breadcrumb "Reports / Submission Summary" at top
    - Render title "Submission Summary Report" with "Export PDF" button (`.btn-export`) in top-right
    - Render filter bar: search input (placeholder "Search by employee name"), period dropdown populated from `$periods`, status dropdown with "All Status" default
    - Render data table with columns: NAME, CHARGEABLE HOURS, TOTAL HOURS, CURRENT PERIOD CHARGEABILITY (%), YTD CHARGEABILITY (%)
    - Each chargeability cell renders a `.progress-bar` with `.progress-bar-fill` using the correct color class based on percentage thresholds
    - Render totals row at bottom with aggregate chargeable hours, total hours, and overall chargeability percentages
    - Render pagination controls showing "Showing X of Y submissions" and page navigation
    - Show loading spinner while data loads, error message with retry button on API failure
    - Show "No data found for the selected period." when submission list is empty
    - _Requirements: 4.1, 4.2, 4.4, 4.5, 4.7, 4.8, 4.11, 6.1, 6.2, 6.4, 7.4, 7.5_

- [x] 8. Checkpoint — Ensure report pages render correctly
  - Ensure all tests pass, ask the user if questions arise.

- [x] 9. Implement client-side filtering, pagination, and PDF export
  - [x] 9.1 Create `frontend/public/js/reports.js` for client-side report interactions
    - Implement search input filtering: on keyup, filter table rows by case-insensitive substring match on project code/name (Project Summary) or employee name (Submission Summary)
    - Implement pagination: show N rows per page (default 10), render page number controls, update "Showing X of Y" count text
    - Implement period dropdown change: submit form or navigate to reload page with selected period parameter
    - Implement Export PDF button click: send AJAX GET to the export endpoint with selected periodId, show loading state on button, on success trigger browser download from returned URL, on failure show error notification and re-enable button
    - Implement sidebar Reports menu toggle: click handler on `.nav-group-toggle` to expand/collapse `.nav-group-items` and rotate chevron
    - _Requirements: 3.9, 3.10, 3.11, 4.9, 4.10, 4.11, 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 1.2, 1.3_

  - [ ]* 9.2 Write property test for search filter correctness
    - **Property 6: Search filter returns only matching rows**
    - Generate random search strings and item lists, apply filter logic, assert filtered set contains exactly matching items
    - **Validates: Requirements 3.9, 4.9**

  - [ ]* 9.3 Write property test for pagination correctness
    - **Property 7: Pagination displays correct counts and pages**
    - Generate random item counts and page sizes, compute pagination metadata, assert page count equals ceil(N/P) and item counts are correct
    - **Validates: Requirements 3.11, 4.11**

- [x] 10. Final checkpoint — Ensure all report features work end-to-end
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- The implementation follows existing patterns: server-side Blade views, GraphQLClient for API calls, client-side JS for filtering/pagination
- Period selection triggers server-side re-fetch; search filtering and pagination are client-side only
- PDF export uses AJAX to get a pre-signed S3 URL, then triggers browser download
- Property tests use PHPUnit data providers with randomized inputs (minimum 100 iterations)
