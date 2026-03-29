<?php

namespace App\Http\Controllers;

use App\Services\GraphQLClient;
use App\Services\GraphQLQueries;
use App\Services\TimesheetEntryMapper;
use Carbon\Carbon;
use Exception;
use Illuminate\Auth\AuthenticationException;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Routing\Controller;

class TimesheetController extends Controller
{
    protected GraphQLClient $graphql;
    protected TimesheetEntryMapper $mapper;

    public function __construct(GraphQLClient $graphql, TimesheetEntryMapper $mapper)
    {
        $this->graphql = $graphql;
        $this->mapper = $mapper;
    }

    /**
     * Render the timesheet page.
     *
     * Admin/superadmin users see the Submissions View with all employee submissions.
     * Regular users see the employee timesheet entry form.
     */
    public function index()
    {
        $userType = session('user.userType', 'user');

        if (in_array($userType, ['admin', 'superadmin'])) {
            return $this->renderSubmissionsView();
        }

        return $this->renderEmployeeTimesheet();
    }

    /**
     * Render the admin/superadmin Submissions View.
     *
     * Fetches all submissions via listAllSubmissions and resolves employee
     * names via listUsers, then renders the timesheet-submissions template.
     */
    protected function renderSubmissionsView()
    {
        try {
            // Fetch all submissions
            $submissionsData = $this->graphql->query(GraphQLQueries::LIST_ALL_SUBMISSIONS);
            $submissions = $submissionsData['listAllSubmissions'] ?? [];

            // Fetch users to resolve employeeId → fullName
            $usersData = $this->graphql->query(GraphQLQueries::LIST_USERS);
            $users = $usersData['listUsers']['items'] ?? [];
            $userMap = [];
            foreach ($users as $user) {
                $userMap[$user['userId']] = $user['fullName'] ?? $user['userId'];
            }

            // Fetch all periods to resolve periodId → periodString
            $periodsData = $this->graphql->query(GraphQLQueries::LIST_TIMESHEET_PERIODS);
            $periods = $periodsData['listTimesheetPeriods'] ?? [];
            $periodMap = [];
            foreach ($periods as $period) {
                $periodMap[$period['periodId']] = $period['periodString'] ?? $period['periodId'];
            }

            return view('pages.timesheet-submissions', [
                'submissions' => $submissions,
                'userMap' => $userMap,
                'users' => $users,
                'periodMap' => $periodMap,
                'periods' => $periods,
                'error' => null,
            ]);
        } catch (AuthenticationException $e) {
            return redirect('/login')->withErrors(['auth' => $e->getMessage()]);
        } catch (Exception $e) {
            \Log::error('Timesheet submissions load failed: ' . $e->getMessage());
            return view('pages.timesheet-submissions', [
                'submissions' => [],
                'userMap' => [],
                'users' => [],
                'periodMap' => [],
                'periods' => [],
                'error' => 'Unable to load submissions: ' . $e->getMessage(),
            ]);
        }
    }

