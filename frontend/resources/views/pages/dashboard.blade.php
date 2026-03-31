@extends('layouts.app')

@section('title', 'Dashboard — TimeFlow')

@section('content')
    {{-- Error state --}}
    @if(!empty($error))
        <div class="page-header">
            <h1 class="page-title">Dashboard</h1>
        </div>
        <div class="alert alert-error">
            {{ $error }}
        </div>
        <a href="/dashboard" class="btn btn-primary">Retry</a>
    @else
        {{-- Welcome message --}}
        <div class="page-header">
            <h1 class="page-title">Welcome back, {{ $userName }}</h1>
            <div class="page-actions">
                <a href="/timesheet" class="btn btn-primary">View Timesheet</a>
            </div>
        </div>

        {{-- Summary cards --}}
        <div class="summary-cards">
            @include('components.summary-card', [
                'title' => 'Current Week Period',
                'value' => $period['periodString'] ?? ($period['startDate'] . ' – ' . $period['endDate']),
                'icon' => '📅',
            ])

            @include('components.summary-card', [
                'title' => 'Submission Deadline',
                'value' => isset($period['submissionDeadline']) 
                    ? \Carbon\Carbon::parse($period['submissionDeadline'])->setTimezone('Asia/Kuala_Lumpur')->format('l \a\t H:i (T)') 
                    : '',
                'icon' => '⏰',
                'slot' => 'countdown',
                'countdown' => $countdown,
            ])

            @include('components.summary-card', [
                'title' => 'Personal Summary',
                'value' => number_format($totalHours, 1) . ' hours',
                'icon' => '⏱️',
            ])
        </div>

        {{-- Weekly Activity chart --}}
        <div class="chart-container">
            <h3 style="font-size: 0.9rem; font-weight: 600; color: #f1f5f9; margin-bottom: 1rem;">Weekly Activity</h3>
            <div class="chart-bar-group">
                @php
                    $days = [
                        'Mon' => $dailyHours['monday'] ?? 0,
                        'Tue' => $dailyHours['tuesday'] ?? 0,
                        'Wed' => $dailyHours['wednesday'] ?? 0,
                        'Thu' => $dailyHours['thursday'] ?? 0,
                        'Fri' => $dailyHours['friday'] ?? 0,
                    ];
                    $maxHours = 8;
                @endphp
                @foreach($days as $label => $hours)
                    <div class="chart-bar-wrapper">
                        <span class="chart-bar-value">{{ number_format($hours, 1) }}h</span>
                        <div class="chart-bar" style="height: {{ $maxHours > 0 ? min(($hours / $maxHours) * 100, 100) : 0 }}%;"></div>
                        <span class="chart-bar-label">{{ $label }}</span>
                    </div>
                @endforeach
            </div>
        </div>

        {{-- Recent Time Entries --}}
        <div style="margin-bottom: 1.5rem;">
            <h3 style="font-size: 0.9rem; font-weight: 600; color: #f1f5f9; margin-bottom: 1rem;">Recent Time Entries</h3>
            @if(count($recentEntries) > 0)
                <table class="data-table">
                    <thead>
                        <tr>
                            <th>Date</th>
                            <th>Project Code</th>
                            <th>Description</th>
                            <th>Charged Hours</th>
                        </tr>
                    </thead>
                    <tbody>
                        @foreach($recentEntries as $entry)
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
                <p style="color: #94a3b8; font-size: 0.875rem;">No time entries for this period yet.</p>
            @endif
        </div>
    @endif
@endsection
