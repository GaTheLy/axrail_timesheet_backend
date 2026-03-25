@extends('layouts.app')

@section('title', 'History — TimeFlow')

@section('content')
    {{-- Error state --}}
    @if(!empty($error))
        <div class="page-header">
            <h1 class="page-title">History</h1>
        </div>
        <div class="alert alert-error">
            {{ $error }}
        </div>
        <a href="/timesheet/history" class="btn btn-primary">Retry</a>
    @else
        {{-- Page header --}}
        <div class="page-header">
            <div>
                <h1 class="page-title">History</h1>
                <p style="color: #94a3b8; font-size: 0.875rem; margin-top: 0.25rem;">
                    Review your past timesheet entries
                </p>
            </div>
            <div class="page-actions">
                <a href="/timesheet" class="btn btn-secondary btn-sm">Back to Timesheet</a>
            </div>
        </div>

        {{-- Date range picker --}}
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
            <span id="entry-count-badge" class="badge badge-info">
                {{ $totalEntries }} {{ $totalEntries === 1 ? 'entry' : 'entries' }}
            </span>
        </div>

        {{-- Weekly total --}}
        <div style="display: flex; align-items: center; gap: 1rem; margin-bottom: 1.25rem;">
            <span style="font-size: 0.875rem; color: #94a3b8;">Total Hours:</span>
            <span id="weekly-total" style="font-size: 1.25rem; font-weight: 700; color: #f1f5f9;">
                {{ number_format($weeklyTotal, 1) }}h
            </span>
        </div>

        {{-- Entries table --}}
        @if(count($entries) > 0)
            <table class="data-table" id="history-table">
                <thead>
                    <tr>
                        <th>Date</th>
                        <th>Project</th>
                        <th>Description</th>
                        <th>Charged Hours</th>
                    </tr>
                </thead>
                <tbody id="history-table-body">
                    @foreach($entries as $entry)
                        <tr>
                            <td>{{ $entry['date'] ?? '' }}</td>
                            <td><span class="badge badge-info">{{ $entry['projectCode'] ?? '' }}</span></td>
                            <td>{{ $entry['description'] ?? '' }}</td>
                            <td>{{ number_format($entry['chargedHours'] ?? 0, 1) }}h</td>
                        </tr>
                    @endforeach
                </tbody>
            </table>
        @else
            <div id="empty-state" style="text-align: center; padding: 3rem 1rem; color: #94a3b8;">
                <p style="font-size: 0.9rem;">No history entries found.</p>
            </div>
        @endif
    @endif
@endsection

@push('scripts')
<script>
(function () {
    const startDateInput = document.getElementById('start-date');
    const endDateInput = document.getElementById('end-date');
    const entryCountBadge = document.getElementById('entry-count-badge');
    const weeklyTotalEl = document.getElementById('weekly-total');
    const tableBody = document.getElementById('history-table-body');
    const table = document.getElementById('history-table');
    const emptyState = document.getElementById('empty-state');
    const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || '';

    if (!startDateInput || !endDateInput) return;

    startDateInput.addEventListener('change', onDateRangeChange);
    endDateInput.addEventListener('change', onDateRangeChange);

    function onDateRangeChange() {
        const startDate = startDateInput.value;
        const endDate = endDateInput.value;

        if (!startDate || !endDate) return;
        if (startDate > endDate) return;

        fetchFilteredData(startDate, endDate);
    }

    function fetchFilteredData(startDate, endDate) {
        const overlay = document.getElementById('loading-overlay');
        if (overlay) overlay.style.display = 'flex';

        fetch('/timesheet/history/filter?start_date=' + encodeURIComponent(startDate) + '&end_date=' + encodeURIComponent(endDate), {
            method: 'GET',
            headers: {
                'Accept': 'application/json',
                'X-CSRF-TOKEN': csrfToken,
                'X-Requested-With': 'XMLHttpRequest'
            }
        })
        .then(function (response) { return response.json(); })
        .then(function (data) {
            if (overlay) overlay.style.display = 'none';

            if (data.success) {
                updateTable(data.data || []);
                updateCount(data.count || 0);
                updateWeeklyTotal(data.weeklyTotal || 0);
            } else if (data.error) {
                alert(data.error);
            }
        })
        .catch(function (err) {
            if (overlay) overlay.style.display = 'none';
            console.error('History filter error:', err);
        });
    }

    function updateTable(entries) {
        // Ensure table exists; create if needed
        if (entries.length > 0) {
            if (!table) {
                // Replace empty state with a new table
                var container = emptyState ? emptyState.parentNode : document.querySelector('.main-content');
                if (emptyState) emptyState.style.display = 'none';

                var newTable = document.createElement('table');
                newTable.className = 'data-table';
                newTable.id = 'history-table';
                newTable.innerHTML = '<thead><tr><th>Date</th><th>Project</th><th>Description</th><th>Charged Hours</th></tr></thead><tbody id="history-table-body"></tbody>';
                container.appendChild(newTable);

                renderRows(newTable.querySelector('tbody'), entries);
                return;
            }
        }

        var tbody = tableBody || document.getElementById('history-table-body');
        if (tbody) {
            renderRows(tbody, entries);
        }

        // Toggle visibility
        var tbl = table || document.getElementById('history-table');
        var empty = emptyState || document.getElementById('empty-state');
        if (entries.length === 0) {
            if (tbl) tbl.style.display = 'none';
            if (empty) {
                empty.style.display = '';
            } else {
                // Create empty state
                var div = document.createElement('div');
                div.id = 'empty-state';
                div.style.cssText = 'text-align: center; padding: 3rem 1rem; color: #94a3b8;';
                div.innerHTML = '<p style="font-size: 0.9rem;">No entries found for the selected date range.</p>';
                (tbl ? tbl.parentNode : document.querySelector('.main-content')).appendChild(div);
            }
        } else {
            if (tbl) tbl.style.display = '';
            if (empty) empty.style.display = 'none';
        }
    }

    function renderRows(tbody, entries) {
        var html = '';
        for (var i = 0; i < entries.length; i++) {
            var e = entries[i];
            var hours = parseFloat(e.chargedHours || 0).toFixed(1);
            html += '<tr>'
                + '<td>' + escapeHtml(e.date || '') + '</td>'
                + '<td><span class="badge badge-info">' + escapeHtml(e.projectCode || '') + '</span></td>'
                + '<td>' + escapeHtml(e.description || '') + '</td>'
                + '<td>' + hours + 'h</td>'
                + '</tr>';
        }
        tbody.innerHTML = html;
    }

    function updateCount(count) {
        if (entryCountBadge) {
            entryCountBadge.textContent = count + (count === 1 ? ' entry' : ' entries');
        }
    }

    function updateWeeklyTotal(total) {
        if (weeklyTotalEl) {
            weeklyTotalEl.textContent = parseFloat(total).toFixed(1) + 'h';
        }
    }

    function escapeHtml(str) {
        var div = document.createElement('div');
        div.appendChild(document.createTextNode(str));
        return div.innerHTML;
    }
})();
</script>
@endpush
