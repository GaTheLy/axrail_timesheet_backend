@extends('layouts.app')

@section('title', 'Approvals — TimeFlow')

@section('content')
    <nav class="breadcrumb" aria-label="Breadcrumb">
        <a href="/admin/approvals">Approvals</a>
        <span class="separator" aria-hidden="true">/</span>
        <span class="current">Pending Review</span>
    </nav>

    <div class="page-header">
        <h1 class="page-title">Approvals</h1>
    </div>

    {{-- Tab Navigation --}}
    <div class="tab-nav" style="display: flex; gap: 0; border-bottom: 2px solid #e2e8f0; margin-bottom: 1.5rem;">
        <button type="button" class="tab-btn active" data-tab="projects" style="padding: 0.75rem 1.5rem; border: none; background: none; cursor: pointer; font-size: 0.875rem; font-weight: 500; color: #3b82f6; border-bottom: 2px solid #3b82f6; margin-bottom: -2px;">
            Projects ({{ count($pendingProjects) }})
        </button>
        <button type="button" class="tab-btn" data-tab="departments" style="padding: 0.75rem 1.5rem; border: none; background: none; cursor: pointer; font-size: 0.875rem; font-weight: 500; color: #64748b; border-bottom: 2px solid transparent; margin-bottom: -2px;">
            Departments ({{ count($pendingDepartments) }})
        </button>
        <button type="button" class="tab-btn" data-tab="positions" style="padding: 0.75rem 1.5rem; border: none; background: none; cursor: pointer; font-size: 0.875rem; font-weight: 500; color: #64748b; border-bottom: 2px solid transparent; margin-bottom: -2px;">
            Positions ({{ count($pendingPositions) }})
        </button>
    </div>

    {{-- Projects Tab --}}
    <div class="tab-content" id="tab-projects">
        @if(count($pendingProjects) > 0)
            <table class="data-table">
                <thead>
                    <tr>
                        <th>NAME</th>
                        <th>CODE</th>
                        <th>CREATED DATE</th>
                        <th>CREATED BY</th>
                        <th>ACTIONS</th>
                    </tr>
                </thead>
                <tbody>
                    @foreach($pendingProjects as $project)
                        <tr data-entity-type="project" data-entity-id="{{ $project['projectId'] ?? '' }}">
                            <td><strong>{{ $project['projectName'] ?? '' }}</strong></td>
                            <td style="color: #3b82f6;">{{ $project['projectCode'] ?? '' }}</td>
                            <td>{{ isset($project['createdAt']) ? \Carbon\Carbon::parse($project['createdAt'])->format('M d, Y') : '—' }}</td>
                            <td>{{ ($userMap ?? [])[$project['createdBy'] ?? ''] ?? 'Unknown User' }}</td>
                            <td>
                                <button type="button" class="btn btn-sm btn-approve" data-type="project" data-id="{{ $project['projectId'] ?? '' }}" data-name="{{ $project['projectName'] ?? '' }}" aria-label="Approve project {{ $project['projectName'] ?? '' }}" style="background-color: #16a34a; color: #fff; border: none; padding: 0.25rem 0.75rem; border-radius: 0.25rem; cursor: pointer; font-size: 0.75rem; margin-right: 0.25rem;">
                                    ✓ Approve
                                </button>
                                <button type="button" class="btn btn-sm btn-reject" data-type="project" data-id="{{ $project['projectId'] ?? '' }}" data-name="{{ $project['projectName'] ?? '' }}" aria-label="Reject project {{ $project['projectName'] ?? '' }}" style="background-color: #dc2626; color: #fff; border: none; padding: 0.25rem 0.75rem; border-radius: 0.25rem; cursor: pointer; font-size: 0.75rem;">
                                    ✗ Reject
                                </button>
                            </td>
                        </tr>
                    @endforeach
                </tbody>
            </table>
        @else
            <div style="text-align: center; padding: 3rem 1rem; color: #94a3b8;">
                <p>No pending projects.</p>
            </div>
        @endif
    </div>

    {{-- Departments Tab --}}
    <div class="tab-content" id="tab-departments" style="display: none;">
        @if(count($pendingDepartments) > 0)
            <table class="data-table">
                <thead>
                    <tr>
                        <th>NAME</th>
                        <th>CODE</th>
                        <th>CREATED DATE</th>
                        <th>CREATED BY</th>
                        <th>ACTIONS</th>
                    </tr>
                </thead>
                <tbody>
                    @foreach($pendingDepartments as $index => $dept)
                        <tr data-entity-type="department" data-entity-id="{{ $dept['departmentId'] ?? '' }}">
                            <td><strong>{{ $dept['departmentName'] ?? '' }}</strong></td>
                            <td style="color: #3b82f6;">DEP-{{ str_pad($index + 1, 3, '0', STR_PAD_LEFT) }}</td>
                            <td>{{ isset($dept['createdAt']) ? \Carbon\Carbon::parse($dept['createdAt'])->format('M d, Y') : '—' }}</td>
                            <td>{{ ($userMap ?? [])[$dept['createdBy'] ?? ''] ?? 'Unknown User' }}</td>
                            <td>
                                <button type="button" class="btn btn-sm btn-approve" data-type="department" data-id="{{ $dept['departmentId'] ?? '' }}" data-name="{{ $dept['departmentName'] ?? '' }}" aria-label="Approve department {{ $dept['departmentName'] ?? '' }}" style="background-color: #16a34a; color: #fff; border: none; padding: 0.25rem 0.75rem; border-radius: 0.25rem; cursor: pointer; font-size: 0.75rem; margin-right: 0.25rem;">
                                    ✓ Approve
                                </button>
                                <button type="button" class="btn btn-sm btn-reject" data-type="department" data-id="{{ $dept['departmentId'] ?? '' }}" data-name="{{ $dept['departmentName'] ?? '' }}" aria-label="Reject department {{ $dept['departmentName'] ?? '' }}" style="background-color: #dc2626; color: #fff; border: none; padding: 0.25rem 0.75rem; border-radius: 0.25rem; cursor: pointer; font-size: 0.75rem;">
                                    ✗ Reject
                                </button>
                            </td>
                        </tr>
                    @endforeach
                </tbody>
            </table>
        @else
            <div style="text-align: center; padding: 3rem 1rem; color: #94a3b8;">
                <p>No pending departments.</p>
            </div>
        @endif
    </div>

    {{-- Positions Tab --}}
    <div class="tab-content" id="tab-positions" style="display: none;">
        @if(count($pendingPositions) > 0)
            <table class="data-table">
                <thead>
                    <tr>
                        <th>NAME</th>
                        <th>CODE</th>
                        <th>CREATED DATE</th>
                        <th>CREATED BY</th>
                        <th>ACTIONS</th>
                    </tr>
                </thead>
                <tbody>
                    @foreach($pendingPositions as $pos)
                        <tr data-entity-type="position" data-entity-id="{{ $pos['positionId'] ?? '' }}">
                            <td><strong>{{ $pos['positionName'] ?? '' }}</strong></td>
                            <td style="color: #3b82f6;">{{ $pos['positionCode'] ?? '—' }}</td>
                            <td>{{ isset($pos['createdAt']) ? \Carbon\Carbon::parse($pos['createdAt'])->format('M d, Y') : '—' }}</td>
                            <td>{{ ($userMap ?? [])[$pos['createdBy'] ?? ''] ?? 'Unknown User' }}</td>
                            <td>
                                <button type="button" class="btn btn-sm btn-approve" data-type="position" data-id="{{ $pos['positionId'] ?? '' }}" data-name="{{ $pos['positionName'] ?? '' }}" aria-label="Approve position {{ $pos['positionName'] ?? '' }}" style="background-color: #16a34a; color: #fff; border: none; padding: 0.25rem 0.75rem; border-radius: 0.25rem; cursor: pointer; font-size: 0.75rem; margin-right: 0.25rem;">
                                    ✓ Approve
                                </button>
                                <button type="button" class="btn btn-sm btn-reject" data-type="position" data-id="{{ $pos['positionId'] ?? '' }}" data-name="{{ $pos['positionName'] ?? '' }}" aria-label="Reject position {{ $pos['positionName'] ?? '' }}" style="background-color: #dc2626; color: #fff; border: none; padding: 0.25rem 0.75rem; border-radius: 0.25rem; cursor: pointer; font-size: 0.75rem;">
                                    ✗ Reject
                                </button>
                            </td>
                        </tr>
                    @endforeach
                </tbody>
            </table>
        @else
            <div style="text-align: center; padding: 3rem 1rem; color: #94a3b8;">
                <p>No pending positions.</p>
            </div>
        @endif
    </div>

    {{-- Approval Confirmation Modal --}}
    <div class="modal-overlay" id="approve-modal-overlay">
        <div class="modal" role="dialog" aria-labelledby="approve-modal-title" aria-modal="true">
            <div class="modal-header">
                <h3 id="approve-modal-title">Approve Entity</h3>
                <button type="button" class="modal-close" id="approve-modal-close" aria-label="Close modal">&times;</button>
            </div>
            <div class="modal-body">
                <p id="approve-modal-message">Are you sure you want to approve this entity?</p>
                <input type="hidden" id="approve-entity-type" value="">
                <input type="hidden" id="approve-entity-id" value="">
            </div>
            <div class="modal-footer">
                <button type="button" class="btn btn-secondary" id="approve-modal-cancel">Cancel</button>
                <button type="button" class="btn btn-success" id="approve-modal-submit" style="background-color: #16a34a; color: #fff; border: none; padding: 0.5rem 1rem; border-radius: 0.375rem; cursor: pointer; font-size: 0.875rem;">Approve</button>
            </div>
        </div>
    </div>

    {{-- Rejection Confirmation Modal --}}
    <div class="modal-overlay" id="reject-modal-overlay">
        <div class="modal" role="dialog" aria-labelledby="reject-modal-title" aria-modal="true">
            <div class="modal-header">
                <h3 id="reject-modal-title">Reject Entity</h3>
                <button type="button" class="modal-close" id="reject-modal-close" aria-label="Close modal">&times;</button>
            </div>
            <div class="modal-body">
                <input type="hidden" id="reject-entity-type" value="">
                <input type="hidden" id="reject-entity-id" value="">
                <p id="reject-confirm-message">Are you sure you want to reject this entity?</p>
            </div>
            <div class="modal-footer">
                <button type="button" class="btn btn-secondary" id="reject-modal-cancel">Cancel</button>
                <button type="button" class="btn btn-danger" id="reject-modal-submit">Reject</button>
            </div>
        </div>
    </div>
