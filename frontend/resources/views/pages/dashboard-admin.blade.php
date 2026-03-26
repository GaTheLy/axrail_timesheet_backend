@extends('layouts.app')

@section('title', 'Dashboard — TimeFlow')

@section('content')
    @php $userType = session('user.userType', 'user'); @endphp

    @if(!empty($error))
        <div class="page-header">
            <h1 class="page-title">Dashboard</h1>
        </div>
        <div class="alert alert-error">{{ $error }}</div>
        <a href="/dashboard" class="btn btn-primary">Retry</a>
    @else
        <div class="page-header">
            <h1 class="page-title">Dashboard</h1>
        </div>
        <p style="color: #94a3b8; font-size: 0.875rem; margin-bottom: 1.25rem;">Welcome back, {{ $userName }}. Here's what's happening this week.</p>

        {{-- Summary Cards (reuse existing .summary-cards grid but 2 columns) --}}
        <div class="summary-cards" style="grid-template-columns: 1fr 1fr;">
            <div class="summary-card">
                <div class="summary-card-icon">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#3b82f6" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <rect x="3" y="4" width="18" height="18" rx="2" ry="2"></rect>
                        <line x1="16" y1="2" x2="16" y2="6"></line>
                        <line x1="8" y1="2" x2="8" y2="6"></line>
                        <line x1="3" y1="10" x2="21" y2="10"></line>
                    </svg>
                </div>
                <div class="summary-card-content">
                    <div class="summary-card-title">Current Week Period</div>
                    <div class="summary-card-value">{{ $periodString ?: 'No active period' }}</div>
                </div>
            </div>

            <div class="summary-card">
                <div class="summary-card-icon">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#3b82f6" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path>
                        <circle cx="9" cy="7" r="4"></circle>
                        <path d="M23 21v-2a4 4 0 0 0-3-3.87"></path>
                        <path d="M16 3.13a4 4 0 0 1 0 7.75"></path>
                    </svg>
                </div>
                <div class="summary-card-content">
                    <div class="summary-card-title">Total Active Users</div>
                    <div class="summary-card-value">{{ $activeUserCount }}</div>
                </div>
            </div>
        </div>

        {{-- Approval Requests Section (superadmin only) --}}
        @if($userType === 'superadmin')
            <div style="margin-bottom: 1.25rem;">
                <h3 style="font-size: 0.9rem; font-weight: 600; color: #f1f5f9; margin: 0 0 0.75rem 0;">Approval Requests</h3>
                <div class="summary-cards" style="grid-template-columns: 1fr 1fr 1fr;">
                    <div class="summary-card">
                        <div class="summary-card-icon">
                            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#f59e0b" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path>
                            </svg>
                        </div>
                        <div class="summary-card-content">
                            <div class="summary-card-title">Projects</div>
                            <div class="summary-card-value">{{ $pendingProjects ?? 0 }}</div>
                        </div>
                        <a href="/admin/approvals" class="btn btn-sm" style="margin-left: auto; background-color: rgba(245,158,11,0.15); color: #f59e0b; border: 1px solid rgba(245,158,11,0.3); padding: 0.25rem 0.75rem; border-radius: 0.375rem; font-size: 0.75rem; text-decoration: none;">Review</a>
                    </div>

                    <div class="summary-card">
                        <div class="summary-card-icon">
                            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#f59e0b" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path>
                                <circle cx="9" cy="7" r="4"></circle>
                                <path d="M23 21v-2a4 4 0 0 0-3-3.87"></path>
                                <path d="M16 3.13a4 4 0 0 1 0 7.75"></path>
                            </svg>
                        </div>
                        <div class="summary-card-content">
                            <div class="summary-card-title">Departments</div>
                            <div class="summary-card-value">{{ $pendingDepartments ?? 0 }}</div>
                        </div>
                        <a href="/admin/approvals" class="btn btn-sm" style="margin-left: auto; background-color: rgba(245,158,11,0.15); color: #f59e0b; border: 1px solid rgba(245,158,11,0.3); padding: 0.25rem 0.75rem; border-radius: 0.375rem; font-size: 0.75rem; text-decoration: none;">Review</a>
                    </div>

                    <div class="summary-card">
                        <div class="summary-card-icon">
                            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#f59e0b" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path>
                                <circle cx="12" cy="7" r="4"></circle>
                            </svg>
                        </div>
                        <div class="summary-card-content">
                            <div class="summary-card-title">Positions</div>
                            <div class="summary-card-value">{{ $pendingPositions ?? 0 }}</div>
                        </div>
                        <a href="/admin/approvals" class="btn btn-sm" style="margin-left: auto; background-color: rgba(245,158,11,0.15); color: #f59e0b; border: 1px solid rgba(245,158,11,0.3); padding: 0.25rem 0.75rem; border-radius: 0.375rem; font-size: 0.75rem; text-decoration: none;">Review</a>
                    </div>
                </div>
            </div>
        @endif

        {{-- Submission Trends --}}
        <div class="chart-container">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.25rem;">
                <div>
                    <h3 style="font-size: 0.9rem; font-weight: 600; color: #f1f5f9; margin: 0;">Submission Trends</h3>
                    <p style="color: #94a3b8; font-size: 0.75rem; margin: 0.25rem 0 0 0;">Average hours worked per week</p>
                </div>
                <div style="display: flex; align-items: center; gap: 1rem; font-size: 0.75rem; color: #94a3b8;">
                    <span style="display: flex; align-items: center; gap: 0.35rem;">
                        <span style="display: inline-block; width: 8px; height: 8px; border-radius: 50%; background-color: #3b82f6;"></span>
                        Submissions
                    </span>
                    <span style="display: flex; align-items: center; gap: 0.35rem;">
                        <span style="display: inline-block; width: 8px; height: 8px; border-radius: 50%; background-color: rgba(59,130,246,0.2);"></span>
                        Target
                    </span>
                </div>
            </div>

            @php
                $trendsData = $trends ?? [];
                $maxVal = 1;
                foreach ($trendsData as $t) {
                    $maxVal = max($maxVal, $t['target'], $t['actual']);
                }
            @endphp

            <div style="display: flex; align-items: flex-end; gap: 1.5rem; height: 200px;">
                @foreach($trendsData as $t)
                    <div style="flex: 1; display: flex; flex-direction: column; align-items: center; height: 100%;">
                        <div style="flex: 1; width: 100%; display: flex; align-items: flex-end; justify-content: center; position: relative;">
                            {{-- Target bar (opaque blue) --}}
                            <div style="position: absolute; bottom: 0; width: 60%; background-color: rgba(59,130,246,0.15); border-radius: 0.375rem 0.375rem 0 0; height: {{ $maxVal > 0 ? ($t['target'] / $maxVal) * 100 : 0 }}%;"></div>
                            {{-- Actual bar (solid blue) --}}
                            <div style="position: relative; z-index: 1; width: 60%; background-color: #3b82f6; border-radius: 0.375rem 0.375rem 0 0; height: {{ $maxVal > 0 ? ($t['actual'] / $maxVal) * 100 : 0 }}%;"></div>
                        </div>
                        <div style="color: #94a3b8; font-size: 0.65rem; margin-top: 0.5rem; text-align: center; white-space: nowrap;">{{ $t['label'] }}</div>
                    </div>
                @endforeach

                @if(count($trendsData) === 0)
                    <div style="flex: 1; display: flex; align-items: center; justify-content: center; color: #64748b; font-size: 0.875rem;">
                        No trend data available.
                    </div>
                @endif
            </div>
        </div>
    @endif
@endsection
