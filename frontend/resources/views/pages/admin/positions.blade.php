@extends('layouts.app')

@section('title', 'Position Management — TimeFlow')

@section('content')
    @php
        $userType = session('user.userType', 'user');
        
        // Build lookup map for displaying department names instead of IDs
        $departmentMap = collect($departments ?? [])->pluck('departmentName', 'departmentId')->toArray();
    @endphp

    <nav class="breadcrumb" aria-label="Breadcrumb">
        <a href="/admin/positions">Master Data</a>
        <span class="separator" aria-hidden="true">/</span>
        <span class="current">Positions</span>
    </nav>

    <div class="page-header">
        <h1 class="page-title">Position Management</h1>
        <div class="page-actions">
            @if($userType === 'superadmin' || $userType === 'admin')
                <button type="button" class="btn btn-primary" id="btn-add-position">
                    + New Position
                </button>
            @else
                <button type="button" class="btn btn-primary" disabled style="opacity: 0.5; cursor: not-allowed;" title="Only admin and superadmin can create positions">
                    + New Position
                </button>
            @endif
        </div>
    </div>

    @if(!empty($error))
        <div class="alert alert-error">{{ $error }}</div>
    @else
        <div class="filter-bar">
            <input type="text" id="search-input" class="search-input" placeholder="Search by position..." aria-label="Search">
            <select id="approval-status-filter" aria-label="Filter by approval status">
                <option value="">All</option>
                <option value="Pending_Approval">Pending_Approval</option>
                <option value="Approved">Approved</option>
                <option value="Rejected">Rejected</option>
            </select>
        </div>

        @if(count($positions) > 0)
            <table class="data-table" id="report-table">
                <thead>
                    <tr>
                        <th>POSITION</th>
                        <th>DEPARTMENT</th>
                        <th>CREATED BY</th>
                        <th>CREATED AT</th>
                        <th>APPROVAL STATUS</th>
                        <th>ACTIONS</th>
                    </tr>
                </thead>
                <tbody>

                    @foreach($positions as $pos)
                        @php
                            $approvalStatus = $pos['approval_status'] ?? 'Approved';
                            $rejectionReason = $pos['rejectionReason'] ?? '';
                            $positionId = $pos['positionId'] ?? '';
                        @endphp
                        <tr data-position-id="{{ $positionId }}" data-approval-status="{{ $approvalStatus }}">
                            <td><strong>{{ $pos['positionName'] ?? '' }}</strong></td>
                            <td>{{ $departmentMap[$pos['departmentId'] ?? ''] ?? '—' }}</td>
                            <td>{{ ($userMap ?? [])[$pos['createdBy'] ?? ''] ?? 'Unknown User' }}</td>
                            <td>{{ isset($pos['createdAt']) ? \Carbon\Carbon::parse($pos['createdAt'])->format('M d, Y') : '—' }}</td>
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
                                @if($approvalStatus !== 'Approved' || $userType === 'superadmin')
                                    <button type="button" class="btn btn-secondary btn-sm btn-edit-pos" data-position-id="{{ $positionId }}" aria-label="Edit position {{ $pos['positionName'] ?? '' }}">
                                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                                            <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path>
                                            <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path>
                                        </svg>
                                    </button>
                                    <button type="button" class="btn btn-danger btn-sm btn-delete-pos" data-position-id="{{ $positionId }}" aria-label="Delete position {{ $pos['positionName'] ?? '' }}">
                                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                                            <polyline points="3 6 5 6 21 6"></polyline>
                                            <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
                                        </svg>
                                    </button>

                                @else
                                    <span style="color: #64748b; font-size: 0.75rem;">—</span>
                                @endif
                            </td>
                        </tr>
                    @endforeach
                </tbody>
            </table>

            <div class="pagination">
                <span class="pagination-info">Showing {{ count($positions) }} of {{ count($positions) }} positions</span>
                <div class="pagination-pages" id="pagination-controls"></div>
            </div>
        @else
            <div style="text-align: center; padding: 3rem 1rem; color: #94a3b8;">
                <p>No positions found.</p>
            </div>
        @endif
    @endif


    {{-- Add Position Modal --}}
    <div class="modal-overlay" id="pos-modal-overlay">
        <div class="modal" role="dialog" aria-labelledby="pos-modal-title" aria-modal="true">
            <div class="modal-header">
                <h3 id="pos-modal-title">Add Position</h3>
                <button type="button" class="modal-close" id="pos-modal-close" aria-label="Close modal">&times;</button>
            </div>
            <div class="modal-body">
                <form id="pos-form" novalidate>
                    <div class="form-group">
                        <label for="pos-form-name">Position Name</label>
                        <input type="text" id="pos-form-name" placeholder="Enter position name" required aria-label="Position name">
                    </div>
                    <div class="form-group">
                        <label for="pos-form-dept">Department</label>
                        <select id="pos-form-dept" required aria-label="Department">
                            <option value="">Select Department</option>
                            @foreach($departments ?? [] as $dept)
                                <option value="{{ $dept['departmentId'] }}">{{ $dept['departmentName'] }}</option>
                            @endforeach
                        </select>
                    </div>
                </form>
            </div>
            <div class="modal-footer">
                <button type="button" class="btn btn-secondary" id="pos-modal-cancel">Cancel</button>
                <button type="button" class="btn btn-primary" id="pos-modal-save">Save Changes</button>
            </div>
        </div>
    </div>


