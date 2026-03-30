# Requirements Document

## Introduction

The TimeFlow frontend currently uses a dark-themed UI (dark navy backgrounds, slate text colors, minimal elevation). This feature overhauls the entire visual style to match a modern, light-themed SaaS admin dashboard reference design. The overhaul covers the global layout, sidebar navigation, top header bar, data tables, form controls, buttons, cards, modals, and all page-level styles across every Blade template. No functional behavior changes — only visual presentation.

## Glossary

- **App_Layout**: The root HTML structure defined in `layouts/app.blade.php` containing the Sidebar, Header_Bar, and Main_Content_Area
- **Sidebar**: The fixed left-hand navigation panel defined in `components/sidebar.blade.php`
- **Header_Bar**: A new top-right header strip containing search, notifications, and user profile controls
- **Main_Content_Area**: The primary content region to the right of the Sidebar and below the Header_Bar
- **Data_Table**: Any HTML `<table>` used to display list/grid data on pages such as user-management, timesheet-submissions, approvals, departments, positions, and projects
- **Summary_Card**: The card component defined in `components/summary-card.blade.php` used on dashboard pages
- **Action_Button**: Inline row-level buttons inside Data_Tables (e.g., View, Edit, Delete, Approve, Reject)
- **Page_Header**: The top section of each page containing the page title and optional subtitle description
- **Tab_Navigation**: Horizontal pill-style or underline-style tab controls used for switching between sub-views on a page
- **Filter_Bar**: A horizontal bar containing search inputs, dropdowns, and action buttons for filtering Data_Table content
- **Nav_Group**: A collapsible menu section in the Sidebar containing child navigation links with a chevron toggle indicator
- **Design_Token**: A CSS custom property (variable) defining a reusable color, spacing, shadow, or typography value
- **Login_Page**: The authentication page at `pages/login.blade.php`
- **Auth_Pages**: The set of pages including Login_Page, force-change-password, forgot-password, and reset-password
- **Entry_Modal**: The modal dialog component defined in `components/entry-modal.blade.php`
- **Pagination_Control**: The numbered page navigation buttons displayed below Data_Tables

## Requirements

### Requirement 1: Global Design Tokens and Base Styles

**User Story:** As a developer, I want a centralized set of CSS design tokens, so that the entire application uses consistent colors, typography, spacing, and elevation values matching the reference design.

#### Acceptance Criteria

