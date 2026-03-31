@extends('layouts.app')

@section('title', 'Submission Summary — TimeFlow')

@section('content')
    {{-- Breadcrumb --}}
    <nav class="breadcrumb" aria-label="Breadcrumb">
        <a href="/reports/submission-summary">Reports</a>
        <span class="separator" aria-hidden="true">/</span>
        <span class="current">Submission Summary</span>
    </nav>

    {{-- Page header with title and export button --}}
    <div class="page-header">
        <h1 class="page-title">Submission Summary Report</h1>
        <div class="page-actions">
            <button class="btn-export" id="export-pdf-btn" {{ !empty($error) ? 'disabled' : '' }}>
                <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                    <polyline points="7 10 12 15 17 10"></polyline>
                    <line x1="12" y1="15" x2="12" y2="3"></line>
                </svg>
                Export PDF
            </button>
        </div>
    </div>

    {{-- Error state --}}
    @if(!empty($error))
        <div class="alert alert-error">
            {{ $error }}
        </div>
        <a href="/reports/submission-summary" class="btn btn-primary">Retry</a>
    @else
        {{-- Filter bar --}}
        <div class="filter-bar">
            <input
                type="text"
                id="search-input"
                class="search-input"
                placeholder="Search by employee name"
                aria-label="Search by employee name"
            >
            <select id="period-select" aria-label="Select period">
                @foreach($periods as $period)
                    <option value="{{ $period['periodId'] }}" {{ ($period['periodId'] ?? '') == $selectedPeriodId ? 'selected' : '' }}>
                        {{ $period['periodString'] ?? ($period['startDate'] . ' – ' . $period['endDate']) }}
                    </option>
                @endforeach
            </select>
            <select id="status-select" aria-label="Filter by status">
                <option value="">All Status</option>
                <option value="submitted">Submitted</option>
                <option value="approved">Approved</option>
                <option value="rejected">Rejected</option>
                <option value="pending">Pending</option>
            </select>
            <select id="completeness-filter" aria-label="Filter by completeness">
                <option value="all" selected>All Submissions</option>
                <option value="complete">Complete</option>
                <option value="incomplete">Incomplete</option>
            </select>
        </div>

        {{-- Loading spinner --}}
        <div id="loading-spinner" class="loading-spinner" style="display: none;">
            <div class="spinner"></div>
            <span class="loading-text">Loading&hellip;</span>
        </div>

        @if(count($submissionRows) === 0)
            <p style="color: #94a3b8; font-size: 0.875rem; margin-top: 1rem;">No data found for the selected period.</p>
        @else
            {{-- Data table --}}
            <table class="data-table" id="report-table">
                <thead>
                    <tr>
                        <th>NAME</th>
                        <th>CHARGEABLE HOURS</th>
                        <th>TOTAL HOURS</th>
                        <th>CURRENT PERIOD CHARGEABILITY (%)</th>
                        <th>YTD CHARGEABILITY (%)</th>
                    </tr>
                </thead>
                <tbody>
                    @foreach($submissionRows as $row)
                        @php
                            $currentChg = $row['currentChargeability'];
                            if ($currentChg < 50) {
                                $currentColorClass = 'progress-yellow';
                            } elseif ($currentChg <= 100) {
                                $currentColorClass = 'progress-green';
                            } else {
                                $currentColorClass = 'progress-red';
                            }

                            $ytdChg = $row['ytdChargeability'];
                            if ($ytdChg < 50) {
                                $ytdColorClass = 'progress-yellow';
                            } elseif ($ytdChg <= 100) {
                                $ytdColorClass = 'progress-green';
                            } else {
                                $ytdColorClass = 'progress-red';
                            }
                        @endphp
                        <tr data-searchable="{{ strtolower($row['employeeName']) }}" data-status="{{ strtolower($row['status']) }}" data-total-hours="{{ $row['totalHours'] }}">
                            <td>{{ $row['employeeName'] }}</td>
                            <td>{{ number_format($row['chargeableHours'], 1) }}</td>
                            <td>{{ number_format($row['totalHours'], 1) }}</td>
                            <td>
                                <span>{{ number_format($currentChg, 1) }}%</span>
                                <div class="progress-bar {{ $currentColorClass }}">
                                    <div class="progress-bar-fill" style="width: {{ min($currentChg, 100) }}%"></div>
                                </div>
                            </td>
                            <td>
                                <span>{{ number_format($ytdChg, 1) }}%</span>
                                <div class="progress-bar {{ $ytdColorClass }}">
                                    <div class="progress-bar-fill" style="width: {{ min($ytdChg, 100) }}%"></div>
                                </div>
                            </td>
                        </tr>
                    @endforeach
                </tbody>
                <tfoot>
                    <tr class="totals-row">
                        <td><strong>Totals</strong></td>
                        <td>{{ number_format($totals['totalChargeableHours'], 1) }}</td>
                        <td>{{ number_format($totals['totalTotalHours'], 1) }}</td>
                        <td>
                            @php
                                $overallChg = $totals['overallChargeability'];
                                if ($overallChg < 50) {
                                    $totalCurrentColorClass = 'progress-yellow';
                                } elseif ($overallChg <= 100) {
                                    $totalCurrentColorClass = 'progress-green';
                                } else {
                                    $totalCurrentColorClass = 'progress-red';
                                }
                            @endphp
                            <span>{{ number_format($overallChg, 1) }}%</span>
                            <div class="progress-bar {{ $totalCurrentColorClass }}">
                                <div class="progress-bar-fill" style="width: {{ min($overallChg, 100) }}%"></div>
                            </div>
                        </td>
                        <td>
                            @php
                                $overallYtd = $totals['overallChargeability'];
                                if ($overallYtd < 50) {
                                    $totalYtdColorClass = 'progress-yellow';
                                } elseif ($overallYtd <= 100) {
                                    $totalYtdColorClass = 'progress-green';
                                } else {
                                    $totalYtdColorClass = 'progress-red';
                                }
                            @endphp
                            <span>{{ number_format($overallYtd, 1) }}%</span>
                            <div class="progress-bar {{ $totalYtdColorClass }}">
                                <div class="progress-bar-fill" style="width: {{ min($overallYtd, 100) }}%"></div>
                            </div>
                        </td>
                    </tr>
                </tfoot>
            </table>

            {{-- Pagination --}}
            <div class="pagination">
                <span class="pagination-info">Showing {{ count($submissionRows) }} of {{ count($submissionRows) }} submissions</span>
                <div class="pagination-pages" id="pagination-controls"></div>
            </div>
        @endif
    @endif
@endsection

@push('scripts')
<script src="https://unpkg.com/jspdf@latest/dist/jspdf.umd.min.js"></script>
<script src="https://unpkg.com/jspdf-autotable@latest/dist/jspdf.plugin.autotable.min.js"></script>
<script src="{{ asset('js/reports.js') }}"></script>
@endpush
