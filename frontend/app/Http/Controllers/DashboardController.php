<?php

namespace App\Http\Controllers;

use App\Services\GraphQLClient;
use App\Services\GraphQLQueries;
use App\Services\TimesheetEntryMapper;
use Carbon\Carbon;
use Exception;
use Illuminate\Auth\AuthenticationException;
use Illuminate\Routing\Controller;

class DashboardController extends Controller
{
    protected GraphQLClient $graphql;
    protected TimesheetEntryMapper $mapper;

    public function __construct(GraphQLClient $graphql, TimesheetEntryMapper $mapper)
    {
        $this->graphql = $graphql;
        $this->mapper = $mapper;
    }

    /**
     * Render the dashboard page with summary data.
     *
     * Admin/superadmin users see an overview dashboard with active user count
     * and submission trends. Regular users see their personal timesheet summary.
     */
    public function index()
    {
        $user = session('user');
        $userType = $user['userType'] ?? 'user';

        if (in_array($userType, ['admin', 'superadmin'])) {
            return $this->adminDashboard($user);
        }

        return $this->employeeDashboard($user);
    }

    /**
     * Admin/superadmin dashboard: current period card, active users card, submission trends.
     */
    protected function adminDashboard(array $user)
    {
        try {
            // Current period
            $periodData = $this->graphql->query(GraphQLQueries::GET_CURRENT_PERIOD);
            $period = $periodData['getCurrentPeriod'] ?? null;

            // Active users count — request only userId to avoid null non-nullable field errors
            $activeUserCount = 0;
            $employeeCount = 0;
            try {
                $usersData = $this->graphql->query(
                    'query ListUsersCount($filter: UserFilterInput) { listUsers(filter: $filter) { items { userId } } }'
                );
                $allUsers = $usersData['listUsers']['items'] ?? [];
                $activeUserCount = count($allUsers);
                $employeeCount = $activeUserCount; // approximate for target calculation
            } catch (Exception $e) {
                \Log::warning('Admin dashboard: failed to load users: ' . $e->getMessage());
            }

            // Last 5 periods for trends
            $recentPeriods = [];
            try {
                $periodsData = $this->graphql->query(GraphQLQueries::LIST_TIMESHEET_PERIODS);
                $allPeriods = $periodsData['listTimesheetPeriods'] ?? [];
                usort($allPeriods, fn($a, $b) => strcmp($b['startDate'], $a['startDate']));
                $recentPeriods = array_reverse(array_slice($allPeriods, 0, 5));
            } catch (Exception $e) {
                \Log::warning('Admin dashboard: failed to load periods: ' . $e->getMessage());
            }

            // Fetch submissions per period — use same pattern as ReportsController
            $hoursByPeriod = [];
            foreach ($recentPeriods as $p) {
                $pid = $p['periodId'] ?? '';
                if (!$pid) continue;
                try {
                    $subData = $this->graphql->query(GraphQLQueries::LIST_ALL_SUBMISSIONS, [
                        'filter' => ['periodId' => $pid],
                    ]);
                    $subs = $subData['listAllSubmissions'] ?? [];
                    $total = 0;
                    foreach ($subs as $s) {
                        // Compute from entries like ReportsController does
                        $entryTotal = 0;
                        foreach ($s['entries'] ?? [] as $entry) {
                            $entryTotal += (float)($entry['totalHours'] ?? 0);
                        }
                        $total += $entryTotal > 0 ? $entryTotal : (float)($s['totalHours'] ?? 0);
                    }
                    $hoursByPeriod[$pid] = $total;
                } catch (Exception $e) {
                    \Log::warning("Admin dashboard: submissions for period {$pid}: " . $e->getMessage());
                    $hoursByPeriod[$pid] = 0;
                }
            }

            // Build trends data
            $trends = [];
            $targetHours = $employeeCount * 40;
            foreach ($recentPeriods as $p) {
                $pid = $p['periodId'] ?? '';
                $start = Carbon::parse($p['startDate']);
                $end = Carbon::parse($p['endDate']);
                $trends[] = [
                    'label' => $start->format('M d') . ' - ' . $end->format('M d'),
                    'actual' => $hoursByPeriod[$pid] ?? 0,
                    'target' => $targetHours,
                ];
            }

            // Format period string for card
            $periodString = '';
            if ($period) {
                $start = Carbon::parse($period['startDate']);
                $end = Carbon::parse($period['endDate']);
                $periodString = $start->format('M d') . ' - ' . $end->format('M d');
            }

            // Pending approval counts for superadmin dashboard
            $viewData = [
                'userName' => $user['fullName'] ?? 'User',
                'periodString' => $periodString,
                'activeUserCount' => $activeUserCount,
                'trends' => $trends,
                'error' => null,
            ];

            if (($user['userType'] ?? '') === 'superadmin') {
                $pendingProjects = 0;
                $pendingDepartments = 0;
                $pendingPositions = 0;

                try {
                    $result = $this->graphql->query(GraphQLQueries::LIST_PROJECTS);
                    $projects = $result['listProjects']['items'] ?? [];
                    $pendingProjects = count(array_filter($projects, fn($item) => ($item['approval_status'] ?? '') === 'Pending_Approval'));
                } catch (Exception $e) {
                    \Log::warning('Superadmin dashboard: failed to load projects: ' . $e->getMessage());
                }

                try {
                    $result = $this->graphql->query(GraphQLQueries::LIST_DEPARTMENTS);
                    $departments = $result['listDepartments'] ?? [];
                    $pendingDepartments = count(array_filter($departments, fn($item) => ($item['approval_status'] ?? '') === 'Pending_Approval'));
                } catch (Exception $e) {
                    \Log::warning('Superadmin dashboard: failed to load departments: ' . $e->getMessage());
                }

                try {
                    $result = $this->graphql->query(GraphQLQueries::LIST_POSITIONS);
                    $positions = $result['listPositions'] ?? [];
                    $pendingPositions = count(array_filter($positions, fn($item) => ($item['approval_status'] ?? '') === 'Pending_Approval'));
                } catch (Exception $e) {
                    \Log::warning('Superadmin dashboard: failed to load positions: ' . $e->getMessage());
                }

                $viewData['pendingProjects'] = $pendingProjects;
                $viewData['pendingDepartments'] = $pendingDepartments;
                $viewData['pendingPositions'] = $pendingPositions;
            }

            return view('pages.dashboard-admin', $viewData);
        } catch (AuthenticationException $e) {
            return redirect('/login')->withErrors(['auth' => $e->getMessage()]);
        } catch (Exception $e) {
            \Log::error('Admin dashboard load failed: ' . $e->getMessage(), ['trace' => $e->getTraceAsString()]);
            return view('pages.dashboard-admin', [
                'error' => 'Unable to load dashboard data. Please try again.',
                'userName' => $user['fullName'] ?? 'User',
            ]);
        }
    }