    /**
     * Show a specific submission's detail view (admin/superadmin only).
     *
     * Fetches the submission via getTimesheetSubmission, resolves the
     * employee name and period string, then renders the detail template.
     */
    public function showSubmission(string $submissionId)
    {
        $userType = session('user.userType', 'user');

        if (!in_array($userType, ['admin', 'superadmin'])) {
            return redirect('/timesheet');
        }

        try {
            // Fetch the submission with entries
            $submissionData = $this->graphql->query(
                GraphQLQueries::GET_TIMESHEET_SUBMISSION,
                ['submissionId' => $submissionId]
            );
            $submission = $submissionData['getTimesheetSubmission'] ?? null;

            if (!$submission) {
                return view('pages.submission-detail', [
                    'submission' => null,
                    'employeeName' => '',
                    'periodString' => '',
                    'entries' => [],
                    'error' => 'Submission not found.',
                ]);
            }

            $entries = $submission['entries'] ?? [];

            // Resolve employee name
            $employeeName = $submission['employeeId'] ?? 'Unknown';
            try {
                $userData = $this->graphql->query(
                    GraphQLQueries::GET_USER,
                    ['userId' => $submission['employeeId']]
                );
                $employeeName = $userData['getUser']['fullName'] ?? $employeeName;
            } catch (Exception $e) {
                \Log::warning('Could not resolve employee name: ' . $e->getMessage());
            }

            // Resolve period string
            $periodString = $submission['periodId'] ?? '';
            try {
                $periodsData = $this->graphql->query(GraphQLQueries::LIST_TIMESHEET_PERIODS);
                $periods = $periodsData['listTimesheetPeriods'] ?? [];
                foreach ($periods as $period) {
                    if (($period['periodId'] ?? '') === $submission['periodId']) {
                        $periodString = $period['periodString'] ?? $periodString;
                        break;
                    }
                }
            } catch (Exception $e) {
                \Log::warning('Could not resolve period string: ' . $e->getMessage());
            }

            return view('pages.submission-detail', [
                'submission' => $submission,
                'employeeName' => $employeeName,
                'periodString' => $periodString,
                'entries' => $entries,
                'error' => null,
            ]);
        } catch (AuthenticationException $e) {
            return redirect('/login')->withErrors(['auth' => $e->getMessage()]);
        } catch (Exception $e) {
            \Log::error('Submission detail load failed: ' . $e->getMessage());
            return view('pages.submission-detail', [
                'submission' => null,
                'employeeName' => '',
                'periodString' => '',
                'entries' => [],
                'error' => 'Unable to load submission: ' . $e->getMessage(),
            ]);
        }
    }

    /**
     * Render the employee timesheet entry form (existing behavior).
     */
    protected function renderEmployeeTimesheet()
    {
        $user = session('user');

        try {
            $periodData = $this->graphql->query(
                'query GetCurrentPeriod { getCurrentPeriod { periodId startDate endDate periodString submissionDeadline } }'
            );
            $period = $periodData['getCurrentPeriod'] ?? null;

            if (!$period) {
                return view('pages.timesheet', [
                    'error' => 'No active period found.',
                    'entries' => [],
                    'weeklyTotal' => 0,
                    'period' => null,
                    'countdown' => ['days' => 0, 'hours' => 0, 'minutes' => 0],
                    'submission' => null,
                ]);
            }

            $submissionData = $this->graphql->query(
                'query ListMySubmissions($filter: SubmissionFilterInput) { listMySubmissions(filter: $filter) { submissionId periodId status entries { entryId projectCode monday tuesday wednesday thursday friday saturday sunday } } }',
                ['filter' => ['periodId' => $period['periodId']]]
            );

            $submissions = $submissionData['listMySubmissions'] ?? [];
            $submission = $submissions[0] ?? null;
            $entries = $submission['entries'] ?? [];

            $weekStartDate = $period['startDate'] ?? Carbon::now()->startOfWeek()->format('Y-m-d');
            $flattenedEntries = $this->mapper->flattenEntries($entries, $weekStartDate);
            $weeklyTotal = $this->mapper->calculateWeeklyTotal($entries);
            $countdown = $this->computeCountdown($period['submissionDeadline'] ?? null);

            return view('pages.timesheet', [
                'entries' => $flattenedEntries,
                'weeklyTotal' => $weeklyTotal,
                'period' => [
                    'startDate' => $period['startDate'] ?? '',
                    'endDate' => $period['endDate'] ?? '',
                    'periodString' => $period['periodString'] ?? '',
                    'submissionDeadline' => $period['submissionDeadline'] ?? '',
                ],
                'countdown' => $countdown,
                'submission' => $submission,
                'error' => null,
            ]);
        } catch (AuthenticationException $e) {
            return redirect('/login')->withErrors(['auth' => $e->getMessage()]);
        } catch (Exception $e) {
            \Log::error('Timesheet load failed: ' . $e->getMessage());
            return view('pages.timesheet', [
                'entries' => [],
                'weeklyTotal' => 0,
                'period' => null,
                'countdown' => ['days' => 0, 'hours' => 0, 'minutes' => 0],
                'submission' => null,
            ]);
        }
    }

