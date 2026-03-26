# Requirements Document

## Introduction

The PM Reports Section extends the TimeFlow frontend portal with a Reports area accessible to users with the Project_Manager or Tech_Lead role. This feature adds a collapsible "Reports" menu item to the Sidebar_Navigation containing two sub-pages: Project Summary and Submission Summary. Each report page provides tabular data with filters, colored utilization/chargeability progress bars, totals, pagination, and PDF export capability. The feature integrates with existing GraphQL queries (`listProjects`, `listAllSubmissions`, `listTimesheetPeriods`, `getProjectSummaryReport`, `getTCSummaryReport`) and the existing role-based access control infrastructure.

## Glossary

- **Portal**: The TimeFlow web application front-end that employees interact with via a browser
- **Reports_Section**: The collapsible sidebar navigation group containing Project Summary and Submission Summary sub-pages, visible only to Tech_Lead_PM users
- **Tech_Lead_PM**: A user with userType `user` and role `Tech_Lead` or `Project_Manager` (admin and superadmin access will be handled in a separate spec)
- **Project_Summary_Page**: The report page at `/reports/project-summary` displaying project-level utilization data for a selected period
- **Submission_Summary_Page**: The report page at `/reports/submission-summary` displaying employee-level chargeability data for a selected period
- **Utilization_Bar**: A colored horizontal progress bar indicating the ratio of charged hours to planned hours for a project (green for normal, yellow for low, red for over 100%)
- **Chargeability_Bar**: A colored horizontal progress bar indicating the chargeability percentage for an employee (green for normal, yellow for low, red for over 100%)
- **API_Service**: The AWS AppSync GraphQL API that serves as the backend data layer
- **Sidebar_Navigation**: The persistent left-side navigation panel with links to pages
- **Period**: A weekly timesheet period running Monday through Friday
- **PDF_Export**: The action of generating and downloading a PDF report via a pre-signed S3 URL returned by the API_Service

## Requirements

### Requirement 1: Reports Sidebar Navigation

**User Story:** As a Tech_Lead_PM user, I want to see a Reports section in the sidebar navigation, so that I can access project and submission reports from any page.

#### Acceptance Criteria

1. WHILE the authenticated user has userType `user` and role `Tech_Lead` or `Project_Manager`, THE Sidebar_Navigation SHALL display a "Reports" menu item with a document/chart icon between the Timesheet and Settings navigation links
2. WHEN the Tech_Lead_PM user clicks the Reports menu item, THE Sidebar_Navigation SHALL expand to reveal two sub-items: "Project Summary" and "Submission Summary"
3. WHEN the Tech_Lead_PM user clicks the expanded Reports menu item again, THE Sidebar_Navigation SHALL collapse the sub-items
4. THE Reports menu item SHALL display a chevron icon that rotates to indicate expanded (downward) or collapsed (rightward) state
5. WHILE the user is on the Project_Summary_Page or Submission_Summary_Page, THE Sidebar_Navigation SHALL highlight the Reports menu item as active and keep the sub-items expanded
6. WHILE the user is on the Project_Summary_Page, THE Sidebar_Navigation SHALL highlight the "Project Summary" sub-item as active
7. WHILE the user is on the Submission_Summary_Page, THE Sidebar_Navigation SHALL highlight the "Submission Summary" sub-item as active
8. WHILE the authenticated user has role Employee and userType user, THE Sidebar_Navigation SHALL hide the Reports menu item

### Requirement 2: Reports Route Protection

**User Story:** As a system operator, I want report pages restricted to authorized roles, so that general employees cannot access PM-level reports.

#### Acceptance Criteria

1. THE Portal SHALL register routes `/reports/project-summary` and `/reports/submission-summary` under the `cognito.auth` middleware group
2. THE Portal SHALL apply a role middleware to report routes that permits access only to users with userType `user` and role `Tech_Lead` or `Project_Manager`
3. IF a user with role Employee and userType user attempts to access a report route, THEN THE Portal SHALL redirect the user to the Dashboard_Page with an error message indicating insufficient permissions
4. IF an unauthenticated user attempts to access a report route, THEN THE Portal SHALL redirect to the login page

### Requirement 3: Project Summary Report Page

**User Story:** As a Tech_Lead_PM user, I want to view a Project Summary report, so that I can monitor project utilization across the selected period.

#### Acceptance Criteria

1. WHEN the Project_Summary_Page loads, THE Portal SHALL display a breadcrumb "Reports / Project Summary" at the top of the content area
2. WHEN the Project_Summary_Page loads, THE Portal SHALL display the title "Project Summary Report"
3. WHEN the Project_Summary_Page loads, THE Portal SHALL query the API_Service using `listProjects` to retrieve all projects and `listTimesheetPeriods` to retrieve available periods
4. THE Project_Summary_Page SHALL display a filter bar containing: a search input for filtering by project name or code, a date range picker for selecting the reporting period, and a status dropdown with options including "All Status"
5. THE Project_Summary_Page SHALL display a data table with columns: PROJECT CODE, PROJECT NAME, PLANNED HOURS, CHARGED HOURS, and UTILIZATION (%)
6. THE Project_Summary_Page SHALL calculate utilization percentage as (Charged Hours / Planned Hours) × 100 for each project row
7. THE Project_Summary_Page SHALL display the utilization percentage with a Utilization_Bar: green for values between 50% and 100%, yellow for values below 50%, and red for values above 100%
8. THE Project_Summary_Page SHALL display a totals row at the bottom of the table showing aggregate Planned Hours, aggregate Charged Hours, and overall utilization percentage
9. WHEN the Tech_Lead_PM user types in the search input, THE Project_Summary_Page SHALL filter the table rows to show only projects whose project code or project name contains the search text (case-insensitive)
10. WHEN the Tech_Lead_PM user selects a date range, THE Project_Summary_Page SHALL filter the data to the selected period and recalculate all values
11. THE Project_Summary_Page SHALL display pagination controls showing the count of displayed projects (e.g., "Showing 5 of 5 projects") and page number navigation when results exceed the page size

