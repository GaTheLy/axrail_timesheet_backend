@extends('layouts.app')

@section('title', 'Project Management — TimeFlow')

@section('content')
    @php $userType = session('user.userType', 'user'); @endphp

    <nav class="breadcrumb" aria-label="Breadcrumb">
        <a href="/admin/projects">Master Data</a>
        <span class="separator" aria-hidden="true">/</span>
        <span class="current">Projects</span>
    </nav>

    <div class="page-header">
        <h1 class="page-title">Project Management</h1>
        <div class="page-actions">
            <button type="button" class="btn btn-primary" id="btn-add-project">
                + New Project
            </button>
        </div>
    </div>

    @if(!empty($error))
        <div class="alert alert-error">{{ $error }}</div>
    @else
        <div class="filter-bar">
            <input type="text" id="search-input" class="search-input" placeholder="Search by name or manager..." aria-label="Search">
            <select id="start-date-select" aria-label="Select start date">
                <option value="">Select Start Date</option>
            </select>
            <select id="status-select" aria-label="Filter by status">
                <option value="">All Status</option>
                <option value="active">Approved</option>
                <option value="pending">Pending</option>
            </select>
        </div>

        @if(count($projects) > 0)
            <table class="data-table" id="report-table">
                <thead>
                    <tr>
                        <th>CODE</th>
                        <th>NAME</th>
                        <th>PROJECT MANAGER</th>
                        <th>START DATE</th>
                        <th>PLANNED HOURS</th>
                        <th>CREATED BY</th>
                        <th>CREATED AT</th>
                        <th>STATUS</th>
                        <th>ACTIONS</th>
                    </tr>
                </thead>
                <tbody>
                    @foreach($projects as $project)
                        @php
                            $approvalStatus = $project['approval_status'] ?? $project['status'] ?? 'Pending_Approval';
                            $projectId = $project['projectId'] ?? '';
                        @endphp
                        <tr data-project-id="{{ $projectId }}" data-approval-status="{{ $approvalStatus }}">
                            <td style="color: #3b82f6;">{{ $project['projectCode'] ?? '' }}</td>
                            <td><strong>{{ $project['projectName'] ?? '' }}</strong></td>
                            <td>{{ $project['projectManagerId'] ?? '—' }}</td>
                            <td>{{ isset($project['startDate']) ? \Carbon\Carbon::parse($project['startDate'])->format('M d, Y') : '—' }}</td>
                            <td>{{ $project['plannedHours'] ?? '—' }}</td>
                            <td>{{ $project['createdBy'] ?? '—' }}</td>
                            <td>{{ isset($project['createdAt']) ? \Carbon\Carbon::parse($project['createdAt'])->format('M d, Y') : '—' }}</td>
                            <td>
                                @if($approvalStatus === 'Approved')
                                    <span class="badge" style="background-color: #dcfce7; color: #166534; padding: 0.2rem 0.6rem; border-radius: 9999px; font-size: 0.75rem;">Approved</span>
                                @elseif($approvalStatus === 'Pending_Approval')
                                    <span class="badge" style="background-color: #fef9c3; color: #854d0e; padding: 0.2rem 0.6rem; border-radius: 9999px; font-size: 0.75rem;">Pending_Approval</span>
                                @elseif($approvalStatus === 'Rejected')
                                    <span class="badge" style="background-color: #fee2e2; color: #991b1b; padding: 0.2rem 0.6rem; border-radius: 9999px; font-size: 0.75rem;">Rejected</span>
                                @else
                                    <span class="badge {{ $approvalStatus === 'Approved' ? 'badge-success' : 'badge-warning' }}">
                                        {{ $approvalStatus }}
                                    </span>
                                @endif
                            </td>
                            <td>
                                @if($approvalStatus !== 'Approved')
                                    <button type="button" class="btn btn-secondary btn-sm btn-edit-project" data-project-id="{{ $projectId }}" aria-label="Edit project">
                                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path></svg>
                                    </button>
                                    <button type="button" class="btn btn-danger btn-sm btn-delete-project" data-project-id="{{ $projectId }}" aria-label="Delete project">
                                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>
                                    </button>
                                    @if($approvalStatus === 'Pending_Approval' && $userType === 'superadmin')
                                        <button type="button" class="btn btn-sm btn-approve-project" data-project-id="{{ $projectId }}" aria-label="Approve project {{ $project['projectName'] ?? '' }}" style="background-color: #16a34a; color: #fff; border: none; padding: 0.25rem 0.5rem; border-radius: 0.25rem; cursor: pointer; font-size: 0.75rem;">
                                            ✓ Approve
                                        </button>
                                        <button type="button" class="btn btn-sm btn-reject-project" data-project-id="{{ $projectId }}" data-project-name="{{ $project['projectName'] ?? '' }}" aria-label="Reject project {{ $project['projectName'] ?? '' }}" style="background-color: #dc2626; color: #fff; border: none; padding: 0.25rem 0.5rem; border-radius: 0.25rem; cursor: pointer; font-size: 0.75rem;">
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
                <span class="pagination-info">Showing {{ count($projects) }} of {{ count($projects) }} projects</span>
                <div class="pagination-pages" id="pagination-controls"></div>
            </div>
        @else
            <div style="text-align: center; padding: 3rem 1rem; color: #94a3b8;">
                <p>No projects found.</p>
            </div>
        @endif
    @endif

    {{-- Rejection Reason Modal --}}
    <div class="modal-overlay" id="reject-project-modal-overlay">
        <div class="modal" role="dialog" aria-labelledby="reject-project-modal-title" aria-modal="true">
            <div class="modal-header">
                <h3 id="reject-project-modal-title">Reject Project</h3>
                <button type="button" class="modal-close" id="reject-project-modal-close" aria-label="Close modal">&times;</button>
            </div>
            <div class="modal-body">
                <form id="reject-project-form" novalidate>
                    <input type="hidden" id="reject-project-id" value="">
                    <div class="form-group">
                        <label for="reject-project-reason">Rejection Reason</label>
                        <textarea id="reject-project-reason" placeholder="Enter reason for rejection" required aria-label="Rejection reason" rows="4" style="width: 100%; padding: 0.5rem; border: 1px solid #d1d5db; border-radius: 0.375rem; font-size: 0.875rem; resize: vertical;"></textarea>
                    </div>
                </form>
            </div>
            <div class="modal-footer">
                <button type="button" class="btn btn-secondary" id="reject-project-modal-cancel">Cancel</button>
                <button type="button" class="btn btn-danger" id="reject-project-modal-submit">Reject</button>
            </div>
        </div>
    </div>

    {{-- Add Project Modal --}}
    <div class="modal-overlay" id="project-modal-overlay">
        <div class="modal" role="dialog" aria-labelledby="project-modal-title" aria-modal="true">
            <div class="modal-header">
                <h3 id="project-modal-title">Add Project</h3>
                <button type="button" class="modal-close" id="project-modal-close" aria-label="Close modal">&times;</button>
            </div>
            <div class="modal-body">
                <form id="project-form" novalidate>
                    <div class="form-group">
                        <label for="project-form-code">Project Code</label>
                        <input type="text" id="project-form-code" placeholder="e.g. PRJ-003" required aria-label="Project code">
                    </div>
                    <div class="form-group">
                        <label for="project-form-name">Project Name</label>
                        <input type="text" id="project-form-name" placeholder="Enter project name" required aria-label="Project name">
                    </div>
                    <div class="form-group">
                        <label for="project-form-start-date">Start Date</label>
                        <input type="date" id="project-form-start-date" required aria-label="Start date">
                    </div>
                    <div class="form-group">
                        <label for="project-form-hours">Planned Hours</label>
                        <input type="number" id="project-form-hours" placeholder="e.g. 500" min="1" step="1" required aria-label="Planned hours">
                    </div>
                    <div class="form-group">
                        <label for="project-form-manager">Project Manager</label>
                        <select id="project-form-manager" required aria-label="Project manager">
                            <option value="">Select Project Manager</option>
                            @foreach($users ?? [] as $u)
                                <option value="{{ $u['userId'] }}">{{ $u['fullName'] ?? $u['userId'] }}</option>
                            @endforeach
                        </select>
                    </div>
                </form>
            </div>
            <div class="modal-footer">
                <button type="button" class="btn btn-secondary" id="project-modal-cancel">Cancel</button>
                <button type="button" class="btn btn-primary" id="project-modal-save">Save</button>
            </div>
        </div>
    </div>
