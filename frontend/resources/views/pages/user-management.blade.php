@extends('layouts.app')

@section('title', 'User Management — TimeFlow')

@section('content')
    @php
        $userType = session('user.userType', 'user');
        
        // Build lookup maps for displaying names instead of IDs
        $departmentMap = collect($departments ?? [])->pluck('departmentName', 'departmentId')->toArray();
        $positionMap = collect($positions ?? [])->pluck('positionName', 'positionId')->toArray();
    @endphp

    <style>
        .toggle-switch {
            position: relative;
            display: inline-block;
            width: 36px;
            height: 20px;
            vertical-align: middle;
            margin-right: 0.5rem;
            cursor: pointer;
        }
        .toggle-switch input {
            opacity: 0;
            width: 0;
            height: 0;
        }
        .toggle-slider {
            position: absolute;
            top: 0; left: 0; right: 0; bottom: 0;
            background-color: #cbd5e1;
            border-radius: 20px;
            transition: background-color 0.25s;
        }
        .toggle-slider::before {
            content: "";
            position: absolute;
            height: 14px;
            width: 14px;
            left: 3px;
            bottom: 3px;
            background-color: #fff;
            border-radius: 50%;
            transition: transform 0.25s;
        }
        .toggle-switch input:checked + .toggle-slider {
            background-color: #22c55e;
        }
        .toggle-switch input:checked + .toggle-slider::before {
            transform: translateX(16px);
        }
        .toggle-switch input:disabled + .toggle-slider {
            opacity: 0.4;
            cursor: not-allowed;
        }
        .toggle-switch:has(input:disabled) {
            cursor: not-allowed;
        }
    </style>

    {{-- Breadcrumb --}}
    <nav class="breadcrumb" aria-label="Breadcrumb">
        <a href="/admin/users">Master Data</a>
        <span class="separator" aria-hidden="true">/</span>
        <span class="current">Users</span>
    </nav>

    {{-- Error state --}}
    @if(!empty($error))
        <div class="page-header">
            <h1 class="page-title">User Management</h1>
        </div>
        <div class="alert alert-error">
            {{ $error }}
        </div>
        <a href="/admin/users" class="btn btn-primary">Retry</a>
    @else
        {{-- Page header --}}
        <div class="page-header">
            <div>
                <h1 class="page-title">User Management</h1>
            </div>
            <div class="page-actions">
                <button type="button" class="btn btn-primary" id="btn-add-user">
                    + New User
                </button>
            </div>
        </div>

        {{-- Filter bar --}}
        <div class="filter-bar">
            <input type="text" id="search-input" class="search-input" placeholder="Search by name or email..." aria-label="Search by name or email">
            <select id="department-filter" aria-label="Filter by department">
                <option value="">All Departments</option>
            </select>
            <select id="position-filter" aria-label="Filter by position">
                <option value="">All Positions</option>
            </select>
            @if($userType === 'superadmin')
                <select id="user-approval-status-filter" aria-label="Filter by approval status">
                    <option value="">All</option>
                    <option value="Pending_Approval">Pending_Approval</option>
                    <option value="Approved">Approved</option>
                    <option value="Rejected">Rejected</option>
                </select>
            @endif
        </div>

        {{-- Users table --}}
        @if(count($users) > 0)
            <table class="data-table" id="users-table">
                <thead>
                    <tr>
                        <th>USER CODE</th>
                        <th>FULL NAME</th>
                        <th>EMAIL ADDRESS</th>
                        <th>ROLE</th>
                        <th>DEPARTMENT</th>
                        <th>POSITION</th>
                        <th>CREATED AT</th>
                        <th>STATUS</th>
                        @if($userType === 'superadmin')
                            <th>APPROVAL STATUS</th>
                        @endif
                        <th>ACTIONS</th>
                    </tr>
                </thead>
                <tbody>
                    @foreach($users as $user)
                        @php
                            $approvalStatus = $user['approval_status'] ?? 'Approved';
                            $rejectionReason = $user['rejectionReason'] ?? '';
                            $userId = $user['userId'] ?? '';
                        @endphp
                        <tr data-user-id="{{ $userId }}" data-user-status="{{ $user['status'] ?? '' }}" data-approval-status="{{ $approvalStatus }}" data-department="{{ $user['departmentId'] ?? '' }}" data-position="{{ $user['positionId'] ?? '' }}">
                            <td style="color: #3b82f6;">{{ $user['userCode'] ?? '—' }}</td>
                            <td><strong>{{ $user['fullName'] ?? '' }}</strong></td>
                            <td>{{ $user['email'] ?? '' }}</td>
                            <td>
                                <span class="badge" style="background-color: #e0e7ff; color: #3730a3; padding: 0.2rem 0.6rem; border-radius: 9999px; font-size: 0.75rem;">
                                    {{ ucfirst($user['userType'] ?? 'User') }}
                                </span>
                            </td>
                            <td>{{ $departmentMap[$user['departmentId'] ?? ''] ?? '—' }}</td>
                            <td>{{ $positionMap[$user['positionId'] ?? ''] ?? '—' }}</td>
                            <td>{{ isset($user['createdAt']) ? \Carbon\Carbon::parse($user['createdAt'])->format('M d, Y') : '—' }}</td>
                            <td>
                                @php
                                    $status = $user['status'] ?? 'unknown';
                                    $badgeClass = match($status) {
                                        'active' => 'badge-success',
                                        'rejected' => 'badge-danger',
                                        default => 'badge-warning',
                                    };
                                    $statusLabel = match($status) {
                                        'active' => 'Active',
                                        'inactive' => 'Inactive',
                                        default => ucfirst($status),
                                    };
                                @endphp
                                <span class="badge {{ $badgeClass }}">{{ $statusLabel }}</span>
                            </td>
                            @if($userType === 'superadmin')
                            <td>
                                @if($approvalStatus === 'Approved')
                                    <span class="badge" style="background-color: #dcfce7; color: #166534; padding: 0.2rem 0.6rem; border-radius: 9999px; font-size: 0.75rem;">Approved</span>
                                @elseif($approvalStatus === 'Pending_Approval')
                                    <span class="badge" style="background-color: #fef9c3; color: #854d0e; padding: 0.2rem 0.6rem; border-radius: 9999px; font-size: 0.75rem;">Pending_Approval</span>
                                @elseif($approvalStatus === 'Rejected')
                                    <span class="badge" style="background-color: #fee2e2; color: #991b1b; padding: 0.2rem 0.6rem; border-radius: 9999px; font-size: 0.75rem;" @if($rejectionReason) title="Reason: {{ $rejectionReason }}" @endif>Rejected</span>
                                @else
                                    <span class="badge" style="background-color: #f1f5f9; color: #64748b; padding: 0.2rem 0.6rem; border-radius: 9999px; font-size: 0.75rem;">{{ $approvalStatus }}</span>
                                @endif
                            </td>
                            @endif
                            <td style="white-space: nowrap;">
                                <div style="display: flex; align-items: center; gap: 0.375rem;">
                                <label class="toggle-switch" title="Toggle user active/inactive">
                                    <input type="checkbox" class="toggle-status" data-user-id="{{ $userId }}" {{ ($user['status'] ?? '') === 'active' ? 'checked' : '' }} {{ $approvalStatus === 'Pending_Approval' ? 'disabled' : '' }}>
                                    <span class="toggle-slider"></span>
                                </label>
                                @if($approvalStatus !== 'Approved' || $userType === 'superadmin')
                                    <button
                                        type="button"
                                        class="btn btn-secondary btn-sm btn-edit-user"
                                        data-user-id="{{ $userId }}"
                                        aria-label="Edit user {{ $user['fullName'] ?? '' }}"
                                    >
                                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                                            <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path>
                                            <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path>
                                        </svg>
                                    </button>
                                    <button
                                        type="button"
                                        class="btn btn-danger btn-sm btn-delete-user"
                                        data-user-id="{{ $userId }}"
                                        aria-label="Delete user {{ $user['fullName'] ?? '' }}"
                                    >
                                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                                            <polyline points="3 6 5 6 21 6"></polyline>
                                            <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
                                        </svg>
                                    </button>

                                @else
                                    <span style="color: #64748b; font-size: 0.75rem;">—</span>
                                @endif
                                </div>
                            </td>
                        </tr>
                    @endforeach
                </tbody>
            </table>

            <div class="pagination">
                <span class="pagination-info">Showing {{ count($users) }} of {{ count($users) }} users</span>
                <div class="pagination-pages" id="pagination-controls"></div>
            </div>
        @else
            <div style="text-align: center; padding: 3rem 1rem; color: #94a3b8;">
                <p style="font-size: 0.9rem;">No users found.</p>
            </div>
        @endif

        {{-- Toggle Confirmation Modal --}}
        <div class="modal-overlay" id="toggle-modal-overlay">
            <div class="modal" role="dialog" aria-labelledby="toggle-modal-title" aria-modal="true">
                <div class="modal-header">
                    <h3 id="toggle-modal-title">Confirm Status Change</h3>
                    <button type="button" class="modal-close" id="toggle-modal-close" aria-label="Close modal">&times;</button>
                </div>
                <div class="modal-body">
                    <p id="toggle-modal-message">Are you sure you want to change this user's status?</p>
                    <input type="hidden" id="toggle-user-id" value="">
                    <input type="hidden" id="toggle-action" value="">
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary" id="toggle-modal-cancel">Cancel</button>
                    <button type="button" class="btn btn-primary" id="toggle-modal-confirm" style="padding: 0.5rem 1rem; border-radius: 0.375rem; cursor: pointer; font-size: 0.875rem;">Confirm</button>
                </div>
            </div>
        </div>

        {{-- User Form Modal --}}
        <div class="modal-overlay" id="user-modal-overlay">
            <div class="modal" role="dialog" aria-labelledby="user-modal-title" aria-modal="true">
                <div class="modal-header">
                    <h3 id="user-modal-title">Add User</h3>
                    <button type="button" class="modal-close" id="user-modal-close" aria-label="Close modal">&times;</button>
                </div>
                <div class="modal-body">
                    <form id="user-form" novalidate>
                        <input type="hidden" id="user-form-id" value="">

                        {{-- Code field — read-only, excluded from submission --}}
                        <div class="form-group">
                            <label for="user-form-code">Code</label>
                            <input
                                type="text"
                                id="user-form-code"
                                readonly
                                disabled
                                placeholder="Auto-generated"
                                style="background-color: #e9ecef; color: #495057; cursor: not-allowed;"
                                aria-label="User code (auto-generated)"
                            >
                        </div>

                        <div class="form-group">
                            <label for="user-form-name">Full Name</label>
                            <input
                                type="text"
                                id="user-form-name"
                                placeholder="Enter full name"
                                required
                                aria-label="Full name"
                            >
                        </div>

                        <div class="form-group">
                            <label for="user-form-email">Email</label>
                            <input
                                type="email"
                                id="user-form-email"
                                placeholder="Enter email address"
                                required
                                aria-label="Email address"
                            >
                        </div>

                        {{-- Role field --}}
                        <div class="form-group" id="form-group-role">
                            <label for="user-form-role">Role</label>
                            @if($userType === 'superadmin')
                                <select id="user-form-role" aria-label="User role">
                                    <option value="admin">Admin</option>
                                    <option value="user" selected>User</option>
                                </select>
                            @else
                                <input
                                    type="text"
                                    id="user-form-role"
                                    readonly
                                    disabled
                                    value="User"
                                    style="background-color: #e9ecef; color: #495057; cursor: not-allowed;"
                                    aria-label="User role (auto-assigned)"
                                >
                            @endif
                        </div>

                        <div class="form-group" id="form-group-department">
                            <label for="user-form-department">Department</label>
                            <select
                                id="user-form-department"
                                aria-label="Department"
                            >
                                <option value="">Select Department</option>
                                @foreach($departments ?? [] as $dept)
                                    <option value="{{ $dept['departmentId'] }}">{{ $dept['departmentName'] }}</option>
                                @endforeach
                            </select>
                        </div>

                        <div class="form-group" id="form-group-position">
                            <label for="user-form-position">Position</label>
                            <select
                                id="user-form-position"
                                aria-label="Position"
                            >
                                <option value="">Select Position</option>
                                @foreach($positions ?? [] as $pos)
                                    <option value="{{ $pos['positionId'] }}">{{ $pos['positionName'] }}</option>
                                @endforeach
                            </select>
                        </div>
                    </form>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary" id="user-modal-cancel">Cancel</button>
                    <button type="button" class="btn btn-primary" id="user-modal-save">Save</button>
                </div>
            </div>
        </div>

    @endif
