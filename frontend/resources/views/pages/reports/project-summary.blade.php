@extends('layouts.app')

@section('title', 'Project Summary — TimeFlow')

@section('content')
    {{-- Breadcrumb --}}
    <nav class="breadcrumb" aria-label="Breadcrumb">
        <a href="/reports/project-summary">Reports</a>
        <span class="separator" aria-hidden="true">/</span>
        <span class="current">Project Summary</span>
    </nav>

    {{-- Page header with title and export button --}}
    <div class="page-header">
        <h1 class="page-title">Project Summary Report</h1>
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
        <a href="/reports/project-summary" class="btn btn-primary">Retry</a>
    @else
        {{-- Filter bar --}}
        <div class="filter-bar">
            <input
                type="text"
                id="search-input"
                class="search-input"
                placeholder="Search by project code or name"
                aria-label="Search by project code or name"
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
                <option value="active">Active</option>
                <option value="inactive">Inactive</option>
            </select>
        </div>

        {{-- Loading spinner --}}
        <div id="loading-spinner" class="loading-spinner" style="display: none;">
            <div class="spinner"></div>
            <span class="loading-text">Loading&hellip;</span>
        </div>

        @if(count($projectRows) === 0)
            <p style="color: #94a3b8; font-size: 0.875rem; margin-top: 1rem;">No data found for the selected period.</p>
        @else
            {{-- Data table --}}
            <table class="data-table" id="report-table">
                <thead>
                    <tr>
                        <th>PROJECT CODE</th>
                        <th>PROJECT NAME</th>
                        <th>PLANNED HOURS</th>
                        <th>CHARGED HOURS</th>
                        <th>UTILIZATION (%)</th>
                    </tr>
                </thead>
                <tbody>
                    @foreach($projectRows as $row)
                        @php
                            $util = $row['utilizationPercent'];
                            if ($util < 50) {
                                $colorClass = 'progress-yellow';
                            } elseif ($util <= 100) {
                                $colorClass = 'progress-green';
                            } else {
                                $colorClass = 'progress-red';
                            }
                        @endphp
                        <tr data-searchable="{{ strtolower($row['projectCode'] . ' ' . $row['projectName']) }}" data-status="{{ strtolower($row['status']) }}">
                            <td>{{ $row['projectCode'] }}</td>
                            <td>{{ $row['projectName'] }}</td>
                            <td>{{ number_format($row['plannedHours'], 1) }}</td>
                            <td>{{ number_format($row['chargedHours'], 1) }}</td>
                            <td>
                                <span>{{ number_format($util, 1) }}%</span>
                                <div class="progress-bar {{ $colorClass }}">
                                    <div class="progress-bar-fill" style="width: {{ min($util, 100) }}%"></div>
                                </div>
                            </td>
                        </tr>
                    @endforeach
                </tbody>
                <tfoot>
                    <tr class="totals-row">
                        <td colspan="2"><strong>Totals</strong></td>
                        <td>{{ number_format($totals['totalPlannedHours'], 1) }}</td>
                        <td>{{ number_format($totals['totalChargedHours'], 1) }}</td>
                        <td>
                            @php
                                $overallUtil = $totals['overallUtilization'];
                                if ($overallUtil < 50) {
                                    $totalColorClass = 'progress-yellow';
                                } elseif ($overallUtil <= 100) {
                                    $totalColorClass = 'progress-green';
                                } else {
                                    $totalColorClass = 'progress-red';
                                }
                            @endphp
                            <span>{{ number_format($overallUtil, 1) }}%</span>
                            <div class="progress-bar {{ $totalColorClass }}">
                                <div class="progress-bar-fill" style="width: {{ min($overallUtil, 100) }}%"></div>
                            </div>
                        </td>
                    </tr>
                </tfoot>
            </table>

            {{-- Pagination --}}
            <div class="pagination">
                <span class="pagination-info">Showing {{ count($projectRows) }} of {{ count($projectRows) }} projects</span>
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
