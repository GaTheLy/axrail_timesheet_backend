@php
    $user = session('user', []);
    $fullName = $user['fullName'] ?? 'User';
    $userType = $user['userType'] ?? 'user';
    $role = $user['role'] ?? 'Employee';
@endphp

<aside id="sidebar" class="sidebar" role="navigation" aria-label="Main navigation">
    {{-- Mobile hamburger toggle --}}
    <button id="sidebar-toggle" class="sidebar-toggle" aria-label="Toggle navigation" aria-expanded="false">
        <span class="hamburger-line"></span>
        <span class="hamburger-line"></span>
        <span class="hamburger-line"></span>
    </button>

    {{-- Logo --}}
    <div class="sidebar-brand">
        <span class="logo-icon" aria-hidden="true">⏱</span>
        <span class="logo-text">TimeFlow</span>
    </div>

    {{-- Navigation links (role-based rendering) --}}
    <nav class="sidebar-nav">
        <ul>
            {{-- Employee nav items: visible to all authenticated roles --}}
            <li>
                <a href="/dashboard" class="{{ request()->is('dashboard*') ? 'active' : '' }}" aria-current="{{ request()->is('dashboard*') ? 'page' : 'false' }}">
                    <svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                        <rect x="3" y="3" width="7" height="7"></rect>
                        <rect x="14" y="3" width="7" height="7"></rect>
                        <rect x="3" y="14" width="7" height="7"></rect>
                        <rect x="14" y="14" width="7" height="7"></rect>
                    </svg>
                    Dashboard
                </a>
            </li>
            <li>
                <a href="/timesheet" class="{{ request()->is('timesheet*') ? 'active' : '' }}" aria-current="{{ request()->is('timesheet*') ? 'page' : 'false' }}">
                    <svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                        <circle cx="12" cy="12" r="10"></circle>
                        <polyline points="12 6 12 12 16 14"></polyline>
                    </svg>
                    Timesheet
                </a>
            </li>
            <li>
                <a href="/settings" class="{{ request()->is('settings*') ? 'active' : '' }}" aria-current="{{ request()->is('settings*') ? 'page' : 'false' }}">
                    <svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                        <circle cx="12" cy="12" r="3"></circle>
                        <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"></path>
                    </svg>
                    Settings
                </a>
            </li>

            {{-- Tech_Lead / Project_Manager nav items --}}
            @if(in_array($role, ['Tech_Lead', 'Project_Manager']) || in_array($userType, ['admin', 'superadmin']))
                {{-- TODO: Add Team Timesheets, Approvals nav items for Tech_Lead_PM role --}}
            @endif

            {{-- Admin nav items --}}
            @if(in_array($userType, ['admin', 'superadmin']))
                {{-- TODO: Add User Management, Project Management, Reports nav items for Admin role --}}
            @endif

            {{-- Super Admin nav items --}}
            @if($userType === 'superadmin')
                {{-- TODO: Add Admin Management, System Settings nav items for Super_Admin role --}}
            @endif
        </ul>
    </nav>

    {{-- User info and logout --}}
    <div class="sidebar-footer">
        <div class="sidebar-user">
            <div class="user-avatar" aria-hidden="true">{{ strtoupper(substr($fullName, 0, 1)) }}</div>
            <div class="user-info">
                <span class="user-name">{{ $fullName }}</span>
                <span class="user-role">{{ str_replace('_', ' ', $role) }}</span>
            </div>
        </div>
        <form method="POST" action="/logout" class="sidebar-logout">
            @csrf
            <button type="submit" aria-label="Sign out">
                <svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                    <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"></path>
                    <polyline points="16 17 21 12 16 7"></polyline>
                    <line x1="21" y1="12" x2="9" y2="12"></line>
                </svg>
            </button>
        </form>
    </div>
</aside>
