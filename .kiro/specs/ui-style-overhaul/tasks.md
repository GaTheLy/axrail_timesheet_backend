# Implementation Plan: UI Style Overhaul

## Overview

Convert the TimeFlow frontend from a dark theme to a modern light theme by introducing CSS design tokens, rewriting `app.css` to reference those tokens, adding a new Header Bar component, updating auth page inline styles, and ensuring responsive behavior. All existing CSS class names are preserved — only values change.

## Tasks

- [x] 1. Define global design tokens and base styles in `app.css`
  - [x] 1.1 Add `:root` block with all CSS custom properties (colors, radii, shadows, typography) as specified in the design
    - Define `--color-primary`, `--color-primary-hover`, `--color-primary-light`, `--color-sidebar-bg`, `--color-sidebar-text`, `--color-sidebar-active-bg`, `--color-sidebar-hover-bg`, `--color-body-bg`, `--color-surface`, `--color-surface-hover`, `--color-text-primary`, `--color-text-secondary`, `--color-border`, `--color-danger`, `--color-danger-hover`, `--radius-sm`, `--radius-md`, `--radius-lg`, `--shadow-sm`, `--shadow-md`, `--font-family`, `--font-size-base`, `--line-height-base`
    - _Requirements: 1.1_
  - [x] 1.2 Update `body` and base element styles to use design tokens
    - Set `background: var(--color-body-bg)`, `color: var(--color-text-primary)`, `font-family: var(--font-family)`, `font-size: var(--font-size-base)`, `line-height: var(--line-height-base)`
    - _Requirements: 1.2, 1.3_
  - [x] 1.3 Write property test for design token completeness (Property 1)
    - **Property 1: Design token completeness and correctness**
    - Parse `:root` block and verify all specified tokens exist with correct values
    - **Validates: Requirements 1.1**

- [x] 2. Update layout structure and add Header Bar
  - [x] 2.1 Create `frontend/resources/views/components/header-bar.blade.php`
    - Add header HTML with search icon, notification bell, user avatar, and user name
    - Include proper `role="banner"` and `aria-label` attributes for accessibility
    - _Requirements: 3.1, 3.2_
  - [x] 2.2 Update `frontend/resources/views/layouts/app.blade.php` to include Header Bar
    - Add `.content-wrapper` div wrapping the Header Bar include and `main.main-content`
    - Ensure `@include('components.header-bar')` is placed before `@yield('content')`
    - _Requirements: 3.1, 4.2_
  - [x] 2.3 Add Header Bar CSS styles in `app.css`
    - Style `.header-bar` with white background, bottom border, shadow-sm, sticky positioning, 56px height
    - Style `.header-bar-right`, `.header-icon`, `.header-notification`, `.header-user`, `.header-user-avatar`, `.header-user-name`
    - _Requirements: 3.1, 3.2, 3.3_
  - [x] 2.4 Add `.content-wrapper` and update `.main-content` CSS
    - `.content-wrapper`: `margin-left: 260px`, `flex: 1`, `display: flex`, `flex-direction: column`, `min-height: 100vh`
    - `.main-content`: `flex: 1`, `padding: 1.5rem`, remove old `margin-left`
    - _Requirements: 4.1, 4.2, 4.4_

- [x] 3. Restyle Sidebar navigation
  - [x] 3.1 Update sidebar container and brand area styles
    - Set background to `var(--color-sidebar-bg)`, text to `var(--color-sidebar-text)`, `border-radius: var(--radius-lg)`, fixed width 260px
    - Style logo/brand area with consistent dark background
    - _Requirements: 2.1, 2.2, 2.8_
  - [x] 3.2 Update sidebar navigation link styles (active, hover, nav groups)
    - Active link: `background: var(--color-sidebar-active-bg)`, left 3px border accent
    - Hover: `background: var(--color-sidebar-hover-bg)`
    - Nav group chevron: white, rotate 180° on expand
    - _Requirements: 2.3, 2.4, 2.5_
  - [x] 3.3 Update sidebar footer (user avatar, name, role)
    - White/light text for name, `rgba(255,255,255,0.6)` for role
    - _Requirements: 2.6_

- [x] 4. Checkpoint — Verify layout and navigation
  - Ensure all tests pass, ask the user if questions arise.