1. THE App_Layout SHALL define CSS custom properties for primary color (#2563eb), primary-hover color, sidebar background (#1e3a5f), sidebar text color (#ffffff), body background (#f1f5f9), surface background (#ffffff), text-primary (#1e293b), text-secondary (#64748b), border color (#e2e8f0), border-radius-sm (6px), border-radius-md (8px), border-radius-lg (12px), shadow-sm, shadow-md, and font-family (Inter or system sans-serif stack)
2. THE App_Layout SHALL apply the body background Design_Token to the `<body>` element with text-primary as the default text color
3. THE App_Layout SHALL use a base font size of 14px with a line-height of 1.5
4. WHEN a Design_Token value is changed, THE App_Layout SHALL propagate the change to all components that reference the token without requiring per-component edits

### Requirement 2: Sidebar Navigation Restyling

**User Story:** As a user, I want a visually updated sidebar navigation with a dark blue background and clear active-state indicators, so that I can navigate the application with a modern, polished experience.

#### Acceptance Criteria

1. THE Sidebar SHALL render with a dark navy background (#1e3a5f), white text (#ffffff), and rounded corners (border-radius-lg) on the container
2. THE Sidebar SHALL display the TimeFlow logo area at the top with the brand icon and text on a consistent dark background
3. WHEN a navigation link is the active page, THE Sidebar SHALL highlight the active link with a lighter blue background (rgba(255,255,255,0.12)) and a left border accent or distinct background differentiation
4. WHEN a user hovers over a non-active navigation link, THE Sidebar SHALL display a subtle background highlight (rgba(255,255,255,0.06))
5. THE Nav_Group SHALL display a chevron indicator that rotates when the group is expanded or collapsed
6. THE Sidebar SHALL display the user avatar, full name, and role in the footer section with white/light text
7. WHEN the viewport width is below 768px, THE Sidebar SHALL collapse off-screen and be togglable via a hamburger button
8. THE Sidebar SHALL maintain a fixed width of 260px on desktop viewports

### Requirement 3: Top Header Bar

**User Story:** As a user, I want a top header bar with search, notifications, and my profile, so that I have quick access to global actions without scrolling.

#### Acceptance Criteria

1. THE Header_Bar SHALL render as a horizontal strip at the top of the Main_Content_Area with a white background (#ffffff), bottom border (#e2e8f0), and subtle shadow (shadow-sm)
2. THE Header_Bar SHALL display a search icon, notification bell icon, user avatar with the user name, and an overflow menu icon aligned to the right
3. THE Header_Bar SHALL remain fixed at the top of the Main_Content_Area when the page scrolls
4. WHEN the viewport width is below 768px, THE Header_Bar SHALL adapt its layout to remain usable without horizontal overflow

### Requirement 4: Main Content Area and Page Layout

**User Story:** As a user, I want the main content area to have a clean, light background with consistent spacing, so that page content is easy to read and visually organized.

#### Acceptance Criteria

1. THE Main_Content_Area SHALL render with the body background color (#f1f5f9) and padding of 1.5rem on all sides
2. THE Main_Content_Area SHALL be positioned to the right of the Sidebar (260px offset) and below the Header_Bar
3. THE Page_Header SHALL display the page title in text-primary color with font-size 1.5rem and font-weight 600, and an optional subtitle in text-secondary color with font-size 0.875rem
4. THE Main_Content_Area SHALL apply consistent vertical spacing (1.25rem) between major content sections

### Requirement 5: Data Table Restyling

**User Story:** As a user, I want clean, readable data tables with clear row separation and styled action buttons, so that I can scan and interact with tabular data efficiently.

#### Acceptance Criteria

1. THE Data_Table SHALL render with a white surface background (#ffffff), border-radius-lg on the container, and shadow-sm elevation
2. THE Data_Table SHALL display a header row with a light gray background (#f8fafc), text-secondary color text, uppercase font-size 0.75rem, and font-weight 600
3. THE Data_Table SHALL display body rows with white background and a 1px bottom border (#e2e8f0) between rows
4. WHEN a user hovers over a Data_Table body row, THE Data_Table SHALL apply a subtle background highlight (#f8fafc)
5. THE Action_Button SHALL render as outlined rounded buttons with a 1px border, border-radius of 6px, and color-coded variants: blue for primary actions, red for destructive actions, and gray for neutral actions
6. THE Pagination_Control SHALL render as a row of numbered page buttons with border-radius-md, with the active page button using the primary color background and white text

### Requirement 6: Filter Bar and Search Controls

**User Story:** As a user, I want styled filter bars with search inputs, dropdowns, and action buttons, so that I can filter and search data tables with a consistent, modern look.

#### Acceptance Criteria

1. THE Filter_Bar SHALL render as a horizontal flex container with gap spacing (0.75rem) between controls, aligned above the Data_Table
2. THE Filter_Bar input fields SHALL render with a white background, 1px border (#e2e8f0), border-radius-md, padding of 0.5rem 0.75rem, and text-primary color text
3. THE Filter_Bar dropdown selects SHALL render with the same styling as input fields with a chevron indicator
4. THE Filter_Bar search button SHALL render as an outlined button with primary color border and text
5. THE Filter_Bar export button SHALL render as a filled primary color button with white text and a download icon
6. WHEN a Filter_Bar input field receives focus, THE Filter_Bar SHALL display a primary color border (2px) on the focused field

### Requirement 7: Summary Cards Restyling

**User Story:** As a user, I want dashboard summary cards with a light, elevated style, so that key metrics are visually prominent and easy to read.

#### Acceptance Criteria

1. THE Summary_Card SHALL render with a white surface background (#ffffff), border-radius-lg, shadow-sm, and padding of 1.25rem
2. THE Summary_Card SHALL display the icon in a light primary-tinted background circle (rgba(37,99,235,0.1)) with primary color icon stroke
3. THE Summary_Card SHALL display the title in text-secondary color (font-size 0.8rem) and the value in text-primary color (font-size 1.25rem, font-weight 700)

### Requirement 8: Button Styles

**User Story:** As a user, I want consistent, modern button styles across the application, so that interactive elements are clearly identifiable and visually cohesive.

#### Acceptance Criteria

1. THE App_Layout SHALL define a primary button style with primary color background (#2563eb), white text, border-radius-md, padding 0.5rem 1rem, font-weight 500, and shadow-sm
2. THE App_Layout SHALL define an outlined button style with transparent background, 1px primary color border, primary color text, and border-radius-md
3. THE App_Layout SHALL define a danger button style with red background (#dc2626) for destructive actions and a danger-outlined variant with red border and red text
4. WHEN a user hovers over a button, THE App_Layout SHALL darken the background color by 10% or increase border opacity for outlined variants
5. WHEN a button is in a disabled state, THE App_Layout SHALL reduce the button opacity to 0.5 and set cursor to not-allowed

### Requirement 9: Form and Input Styles

**User Story:** As a user, I want clean, consistent form inputs across all pages, so that data entry feels polished and predictable.

#### Acceptance Criteria

1. THE App_Layout SHALL style all text inputs, textareas, and select elements with white background, 1px border (#e2e8f0), border-radius-md, padding 0.5rem 0.75rem, font-size 0.875rem, and text-primary color
2. WHEN an input field receives focus, THE App_Layout SHALL display a 2px primary color border and a subtle primary-tinted box-shadow
3. WHEN an input field has a validation error, THE App_Layout SHALL display a red border (#dc2626) and red error message text below the field
4. THE App_Layout SHALL style form labels with text-secondary color, font-size 0.8rem, font-weight 500, and margin-bottom 0.375rem

### Requirement 10: Modal Dialog Restyling

**User Story:** As a user, I want modal dialogs with a clean, light design, so that overlay interactions feel consistent with the rest of the application.

#### Acceptance Criteria

1. THE Entry_Modal SHALL render with a white surface background, border-radius-lg, shadow-md, and a semi-transparent dark overlay (rgba(0,0,0,0.4))
2. THE Entry_Modal SHALL display a header section with text-primary title, a close button, and a 1px bottom border separator
3. THE Entry_Modal SHALL display a footer section with right-aligned action buttons using the standard button styles
4. WHEN the Entry_Modal is opened, THE Entry_Modal SHALL animate in with a fade and slight scale-up transition (200ms ease)

### Requirement 11: Authentication Pages Restyling

**User Story:** As a user, I want the login and authentication pages to match the new light design language, so that the first impression of the application is modern and professional.

#### Acceptance Criteria

1. THE Auth_Pages SHALL render with a centered card layout on a light background (#f1f5f9) with the TimeFlow logo above the form
2. THE Auth_Pages form card SHALL use white surface background, border-radius-lg, shadow-md, and padding of 2rem
3. THE Auth_Pages SHALL style the submit button as a full-width primary button
4. IF a login or authentication error occurs, THEN THE Auth_Pages SHALL display the error message in a red-tinted alert box with border-radius-md

### Requirement 12: Tab Navigation Restyling

**User Story:** As a user, I want styled tab navigation on pages that use tabs, so that switching between views is visually clear and consistent.

#### Acceptance Criteria

1. THE Tab_Navigation SHALL render as horizontal inline items with text-secondary color, font-size 0.875rem, and font-weight 500
2. WHEN a tab is active, THE Tab_Navigation SHALL display a primary color bottom border (2px) and primary color text on the active tab
3. WHEN a user hovers over an inactive tab, THE Tab_Navigation SHALL display text-primary color on the hovered tab
4. THE Tab_Navigation SHALL include consistent horizontal padding (1rem) and bottom margin (1.25rem) to separate tabs from content below

### Requirement 13: Alert and Notification Styles

**User Story:** As a user, I want styled alert messages for success, error, warning, and info states, so that system feedback is visually distinct and easy to understand.

#### Acceptance Criteria

1. THE App_Layout SHALL define a success alert style with green-tinted background (#f0fdf4), green border (#bbf7d0), green text (#166534), and border-radius-md
2. THE App_Layout SHALL define an error alert style with red-tinted background (#fef2f2), red border (#fecaca), red text (#991b1b), and border-radius-md
3. THE App_Layout SHALL define a warning alert style with amber-tinted background (#fffbeb), amber border (#fde68a), amber text (#92400e), and border-radius-md
4. THE App_Layout SHALL define an info alert style with blue-tinted background (#eff6ff), blue border (#bfdbfe), blue text (#1e40af), and border-radius-md

### Requirement 14: Responsive Layout Behavior

**User Story:** As a user accessing TimeFlow on different devices, I want the layout to adapt gracefully, so that the application remains usable on tablets and mobile screens.

#### Acceptance Criteria

1. WHEN the viewport width is below 768px, THE Sidebar SHALL collapse off-screen and the Main_Content_Area SHALL expand to full width
2. WHEN the viewport width is below 768px, THE Data_Table SHALL enable horizontal scrolling within its container to prevent layout overflow
3. WHEN the viewport width is below 768px, THE Summary_Card grid SHALL switch from multi-column to single-column layout
4. WHEN the viewport width is below 768px, THE Filter_Bar SHALL wrap its controls vertically with full-width inputs

### Requirement 15: Loading Overlay Restyling

**User Story:** As a user, I want the loading overlay to match the new light theme, so that loading states feel consistent with the overall design.

#### Acceptance Criteria

1. THE App_Layout loading overlay SHALL render with a semi-transparent white background (rgba(255,255,255,0.7)) instead of the current dark overlay
2. THE App_Layout loading spinner SHALL use the primary color (#2563eb) for the spinning border accent
3. THE App_Layout loading text SHALL display in text-secondary color
