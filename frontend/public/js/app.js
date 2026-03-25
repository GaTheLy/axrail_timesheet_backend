/**
 * TimeFlow — Shared JavaScript utilities
 *
 * Provides: CSRF token auto-attachment, loading overlay management,
 * toast notifications, and sidebar hamburger toggle for mobile.
 */
(function () {
    'use strict';

    // ── CSRF Token ──────────────────────────────────────────────────────

    var csrfMeta = document.querySelector('meta[name="csrf-token"]');
    var csrfToken = csrfMeta ? csrfMeta.content : '';

    /**
     * Patch the native fetch so every non-GET request automatically
     * includes the X-CSRF-TOKEN header.
     */
    var _originalFetch = window.fetch;
    window.fetch = function (url, options) {
        options = options || {};
        var method = (options.method || 'GET').toUpperCase();

        if (method !== 'GET' && method !== 'HEAD') {
            options.headers = options.headers || {};

            // Support both plain objects and Headers instances
            if (options.headers instanceof Headers) {
                if (!options.headers.has('X-CSRF-TOKEN')) {
                    options.headers.set('X-CSRF-TOKEN', csrfToken);
                }
            } else {
                if (!options.headers['X-CSRF-TOKEN']) {
                    options.headers['X-CSRF-TOKEN'] = csrfToken;
                }
            }
        }

        return _originalFetch.call(window, url, options);
    };

    /**
     * Patch XMLHttpRequest.prototype.send so every non-GET XHR
     * automatically includes the X-CSRF-TOKEN header.
     */
    var _originalXHROpen = XMLHttpRequest.prototype.open;
    var _originalXHRSend = XMLHttpRequest.prototype.send;

    XMLHttpRequest.prototype.open = function (method) {
        this._method = (method || 'GET').toUpperCase();
        return _originalXHROpen.apply(this, arguments);
    };

    XMLHttpRequest.prototype.send = function () {
        if (this._method && this._method !== 'GET' && this._method !== 'HEAD') {
            try {
                this.setRequestHeader('X-CSRF-TOKEN', csrfToken);
            } catch (e) {
                // Header may already be set or request not yet opened — ignore
            }
        }
        return _originalXHRSend.apply(this, arguments);
    };

    // ── Loading Overlay ─────────────────────────────────────────────────

    function showLoading() {
        var el = document.getElementById('loading-overlay');
        if (el) el.style.display = 'flex';
    }

    function hideLoading() {
        var el = document.getElementById('loading-overlay');
        if (el) el.style.display = 'none';
    }

    // Expose globally so page-specific scripts can use them
    window.showLoading = showLoading;
    window.hideLoading = hideLoading;

    // ── Toast Notifications ─────────────────────────────────────────────

    /**
     * Show a temporary toast notification.
     *
     * @param {string} message  Text to display
     * @param {string} type     'success' | 'error' | 'info'  (default: 'info')
     */
    function showNotification(message, type) {
        type = type || 'info';

        // Create container on first use
        var container = document.getElementById('toast-container');
        if (!container) {
            container = document.createElement('div');
            container.id = 'toast-container';
            container.style.cssText =
                'position:fixed;top:1rem;right:1rem;z-index:10000;' +
                'display:flex;flex-direction:column;gap:0.5rem;max-width:360px;';
            document.body.appendChild(container);
        }

        var toast = document.createElement('div');
        toast.className = 'alert alert-' + type;
        toast.style.cssText =
            'animation:toast-in 0.3s ease;cursor:pointer;box-shadow:0 4px 12px rgba(0,0,0,0.3);';
        toast.textContent = message;
        toast.setAttribute('role', 'alert');

        // Dismiss on click
        toast.addEventListener('click', function () {
            removeToast(toast);
        });

        container.appendChild(toast);

        // Auto-dismiss after 4 seconds
        setTimeout(function () {
            removeToast(toast);
        }, 4000);
    }

    function removeToast(toast) {
        if (!toast || !toast.parentNode) return;
        toast.style.opacity = '0';
        toast.style.transform = 'translateX(20px)';
        toast.style.transition = 'opacity 0.3s, transform 0.3s';
        setTimeout(function () {
            if (toast.parentNode) toast.parentNode.removeChild(toast);
        }, 300);
    }

    // Inject toast keyframe animation once
    var style = document.createElement('style');
    style.textContent =
        '@keyframes toast-in{from{opacity:0;transform:translateX(20px)}to{opacity:1;transform:translateX(0)}}';
    document.head.appendChild(style);

    window.showNotification = showNotification;

    // ── Sidebar Hamburger Toggle ────────────────────────────────────────

    document.addEventListener('DOMContentLoaded', function () {
        var sidebar = document.getElementById('sidebar');
        var toggle  = document.getElementById('sidebar-toggle');

        if (!sidebar || !toggle) return;

        toggle.addEventListener('click', function () {
            var isOpen = sidebar.classList.toggle('open');
            toggle.classList.toggle('active', isOpen);
            toggle.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
        });

        // Close sidebar when clicking outside on mobile
        document.addEventListener('click', function (e) {
            if (!sidebar.classList.contains('open')) return;
            // Ignore clicks inside the sidebar or on the toggle button
            if (sidebar.contains(e.target) || toggle.contains(e.target)) return;
            sidebar.classList.remove('open');
            toggle.classList.remove('active');
            toggle.setAttribute('aria-expanded', 'false');
        });
    });

})();
