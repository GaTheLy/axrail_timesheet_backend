/**
 * TimeFlow — Timesheet page AJAX interactions
 *
 * Handles: modal open/close, add/edit/delete entries via AJAX,
 * client-side search & filter, charged-hours validation,
 * and save-button enable/disable logic.
 */
(function () {
    'use strict';

    // ── Helpers ──────────────────────────────────────────────────────────

    function csrfToken() {
        var meta = document.querySelector('meta[name="csrf-token"]');
        return meta ? meta.content : '';
    }

    function showLoading() {
        var el = document.getElementById('loading-overlay');
        if (el) el.style.display = 'flex';
    }

    function hideLoading() {
        var el = document.getElementById('loading-overlay');
        if (el) el.style.display = 'none';
    }

    function showToast(message, type) {
        var toast = document.createElement('div');
        toast.className = 'toast toast-' + (type || 'info');
        toast.textContent = message;
        toast.style.cssText = 'position:fixed;top:20px;right:20px;padding:12px 24px;border-radius:8px;color:#fff;font-weight:500;z-index:10000;animation:fadeIn 0.3s ease;';
        toast.style.backgroundColor = type === 'success' ? '#10b981' : type === 'error' ? '#ef4444' : '#3b82f6';
        document.body.appendChild(toast);
        setTimeout(function() {
            toast.style.opacity = '0';
            toast.style.transition = 'opacity 0.3s ease';
            setTimeout(function() { toast.remove(); }, 300);
        }, 2500);
    }

    // ── Modal references ────────────────────────────────────────────────

    var overlay       = document.getElementById('entry-modal-overlay');
    var modalTitle    = document.getElementById('entry-modal-title');
    var entryId       = document.getElementById('entry-id');
    var projectCode   = document.getElementById('entry-project-code');
    var description   = document.getElementById('entry-description');
    var dateInput     = document.getElementById('entry-date');
    var hoursInput    = document.getElementById('entry-hours');
    var saveBtn       = document.getElementById('btn-save-entry');
    var cancelBtn     = document.getElementById('btn-cancel-entry');
    var closeBtn      = document.getElementById('btn-close-entry-modal');
    var modalError    = document.getElementById('entry-modal-error');
    var newEntryBtn   = document.getElementById('btn-new-entry');
    var searchInput   = document.getElementById('search-input');
    var projectFilter = document.getElementById('project-filter');

    // ── Date constraints ───────────────────────────────────────────────

    /**
     * Get the Monday of the current week (start of week).
     * @returns {Date}
     */
    function getWeekStart() {
        var now = new Date();
        var day = now.getDay(); // 0 = Sunday, 1 = Monday, ...
        var diff = day === 0 ? -6 : 1 - day; // Adjust to get Monday
        var monday = new Date(now);
        monday.setDate(now.getDate() + diff);
        monday.setHours(0, 0, 0, 0);
        return monday;
    }

    /**
     * Format a Date object as YYYY-MM-DD for input[type=date].
     * @param {Date} date
     * @returns {string}
     */
    function formatDateForInput(date) {
        var year = date.getFullYear();
        var month = String(date.getMonth() + 1).padStart(2, '0');
        var day = String(date.getDate()).padStart(2, '0');
        return year + '-' + month + '-' + day;
    }

    /**
     * Set date input constraints:
     * - min: Monday of current week
     * - max: Today (no future dates)
     */
    function setDateConstraints() {
        if (!dateInput) return;
        
        var weekStart = getWeekStart();
        var today = new Date();
        today.setHours(0, 0, 0, 0);
        
        dateInput.min = formatDateForInput(weekStart);
        dateInput.max = formatDateForInput(today);
    }

    // ── Modal open / close ──────────────────────────────────────────────

    function openModal() {
        if (overlay) overlay.classList.add('active');
    }

    function closeModal() {
        if (overlay) overlay.classList.remove('active');
        resetModal();
    }

    function resetModal() {
        if (entryId)      entryId.value = '';
        if (projectCode)  projectCode.value = '';
        if (description)  description.value = '';
        if (dateInput)    dateInput.value = '';
        if (hoursInput)   hoursInput.value = '';
        if (modalError)   { modalError.style.display = 'none'; modalError.textContent = ''; }
        if (modalTitle)   modalTitle.textContent = 'Add New Entry';
        toggleSaveButton();
    }

    function showModalError(msg) {
        if (!modalError) return;
        modalError.textContent = msg;
        modalError.style.display = 'block';
    }

    function hideModalError() {
        if (!modalError) return;
        modalError.textContent = '';
        modalError.style.display = 'none';
    }

    // ── Projects dropdown population ────────────────────────────────────

    var projectsLoaded = false;

    function loadProjects(callback) {
        if (projectsLoaded) { if (callback) callback(); return; }

        fetch('/timesheet/projects', {
            method: 'GET',
            headers: { 'Accept': 'application/json', 'X-CSRF-TOKEN': csrfToken() }
        })
        .then(function (res) { return res.json(); })
        .then(function (data) {
            if (data.success && Array.isArray(data.data) && projectCode) {
                // Keep the placeholder option, remove the rest
                while (projectCode.options.length > 1) {
                    projectCode.remove(1);
                }
                data.data.forEach(function (p) {
                    var opt = document.createElement('option');
                    opt.value = p.projectCode;
                    opt.textContent = p.projectCode + ' — ' + p.projectName;
                    projectCode.appendChild(opt);
                });
                projectsLoaded = true;
            }
            if (callback) callback();
        })
        .catch(function () {
            if (callback) callback();
        });
    }

    // ── Validation ──────────────────────────────────────────────────────

    /**
     * Validate charged hours: non-negative, max 2 decimal places.
     * Returns true if valid, false otherwise.
     */
    function validateHours(value) {
        if (value === '' || value === null || value === undefined) return false;
        var num = parseFloat(value);
        if (isNaN(num) || num < 0) return false;
        // Max 2 decimal places: multiply by 100, check it's an integer
        if (Math.round(num * 100) !== num * 100) return false;
        return true;
    }

    /**
     * Enable Save button only when all required fields are filled
     * and hours pass validation.
     */
    function toggleSaveButton() {
        if (!saveBtn) return;
        var hasProject = projectCode && projectCode.value !== '';
        var hasDate    = dateInput && dateInput.value !== '';
        var hasHours   = hoursInput && hoursInput.value !== '' && validateHours(hoursInput.value);
        saveBtn.disabled = !(hasProject && hasDate && hasHours);
    }

    // Attach change/input listeners for live validation
    if (projectCode) projectCode.addEventListener('change', toggleSaveButton);
    if (dateInput)   dateInput.addEventListener('input', toggleSaveButton);
    if (hoursInput)  hoursInput.addEventListener('input', toggleSaveButton);

    // ── Open modal for Add ──────────────────────────────────────────────

    if (newEntryBtn) {
        newEntryBtn.addEventListener('click', function () {
            loadProjects(function () {
                resetModal();
                setDateConstraints(); // Apply date restrictions
                originalDate = null; // Clear original date for new entries
                if (modalTitle) modalTitle.textContent = 'Add New Entry';
                openModal();
            });
        });
    }

    // ── Open modal for Edit ─────────────────────────────────────────────

    var originalDate = null; // Store original date for edit operations

    document.addEventListener('click', function (e) {
        var btn = e.target.closest('.btn-edit-entry');
        if (!btn) return;

        loadProjects(function () {
            resetModal();
            setDateConstraints(); // Apply date restrictions
            if (modalTitle) modalTitle.textContent = 'Edit Entry';
            if (entryId)     entryId.value     = btn.getAttribute('data-entry-id') || '';
            if (projectCode) projectCode.value = btn.getAttribute('data-project-code') || '';
            if (description) description.value = btn.getAttribute('data-description') || '';
            if (dateInput)   dateInput.value   = btn.getAttribute('data-date') || '';
            if (hoursInput)  hoursInput.value  = btn.getAttribute('data-hours') || '';
            originalDate = btn.getAttribute('data-date') || null; // Store original date
            toggleSaveButton();
            openModal();
        });
    });

    // ── Close modal ─────────────────────────────────────────────────────

    if (cancelBtn) cancelBtn.addEventListener('click', closeModal);
    if (closeBtn)  closeBtn.addEventListener('click', closeModal);

    // Close on overlay click (outside modal box)
    if (overlay) {
        overlay.addEventListener('click', function (e) {
            if (e.target === overlay) closeModal();
        });
    }

    // Close on Escape key
    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape' && overlay && overlay.classList.contains('active')) {
            closeModal();
        }
    });

    // ── Save entry (Add or Edit) ────────────────────────────────────────

    if (saveBtn) {
        saveBtn.addEventListener('click', function () {
            hideModalError();

            // Client-side hours validation
            if (!validateHours(hoursInput.value)) {
                showModalError('Charged hours must be a non-negative number with at most 2 decimal places.');
                return;
            }

            var id = entryId ? entryId.value : '';
            var isEdit = id !== '';
            var url = isEdit ? '/timesheet/entry/' + id : '/timesheet/entry';
            var method = isEdit ? 'PUT' : 'POST';

            var body = {
                projectCode:  projectCode ? projectCode.value : '',
                description:  description ? description.value : '',
                date:         dateInput ? dateInput.value : '',
                chargedHours: hoursInput ? parseFloat(hoursInput.value) : 0
            };

            // Include original date for edit operations (to zero out old day if date changed)
            if (isEdit && originalDate) {
                body.originalDate = originalDate;
            }

            showLoading();
            saveBtn.disabled = true;

            fetch(url, {
                method: method,
                headers: {
                    'Content-Type': 'application/json',
                    'Accept': 'application/json',
                    'X-CSRF-TOKEN': csrfToken()
                },
                body: JSON.stringify(body)
            })
            .then(function (res) { return res.json().then(function (data) { return { status: res.status, data: data }; }); })
            .then(function (result) {
                hideLoading();
                if (result.data.success) {
                    closeModal();
                    showToast(isEdit ? 'Entry updated successfully!' : 'Entry added successfully!', 'success');
                    setTimeout(function() {
                        window.location.reload();
                    }, 1000);
                } else {
                    showModalError(result.data.error || 'An unexpected error occurred.');
                    toggleSaveButton();
                }
            })
            .catch(function () {
                hideLoading();
                showModalError('Network error. Please try again.');
                toggleSaveButton();
            });
        });
    }

    // ── Delete entry ────────────────────────────────────────────────────

    document.addEventListener('click', function (e) {
        var btn = e.target.closest('.btn-delete-entry');
        if (!btn) return;

        var id   = btn.getAttribute('data-entry-id') || '';
        var date = btn.getAttribute('data-date') || '';
        var code = btn.getAttribute('data-project-code') || '';

        if (!confirm('Are you sure you want to delete the entry for ' + code + ' on ' + date + '?')) {
            return;
        }

        showLoading();

        fetch('/timesheet/entry/' + id, {
            method: 'DELETE',
            headers: {
                'Content-Type': 'application/json',
                'Accept': 'application/json',
                'X-CSRF-TOKEN': csrfToken()
            },
            body: JSON.stringify({ date: date })
        })
        .then(function (res) { return res.json().then(function (data) { return { status: res.status, data: data }; }); })
        .then(function (result) {
            hideLoading();
            if (result.data.success) {
                showToast('Entry deleted successfully!', 'success');
                setTimeout(function() {
                    window.location.reload();
                }, 1000);
            } else {
                alert(result.data.error || 'Failed to delete entry.');
            }
        })
        .catch(function () {
            hideLoading();
            alert('Network error. Please try again.');
        });
    });

    // ── Client-side search & filter ─────────────────────────────────────

    function filterEntries() {
        var searchTerm   = searchInput ? searchInput.value.toLowerCase().trim() : '';
        var projectValue = projectFilter ? projectFilter.value : '';
        var rows = document.querySelectorAll('.entry-row');

        rows.forEach(function (row) {
            var rowProject     = (row.getAttribute('data-project-code') || '').toLowerCase();
            var rowDescription = (row.getAttribute('data-description') || '').toLowerCase();

            var matchesSearch = searchTerm === ''
                || rowProject.indexOf(searchTerm) !== -1
                || rowDescription.indexOf(searchTerm) !== -1;

            var matchesProject = projectValue === ''
                || (row.getAttribute('data-project-code') || '') === projectValue;

            row.style.display = (matchesSearch && matchesProject) ? '' : 'none';
        });
    }

    if (searchInput)   searchInput.addEventListener('input', filterEntries);
    if (projectFilter) projectFilter.addEventListener('change', filterEntries);

})();
