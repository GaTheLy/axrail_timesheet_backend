@extends('layouts.app')

@section('title', 'Submission Detail — TimeFlow')

@section('content')
    {{-- Error state --}}
    @if(!empty($error))
        <div class="page-header">
            <h1 class="page-title">Submission Detail</h1>
        </div>
        <div class="alert alert-error">
            {{ $error }}
        </div>
        <a href="/timesheet" class="btn btn-secondary">&larr; Back to Submissions</a>
    @else
        {{-- Back navigation --}}
        <div style="margin-bottom: 1rem;">
            <a href="/timesheet" class="btn btn-secondary btn-sm" aria-label="Back to Timesheet Submissions">&larr; Back to Submissions</a>
        </div>

        {{-- Page header with submission info --}}
        <div class="page-header">
            <h1 class="page-title">Submission Detail</h1>
        </div>

        <div style="display: flex; flex-wrap: wrap; gap: 1.5rem; margin-bottom: 1.5rem; padding: 1rem; background: #1e293b; border-radius: 8px;">
            <div>
                <span style="font-size: 0.75rem; font-weight: 600; color: #94a3b8; text-transform: uppercase;">Employee</span>
                <p style="margin: 0.25rem 0 0; font-size: 0.95rem; color: #f1f5f9;">{{ $employeeName }}</p>
            </div>
            <div>
                <span style="font-size: 0.75rem; font-weight: 600; color: #94a3b8; text-transform: uppercase;">Week Period</span>
                <p style="margin: 0.25rem 0 0; font-size: 0.95rem; color: #f1f5f9;">{{ $periodString }}</p>
            </div>
            <div>
                <span style="font-size: 0.75rem; font-weight: 600; color: #94a3b8; text-transform: uppercase;">Status</span>
                <p style="margin: 0.25rem 0 0;">
                    @if(($submission['status'] ?? '') === 'Submitted')
                        <span class="badge badge-success">Submitted</span>
                    @elseif(($submission['status'] ?? '') === 'Draft')
                        <span class="badge badge-danger">Draft</span>
                    @else
                        <span class="badge badge-info">{{ $submission['status'] ?? '' }}</span>
                    @endif
                </p>
            </div>
            <div>
                <span style="font-size: 0.75rem; font-weight: 600; color: #94a3b8; text-transform: uppercase;">Total Hours</span>
                <p style="margin: 0.25rem 0 0; font-size: 0.95rem; color: #f1f5f9;">{{ number_format($submission['totalHours'] ?? 0, 1) }}h</p>
            </div>
        </div>

        {{-- Entries table --}}
        @if(count($entries) > 0)
            <table class="data-table">
                <thead>
                    <tr>
                        <th>Project Code</th>
                        <th>Saturday</th>
                        <th>Sunday</th>
                        <th>Monday</th>
                        <th>Tuesday</th>
                        <th>Wednesday</th>
                        <th>Thursday</th>
                        <th>Friday</th>
                        <th>Total Hours</th>
                    </tr>
                </thead>
                <tbody>
                    @foreach($entries as $entry)
                        <tr>
                            <td>{{ $entry['projectCode'] ?? '' }}</td>
                            <td>{{ number_format($entry['saturday'] ?? 0, 1) }}</td>
                            <td>{{ number_format($entry['sunday'] ?? 0, 1) }}</td>
                            <td>{{ number_format($entry['monday'] ?? 0, 1) }}</td>
                            <td>{{ number_format($entry['tuesday'] ?? 0, 1) }}</td>
                            <td>{{ number_format($entry['wednesday'] ?? 0, 1) }}</td>
                            <td>{{ number_format($entry['thursday'] ?? 0, 1) }}</td>
                            <td>{{ number_format($entry['friday'] ?? 0, 1) }}</td>
                            <td>{{ number_format($entry['totalHours'] ?? 0, 1) }}h</td>
                        </tr>
                    @endforeach
                </tbody>
            </table>
        @else
            <div style="text-align: center; padding: 3rem 1rem; color: #94a3b8;">
                <p style="font-size: 0.9rem;">No entries were logged for this period.</p>
            </div>
        @endif
    @endif
@endsection
