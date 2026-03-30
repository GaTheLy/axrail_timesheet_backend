<header class="header-bar" role="banner" aria-label="Top navigation bar">
    <div class="header-bar-left">
        <!-- Placeholder for breadcrumbs or page context -->
    </div>
    <div class="header-bar-right">
        <div class="header-search">
            <svg class="header-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                 stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                <circle cx="11" cy="11" r="8"></circle>
                <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
            </svg>
        </div>
        <button class="header-notification" aria-label="Notifications">
            <svg class="header-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                 stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"></path>
                <path d="M13.73 21a2 2 0 0 1-3.46 0"></path>
            </svg>
        </button>
        <div class="header-user">
            <div class="header-user-avatar" aria-hidden="true">
                {{ strtoupper(substr(session('user.fullName', 'U'), 0, 1)) }}
            </div>
            <span class="header-user-name">{{ session('user.fullName', 'User') }}</span>
        </div>
    </div>
</header>
