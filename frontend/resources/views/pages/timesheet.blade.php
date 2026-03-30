@extends('layouts.app')

@section('title', 'Timesheet — TimeFlow')

@section('content')
    {{-- Error state --}}
    @if(!empty($error))
        <div class="page-header">
            <h1 class="page-title">Timesheet</h1>
        </div>
        <div class="alert alert-error">
            {{ $error }}
        </div>
        <a href="/timesheet" class="btn btn-primary">Retry</a>
    @else
        @php
            $isSubmitted = ($submission['status'] ?? '') === 'Submitted';
            $startFormatted = $period ? \Carbon\Carbon::parse($period['startDate'])->format('D, M j') : '';
            $endFormatted = $period ? \Carbon\Carbon::parse($period['endDate'])->format('D, M j') : '';
        @endphp

        {{-- Page header with week range and actions --}}
        <div class="page-header">
            <div>
                <h1 class="page-title">Timesheet</h1>
                @if($period)
                    <p style="color: #94a3b8; font-size: 0.875rem; margin-top: 0.25rem;">
                        {{ $startFormatted }} &ndash; {{ $endFormatted }}
                    </p>
                @endif
            </div>
            <div class="page-actions">
                @include('components.countdown', ['countdown' => $countdown])
                @if($isSubmitted)
                    <span class="badge badge-success">Submitted</span>
                @endif
                <a href="/timesheet/history" class="btn btn-secondary btn-sm">History</a>
                @if(!$isSubmitted)
                    <button type="button" id="btn-new-entry" class="btn btn-primary btn-sm">+ New Entry</button>
                @endif
            </div>
        </div>

        {{-- Weekly total --}}
        <div style="display: flex; align-items: center; gap: 1rem; margin-bottom: 1.25rem;">
            <span style="font-size: 0.875rem; color: #94a3b8;">Weekly Total:</span>
            <span style="font-size: 1.25rem; font-weight: 700; color: {{ $weeklyTotal >= 40 ? '#22c55e' : '#f1f5f9' }};">
                {{ number_format($weeklyTotal, 1) }}h
            </span>
            <span style="font-size: 0.8rem; color: #64748b;">/ 40h target</span>
        </div>

        {{-- Search and filter bar --}}
        <div class="filter-bar">
            <input
                type="text"
                id="search-input"
                class="search-input"
                placeholder="Search by project code or description…"
                aria-label="Search entries"
            >
            <select id="project-filter" aria-label="Filter by project">
                <option value="">All Projects</option>
                @php
                    $projectCodes = collect($entries)->pluck('projectCode')->unique()->sort()->values();
                @endphp
                @foreach($projectCodes as $code)
                    <option value="{{ $code }}">{{ $code }}</option>
                @endforeach
            </select>
        </div>

        {{-- Entries table --}}
        @if(count($entries) > 0)
            <table class="data-table" id="entries-table">
                <thead>
                    <tr>
                        <th>Date</th>
                        <th>Project Code</th>
                        <th>Description</th>
                        <th>Charged Hours</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody>
                    @foreach($entries as $entry)
                        <tr
                            class="entry-row"
                            data-project-code="{{ $entry['projectCode'] ?? '' }}"
                            data-description="{{ $entry['description'] ?? '' }}"
                        >
                            <td>{{ $entry['date'] ?? '' }}</td>
                            <td><span class="badge badge-info">{{ $entry['projectCode'] ?? '' }}</span></td>
                            <td>{{ $entry['description'] ?? '' }}</td>
                            <td>{{ number_format($entry['chargedHours'] ?? 0, 1) }}h</td>
                            <td>
                                @if(!empty($entry['isEditable']) && !$isSubmitted)
                                    <button
                                        type="button"
                                        class="btn btn-secondary btn-sm btn-edit-entry"
                                        data-entry-id="{{ $entry['entryId'] ?? '' }}"
                                        data-date="{{ $entry['date'] ?? '' }}"
                                        data-project-code="{{ $entry['projectCode'] ?? '' }}"
                                        data-hours="{{ $entry['chargedHours'] ?? 0 }}"
                                        data-description="{{ $entry['description'] ?? '' }}"
                                        aria-label="Edit entry for {{ $entry['projectCode'] ?? '' }} on {{ $entry['date'] ?? '' }}"
                                    >
                                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                                            <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path>
                                            <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path>
                                        </svg>
                                    </button>
                                    <button
                                        type="button"
                                        class="btn btn-danger btn-sm btn-delete-entry"
                                        data-entry-id="{{ $entry['entryId'] ?? '' }}"
                                        data-date="{{ $entry['date'] ?? '' }}"
                                        data-project-code="{{ $entry['projectCode'] ?? '' }}"
                                        data-hours="{{ $entry['chargedHours'] ?? 0 }}"
                                        data-description="{{ $entry['description'] ?? '' }}"
                                        aria-label="Delete entry for {{ $entry['projectCode'] ?? '' }} on {{ $entry['date'] ?? '' }}"
                                    >
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
        @else
            <div style="text-align: center; padding: 3rem 1rem; color: #94a3b8;">
                <p style="font-size: 0.9rem; margin-bottom: 0.5rem;">No time entries for this period yet.</p>
                @if(!$isSubmitted)
                    <p style="font-size: 0.8rem;">Click "+ New Entry" to add your first entry.</p>
                @endif
            </div>
        @endif
    @endif

    {{-- Entry modal (created in task 7.3) --}}
    @includeIf('components.entry-modal')
@endsection

@push('scripts')
    <script>
        window.timesheetPeriod = {
            startDate: '{{ $period['startDate'] ?? '' }}',
            endDate: '{{ $period['endDate'] ?? '' }}'
        };
    </script>
    <script src="{{ asset('js/timesheet.js') }}"></script>
@endpush
