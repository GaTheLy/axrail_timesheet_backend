<?php

namespace App\Http\Controllers;

use App\Services\GraphQLClient;
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
     * Fetches the current period and submission, computes countdown,
     * prepares chart data and recent entries for the view.
     */
    public function index()
    {
        $user = session('user');

        try {
            // Fetch current period
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

            // Fetch current submission filtered by periodId
            $submissionData = $this->graphql->query(
                'query ListMySubmissions($filter: SubmissionFilterInput) { listMySubmissions(filter: $filter) { items { submissionId periodId status entries { entryId projectCode projectName monday tuesday wednesday thursday friday saturday sunday } } } }',
                ['filter' => ['periodId' => $period['periodId']]]
            );

            $submissions = $submissionData['listMySubmissions']['items'] ?? [];
            $submission = $submissions[0] ?? null;
            $entries = $submission['entries'] ?? [];

            // Compute deadline countdown
            $countdown = $this->computeCountdown($period['submissionDeadline'] ?? null);

            // Prepare data using TimesheetEntryMapper
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
