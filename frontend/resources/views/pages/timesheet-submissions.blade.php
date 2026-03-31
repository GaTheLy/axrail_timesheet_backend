@extends('layouts.app')

@section('title', 'Timesheet Submissions — TimeFlow')

@section('content')
    {{-- Error state --}}
    @if(!empty($error))
        <div class="page-header">
            <h1 class="page-title">Timesheet Submissions</h1>
        </div>
        <div class="alert alert-error">
            {{ $error }}
        </div>
        <a href="/timesheet" class="btn btn-primary">Retry</a>
    @else
        {{-- Page header --}}
        <div class="page-header">
            <h1 class="page-title">Timesheet Submissions</h1>
        </div>

        {{-- Filter bar --}}
        <div class="filter-bar">
            <div style="display: flex; align-items: center; gap: 0.5rem;">
                <label for="start-date" style="font-size: 0.8rem; font-weight: 600; color: #94a3b8;">From</label>
                <input
                    type="date"
                    id="start-date"
                    class="search-input"
                    style="min-width: 160px; flex: none;"
                    aria-label="Start date"
                >
            </div>
            <div style="display: flex; align-items: center; gap: 0.5rem;">
                <label for="end-date" style="font-size: 0.8rem; font-weight: 600; color: #94a3b8;">To</label>
                <input
                    type="date"
                    id="end-date"
                    class="search-input"
                    style="min-width: 160px; flex: none;"
                    aria-label="End date"
                >
            </div>

            <select id="user-filter" aria-label="Filter by user">
                <option value="">All Users</option>
                @foreach($users as $user)
                    <option value="{{ $user['userId'] ?? '' }}">{{ $user['fullName'] ?? $user['userId'] ?? '' }}</option>
                @endforeach
            </select>

            <select id="status-filter" aria-label="Filter by status">
                <option value="">All Status</option>
                <option value="Draft">Draft</option>
                <option value="Submitted">Submitted</option>
            </select>
        </div>

        {{-- Submissions table --}}
        @if(count($submissions) > 0)
            <table class="data-table" id="submissions-table">
                <thead>
                    <tr>
                        <th>Week Period</th>
                        <th>User Name</th>
                        <th>Total Hours</th>
                        <th>Status</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody id="submissions-table-body">
                    @foreach($submissions as $submission)
                        @php
                            $employeeId = $submission['employeeId'] ?? '';
                            $userName = $userMap[$employeeId] ?? 'Unknown User';
                            $periodId = $submission['periodId'] ?? '';
                            $periodString = $periodMap[$periodId] ?? $periodId;
                            $status = $submission['status'] ?? '';
                            $submissionEntries = $submission['entries'] ?? [];
                            $computedTotal = 0;
                            foreach ($submissionEntries as $e) {
                                $computedTotal += floatval($e['totalHours'] ?? 0);
                            }
                            $totalHours = $computedTotal > 0 ? $computedTotal : floatval($submission['totalHours'] ?? 0);
                            $submissionId = $submission['submissionId'] ?? '';
                        @endphp
                        <tr
                            class="submission-row"
                            data-period="{{ $periodId }}"
                            data-employee="{{ $employeeId }}"
                            data-status="{{ $status }}"
                        >
                            <td>{{ $periodString }}</td>
                            <td>{{ $userName }}</td>
                            <td>{{ number_format($totalHours, 1) }}h</td>
                            <td>
                                @if($status === 'Submitted')
                                    <span class="badge badge-success">Submitted</span>
                                @elseif($status === 'Draft')
                                    <span class="badge badge-danger">Draft</span>
                                @else
                                    <span class="badge badge-info">{{ $status }}</span>
                                @endif
                            </td>
                            <td>
                                <a
                                    href="/timesheet/submissions/{{ $submissionId }}"
                                    class="btn btn-secondary btn-sm"
                                    aria-label="View submission for {{ $userName }} — {{ $periodString }}"
                                >
                                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                                        <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path>
                                        <circle cx="12" cy="12" r="3"></circle>
                                    </svg>
                                </a>
                            </td>
                        </tr>
                    @endforeach
                </tbody>
            </table>
        @else
            <div id="empty-state" style="text-align: center; padding: 3rem 1rem; color: #94a3b8;">
                <p style="font-size: 0.9rem;">No timesheet submissions found.</p>
            </div>
        @endif
    @endif