- [x] 5. Restyle Data Tables and Pagination
  - [x] 5.1 Update Data Table container, header row, and body row styles
    - Container: `var(--color-surface)`, `border-radius: var(--radius-lg)`, `box-shadow: var(--shadow-sm)`
    - Header: `var(--color-surface-hover)` background, `var(--color-text-secondary)` text, uppercase 0.75rem
    - Body rows: white background, `1px solid var(--color-border)` bottom border, hover `var(--color-surface-hover)`
    - Remove alternating row colors
    - _Requirements: 5.1, 5.2, 5.3, 5.4_
  - [x] 5.2 Update Action Button styles inside tables
    - Outlined rounded buttons with `border-radius: var(--radius-sm)`, color-coded: blue primary, red destructive, gray neutral
    - _Requirements: 5.5_
  - [x] 5.3 Update Pagination Control styles
    - Buttons: `var(--color-surface)` background, `var(--color-border)` border, `border-radius: var(--radius-md)`
    - Active: `var(--color-primary)` background, white text
    - Hover: `border-color: var(--color-primary)`
    - _Requirements: 5.6_

- [x] 6. Restyle Filter Bar and Search Controls
  - [x] 6.1 Update Filter Bar layout and input/dropdown styles
    - Flex container with `gap: 0.75rem`, inputs with white background, `1px solid var(--color-border)`, `border-radius: var(--radius-md)`
    - Focus state: `2px solid var(--color-primary)` border
    - _Requirements: 6.1, 6.2, 6.3, 6.6_
  - [x] 6.2 Update Filter Bar button styles (search and export)
    - Search: outlined with primary border and text
    - Export: filled primary with white text and download icon
    - _Requirements: 6.4, 6.5_

- [x] 7. Restyle Summary Cards
  - Update `.summary-card` with `var(--color-surface)` background, `border-radius: var(--radius-lg)`, `box-shadow: var(--shadow-sm)`, padding 1.25rem
  - Icon circle: `var(--color-primary-light)` background, `var(--color-primary)` icon color
  - Title: `var(--color-text-secondary)` 0.8rem; Value: `var(--color-text-primary)` 1.25rem bold
  - Remove dark border, use shadow instead
  - _Requirements: 7.1, 7.2, 7.3_

- [x] 8. Restyle Buttons, Forms, and Inputs
  - [x] 8.1 Update global button styles (primary, outlined, danger, disabled)
    - Primary: `var(--color-primary)` bg, white text, `border-radius: var(--radius-md)`, `box-shadow: var(--shadow-sm)`
    - Outlined: transparent bg, `1px solid var(--color-primary)`, primary text
    - Danger: `var(--color-danger)` bg, white text; danger-outlined: red border, red text
    - Hover: use `--color-primary-hover` / `--color-danger-hover`
    - Disabled: `opacity: 0.5`, `cursor: not-allowed`
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5_
  - [x] 8.2 Update form input, textarea, select, and label styles
    - Inputs: `var(--color-surface)` bg, `1px solid var(--color-border)`, `border-radius: var(--radius-md)`, `var(--color-text-primary)` text
    - Focus: `2px solid var(--color-primary)`, `box-shadow: 0 0 0 3px var(--color-primary-light)`
    - Error: `var(--color-danger)` border, red error text
    - Labels: `var(--color-text-secondary)`, 0.8rem, font-weight 500
    - _Requirements: 9.1, 9.2, 9.3, 9.4_

- [x] 9. Restyle Modals
  - Update `.modal` / Entry_Modal with `var(--color-surface)` bg, `border-radius: var(--radius-lg)`, `box-shadow: var(--shadow-md)`
  - Overlay: `rgba(0,0,0,0.4)`
  - Header: text-primary title, close button, bottom border separator
  - Footer: right-aligned action buttons using standard button styles
  - Open animation: fade + scale-up 200ms ease
  - Remove dark border
  - _Requirements: 10.1, 10.2, 10.3, 10.4_