@endsection

@push('scripts')
<script>
(function () {
    var modalOverlay = document.getElementById('user-modal-overlay');
    var modalTitle = document.getElementById('user-modal-title');
    var modalClose = document.getElementById('user-modal-close');
    var modalCancel = document.getElementById('user-modal-cancel');
    var modalSave = document.getElementById('user-modal-save');
    var formId = document.getElementById('user-form-id');
    var formCode = document.getElementById('user-form-code');
    var formName = document.getElementById('user-form-name');
    var formEmail = document.getElementById('user-form-email');
    var formRole = document.getElementById('user-form-role');
    var formPosition = document.getElementById('user-form-position');
    var formDepartment = document.getElementById('user-form-department');
    var addBtn = document.getElementById('btn-add-user');

    var approvalFilter = document.getElementById('user-approval-status-filter');
    var searchInput = document.getElementById('search-input');

    // Store user data from the table for edit lookups
    var usersData = @json($users ?? []);

    // ── Helpers ────────────────────────────────────────────────────

    function ucFirst(str) {
        return str ? str.charAt(0).toUpperCase() + str.slice(1) : '';
    }

    // ── Toast notification ──────────────────────────────────────────

    function showToast(message, type) {
        var existing = document.getElementById('user-toast');
        if (existing) existing.remove();

        var toast = document.createElement('div');
        toast.id = 'user-toast';
        toast.setAttribute('role', 'alert');
        toast.style.cssText = 'position:fixed;top:1rem;right:1rem;z-index:10000;padding:0.75rem 1.25rem;border-radius:0.375rem;font-size:0.875rem;max-width:28rem;box-shadow:0 4px 12px rgba(0,0,0,0.15);transition:opacity 0.3s;';
        if (type === 'error') {
            toast.style.backgroundColor = '#fef2f2';
            toast.style.color = '#991b1b';
            toast.style.border = '1px solid #fecaca';
        } else {
            toast.style.backgroundColor = '#f0fdf4';
            toast.style.color = '#166534';
            toast.style.border = '1px solid #bbf7d0';
        }
        toast.textContent = message;
        document.body.appendChild(toast);

        setTimeout(function () {
            toast.style.opacity = '0';
            setTimeout(function () { if (toast.parentNode) toast.remove(); }, 300);
        }, 5000);
    }

    // ── CSRF helper ─────────────────────────────────────────────────

    function csrfToken() {
        var meta = document.querySelector('meta[name="csrf-token"]');
        return meta ? meta.content : '';
    }

    // ── User Form Modal helpers ─────────────────────────────────────

    function openModal(mode, userData) {
        if (!modalOverlay) return;

        if (mode === 'edit' && userData) {
            modalTitle.textContent = 'Edit User';
            formId.value = userData.userId || '';
            formCode.value = userData.userCode || '';
            formCode.placeholder = '';
            formName.value = userData.fullName || '';
            formEmail.value = userData.email || '';
            if (formRole.tagName === 'SELECT') {
                formRole.value = userData.userType || 'user';
            } else {
                formRole.value = userData.userType ? ucFirst(userData.userType) : 'User';
            }
            formDepartment.value = userData.departmentId || '';
            formPosition.value = userData.positionId || '';
        } else {
            modalTitle.textContent = 'Add User';
            formId.value = '';
            formCode.value = '';
            formCode.placeholder = 'Auto-generated';
            formName.value = '';
            formEmail.value = '';
            if (formRole.tagName === 'SELECT') {
                formRole.value = 'user';
            } else {
                formRole.value = 'User';
            }
            formPosition.value = '';
            formDepartment.value = '';
        }

        modalOverlay.classList.add('active');
        toggleUserTypeFields();
    }

    function closeModal() {
        if (modalOverlay) {
            modalOverlay.classList.remove('active');
        }
    }

    // ── Add User button ─────────────────────────────────────────────

    if (addBtn) {
        addBtn.addEventListener('click', function () {
            openModal('add');
        });
    }

    // ── Edit User buttons ───────────────────────────────────────────

    document.querySelectorAll('.btn-edit-user').forEach(function (btn) {
        btn.addEventListener('click', function () {
            var userId = this.getAttribute('data-user-id');
            var userData = null;
            for (var i = 0; i < usersData.length; i++) {
                if (usersData[i].userId === userId) {
                    userData = usersData[i];
                    break;
                }
            }
            openModal('edit', userData);
        });
    });

    // ── Save handler (create/update user via API) ───────────────────

    if (modalSave) {
        modalSave.addEventListener('click', function () {
            var form = document.getElementById('user-form');
            if (form && !form.reportValidity()) return;

            var userId = formId ? formId.value : '';
            var body = {
                fullName:     formName ? formName.value : '',
                email:        formEmail ? formEmail.value : '',
                positionId:   formPosition ? formPosition.value : '',
                departmentId: formDepartment ? formDepartment.value : ''
            };

            // Include userType from role dropdown when creating a new user (superadmin only)
            if (!userId && formRole && formRole.tagName === 'SELECT') {
                body.userType = formRole.value;
            }

            modalSave.disabled = true;

            var url, method;
            if (userId) {
                url = '/admin/users/' + encodeURIComponent(userId);
                method = 'PUT';
            } else {
                url = '/admin/users';
                method = 'POST';
            }

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
                modalSave.disabled = false;
                if (result.data.success) {
                    closeModal();
                    var action = userId ? 'updated' : 'created';
                    showToast('User ' + action + ' successfully.', 'success');
                    setTimeout(function() { window.location.reload(); }, 1500);
                } else {
                    closeModal();
                    var failAction = userId ? 'update' : 'create';
                    showToast(result.data.error || 'Failed to ' + failAction + ' user.', 'error');
                }
            })
            .catch(function () {
                modalSave.disabled = false;
                closeModal();
                showToast('Network error. Please try again.', 'error');
            });
        });
    }

    // ── Delete User buttons ─────────────────────────────────────────

    document.querySelectorAll('.btn-delete-user').forEach(function (btn) {
        btn.addEventListener('click', function () {
            var userId = this.getAttribute('data-user-id');
            var row = this.closest('tr');
            var userName = row ? row.querySelector('td:nth-child(2)').textContent.trim() : 'this user';

            if (!confirm('Are you sure you want to delete ' + userName + '?')) {
                return;
            }

            fetch('/admin/users/' + encodeURIComponent(userId), {
                method: 'DELETE',
                headers: {
                    'Content-Type': 'application/json',
                    'Accept': 'application/json',
                    'X-CSRF-TOKEN': csrfToken()
                }
            })
            .then(function (res) { return res.json().then(function (data) { return { status: res.status, data: data }; }); })
            .then(function (result) {
                if (result.data.success) {
                    showToast('User deleted successfully.', 'success');
                    setTimeout(function() { window.location.reload(); }, 1500);
                } else {
                    showToast(result.data.error || 'Failed to delete user.', 'error');
                }
            })
            .catch(function () {
                showToast('Network error. Please try again.', 'error');
            });
        });
    });

    // ── Close modals ────────────────────────────────────────────────

    if (modalClose) modalClose.addEventListener('click', closeModal);
    if (modalCancel) modalCancel.addEventListener('click', closeModal);

    if (modalOverlay) {
        modalOverlay.addEventListener('click', function (e) {
            if (e.target === modalOverlay) closeModal();
        });
    }

    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape') {
            closeModal();
        }
    });

    var departmentFilter = document.getElementById('department-filter');
    var positionFilter = document.getElementById('position-filter');

    // Lookup maps for displaying names instead of IDs
    var departmentMap = @json(collect($departments ?? [])->pluck('departmentName', 'departmentId')->toArray());
    var positionMap = @json(collect($positions ?? [])->pluck('positionName', 'positionId')->toArray());

    // ── Populate department and position filter dropdowns ────────────

    function populateFilterDropdowns() {
        var departments = {};
        var positions = {};

        for (var i = 0; i < usersData.length; i++) {
            var u = usersData[i];
            if (u.departmentId) departments[u.departmentId] = true;
            if (u.positionId) positions[u.positionId] = true;
        }

        if (departmentFilter) {
            var deptKeys = Object.keys(departments).sort();
            for (var d = 0; d < deptKeys.length; d++) {
                var opt = document.createElement('option');
                opt.value = deptKeys[d];
                opt.textContent = departmentMap[deptKeys[d]] || deptKeys[d];
                departmentFilter.appendChild(opt);
            }
        }

        if (positionFilter) {
            var posKeys = Object.keys(positions).sort();
            for (var p = 0; p < posKeys.length; p++) {
                var opt = document.createElement('option');
                opt.value = posKeys[p];
                opt.textContent = positionMap[posKeys[p]] || posKeys[p];
                positionFilter.appendChild(opt);
            }
        }
    }

    populateFilterDropdowns();

    // ── Client-side filters (search, department, position, approval status) ──

    function applyFilters() {
        var filterValue = approvalFilter ? approvalFilter.value : '';
        var searchValue = searchInput ? searchInput.value.trim().toLowerCase() : '';
        var deptValue = departmentFilter ? departmentFilter.value : '';
        var posValue = positionFilter ? positionFilter.value : '';
        var rows = document.querySelectorAll('#users-table tbody tr');

        rows.forEach(function (row) {
            var rowApprovalStatus = row.getAttribute('data-approval-status') || '';
            var rowDepartment = row.getAttribute('data-department') || '';
            var rowPosition = row.getAttribute('data-position') || '';
            var rowText = row.textContent.toLowerCase();

            var matchesApproval = !filterValue || rowApprovalStatus === filterValue;
            var matchesSearch = !searchValue || rowText.indexOf(searchValue) !== -1;
            var matchesDept = !deptValue || rowDepartment === deptValue;
            var matchesPos = !posValue || rowPosition === posValue;

            row.style.display = (matchesApproval && matchesSearch && matchesDept && matchesPos) ? '' : 'none';
        });
    }

    if (approvalFilter) approvalFilter.addEventListener('change', applyFilters);
    if (searchInput) searchInput.addEventListener('input', applyFilters);
    if (departmentFilter) departmentFilter.addEventListener('change', applyFilters);
    if (positionFilter) positionFilter.addEventListener('change', applyFilters);

    // ── Toggle Status Confirmation Modal ────────────────────────────

    var toggleOverlay = document.getElementById('toggle-modal-overlay');
    var toggleModalTitle = document.getElementById('toggle-modal-title');
    var toggleModalMessage = document.getElementById('toggle-modal-message');
    var toggleModalClose = document.getElementById('toggle-modal-close');
    var toggleModalCancel = document.getElementById('toggle-modal-cancel');
    var toggleModalConfirm = document.getElementById('toggle-modal-confirm');
    var toggleUserId = document.getElementById('toggle-user-id');
    var toggleAction = document.getElementById('toggle-action');
    var pendingToggleCheckbox = null;

    function openToggleModal(userId, userName, newAction) {
        if (!toggleOverlay) return;
        toggleUserId.value = userId;
        toggleAction.value = newAction;
        var actionLabel = newAction === 'activate' ? 'activate' : 'deactivate';
        toggleModalTitle.textContent = ucFirst(actionLabel) + ' User';
        toggleModalMessage.textContent = 'Are you sure you want to ' + actionLabel + ' user "' + userName + '"?';
        toggleOverlay.classList.add('active');
    }

    function closeToggleModal() {
        if (toggleOverlay) toggleOverlay.classList.remove('active');
        pendingToggleCheckbox = null;
    }

    if (toggleModalClose) toggleModalClose.addEventListener('click', function () {
        revertPendingToggle();
        closeToggleModal();
    });
    if (toggleModalCancel) toggleModalCancel.addEventListener('click', function () {
        revertPendingToggle();
        closeToggleModal();
    });
    if (toggleOverlay) toggleOverlay.addEventListener('click', function (e) {
        if (e.target === toggleOverlay) {
            revertPendingToggle();
            closeToggleModal();
        }
    });

    function revertPendingToggle() {
        if (pendingToggleCheckbox) {
            pendingToggleCheckbox.checked = !pendingToggleCheckbox.checked;
        }
    }

    // ── Toggle click handler ────────────────────────────────────────

    document.querySelectorAll('.toggle-status').forEach(function (checkbox) {
        checkbox.addEventListener('change', function () {
            var userId = this.getAttribute('data-user-id');
            var row = this.closest('tr');
            var userName = row ? row.querySelector('td:nth-child(2)').textContent.trim() : 'this user';
            var newAction = this.checked ? 'activate' : 'deactivate';

            pendingToggleCheckbox = this;
            openToggleModal(userId, userName, newAction);
        });
    });

    // ── Toggle confirm handler ──────────────────────────────────────

    if (toggleModalConfirm) {
        toggleModalConfirm.addEventListener('click', function () {
            var userId = toggleUserId ? toggleUserId.value : '';
            var action = toggleAction ? toggleAction.value : '';
            var checkbox = pendingToggleCheckbox;

            if (!userId || !action || !checkbox) {
                closeToggleModal();
                return;
            }

            toggleModalConfirm.disabled = true;

            var url = '/admin/users/' + encodeURIComponent(userId) + '/' + action;

            fetch(url, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Accept': 'application/json',
                    'X-CSRF-TOKEN': csrfToken()
                }
            })
            .then(function (res) { return res.json().then(function (data) { return { status: res.status, data: data }; }); })
            .then(function (result) {
                toggleModalConfirm.disabled = false;
                closeToggleModal();

                if (result.data.success) {
                    // Update row data-user-status attribute
                    var row = checkbox.closest('tr');
                    var newStatus = action === 'activate' ? 'active' : 'inactive';
                    if (row) {
                        row.setAttribute('data-user-status', newStatus);

                        // Update status badge
                        var statusCell = row.querySelector('td:nth-child(8)');
                        if (statusCell) {
                            var badge = statusCell.querySelector('.badge');
                            if (badge) {
                                if (newStatus === 'active') {
                                    badge.className = 'badge badge-success';
                                    badge.textContent = 'Active';
                                } else {
                                    badge.className = 'badge badge-warning';
                                    badge.textContent = 'Inactive';
                                }
                            }
                        }
                    }

                    var statusLabel = action === 'activate' ? 'activated' : 'deactivated';
                    showToast('User ' + statusLabel + ' successfully.', 'success');
                } else {
                    // Revert toggle on failure
                    checkbox.checked = !checkbox.checked;
                    showToast(result.data.error || 'Failed to ' + action + ' user.', 'error');
                }
                pendingToggleCheckbox = null;
            })
            .catch(function () {
                toggleModalConfirm.disabled = false;
                closeToggleModal();
                // Revert toggle on network error
                checkbox.checked = !checkbox.checked;
                pendingToggleCheckbox = null;
                showToast('Network error. Please try again.', 'error');
            });
        });
    }

    // Also close toggle modal on Escape key
    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape' && toggleOverlay && toggleOverlay.classList.contains('active')) {
            revertPendingToggle();
            closeToggleModal();
        }
    });

    // ── Toggle Position/Role fields based on userType selection ──────

    var positionGroup = document.getElementById('form-group-position');
    var departmentGroup = document.getElementById('form-group-department');

    function toggleUserTypeFields() {
        if (!formRole || formRole.tagName !== 'SELECT') return;

        var selectedType = formRole.value;
        var isAdmin = (selectedType === 'admin' || selectedType === 'superadmin');

        if (positionGroup) {
            positionGroup.style.display = isAdmin ? 'none' : '';
        }
        if (departmentGroup) {
            departmentGroup.style.display = isAdmin ? 'none' : '';
        }

        // Clear values when hidden
        if (isAdmin) {
            if (formPosition) formPosition.value = '';
            if (formDepartment) formDepartment.value = '';
        }
    }

    if (formRole && formRole.tagName === 'SELECT') {
        formRole.addEventListener('change', toggleUserTypeFields);
        // Set initial state on page load
        toggleUserTypeFields();
    }
})();
</script>
@endpush