@endsection

@push('scripts')
<script>
(function () {
    var startDateInput = document.getElementById('start-date');
    var endDateInput = document.getElementById('end-date');
    var userFilter = document.getElementById('user-filter');
    var statusFilter = document.getElementById('status-filter');
    var rows = document.querySelectorAll('.submission-row');
    var table = document.getElementById('submissions-table');
    var emptyState = document.getElementById('empty-state');

    if (!startDateInput || !endDateInput || !userFilter || !statusFilter) return;

    // Set default date range to current week (Saturday to Friday)
    var today = new Date();
    var dayOfWeek = today.getDay(); // 0=Sun, 6=Sat
    // Calculate Saturday start: go back to the most recent Saturday
    var satOffset = (dayOfWeek + 1) % 7; // days since last Saturday
    var saturday = new Date(today);
    saturday.setDate(today.getDate() - satOffset);
    var friday = new Date(saturday);
    friday.setDate(saturday.getDate() + 6);

    startDateInput.value = formatDate(saturday);
    endDateInput.value = formatDate(friday);

    // Build a lookup of periodId → { startDate, endDate } from server data
    var periodLookup = {};
    @foreach($periods as $period)
        periodLookup['{{ $period['periodId'] ?? '' }}'] = {
            startDate: '{{ $period['startDate'] ?? '' }}',
            endDate: '{{ $period['endDate'] ?? '' }}'
        };
    @endforeach

    startDateInput.addEventListener('change', applyFilters);
    endDateInput.addEventListener('change', applyFilters);
    userFilter.addEventListener('change', applyFilters);
    statusFilter.addEventListener('change', applyFilters);

    // Apply initial filter
    applyFilters();

    function applyFilters() {
        var startDate = startDateInput.value;
        var endDate = endDateInput.value;
        var selectedUser = userFilter.value;
        var selectedStatus = statusFilter.value;
        var visibleCount = 0;

        for (var i = 0; i < rows.length; i++) {
            var row = rows[i];
            var periodId = row.getAttribute('data-period');
            var employee = row.getAttribute('data-employee');
            var status = row.getAttribute('data-status');
            var show = true;

            // Date range filter
            if (startDate && endDate && periodId && periodLookup[periodId]) {
                var pStart = periodLookup[periodId].startDate;
                var pEnd = periodLookup[periodId].endDate;
                // Show if period overlaps with selected range
                if (pEnd < startDate || pStart > endDate) {
                    show = false;
                }
            }

            // User filter
            if (show && selectedUser && employee !== selectedUser) {
                show = false;
            }

            // Status filter
            if (show && selectedStatus && status !== selectedStatus) {
                show = false;
            }

            row.style.display = show ? '' : 'none';
            if (show) visibleCount++;
        }

        // Toggle empty state
        if (table) table.style.display = visibleCount > 0 ? '' : 'none';
        if (emptyState) {
            emptyState.style.display = visibleCount > 0 ? 'none' : '';
            emptyState.innerHTML = '<p style="font-size: 0.9rem;">No timesheet submissions match the selected filters.</p>';
        } else if (visibleCount === 0 && table) {
            var div = document.createElement('div');
            div.id = 'empty-state';
            div.style.cssText = 'text-align: center; padding: 3rem 1rem; color: #94a3b8;';
            div.innerHTML = '<p style="font-size: 0.9rem;">No timesheet submissions match the selected filters.</p>';
            table.parentNode.insertBefore(div, table.nextSibling);
            emptyState = div;
        }
    }

    function formatDate(date) {
        var y = date.getFullYear();
        var m = String(date.getMonth() + 1).padStart(2, '0');
        var d = String(date.getDate()).padStart(2, '0');
        return y + '-' + m + '-' + d;
    }
})();
</script>
@endpush
