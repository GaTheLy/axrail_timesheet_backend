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

            {{-- Reports menu: visible only to Tech_Lead/Project_Manager with userType user --}}
            @if(in_array($role, ['Tech_Lead', 'Project_Manager']) && $userType === 'user')
                <li class="nav-group {{ request()->is('reports*') ? 'active open' : '' }}">
                    <button class="nav-group-toggle" aria-expanded="{{ request()->is('reports*') ? 'true' : 'false' }}" onclick="this.setAttribute('aria-expanded', this.getAttribute('aria-expanded') === 'true' ? 'false' : 'true'); this.closest('.nav-group').classList.toggle('open');">
                        <svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                            <polyline points="14 2 14 8 20 8"></polyline>
                            <line x1="16" y1="13" x2="8" y2="13"></line>
                            <line x1="16" y1="17" x2="8" y2="17"></line>
                            <polyline points="10 9 9 9 8 9"></polyline>
                        </svg>
                        <span>Reports</span>
                        <svg class="nav-group-chevron" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                            <polyline points="6 9 12 15 18 9"></polyline>
                        </svg>
                    </button>
                    <ul class="nav-group-items">
                        <li>
                            <a href="/reports/project-summary" class="{{ request()->is('reports/project-summary') ? 'active' : '' }}" aria-current="{{ request()->is('reports/project-summary') ? 'page' : 'false' }}">
                                Project Summary
                            </a>
                        </li>
                        <li>
                            <a href="/reports/submission-summary" class="{{ request()->is('reports/submission-summary') ? 'active' : '' }}" aria-current="{{ request()->is('reports/submission-summary') ? 'page' : 'false' }}">
                                Submission Summary
                            </a>
                        </li>
                    </ul>
                </li>
            @endif

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
                {{-- Master Data group --}}
                <li class="nav-group {{ request()->is('admin/*') ? 'active open' : '' }}">
                    <button class="nav-group-toggle" aria-expanded="{{ request()->is('admin/*') ? 'true' : 'false' }}" onclick="this.setAttribute('aria-expanded', this.getAttribute('aria-expanded') === 'true' ? 'false' : 'true'); this.closest('.nav-group').classList.toggle('open');">
                        <svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                            <path d="M20 7h-9"></path>
                            <path d="M14 17H5"></path>
                            <circle cx="17" cy="17" r="3"></circle>
                            <circle cx="7" cy="7" r="3"></circle>
                        </svg>
                        <span>Master Data</span>
                        <svg class="nav-group-chevron" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                            <polyline points="6 9 12 15 18 9"></polyline>
                        </svg>
                    </button>
                    <ul class="nav-group-items">
                        <li>
                            <a href="/admin/users" class="{{ request()->is('admin/users*') ? 'active' : '' }}" aria-current="{{ request()->is('admin/users*') ? 'page' : 'false' }}">
                                Users
                            </a>
                        </li>
                        <li>
                            <a href="/admin/departments" class="{{ request()->is('admin/departments*') ? 'active' : '' }}" aria-current="{{ request()->is('admin/departments*') ? 'page' : 'false' }}">
                                Departments
                            </a>
                        </li>
                        <li>
                            <a href="/admin/positions" class="{{ request()->is('admin/positions*') ? 'active' : '' }}" aria-current="{{ request()->is('admin/positions*') ? 'page' : 'false' }}">
                                Positions
                            </a>
                        </li>
                        <li>
                            <a href="/admin/projects" class="{{ request()->is('admin/projects*') ? 'active' : '' }}" aria-current="{{ request()->is('admin/projects*') ? 'page' : 'false' }}">
                                Projects
                            </a>
                        </li>
                    </ul>
                </li>

                {{-- Reports group for admin --}}
                <li class="nav-group {{ request()->is('reports*') ? 'active open' : '' }}">
                    <button class="nav-group-toggle" aria-expanded="{{ request()->is('reports*') ? 'true' : 'false' }}" onclick="this.setAttribute('aria-expanded', this.getAttribute('aria-expanded') === 'true' ? 'false' : 'true'); this.closest('.nav-group').classList.toggle('open');">
                        <svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                            <polyline points="14 2 14 8 20 8"></polyline>
                            <line x1="16" y1="13" x2="8" y2="13"></line>
                            <line x1="16" y1="17" x2="8" y2="17"></line>
                            <polyline points="10 9 9 9 8 9"></polyline>
                        </svg>
                        <span>Reports</span>
                        <svg class="nav-group-chevron" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                            <polyline points="6 9 12 15 18 9"></polyline>
                        </svg>
                    </button>
                    <ul class="nav-group-items">
                        <li>
                            <a href="/reports/project-summary" class="{{ request()->is('reports/project-summary') ? 'active' : '' }}" aria-current="{{ request()->is('reports/project-summary') ? 'page' : 'false' }}">
                                Project Summary
                            </a>
                        </li>
                        <li>
                            <a href="/reports/submission-summary" class="{{ request()->is('reports/submission-summary') ? 'active' : '' }}" aria-current="{{ request()->is('reports/submission-summary') ? 'page' : 'false' }}">
                                Submission Summary
                            </a>
                        </li>
                    </ul>
                </li>
            @endif

            {{-- Super Admin nav items --}}
            @if($userType === 'superadmin')
                <li>
                    <a href="/admin/approvals" class="{{ request()->is('admin/approvals*') ? 'active' : '' }}" aria-current="{{ request()->is('admin/approvals*') ? 'page' : 'false' }}">
                        <svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                            <path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"></path>
                            <rect x="8" y="2" width="8" height="4" rx="1" ry="1"></rect>
                            <path d="M9 14l2 2 4-4"></path>
                        </svg>
                        Approvals
                    </a>
                </li>
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