@endsection


@push('scripts')
<script>
(function () {
    // ── DOM references ──────────────────────────────────────────────
    var overlay = document.getElementById('pos-modal-overlay');
    var closeBtn = document.getElementById('pos-modal-close');
    var cancelBtn = document.getElementById('pos-modal-cancel');
    var saveBtn = document.getElementById('pos-modal-save');
    var addBtn = document.getElementById('btn-add-position');
    var nameInput = document.getElementById('pos-form-name');
    var descInput = document.getElementById('pos-form-dept');

    var approvalFilter = document.getElementById('approval-status-filter');
    var searchInput = document.getElementById('search-input');

    // ── CSRF helper ─────────────────────────────────────────────────
    function csrfToken() {
        var meta = document.querySelector('meta[name="csrf-token"]');
        return meta ? meta.content : '';
    }

    // ── Toast notification ──────────────────────────────────────────
    function showToast(message, type) {
        var existing = document.getElementById('pos-toast');
        if (existing) existing.remove();
        var toast = document.createElement('div');
        toast.id = 'pos-toast';
        toast.setAttribute('role', 'alert');
        toast.style.cssText = 'position:fixed;top:1rem;right:1rem;z-index:10000;padding:0.75rem 1.25rem;border-radius:0.375rem;font-size:0.875rem;max-width:28rem;box-shadow:0 4px 12px rgba(0,0,0,0.15);transition:opacity 0.3s;';
        toast.style.backgroundColor = type === 'error' ? '#fef2f2' : '#f0fdf4';
        toast.style.color = type === 'error' ? '#991b1b' : '#166534';
        toast.style.border = '1px solid ' + (type === 'error' ? '#fecaca' : '#bbf7d0');
        toast.textContent = message;
        document.body.appendChild(toast);
        setTimeout(function () { toast.style.opacity = '0'; setTimeout(function () { if (toast.parentNode) toast.remove(); }, 300); }, 5000);
    }


    // ── Add/Edit Position Modal ────────────────────────────────────
    var editingPosId = null;
    var modalTitle = document.getElementById('pos-modal-title');

    function openModal(mode, posId, posName, posDept) {
        if (!overlay) return;
        if (mode === 'edit') {
            editingPosId = posId;
            modalTitle.textContent = 'Edit Position';
            nameInput.value = posName || '';
            if (descInput) descInput.value = posDept || '';
        } else {
            editingPosId = null;
            modalTitle.textContent = 'Add Position';
            nameInput.value = '';
            if (descInput) descInput.value = '';
        }
        overlay.classList.add('active');
    }
    function closeModal() { if (overlay) overlay.classList.remove('active'); }

    if (addBtn) addBtn.addEventListener('click', function () { openModal('add'); });
    if (closeBtn) closeBtn.addEventListener('click', closeModal);
    if (cancelBtn) cancelBtn.addEventListener('click', closeModal);
    if (overlay) overlay.addEventListener('click', function (e) { if (e.target === overlay) closeModal(); });

    // ── Edit buttons ────────────────────────────────────────────────
    document.querySelectorAll('.btn-edit-pos').forEach(function (btn) {
        btn.addEventListener('click', function () {
            var posId = this.getAttribute('data-position-id');
            var row = this.closest('tr');
            var posName = row ? row.querySelector('td:nth-child(1)').textContent.trim() : '';
            var posDept = row ? row.querySelector('td:nth-child(2)').textContent.trim() : '';
            if (posDept === '—') posDept = '';
            openModal('edit', posId, posName, posDept);
        });
    });

    if (saveBtn) {
        saveBtn.addEventListener('click', function () {
            var name = nameInput ? nameInput.value.trim() : '';
            if (!name) {
                nameInput.setCustomValidity('Fill out this field');
                nameInput.reportValidity();
                return;
            }
            nameInput.setCustomValidity('');
            var body = { positionName: name };
            var dept = descInput ? descInput.value.trim() : '';
            if (!dept) {
                descInput.setCustomValidity('Fill out this field');
                descInput.reportValidity();
                return;
            }
            descInput.setCustomValidity('');
            body.departmentId = dept;

            saveBtn.disabled = true;
            var url, method;
            if (editingPosId) {
                url = '/admin/positions/' + encodeURIComponent(editingPosId);
                method = 'PUT';
            } else {
                url = '/admin/positions';
                method = 'POST';
            }

            fetch(url, {
                method: method,
                headers: { 'Content-Type': 'application/json', 'Accept': 'application/json', 'X-CSRF-TOKEN': csrfToken() },
                body: JSON.stringify(body)
            })
            .then(function (res) { return res.json().then(function (data) { return { status: res.status, data: data }; }); })
            .then(function (result) {
                saveBtn.disabled = false;
                if (result.data.success) {
                    closeModal();
                    var action = editingPosId ? 'updated' : 'created';
                    showToast('Position ' + action + ' successfully.', 'success');
                    setTimeout(function () { window.location.reload(); }, 1500);
                } else {
                    closeModal();
                    var defaultMsg = editingPosId ? 'Failed to update position.' : 'Failed to create position.';
                    showToast(result.data.error || defaultMsg, 'error');
                }
            })
            .catch(function () { saveBtn.disabled = false; closeModal(); showToast('Network error. Please try again.', 'error'); });
        });
    }

    // ── Delete action ───────────────────────────────────────────────
    document.querySelectorAll('.btn-delete-pos').forEach(function (btn) {
        btn.addEventListener('click', function () {
            var positionId = this.getAttribute('data-position-id');
            var row = this.closest('tr');
            var posName = row ? row.querySelector('td:nth-child(1)').textContent.trim() : 'this position';
            if (!confirm('Are you sure you want to delete ' + posName + '?')) return;

            fetch('/admin/positions/' + encodeURIComponent(positionId), {
                method: 'DELETE',
                headers: { 'Content-Type': 'application/json', 'Accept': 'application/json', 'X-CSRF-TOKEN': csrfToken() }
            })
            .then(function (res) { return res.json().then(function (data) { return { status: res.status, data: data }; }); })
            .then(function (result) {
                if (result.data.success) {
                    showToast('Position deleted successfully.', 'success');
                    setTimeout(function () { window.location.reload(); }, 1500);
                } else {
                    showToast(result.data.error || 'Failed to delete position.', 'error');
                }
            })
            .catch(function () { showToast('Network error. Please try again.', 'error'); });
        });
    });

    // ── Client-side approval status filter ──────────────────────────
    function applyFilters() {
        var filterValue = approvalFilter ? approvalFilter.value : '';
        var searchValue = searchInput ? searchInput.value.trim().toLowerCase() : '';
        var rows = document.querySelectorAll('#report-table tbody tr');

        rows.forEach(function (row) {
            var rowStatus = row.getAttribute('data-approval-status') || '';
            var rowText = row.textContent.toLowerCase();
            var matchesFilter = !filterValue || rowStatus === filterValue;
            var matchesSearch = !searchValue || rowText.indexOf(searchValue) !== -1;
            row.style.display = (matchesFilter && matchesSearch) ? '' : 'none';
        });
    }

    if (approvalFilter) approvalFilter.addEventListener('change', applyFilters);
    if (searchInput) searchInput.addEventListener('input', applyFilters);

    // ── Close modals on Escape ──────────────────────────────────────
    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape') {
            closeModal();
        }
    });
})();
</script>
@endpush