    /**
     * Add a new timesheet entry (AJAX).
     */
    public function storeEntry(Request $request): JsonResponse
    {
        $request->validate([
            'projectCode' => 'required|string',
            'date' => 'required|date',
            'chargedHours' => 'required|numeric|min:0',
        ]);

        try {
            $submission = $this->getCurrentSubmission();

            if (!$submission) {
                return response()->json(['error' => 'No active submission found for the current period.'], 404);
            }

            if ($this->isSubmitted($submission)) {
                return response()->json(['error' => 'Cannot add entries to a submitted timesheet.'], 403);
            }

            $entries = $submission['entries'] ?? [];
            $mapping = $this->mapper->mapToEntryInput(
                $request->input('projectCode'),
                $request->input('date'),
                (float) $request->input('chargedHours'),
                $entries
            );

            if ($mapping['operation'] === 'add') {
                $result = $this->graphql->mutate(
                    'mutation AddTimesheetEntry($submissionId: ID!, $input: TimesheetEntryInput!) { addTimesheetEntry(submissionId: $submissionId, input: $input) { entryId projectCode monday tuesday wednesday thursday friday saturday sunday } }',
                    [
                        'submissionId' => $submission['submissionId'],
                        'input' => $mapping['input'],
                    ]
                );
            } else {
                $result = $this->graphql->mutate(
                    'mutation UpdateTimesheetEntry($entryId: ID!, $input: TimesheetEntryInput!) { updateTimesheetEntry(entryId: $entryId, input: $input) { entryId projectCode monday tuesday wednesday thursday friday saturday sunday } }',
                    [
                        'entryId' => $mapping['entryId'],
                        'input' => $mapping['input'],
                    ]
                );
            }

            return response()->json(['success' => true, 'data' => $result]);
        } catch (AuthenticationException $e) {
            return response()->json(['error' => 'Session expired. Please log in again.'], 401);
        } catch (Exception $e) {
            return response()->json(['error' => $e->getMessage()], 500);
        }
    }

    /**
     * Update an existing timesheet entry (AJAX).
     */
    public function updateEntry(Request $request, string $entryId): JsonResponse
    {
        $request->validate([
            'projectCode' => 'required|string',
            'date' => 'required|date',
            'chargedHours' => 'required|numeric|min:0',
        ]);

        try {
            $submission = $this->getCurrentSubmission();

            if (!$submission) {
                return response()->json(['error' => 'No active submission found for the current period.'], 404);
            }

            if ($this->isSubmitted($submission)) {
                return response()->json(['error' => 'Cannot edit entries on a submitted timesheet.'], 403);
            }

            $entries = $submission['entries'] ?? [];
            $mapping = $this->mapper->mapToEntryInput(
                $request->input('projectCode'),
                $request->input('date'),
                (float) $request->input('chargedHours'),
                $entries
            );

            $result = $this->graphql->mutate(
                'mutation UpdateTimesheetEntry($entryId: ID!, $input: TimesheetEntryInput!) { updateTimesheetEntry(entryId: $entryId, input: $input) { entryId projectCode monday tuesday wednesday thursday friday saturday sunday } }',
                [
                    'entryId' => $entryId,
                    'input' => $mapping['input'],
                ]
            );

            return response()->json(['success' => true, 'data' => $result]);
        } catch (AuthenticationException $e) {
            return response()->json(['error' => 'Session expired. Please log in again.'], 401);
        } catch (Exception $e) {
            return response()->json(['error' => $e->getMessage()], 500);
        }
    }

