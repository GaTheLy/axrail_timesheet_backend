@extends('layouts.app')

@section('title', 'User Management — TimeFlow')

@section('content')
    @php $userType = session('user.userType', 'user'); @endphp

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
            <select id="user-approval-status-filter" aria-label="Filter by approval status">
                <option value="">All</option>
                <option value="Pending_Approval">Pending_Approval</option>
                <option value="Approved">Approved</option>
                <option value="Rejected">Rejected</option>
            </select>
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
                        <th>APPROVAL STATUS</th>
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
                        <tr data-user-id="{{ $userId }}" data-user-status="{{ $user['status'] ?? '' }}" data-approval-status="{{ $approvalStatus }}">
                            <td style="color: #3b82f6;">{{ $user['userCode'] ?? '—' }}</td>
                            <td><strong>{{ $user['fullName'] ?? '' }}</strong></td>
                            <td>{{ $user['email'] ?? '' }}</td>
                            <td>
                                <span class="badge" style="background-color: #e0e7ff; color: #3730a3; padding: 0.2rem 0.6rem; border-radius: 9999px; font-size: 0.75rem;">
                                    {{ ucfirst($user['userType'] ?? 'User') }}
                                </span>
                            </td>
                            <td>{{ $user['departmentId'] ?? '—' }}</td>
                            <td>{{ $user['positionId'] ?? '—' }}</td>
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
                            <td>
                                @if($approvalStatus !== 'Approved')
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
                                    @if($approvalStatus === 'Pending_Approval' && $userType === 'superadmin')
                                        <button type="button" class="btn btn-sm btn-approve-user" data-user-id="{{ $userId }}" aria-label="Approve user {{ $user['fullName'] ?? '' }}" style="background-color: #16a34a; color: #fff; border: none; padding: 0.25rem 0.5rem; border-radius: 0.25rem; cursor: pointer; font-size: 0.75rem;">
                                            ✓ Approve
                                        </button>
                                        <button type="button" class="btn btn-sm btn-reject-user" data-user-id="{{ $userId }}" data-user-name="{{ $user['fullName'] ?? '' }}" aria-label="Reject user {{ $user['fullName'] ?? '' }}" style="background-color: #dc2626; color: #fff; border: none; padding: 0.25rem 0.5rem; border-radius: 0.25rem; cursor: pointer; font-size: 0.75rem;">
                                            ✗ Reject
                                        </button>
                                    @endif
                                @else
                                    <span style="color: #64748b; font-size: 0.75rem;">—</span>
                                @endif
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

                        {{-- Role field — read-only, excluded from submission --}}
                        <div class="form-group">
                            <label for="user-form-role">Role</label>
                            <input
                                type="text"
                                id="user-form-role"
                                readonly
                                disabled
                                value="User"
                                style="background-color: #e9ecef; color: #495057; cursor: not-allowed;"
                                aria-label="User role (auto-assigned)"
                            >
                        </div>

                        <div class="form-group">
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

                        <div class="form-group">
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

        {{-- Rejection Reason Modal --}}
        <div class="modal-overlay" id="user-reject-modal-overlay">
            <div class="modal" role="dialog" aria-labelledby="user-reject-modal-title" aria-modal="true">
                <div class="modal-header">
                    <h3 id="user-reject-modal-title">Reject User</h3>
                    <button type="button" class="modal-close" id="user-reject-modal-close" aria-label="Close modal">&times;</button>
                </div>
                <div class="modal-body">
                    <form id="user-reject-form" novalidate>
                        <input type="hidden" id="user-reject-user-id" value="">
                        <div class="form-group">
                            <label for="user-reject-reason">Rejection Reason</label>
                            <textarea id="user-reject-reason" placeholder="Enter reason for rejection" required aria-label="Rejection reason" rows="4" style="width: 100%; padding: 0.5rem; border: 1px solid #d1d5db; border-radius: 0.375rem; font-size: 0.875rem; resize: vertical;"></textarea>
                        </div>
                    </form>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary" id="user-reject-modal-cancel">Cancel</button>
                    <button type="button" class="btn btn-danger" id="user-reject-modal-submit">Reject</button>
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

    var rejectOverlay = document.getElementById('user-reject-modal-overlay');
    var rejectCloseBtn = document.getElementById('user-reject-modal-close');
    var rejectCancelBtn = document.getElementById('user-reject-modal-cancel');
    var rejectSubmitBtn = document.getElementById('user-reject-modal-submit');
    var rejectUserIdInput = document.getElementById('user-reject-user-id');
    var rejectReasonInput = document.getElementById('user-reject-reason');

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
            formRole.value = userData.userType ? ucFirst(userData.userType) : 'User';
            formDepartment.value = userData.departmentId || '';
            formPosition.value = userData.positionId || '';
        } else {
            modalTitle.textContent = 'Add User';
            formId.value = '';
            formCode.value = '';
            formCode.placeholder = 'Auto-generated';
            formName.value = '';
            formEmail.value = '';
            formRole.value = 'User';
            formPosition.value = '';
            formDepartment.value = '';
        }

        modalOverlay.classList.add('active');
    }

    function closeModal() {
        if (modalOverlay) {
            modalOverlay.classList.remove('active');
        }
    }

    // ── Rejection Modal helpers ─────────────────────────────────────

    function openRejectModal(userId) {
        if (rejectOverlay) {
            rejectUserIdInput.value = userId;
            rejectReasonInput.value = '';
            rejectOverlay.classList.add('active');
        }
    }

    function closeRejectModal() {
        if (rejectOverlay) rejectOverlay.classList.remove('active');
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
            var userId = formId ? formId.value : '';
            var body = {
                fullName:     formName ? formName.value : '',
                email:        formEmail ? formEmail.value : '',
                positionId:   formPosition ? formPosition.value : '',
                departmentId: formDepartment ? formDepartment.value : ''
            };

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
                    window.location.reload();
                } else {
                    closeModal();
                    showToast(result.data.error || 'Failed to save user.', 'error');
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
                    window.location.reload();
                } else {
                    showToast(result.data.error || 'Failed to delete user.', 'error');
                }
            })
            .catch(function () {
                showToast('Network error. Please try again.', 'error');
            });
        });
    });

    // ── Approve User action ─────────────────────────────────────────

    document.querySelectorAll('.btn-approve-user').forEach(function (btn) {
        btn.addEventListener('click', function () {
            var userId = this.getAttribute('data-user-id');
            if (!confirm('Are you sure you want to approve this user?')) return;

            btn.disabled = true;
            fetch('/admin/users/' + encodeURIComponent(userId) + '/approve', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'Accept': 'application/json', 'X-CSRF-TOKEN': csrfToken() }
            })
            .then(function (res) { return res.json().then(function (data) { return { status: res.status, data: data }; }); })
            .then(function (result) {
                btn.disabled = false;
                if (result.data.success) { showToast('User approved successfully.', 'success'); window.location.reload(); }
                else { showToast(result.data.error || 'Failed to approve user.', 'error'); }
            })
            .catch(function () { btn.disabled = false; showToast('Network error. Please try again.', 'error'); });
        });
    });

    // ── Reject User action (opens modal) ────────────────────────────

    document.querySelectorAll('.btn-reject-user').forEach(function (btn) {
        btn.addEventListener('click', function () {
            var userId = this.getAttribute('data-user-id');
            openRejectModal(userId);
        });
    });

    // ── Rejection Modal event handlers ──────────────────────────────

    if (rejectCloseBtn) rejectCloseBtn.addEventListener('click', closeRejectModal);
    if (rejectCancelBtn) rejectCancelBtn.addEventListener('click', closeRejectModal);
    if (rejectOverlay) rejectOverlay.addEventListener('click', function (e) { if (e.target === rejectOverlay) closeRejectModal(); });

    if (rejectSubmitBtn) {
        rejectSubmitBtn.addEventListener('click', function () {
            var userId = rejectUserIdInput ? rejectUserIdInput.value : '';
            var reason = rejectReasonInput ? rejectReasonInput.value.trim() : '';
            if (!reason) { rejectReasonInput.focus(); return; }

            rejectSubmitBtn.disabled = true;
            fetch('/admin/users/' + encodeURIComponent(userId) + '/reject', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'Accept': 'application/json', 'X-CSRF-TOKEN': csrfToken() },
                body: JSON.stringify({ reason: reason })
            })
            .then(function (res) { return res.json().then(function (data) { return { status: res.status, data: data }; }); })
            .then(function (result) {
                rejectSubmitBtn.disabled = false;
                if (result.data.success) { closeRejectModal(); showToast('User rejected successfully.', 'success'); window.location.reload(); }
                else { closeRejectModal(); showToast(result.data.error || 'Failed to reject user.', 'error'); }
            })
            .catch(function () { rejectSubmitBtn.disabled = false; closeRejectModal(); showToast('Network error. Please try again.', 'error'); });
        });
    }

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
            closeRejectModal();
        }
    });

    // ── Client-side approval status filter ──────────────────────────

    function applyFilters() {
        var filterValue = approvalFilter ? approvalFilter.value : '';
        var searchValue = searchInput ? searchInput.value.trim().toLowerCase() : '';
        var rows = document.querySelectorAll('#users-table tbody tr');

        rows.forEach(function (row) {
            var rowApprovalStatus = row.getAttribute('data-approval-status') || '';
            var rowText = row.textContent.toLowerCase();
            var matchesFilter = !filterValue || rowApprovalStatus === filterValue;
            var matchesSearch = !searchValue || rowText.indexOf(searchValue) !== -1;
            row.style.display = (matchesFilter && matchesSearch) ? '' : 'none';
        });
    }

    if (approvalFilter) approvalFilter.addEventListener('change', applyFilters);
    if (searchInput) searchInput.addEventListener('input', applyFilters);
})();
</script>
@endpush
