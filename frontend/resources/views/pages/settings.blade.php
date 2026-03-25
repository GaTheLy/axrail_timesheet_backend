@extends('layouts.app')

@section('title', 'Settings — TimeFlow')

@section('content')
    {{-- Page header --}}
    <div class="page-header">
        <div>
            <h1 class="page-title">Settings</h1>
            <p style="color: #94a3b8; font-size: 0.875rem; margin-top: 0.25rem;">
                Manage your profile and security preferences
            </p>
        </div>
    </div>

    {{-- Error state from controller --}}
    @if(!empty($error))
        <div class="alert alert-error">{{ $error }}</div>
    @endif

    {{-- Notification area for AJAX responses --}}
    <div id="settings-notification" class="alert" style="display: none;" role="alert" aria-live="polite"></div>

    {{-- ================================================================
         Profile Section
         ================================================================ --}}
    <div style="background: #1e293b; border: 1px solid #334155; border-radius: 12px; padding: 1.5rem; margin-bottom: 1.5rem;">
        <h2 style="font-size: 1.1rem; font-weight: 600; color: #f1f5f9; margin-bottom: 1.25rem;">Profile Settings</h2>

        {{-- Avatar --}}
        <div style="display: flex; align-items: center; gap: 1.25rem; margin-bottom: 1.5rem;">
            <div id="avatar-container" style="position: relative;">
                @if(!empty($profile['avatarUrl']))
                    <img
                        id="avatar-img"
                        src="{{ $profile['avatarUrl'] }}"
                        alt="Profile avatar"
                        style="width: 72px; height: 72px; border-radius: 50%; object-fit: cover; border: 2px solid #334155;"
                    >
                @else
                    <div
                        id="avatar-placeholder"
                        class="user-avatar"
                        style="width: 72px; height: 72px; font-size: 1.5rem;"
                        aria-label="Profile avatar placeholder"
                    >
                        {{ strtoupper(substr($profile['fullName'] ?? 'U', 0, 1)) }}
                    </div>
                @endif
            </div>
            <div>
                <label for="avatar-upload" class="btn btn-secondary btn-sm" style="cursor: pointer;">
                    Upload Photo
                </label>
                <input
                    type="file"
                    id="avatar-upload"
                    accept="image/jpeg,image/png,image/jpg,image/gif"
                    style="display: none;"
                    aria-label="Upload avatar image"
                >
                <p style="font-size: 0.75rem; color: #64748b; margin-top: 0.375rem;">JPG, PNG or GIF. Max 2MB.</p>
            </div>
        </div>

        {{-- Profile fields --}}
        <div class="form-group">
            <label for="profile-name">Full Name</label>
            <input
                type="text"
                id="profile-name"
                value="{{ $profile['fullName'] ?? '' }}"
                readonly
                aria-label="Full name"
            >
        </div>

        <div class="form-group">
            <label for="profile-email">Email Address</label>
            <input
                type="email"
                id="profile-email"
                value="{{ $profile['email'] ?? '' }}"
                readonly
                style="opacity: 0.6; cursor: not-allowed;"
                aria-label="Email address (read-only)"
            >
            <p style="font-size: 0.75rem; color: #64748b; margin-top: 0.25rem;">Email changes require admin action.</p>
        </div>

        <div class="form-group">
            <label for="profile-department">Department</label>
            <select id="profile-department" aria-label="Department">
                <option value="">Select department</option>
                @foreach($departments as $dept)
                    <option
                        value="{{ $dept['departmentId'] }}"
                        {{ ($profile['departmentId'] ?? '') === $dept['departmentId'] ? 'selected' : '' }}
                    >
                        {{ $dept['name'] }}
                    </option>
                @endforeach
            </select>
        </div>
    </div>

    {{-- ================================================================
         Security Section
         ================================================================ --}}
    <div style="background: #1e293b; border: 1px solid #334155; border-radius: 12px; padding: 1.5rem;">
        <h2 style="font-size: 1.1rem; font-weight: 600; color: #f1f5f9; margin-bottom: 1.25rem;">Security</h2>

        <form id="password-form" novalidate>
            <div class="form-group">
                <label for="current-password">Current Password</label>
                <input
                    type="password"
                    id="current-password"
                    placeholder="Enter current password"
                    autocomplete="current-password"
                    aria-label="Current password"
                >
            </div>

            <div class="form-group">
                <label for="new-password">New Password</label>
                <input
                    type="password"
                    id="new-password"
                    placeholder="Enter new password"
                    autocomplete="new-password"
                    aria-label="New password"
                >
                <div id="password-policy" style="margin-top: 0.5rem;">
                    <p style="font-size: 0.75rem; color: #64748b; margin-bottom: 0.25rem;">Password must contain:</p>
                    <ul style="list-style: none; padding: 0; margin: 0; font-size: 0.75rem;">
                        <li id="policy-length" style="color: #64748b;">&#x2022; At least 8 characters</li>
                        <li id="policy-upper" style="color: #64748b;">&#x2022; One uppercase letter</li>
                        <li id="policy-lower" style="color: #64748b;">&#x2022; One lowercase letter</li>
                        <li id="policy-digit" style="color: #64748b;">&#x2022; One digit</li>
                        <li id="policy-symbol" style="color: #64748b;">&#x2022; One symbol</li>
                    </ul>
                </div>
            </div>

            <div class="form-group">
                <label for="confirm-password">Confirm Password</label>
                <input
                    type="password"
                    id="confirm-password"
                    placeholder="Confirm new password"
                    autocomplete="new-password"
                    aria-label="Confirm new password"
                >
                <p id="password-match-error" class="form-error" style="display: none;">Passwords do not match.</p>
            </div>

            <button type="submit" id="save-password-btn" class="btn btn-primary" disabled>
                Save Changes
            </button>
        </form>
    </div>