@endsection

@push('scripts')
<script>
(function () {
    // ── DOM references ──────────────────────────────────────────────
    var rejectOverlay = document.getElementById('reject-project-modal-overlay');
    var rejectCloseBtn = document.getElementById('reject-project-modal-close');
    var rejectCancelBtn = document.getElementById('reject-project-modal-cancel');
    var rejectSubmitBtn = document.getElementById('reject-project-modal-submit');
    var rejectProjectIdInput = document.getElementById('reject-project-id');
    var rejectReasonInput = document.getElementById('reject-project-reason');

    var addOverlay = document.getElementById('project-modal-overlay');
    var addCloseBtn = document.getElementById('project-modal-close');
    var addCancelBtn = document.getElementById('project-modal-cancel');
    var addSaveBtn = document.getElementById('project-modal-save');
    var addBtn = document.getElementById('btn-add-project');
    var formCode = document.getElementById('project-form-code');
    var formName = document.getElementById('project-form-name');
    var formStartDate = document.getElementById('project-form-start-date');
    var formHours = document.getElementById('project-form-hours');
    var formManager = document.getElementById('project-form-manager');

    // ── CSRF helper ─────────────────────────────────────────────────
    function csrfToken() {
        var meta = document.querySelector('meta[name="csrf-token"]');
        return meta ? meta.content : '';
    }

    // ── Toast notification ──────────────────────────────────────────
    function showToast(message, type) {
        var existing = document.getElementById('project-toast');
        if (existing) existing.remove();
        var toast = document.createElement('div');
        toast.id = 'project-toast';
        toast.setAttribute('role', 'alert');
        toast.style.cssText = 'position:fixed;top:1rem;right:1rem;z-index:10000;padding:0.75rem 1.25rem;border-radius:0.375rem;font-size:0.875rem;max-width:28rem;box-shadow:0 4px 12px rgba(0,0,0,0.15);transition:opacity 0.3s;';
        toast.style.backgroundColor = type === 'error' ? '#fef2f2' : '#f0fdf4';
        toast.style.color = type === 'error' ? '#991b1b' : '#166534';
        toast.style.border = '1px solid ' + (type === 'error' ? '#fecaca' : '#bbf7d0');
        toast.textContent = message;
        document.body.appendChild(toast);
        setTimeout(function () { toast.style.opacity = '0'; setTimeout(function () { if (toast.parentNode) toast.remove(); }, 300); }, 5000);
    }

    // ── Add/Edit Project Modal ──────────────────────────────────────
    var editingProjectId = null;
    var modalTitle = document.getElementById('project-modal-title');
    var codeGroup = formCode ? formCode.closest('.form-group') : null;

    function openAddModal(mode, projectId, projectData) {
        if (!addOverlay) return;
        if (mode === 'edit' && projectData) {
            editingProjectId = projectId;
            modalTitle.textContent = 'Edit Project';
            formCode.value = projectData.code || '';
            formCode.readOnly = true;
            formCode.style.opacity = '0.6';
            formName.value = projectData.name || '';
            formStartDate.value = projectData.startDate || '';
            formHours.value = projectData.hours || '';
            formManager.value = projectData.managerId || '';
        } else {
            editingProjectId = null;
            modalTitle.textContent = 'Add Project';
            formCode.value = '';
            formCode.readOnly = false;
            formCode.style.opacity = '1';
            formName.value = '';
            formStartDate.value = '';
            formHours.value = '';
            formManager.value = '';
        }
        addOverlay.classList.add('active');
    }
    function closeAddModal() { if (addOverlay) addOverlay.classList.remove('active'); }

    if (addBtn) addBtn.addEventListener('click', function () { openAddModal('add'); });
    if (addCloseBtn) addCloseBtn.addEventListener('click', closeAddModal);
    if (addCancelBtn) addCancelBtn.addEventListener('click', closeAddModal);
    if (addOverlay) addOverlay.addEventListener('click', function (e) { if (e.target === addOverlay) closeAddModal(); });

    // ── Edit buttons ────────────────────────────────────────────────
    document.querySelectorAll('.btn-edit-project').forEach(function (btn) {
        btn.addEventListener('click', function () {
            var projectId = this.getAttribute('data-project-id');
            var row = this.closest('tr');
            var code = row ? row.querySelector('td:nth-child(1)').textContent.trim() : '';
            var name = row ? row.querySelector('td:nth-child(2)').textContent.trim() : '';
            var managerId = row ? (row.querySelector('td:nth-child(3)').textContent.trim()) : '';
            var startDateText = row ? row.querySelector('td:nth-child(4)').textContent.trim() : '';
            var hours = row ? row.querySelector('td:nth-child(5)').textContent.trim() : '';
            // Convert displayed date back to YYYY-MM-DD for the input
            var startDate = '';
            if (startDateText && startDateText !== '—') {
                try { startDate = new Date(startDateText).toISOString().split('T')[0]; } catch(e) {}
            }
            openAddModal('edit', projectId, { code: code, name: name, startDate: startDate, hours: hours, managerId: managerId });
        });
    });

    if (addSaveBtn) {
        addSaveBtn.addEventListener('click', function () {
            var name = formName ? formName.value.trim() : '';
            var startDate = formStartDate ? formStartDate.value : '';
            var hours = formHours ? formHours.value : '';
            var manager = formManager ? formManager.value : '';

            if (!name) { formName.focus(); return; }
            if (!startDate) { formStartDate.focus(); return; }
            if (!hours) { formHours.focus(); return; }
            if (!manager) { formManager.focus(); return; }

            addSaveBtn.disabled = true;
            var url, method, body;

            if (editingProjectId) {
                url = '/admin/projects/' + encodeURIComponent(editingProjectId);
                method = 'PUT';
                body = { projectName: name, startDate: startDate, plannedHours: parseFloat(hours), projectManagerId: manager };
            } else {
                var code = formCode ? formCode.value.trim() : '';
                if (!code) { formCode.focus(); addSaveBtn.disabled = false; return; }
                url = '/admin/projects';
                method = 'POST';
                body = { projectCode: code, projectName: name, startDate: startDate, plannedHours: parseFloat(hours), projectManagerId: manager };
            }

            fetch(url, {
                method: method,
                headers: { 'Content-Type': 'application/json', 'Accept': 'application/json', 'X-CSRF-TOKEN': csrfToken() },
                body: JSON.stringify(body)
            })
            .then(function (res) { return res.json().then(function (data) { return { status: res.status, data: data }; }); })
            .then(function (result) {
                addSaveBtn.disabled = false;
                if (result.data.success) { closeAddModal(); showToast(editingProjectId ? 'Project updated.' : 'Project created.', 'success'); window.location.reload(); }
                else { closeAddModal(); showToast(result.data.error || 'Failed to save project.', 'error'); }
            })
            .catch(function () { addSaveBtn.disabled = false; closeAddModal(); showToast('Network error. Please try again.', 'error'); });
        });
    }

    // ── Delete buttons ──────────────────────────────────────────────
    document.querySelectorAll('.btn-delete-project').forEach(function (btn) {
        btn.addEventListener('click', function () {
            var projectId = this.getAttribute('data-project-id');
            var row = this.closest('tr');
            var projName = row ? row.querySelector('td:nth-child(2)').textContent.trim() : 'this project';
            if (!confirm('Are you sure you want to delete ' + projName + '?')) return;

            fetch('/admin/projects/' + encodeURIComponent(projectId), {
                method: 'DELETE',
                headers: { 'Content-Type': 'application/json', 'Accept': 'application/json', 'X-CSRF-TOKEN': csrfToken() }
            })
            .then(function (res) { return res.json().then(function (data) { return { status: res.status, data: data }; }); })
            .then(function (result) {
                if (result.data.success) { showToast('Project deleted.', 'success'); window.location.reload(); }
                else { showToast(result.data.error || 'Failed to delete project.', 'error'); }
            })
            .catch(function () { showToast('Network error. Please try again.', 'error'); });
        });
    });

    // ── Rejection Modal ─────────────────────────────────────────────
    function openRejectModal(projectId) {
        if (rejectOverlay) {
            rejectProjectIdInput.value = projectId;
            rejectReasonInput.value = '';
            rejectOverlay.classList.add('active');
        }
    }
    function closeRejectModal() { if (rejectOverlay) rejectOverlay.classList.remove('active'); }

    if (rejectCloseBtn) rejectCloseBtn.addEventListener('click', closeRejectModal);
    if (rejectCancelBtn) rejectCancelBtn.addEventListener('click', closeRejectModal);
    if (rejectOverlay) rejectOverlay.addEventListener('click', function (e) { if (e.target === rejectOverlay) closeRejectModal(); });

    if (rejectSubmitBtn) {
        rejectSubmitBtn.addEventListener('click', function () {
            var projectId = rejectProjectIdInput ? rejectProjectIdInput.value : '';
            var reason = rejectReasonInput ? rejectReasonInput.value.trim() : '';
            if (!reason) { rejectReasonInput.focus(); return; }

            rejectSubmitBtn.disabled = true;
            fetch('/admin/projects/' + encodeURIComponent(projectId) + '/reject', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'Accept': 'application/json', 'X-CSRF-TOKEN': csrfToken() },
                body: JSON.stringify({ reason: reason })
            })
            .then(function (res) { return res.json().then(function (data) { return { status: res.status, data: data }; }); })
            .then(function (result) {
                rejectSubmitBtn.disabled = false;
                if (result.data.success) { closeRejectModal(); showToast('Project rejected successfully.', 'success'); window.location.reload(); }
                else { closeRejectModal(); showToast(result.data.error || 'Failed to reject project.', 'error'); }
            })
            .catch(function () { rejectSubmitBtn.disabled = false; closeRejectModal(); showToast('Network error. Please try again.', 'error'); });
        });
    }

    // ── Approve action ──────────────────────────────────────────────
    document.querySelectorAll('.btn-approve-project').forEach(function (btn) {
        btn.addEventListener('click', function () {
            var projectId = this.getAttribute('data-project-id');
            if (!confirm('Are you sure you want to approve this project?')) return;

            btn.disabled = true;
            fetch('/admin/projects/' + encodeURIComponent(projectId) + '/approve', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'Accept': 'application/json', 'X-CSRF-TOKEN': csrfToken() }
            })
            .then(function (res) { return res.json().then(function (data) { return { status: res.status, data: data }; }); })
            .then(function (result) {
                btn.disabled = false;
                if (result.data.success) { showToast('Project approved successfully.', 'success'); window.location.reload(); }
                else { showToast(result.data.error || 'Failed to approve project.', 'error'); }
            })
            .catch(function () { btn.disabled = false; showToast('Network error. Please try again.', 'error'); });
        });
    });

    // ── Reject action (opens modal) ─────────────────────────────────
    document.querySelectorAll('.btn-reject-project').forEach(function (btn) {
        btn.addEventListener('click', function () {
            var projectId = this.getAttribute('data-project-id');
            openRejectModal(projectId);
        });
    });

    // ── Close modal on Escape ───────────────────────────────────────
    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape') {
            closeRejectModal();
            closeAddModal();
        }
    });
})();
</script>
@endpush