    /**
     * Delete a timesheet entry (AJAX).
     *
     * Uses the date param to determine whether to zero out a single day
     * or remove the entire entry row.
     */
    public function destroyEntry(Request $request, string $entryId): JsonResponse
    {
        try {
            $submission = $this->getCurrentSubmission();

            if (!$submission) {
                return response()->json(['error' => 'No active submission found for the current period.'], 404);
            }

            if ($this->isSubmitted($submission)) {
                return response()->json(['error' => 'Cannot delete entries from a submitted timesheet.'], 403);
            }

            $entries = $submission['entries'] ?? [];
            $entry = $this->findEntryById($entryId, $entries);

            if (!$entry) {
                return response()->json(['error' => 'Entry not found.'], 404);
            }

            $date = $request->input('date');
            $mapping = $this->mapper->mapToEntryInput(
                $entry['projectCode'],
                $date,
                0,
                $entries
            );

            if ($mapping['operation'] === 'remove') {
                $result = $this->graphql->mutate(
                    'mutation RemoveTimesheetEntry($entryId: ID!) { removeTimesheetEntry(entryId: $entryId) { entryId } }',
                    ['entryId' => $mapping['entryId']]
                );
            } else {
                $result = $this->graphql->mutate(
                    'mutation UpdateTimesheetEntry($entryId: ID!, $input: TimesheetEntryInput!) { updateTimesheetEntry(entryId: $entryId, input: $input) { entryId projectCode monday tuesday wednesday thursday friday saturday sunday } }',
                    [
                        'entryId' => $mapping['entryId'],
                        'input' => $mapping['input'],
                    ]
                );
            }

            return response()->json(['success' => true, 'data' => $result]);
        } catch (AuthenticationException $e) {
            return response()->json(['error' => 'Session expired. Please log in again.'], 401);
        } catch (Exception $e) {
            return response()->json(['error' => $e->getMessage()], 500);
        }
    }

    /**
     * List approved projects for the dropdown (AJAX).
     */
    public function listProjects(): JsonResponse
    {
        try {
            $result = $this->graphql->query(
                'query ListProjects($filter: ProjectFilterInput) { listProjects(filter: $filter) { items { projectCode projectName } } }',
                ['filter' => ['approval_status' => 'Approved']]
            );

            $projects = $result['listProjects']['items'] ?? [];

            return response()->json(['success' => true, 'data' => $projects]);
        } catch (AuthenticationException $e) {
            return response()->json(['error' => 'Session expired. Please log in again.'], 401);
        } catch (Exception $e) {
            return response()->json(['error' => $e->getMessage()], 500);
        }
    }

    /**
     * Fetch the current submission for the active period.
     */
    protected function getCurrentSubmission(): ?array
    {
        $periodData = $this->graphql->query(
            'query GetCurrentPeriod { getCurrentPeriod { periodId } }'
        );
        $period = $periodData['getCurrentPeriod'] ?? null;

        if (!$period) {
            return null;
        }

        $submissionData = $this->graphql->query(
            'query ListMySubmissions($filter: SubmissionFilterInput) { listMySubmissions(filter: $filter) { submissionId periodId status entries { entryId projectCode monday tuesday wednesday thursday friday saturday sunday } } }',
            ['filter' => ['periodId' => $period['periodId']]]
        );

        $submissions = $submissionData['listMySubmissions'] ?? [];

        return $submissions[0] ?? null;
    }

    /**
     * Check if the submission status is "Submitted".
     */
    protected function isSubmitted(?array $submission): bool
    {
        return $submission !== null && ($submission['status'] ?? '') === 'Submitted';
    }

    /**
     * Find an entry by its ID within the entries array.
     */
    protected function findEntryById(string $entryId, array $entries): ?array
    {
        foreach ($entries as $entry) {
            if (($entry['entryId'] ?? '') === $entryId) {
                return $entry;
            }
        }

        return null;
    }

    /**
     * Compute the countdown until the submission deadline.
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