@endsection

@push('scripts')
<script>
(function () {
    var csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || '';

    // ====================================================================
    // Avatar Upload
    // ====================================================================
    var avatarInput = document.getElementById('avatar-upload');
    if (avatarInput) {
        avatarInput.addEventListener('change', function () {
            var file = this.files[0];
            if (!file) return;

            // Validate file size (2MB max)
            if (file.size > 2 * 1024 * 1024) {
                showNotification('File size must be under 2MB.', 'error');
                this.value = '';
                return;
            }

            var formData = new FormData();
            formData.append('avatar', file);

            var overlay = document.getElementById('loading-overlay');
            if (overlay) overlay.style.display = 'flex';

            fetch('/settings/avatar', {
                method: 'POST',
                headers: {
                    'X-CSRF-TOKEN': csrfToken,
                    'X-Requested-With': 'XMLHttpRequest'
                },
                body: formData
            })
            .then(function (res) { return res.json(); })
            .then(function (data) {
                if (overlay) overlay.style.display = 'none';

                if (data.success) {
                    showNotification(data.message || 'Avatar uploaded successfully.', 'success');
                    updateAvatarDisplay(data.avatarUrl);
                } else {
                    showNotification(data.message || 'Failed to upload avatar.', 'error');
                }
            })
            .catch(function () {
                if (overlay) overlay.style.display = 'none';
                showNotification('Network error. Please try again.', 'error');
            });

            this.value = '';
        });
    }

    function updateAvatarDisplay(url) {
        var container = document.getElementById('avatar-container');
        if (!container) return;

        var existingImg = document.getElementById('avatar-img');
        var placeholder = document.getElementById('avatar-placeholder');

        if (existingImg) {
            existingImg.src = url;
        } else {
            if (placeholder) placeholder.style.display = 'none';
            var img = document.createElement('img');
            img.id = 'avatar-img';
            img.src = url;
            img.alt = 'Profile avatar';
            img.style.cssText = 'width: 72px; height: 72px; border-radius: 50%; object-fit: cover; border: 2px solid #334155;';
            container.insertBefore(img, container.firstChild);
        }
    }

    // ====================================================================
    // Password Validation & Change
    // ====================================================================
    var currentPwInput = document.getElementById('current-password');
    var newPwInput = document.getElementById('new-password');
    var confirmPwInput = document.getElementById('confirm-password');
    var saveBtn = document.getElementById('save-password-btn');
    var matchError = document.getElementById('password-match-error');
    var passwordForm = document.getElementById('password-form');

    // Policy indicator elements
    var policyLength = document.getElementById('policy-length');
    var policyUpper = document.getElementById('policy-upper');
    var policyLower = document.getElementById('policy-lower');
    var policyDigit = document.getElementById('policy-digit');
    var policySymbol = document.getElementById('policy-symbol');

    var passColor = '#22c55e';
    var failColor = '#64748b';

    function validatePasswordPolicy(pw) {
        var checks = {
            length: pw.length >= 8,
            upper: /[A-Z]/.test(pw),
            lower: /[a-z]/.test(pw),
            digit: /[0-9]/.test(pw),
            symbol: /[^A-Za-z0-9]/.test(pw)
        };

        if (policyLength) policyLength.style.color = checks.length ? passColor : failColor;
        if (policyUpper) policyUpper.style.color = checks.upper ? passColor : failColor;
        if (policyLower) policyLower.style.color = checks.lower ? passColor : failColor;
        if (policyDigit) policyDigit.style.color = checks.digit ? passColor : failColor;
        if (policySymbol) policySymbol.style.color = checks.symbol ? passColor : failColor;

        return checks.length && checks.upper && checks.lower && checks.digit && checks.symbol;
    }

    function validateForm() {
        var currentPw = currentPwInput ? currentPwInput.value : '';
        var newPw = newPwInput ? newPwInput.value : '';
        var confirmPw = confirmPwInput ? confirmPwInput.value : '';

        var policyMet = validatePasswordPolicy(newPw);
        var passwordsMatch = newPw.length > 0 && newPw === confirmPw;
        var allFilled = currentPw.length > 0 && newPw.length > 0 && confirmPw.length > 0;

        // Show match error only when confirm field has content
        if (confirmPw.length > 0 && !passwordsMatch) {
            if (matchError) matchError.style.display = '';
        } else {
            if (matchError) matchError.style.display = 'none';
        }

        if (saveBtn) {
            saveBtn.disabled = !(allFilled && policyMet && passwordsMatch);
        }
    }

    if (currentPwInput) currentPwInput.addEventListener('input', validateForm);
    if (newPwInput) newPwInput.addEventListener('input', validateForm);
    if (confirmPwInput) confirmPwInput.addEventListener('input', validateForm);

    // Form submission
    if (passwordForm) {
        passwordForm.addEventListener('submit', function (e) {
            e.preventDefault();

            var currentPw = currentPwInput ? currentPwInput.value : '';
            var newPw = newPwInput ? newPwInput.value : '';
            var confirmPw = confirmPwInput ? confirmPwInput.value : '';

            if (newPw !== confirmPw) {
                showNotification('Passwords do not match.', 'error');
                return;
            }

            if (!validatePasswordPolicy(newPw)) {
                showNotification('Password does not meet the required policy.', 'error');
                return;
            }

            var overlay = document.getElementById('loading-overlay');
            if (overlay) overlay.style.display = 'flex';
            if (saveBtn) saveBtn.disabled = true;

            fetch('/settings/password', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Accept': 'application/json',
                    'X-CSRF-TOKEN': csrfToken,
                    'X-Requested-With': 'XMLHttpRequest'
                },
                body: JSON.stringify({
                    current_password: currentPw,
                    new_password: newPw,
                    confirm_password: confirmPw
                })
            })
            .then(function (res) { return res.json(); })
            .then(function (data) {
                if (overlay) overlay.style.display = 'none';

                if (data.success) {
                    showNotification(data.message || 'Password changed successfully.', 'success');
                    // Clear form fields
                    if (currentPwInput) currentPwInput.value = '';
                    if (newPwInput) newPwInput.value = '';
                    if (confirmPwInput) confirmPwInput.value = '';
                    validateForm();
                } else {
                    showNotification(data.message || 'Failed to change password.', 'error');
                }

                if (saveBtn) validateForm();
            })
            .catch(function () {
                if (overlay) overlay.style.display = 'none';
                showNotification('Network error. Please try again.', 'error');
                if (saveBtn) validateForm();
            });
        });
    }

    // ====================================================================
    // Notification Helper
    // ====================================================================
    function showNotification(message, type) {
        var el = document.getElementById('settings-notification');
        if (!el) return;

        el.textContent = message;
        el.className = 'alert alert-' + (type === 'success' ? 'success' : 'error');
        el.style.display = '';

        // Auto-hide after 5 seconds
        clearTimeout(el._hideTimer);
        el._hideTimer = setTimeout(function () {
            el.style.display = 'none';
        }, 5000);

        // Scroll to notification
        el.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
})();
</script>
@endpush