- [x] 10. Restyle Tab Navigation, Alerts, and Loading Overlay
  - [x] 10.1 Update Tab Navigation styles
    - Items: `var(--color-text-secondary)`, 0.875rem, font-weight 500
    - Active: `var(--color-primary)` text, `2px solid var(--color-primary)` bottom border
    - Hover: `var(--color-text-primary)` text
    - Padding: 1rem horizontal, 1.25rem bottom margin
    - _Requirements: 12.1, 12.2, 12.3, 12.4_
  - [x] 10.2 Update Alert styles (success, error, warning, info)
    - Success: bg `#f0fdf4`, border `#bbf7d0`, text `#166534`
    - Error: bg `#fef2f2`, border `#fecaca`, text `#991b1b`
    - Warning: bg `#fffbeb`, border `#fde68a`, text `#92400e`
    - Info: bg `#eff6ff`, border `#bfdbfe`, text `#1e40af`
    - All with `border-radius: var(--radius-md)`
    - _Requirements: 13.1, 13.2, 13.3, 13.4_
  - [x] 10.3 Update Loading Overlay styles
    - Background: `rgba(255,255,255,0.7)`
    - Spinner: `var(--color-border)` track, `var(--color-primary)` accent
    - Text: `var(--color-text-secondary)`
    - _Requirements: 15.1, 15.2, 15.3_

- [x] 11. Checkpoint — Verify component restyling
  - Ensure all tests pass, ask the user if questions arise.

- [x] 12. Restyle Authentication Pages
  - [x] 12.1 Update `login.blade.php` inline styles
    - Body: `var(--color-body-bg)` flat background (no gradient)
    - Card: `var(--color-surface)` bg, `border-radius: var(--radius-lg)`, `box-shadow: var(--shadow-md)`, padding 2rem
    - Logo text: `var(--color-text-primary)`
    - Submit button: full-width primary style
    - Error alert: red-tinted as per alert styles
    - _Requirements: 11.1, 11.2, 11.3, 11.4_
  - [x] 12.2 Update `forgot-password.blade.php` inline styles
    - Apply same light-theme card styling as login page
    - _Requirements: 11.1, 11.2, 11.3_
  - [x] 12.3 Update `reset-password.blade.php` inline styles
    - Apply same light-theme card styling as login page
    - _Requirements: 11.1, 11.2, 11.3_
  - [x] 12.4 Update `force-change-password.blade.php` inline styles
    - Apply same light-theme card styling as login page
    - _Requirements: 11.1, 11.2, 11.3_

- [x] 13. Update Page Header styles
  - Style page title: `var(--color-text-primary)`, font-size 1.5rem, font-weight 600
  - Style subtitle: `var(--color-text-secondary)`, font-size 0.875rem
  - Consistent vertical spacing 1.25rem between sections
  - _Requirements: 4.3, 4.4_

- [x] 14. Add responsive breakpoint styles
  - [x] 14.1 Add mobile breakpoint (below 768px) styles
    - Sidebar collapses off-screen, `.content-wrapper` removes `margin-left`
    - Header Bar: hide user name, keep icons
    - Summary cards: single-column layout
    - Data tables: horizontal scroll wrapper
    - Filter bar: vertical stack, full-width inputs
    - _Requirements: 14.1, 14.2, 14.3, 14.4, 2.7, 3.4_
  - [x] 14.2 Add tablet breakpoint (768px–1023px) styles
    - Sidebar: 200px width, `.content-wrapper` adjusts `margin-left: 200px`
    - Summary cards: 2-column grid
    - _Requirements: 14.1_

- [x] 15. Update remaining visual elements (badges, charts, breadcrumbs, progress bars, skeleton loading, totals row)
  - Update badge pill colors to light-theme tints (success, warning, info, danger)
  - Update chart container to `var(--color-surface)` with shadow, bar color `var(--color-primary)`
  - Update breadcrumb text colors to use tokens
  - Update progress bar track to `var(--color-border)`
  - Update totals row: `2px solid var(--color-border)` top border, `var(--color-primary-light)` background
  - Update skeleton loading gradient to light gray shimmer
  - _Requirements: 1.4_

- [x] 16. Ensure all component color references use design tokens
  - [x] 16.1 Write property test for token usage across all component selectors (Property 2)
    - **Property 2: All component color references use design tokens**
    - Parse all CSS rules in `app.css` (excluding `:root`, alert literals, badge literals) and verify color/background/border-color values reference `var(--...)` custom properties
    - **Validates: Requirements 1.1, 1.4**
  - [x] 16.2 Audit and fix any remaining hardcoded color values in `app.css`
    - Replace any leftover hex/rgba values in component selectors with appropriate design token references
    - _Requirements: 1.1, 1.4_

- [x] 17. Final checkpoint — Full visual verification
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- All existing CSS class names are preserved — only values change
- No backend, routing, or functional logic changes required
- Auth pages use inline `<style>` blocks, so each must be updated independently
- Property tests validate universal correctness properties from the design document