@endsection

@push('scripts')
<script>
(function () {
    // ── CSRF helper ─────────────────────────────────────────────────
    function csrfToken() {
        var meta = document.querySelector('meta[name="csrf-token"]');
        return meta ? meta.content : '';
    }

    // ── Toast notification ──────────────────────────────────────────
    function showToast(message, type) {
        var existing = document.getElementById('approvals-toast');
        if (existing) existing.remove();
        var toast = document.createElement('div');
        toast.id = 'approvals-toast';
        toast.setAttribute('role', 'alert');
        toast.style.cssText = 'position:fixed;top:1rem;right:1rem;z-index:10000;padding:0.75rem 1.25rem;border-radius:0.375rem;font-size:0.875rem;max-width:28rem;box-shadow:0 4px 12px rgba(0,0,0,0.15);transition:opacity 0.3s;';
        toast.style.backgroundColor = type === 'error' ? '#fef2f2' : '#f0fdf4';
        toast.style.color = type === 'error' ? '#991b1b' : '#166534';
        toast.style.border = '1px solid ' + (type === 'error' ? '#fecaca' : '#bbf7d0');
        toast.textContent = message;
        document.body.appendChild(toast);
        setTimeout(function () { toast.style.opacity = '0'; setTimeout(function () { if (toast.parentNode) toast.remove(); }, 300); }, 4000);
    }

    // ── Tab switching ───────────────────────────────────────────────
    var tabBtns = document.querySelectorAll('.tab-btn');
    var tabContents = document.querySelectorAll('.tab-content');

    tabBtns.forEach(function (btn) {
        btn.addEventListener('click', function () {
            var targetTab = this.getAttribute('data-tab');

            // Update button styles
            tabBtns.forEach(function (b) {
                b.style.color = '#64748b';
                b.style.borderBottomColor = 'transparent';
            });
            this.style.color = '#3b82f6';
            this.style.borderBottomColor = '#3b82f6';

            // Show/hide tab content
            tabContents.forEach(function (content) {
                content.style.display = 'none';
            });
            var target = document.getElementById('tab-' + targetTab);
            if (target) target.style.display = '';
        });
    });

    // ── Approve modal ───────────────────────────────────────────────
    var approveOverlay = document.getElementById('approve-modal-overlay');
    var approveCloseBtn = document.getElementById('approve-modal-close');
    var approveCancelBtn = document.getElementById('approve-modal-cancel');
    var approveSubmitBtn = document.getElementById('approve-modal-submit');
    var approveEntityType = document.getElementById('approve-entity-type');
    var approveEntityId = document.getElementById('approve-entity-id');
    var approveModalTitle = document.getElementById('approve-modal-title');
    var approveModalMessage = document.getElementById('approve-modal-message');

    function openApproveModal(entityType, entityId, entityName) {
        if (approveOverlay) {
            approveEntityType.value = entityType;
            approveEntityId.value = entityId;
            var displayType = entityType.charAt(0).toUpperCase() + entityType.slice(1);
            approveModalTitle.textContent = 'Approve ' + displayType;
            approveModalMessage.textContent = 'Are you sure you want to approve ' + displayType + ' "' + entityName + '"?';
            approveOverlay.classList.add('active');
        }
    }

    function closeApproveModal() {
        if (approveOverlay) approveOverlay.classList.remove('active');
    }

    if (approveCloseBtn) approveCloseBtn.addEventListener('click', closeApproveModal);
    if (approveCancelBtn) approveCancelBtn.addEventListener('click', closeApproveModal);
    if (approveOverlay) approveOverlay.addEventListener('click', function (e) { if (e.target === approveOverlay) closeApproveModal(); });

    // ── Approve button click → open modal ───────────────────────────
    document.querySelectorAll('.btn-approve').forEach(function (btn) {
        btn.addEventListener('click', function () {
            var entityType = this.getAttribute('data-type');
            var entityId = this.getAttribute('data-id');
            var entityName = this.getAttribute('data-name') || entityType;
            openApproveModal(entityType, entityId, entityName);
        });
    });

    // ── Approve modal submit → call API ─────────────────────────────
    if (approveSubmitBtn) {
        approveSubmitBtn.addEventListener('click', function () {
            var entityType = approveEntityType ? approveEntityType.value : '';
            var entityId = approveEntityId ? approveEntityId.value : '';
            var row = document.querySelector('tr[data-entity-type="' + entityType + '"][data-entity-id="' + entityId + '"]');
            var entityName = row ? row.querySelector('td:first-child').textContent.trim() : entityType;

            approveSubmitBtn.disabled = true;
            fetch('/admin/approvals/' + encodeURIComponent(entityType) + '/' + encodeURIComponent(entityId) + '/approve', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'Accept': 'application/json', 'X-CSRF-TOKEN': csrfToken() }
            })
            .then(function (res) { return res.json().then(function (data) { return { status: res.status, data: data }; }); })
            .then(function (result) {
                approveSubmitBtn.disabled = false;
                if (result.data.success) {
                    closeApproveModal();
                    showToast(entityName + ' approved successfully.', 'success');
                    if (row) row.remove();
                    updateEmptyState(entityType);
                    updateTabCount(entityType, -1);
                } else {
                    closeApproveModal();
                    showToast(result.data.error || 'Failed to approve ' + entityType + '.', 'error');
                }
            })
            .catch(function () { approveSubmitBtn.disabled = false; closeApproveModal(); showToast('Network error. Please try again.', 'error'); });
        });
    }

    // ── Reject modal ────────────────────────────────────────────────
    var rejectOverlay = document.getElementById('reject-modal-overlay');
    var rejectCloseBtn = document.getElementById('reject-modal-close');
    var rejectCancelBtn = document.getElementById('reject-modal-cancel');
    var rejectSubmitBtn = document.getElementById('reject-modal-submit');
    var rejectEntityType = document.getElementById('reject-entity-type');
    var rejectEntityId = document.getElementById('reject-entity-id');
    var rejectModalTitle = document.getElementById('reject-modal-title');
    var rejectConfirmMessage = document.getElementById('reject-confirm-message');

    function openRejectModal(type, id, name) {
        if (rejectOverlay) {
            rejectEntityType.value = type;
            rejectEntityId.value = id;
            var displayType = type.charAt(0).toUpperCase() + type.slice(1);
            rejectModalTitle.textContent = 'Reject ' + displayType;
            rejectConfirmMessage.textContent = 'Are you sure you want to reject ' + displayType + ' "' + (name || type) + '"?';
            rejectOverlay.classList.add('active');
        }
    }
    function closeRejectModal() { if (rejectOverlay) rejectOverlay.classList.remove('active'); }

    if (rejectCloseBtn) rejectCloseBtn.addEventListener('click', closeRejectModal);
    if (rejectCancelBtn) rejectCancelBtn.addEventListener('click', closeRejectModal);
    if (rejectOverlay) rejectOverlay.addEventListener('click', function (e) { if (e.target === rejectOverlay) closeRejectModal(); });

    document.querySelectorAll('.btn-reject').forEach(function (btn) {
        btn.addEventListener('click', function () {
            var type = this.getAttribute('data-type');
            var id = this.getAttribute('data-id');
            var name = this.getAttribute('data-name') || type;
            openRejectModal(type, id, name);
        });
    });

    if (rejectSubmitBtn) {
        rejectSubmitBtn.addEventListener('click', function () {
            var type = rejectEntityType ? rejectEntityType.value : '';
            var id = rejectEntityId ? rejectEntityId.value : '';
            var reason = 'Rejected by superadmin';

            rejectSubmitBtn.disabled = true;
            fetch('/admin/approvals/' + encodeURIComponent(type) + '/' + encodeURIComponent(id) + '/reject', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'Accept': 'application/json', 'X-CSRF-TOKEN': csrfToken() },
                body: JSON.stringify({ reason: reason })
            })
            .then(function (res) { return res.json().then(function (data) { return { status: res.status, data: data }; }); })
            .then(function (result) {
                rejectSubmitBtn.disabled = false;
                if (result.data.success) {
                    closeRejectModal();
                    showToast(type.charAt(0).toUpperCase() + type.slice(1) + ' rejected successfully.', 'success');
                    var row = document.querySelector('tr[data-entity-type="' + type + '"][data-entity-id="' + id + '"]');
                    if (row) row.remove();
                    updateEmptyState(type);
                    updateTabCount(type, -1);
                } else {
                    closeRejectModal();
                    showToast(result.data.error || 'Failed to reject ' + type + '.', 'error');
                }
            })
            .catch(function () { rejectSubmitBtn.disabled = false; closeRejectModal(); showToast('Network error. Please try again.', 'error'); });
        });
    }

    // ── Helper: update empty state when all rows removed ────────────
    function updateEmptyState(entityType) {
        var tabId = 'tab-' + entityType + 's';
        var tabContent = document.getElementById(tabId);
        if (!tabContent) return;
        var rows = tabContent.querySelectorAll('tbody tr');
        if (rows.length === 0) {
            var table = tabContent.querySelector('table');
            if (table) table.remove();
            var emptyDiv = document.createElement('div');
            emptyDiv.style.cssText = 'text-align: center; padding: 3rem 1rem; color: #94a3b8;';
            emptyDiv.innerHTML = '<p>No pending ' + entityType + 's.</p>';
            tabContent.appendChild(emptyDiv);
        }
    }

    // ── Helper: update tab count after approve/reject ────────────────
    function updateTabCount(entityType, delta) {
        var tabBtn = document.querySelector('.tab-btn[data-tab="' + entityType + 's"]');
        if (!tabBtn) return;
        var text = tabBtn.textContent;
        var match = text.match(/\((\d+)\)/);
        if (match) {
            var count = Math.max(0, parseInt(match[1], 10) + delta);
            tabBtn.textContent = text.replace(/\(\d+\)/, '(' + count + ')');
        }
    }

    // ── Close modals on Escape ──────────────────────────────────────
    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape') {
            closeRejectModal();
            closeApproveModal();
        }
    });
})();
</script>
@endpush