    /**
     * Employee dashboard: personal timesheet summary.
     */
    protected function employeeDashboard(array $user)
    {
        try {
            $periodData = $this->graphql->query(
                'query GetCurrentPeriod { getCurrentPeriod { periodId startDate endDate periodString submissionDeadline } }'
            );
            $period = $periodData['getCurrentPeriod'] ?? null;

            if (!$period) {
                return view('pages.dashboard', [
                    'error' => 'No active period found.',
                    'userName' => $user['fullName'] ?? 'User',
                ]);
            }

            $submissionData = $this->graphql->query(
                'query ListMySubmissions($filter: SubmissionFilterInput) { listMySubmissions(filter: $filter) { submissionId periodId status entries { entryId projectCode monday tuesday wednesday thursday friday saturday sunday } } }',
                ['filter' => ['periodId' => $period['periodId']]]
            );

            $submissions = $submissionData['listMySubmissions'] ?? [];
            $submission = $submissions[0] ?? null;
            $entries = $submission['entries'] ?? [];

            $countdown = $this->computeCountdown($period['submissionDeadline'] ?? null);

            $weekStartDate = $period['startDate'] ?? Carbon::now()->startOfWeek()->format('Y-m-d');
            $recentEntries = $this->mapper->flattenEntries($entries, $weekStartDate);
            $dailyHours = $this->mapper->calculateDailyTotals($entries);
            $totalHours = $this->mapper->calculateWeeklyTotal($entries);

            return view('pages.dashboard', [
                'userName' => $user['fullName'] ?? 'User',
                'period' => [
                    'startDate' => $period['startDate'] ?? '',
                    'endDate' => $period['endDate'] ?? '',
                    'periodString' => $period['periodString'] ?? '',
                    'submissionDeadline' => $period['submissionDeadline'] ?? '',
                ],
                'countdown' => $countdown,
                'totalHours' => $totalHours,
                'dailyHours' => $dailyHours,
                'recentEntries' => $recentEntries,
                'error' => null,
            ]);
        } catch (AuthenticationException $e) {
            return redirect('/login')->withErrors(['auth' => $e->getMessage()]);
        } catch (Exception $e) {
            \Log::error('Dashboard load failed: ' . $e->getMessage());
            return view('pages.dashboard', [
                'error' => 'Unable to load dashboard data. Please try again.',
                'userName' => $user['fullName'] ?? 'User',
            ]);
        }
    }

    /**
     * Compute the countdown (days, hours, minutes) until the submission deadline.
     *
     * @param string|null $deadline ISO datetime string
     * @return array{days: int, hours: int, minutes: int}
     */
    protected function computeCountdown(?string $deadline): array
    {
        if (!$deadline) {
            return ['days' => 0, 'hours' => 0, 'minutes' => 0];
        }

        $now = Carbon::now();
        $deadlineTime = Carbon::parse($deadline);

        if ($now->greaterThanOrEqualTo($deadlineTime)) {
            return ['days' => 0, 'hours' => 0, 'minutes' => 0];
        }

        $diff = $now->diff($deadlineTime);

        return [
            'days' => $diff->days,
            'hours' => $diff->h,
            'minutes' => $diff->i,
        ];
    }
}