### Requirement 4: Submission Summary Report Page

**User Story:** As a Tech_Lead_PM user, I want to view a Submission Summary report, so that I can monitor employee chargeability across the selected period.

#### Acceptance Criteria

1. WHEN the Submission_Summary_Page loads, THE Portal SHALL display a breadcrumb "Reports / Submission Summary" at the top of the content area
2. WHEN the Submission_Summary_Page loads, THE Portal SHALL display the title "Submission Summary Report"
3. WHEN the Submission_Summary_Page loads, THE Portal SHALL query the API_Service using `listAllSubmissions` to retrieve all employee submissions for the selected period
4. THE Submission_Summary_Page SHALL display a filter bar containing: a search input for filtering by employee name, a date range picker for selecting the reporting period, and a status dropdown with options including "All Status"
5. THE Submission_Summary_Page SHALL display a data table with columns: NAME, CHARGEABLE HOURS, TOTAL HOURS, CURRENT PERIOD CHARGEABILITY (%), and YTD CHARGEABILITY (%)
6. THE Submission_Summary_Page SHALL calculate current period chargeability as (Chargeable Hours / Total Hours) × 100 for each employee row
7. THE Submission_Summary_Page SHALL display chargeability percentages with a Chargeability_Bar: green for values between 50% and 100%, yellow for values below 50%, and red for values above 100%
8. THE Submission_Summary_Page SHALL display a totals row at the bottom of the table showing aggregate Chargeable Hours, aggregate Total Hours, and overall chargeability percentages
9. WHEN the Tech_Lead_PM user types in the search input, THE Submission_Summary_Page SHALL filter the table rows to show only employees whose name contains the search text (case-insensitive)
10. WHEN the Tech_Lead_PM user selects a date range, THE Submission_Summary_Page SHALL filter the data to the selected period and recalculate all values
11. THE Submission_Summary_Page SHALL display pagination controls showing the count of displayed submissions (e.g., "Showing 5 of 5 submissions") and page number navigation when results exceed the page size

### Requirement 5: PDF Export

**User Story:** As a Tech_Lead_PM user, I want to export reports as PDF files, so that I can share or archive report data offline.

#### Acceptance Criteria

1. THE Project_Summary_Page SHALL display an "Export PDF" button in the top-right area of the page header
2. THE Submission_Summary_Page SHALL display an "Export PDF" button in the top-right area of the page header
3. WHEN the Tech_Lead_PM user clicks "Export PDF" on the Project_Summary_Page, THE Portal SHALL query the API_Service using `getProjectSummaryReport` with the selected period ID and initiate a browser download from the returned pre-signed URL
4. WHEN the Tech_Lead_PM user clicks "Export PDF" on the Submission_Summary_Page, THE Portal SHALL query the API_Service using `getTCSummaryReport` with the authenticated user's ID and the selected period ID and initiate a browser download from the returned pre-signed URL
5. WHILE the PDF export request is in progress, THE Portal SHALL display a loading indicator on the "Export PDF" button and disable the button to prevent duplicate requests
6. IF the PDF export request fails, THEN THE Portal SHALL display an error notification describing the failure and re-enable the "Export PDF" button

### Requirement 6: Report Page Layout and Styling

**User Story:** As a Tech_Lead_PM user, I want the report pages to match the existing TimeFlow dark theme and layout, so that the experience is visually consistent.

#### Acceptance Criteria

1. THE Project_Summary_Page and Submission_Summary_Page SHALL use the same dark theme color scheme, typography, and layout structure as existing Portal pages (Dashboard_Page, Timesheet_Page)
2. THE report data tables SHALL use alternating row backgrounds consistent with the existing table styling in the Portal
3. THE Utilization_Bar and Chargeability_Bar SHALL use green (#22c55e or similar) for 50%-100%, yellow (#eab308 or similar) for below 50%, and red (#ef4444 or similar) for above 100%
4. THE filter bar SHALL be positioned between the page title and the data table, consistent with the filter layout on the Timesheet_Page
5. THE "Export PDF" button SHALL use the Portal's primary blue button style consistent with other action buttons in the Portal
6. THE pagination controls SHALL be positioned below the data table and styled consistently with standard Portal pagination

### Requirement 7: Period Selection and Data Loading

**User Story:** As a Tech_Lead_PM user, I want the report pages to default to the current period and allow me to select other periods, so that I can view both current and historical report data.

#### Acceptance Criteria

1. WHEN a report page loads, THE Portal SHALL query the API_Service using `getCurrentPeriod` to determine the active period and use the active period as the default date range
2. WHEN a report page loads, THE Portal SHALL query the API_Service using `listTimesheetPeriods` to populate the date range picker with available periods
3. WHEN the Tech_Lead_PM user selects a different period from the date range picker, THE Portal SHALL re-query the API_Service with the selected period filter and refresh the table data
4. WHILE report data is loading, THE Portal SHALL display a loading spinner or skeleton UI in the table area
5. IF the API_Service returns an error during data loading, THEN THE Portal SHALL display a user-friendly error message with a retry option
