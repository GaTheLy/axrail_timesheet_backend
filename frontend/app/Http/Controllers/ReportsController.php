<?php

namespace App\Http\Controllers;

use App\Services\GraphQLClient;
use App\Services\GraphQLQueries;
use Exception;
use Illuminate\Auth\AuthenticationException;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Routing\Controller;
use Illuminate\View\View;
use Illuminate\Http\RedirectResponse;

class ReportsController extends Controller
{
    protected GraphQLClient $graphql;

    public function __construct(GraphQLClient $graphql)
    {
        $this->graphql = $graphql;
    }

    /**
     * Display the Project Summary report page.
     *
     * Fetches projects and submissions for the selected period,
     * computes utilization per project, and renders the view.
     */
    public function projectSummary(Request $request): View|RedirectResponse
    {
        try {
            // Fetch current period
            $periodData = $this->graphql->query(GraphQLQueries::GET_CURRENT_PERIOD);
            $currentPeriod = $periodData['getCurrentPeriod'] ?? null;

            // Fetch all periods for the dropdown
            $periodsData = $this->graphql->query(GraphQLQueries::LIST_TIMESHEET_PERIODS);
            $periods = $periodsData['listTimesheetPeriods'] ?? [];

            // Determine selected period (from request or default to current)
            $selectedPeriodId = $request->input('periodId', $currentPeriod['periodId'] ?? null);

            // Fetch projects — admins see all, PMs see only their own
            $user = session('user', []);
            $userId = $user['userId'] ?? '';
            $userType = $user['userType'] ?? 'user';
            $isAdmin = in_array($userType, ['admin', 'superadmin'], true);

            if ($isAdmin) {
                $projectsData = $this->graphql->query(GraphQLQueries::LIST_PROJECTS);
            } else {
                $projectsData = $this->graphql->query(GraphQLQueries::LIST_PROJECTS, [
                    'filter' => ['projectManagerId' => $userId],
                ]);
            }
            $projects = $projectsData['listProjects']['items'] ?? [];

            // Collect project codes to scope submission data (null = all for admins)
            $pmProjectCodes = null;
            if (!$isAdmin) {
                $pmProjectCodes = [];
                foreach ($projects as $project) {
                    $pmProjectCodes[] = $project['projectCode'] ?? '';
                }
            }

            // Fetch all submissions for the selected period
            $submissions = [];
            if ($selectedPeriodId) {
                $submissionsData = $this->graphql->query(GraphQLQueries::LIST_ALL_SUBMISSIONS, [
                    'filter' => ['periodId' => $selectedPeriodId],
                ]);
                $submissions = $submissionsData['listAllSubmissions'] ?? [];
            }

            // Compute charged hours per project from submissions (only for PM's projects)
            $chargedByProject = $this->computeChargedHoursByProject($submissions, $pmProjectCodes);

            // Build project summary rows with utilization
            $projectRows = [];
            foreach ($projects as $project) {
                $code = $project['projectCode'] ?? '';
                $plannedHours = (float) ($project['plannedHours'] ?? 0);
                $chargedHours = (float) ($chargedByProject[$code] ?? 0);
                $utilization = $plannedHours > 0
                    ? round(($chargedHours / $plannedHours) * 100, 1)
                    : 0;

                $projectRows[] = [
                    'projectCode' => $code,
                    'projectName' => $project['projectName'] ?? '',
                    'plannedHours' => $plannedHours,
                    'chargedHours' => $chargedHours,
                    'utilizationPercent' => $utilization,
                    'status' => $project['status'] ?? '',
                ];
            }

            // Compute totals row
            $totals = $this->computeProjectTotals($projectRows);

            return view('pages.reports.project-summary', [
                'projectRows' => $projectRows,
                'totals' => $totals,
                'periods' => $periods,
                'selectedPeriodId' => $selectedPeriodId,
                'currentPeriod' => $currentPeriod,
                'error' => null,
            ]);
        } catch (AuthenticationException $e) {
            return redirect('/login')->withErrors(['auth' => $e->getMessage()]);
        } catch (Exception $e) {
            \Log::error('Project summary load failed: ' . $e->getMessage());
            return view('pages.reports.project-summary', [
                'projectRows' => [],
                'totals' => $this->emptyProjectTotals(),
                'periods' => [],
                'selectedPeriodId' => null,
                'currentPeriod' => null,
                'error' => 'Unable to load report data: ' . $e->getMessage(),
            ]);
        }
    }

    /**
     * Display the Submission Summary report page.
     *
     * Fetches submissions and users for the selected period,
     * computes chargeability per employee, and renders the view.
     */
    public function submissionSummary(Request $request): View|RedirectResponse
    {
        try {
            // Fetch current period
            $periodData = $this->graphql->query(GraphQLQueries::GET_CURRENT_PERIOD);
            $currentPeriod = $periodData['getCurrentPeriod'] ?? null;

            // Fetch all periods for the dropdown
            $periodsData = $this->graphql->query(GraphQLQueries::LIST_TIMESHEET_PERIODS);
            $periods = $periodsData['listTimesheetPeriods'] ?? [];

            // Determine selected period
            $selectedPeriodId = $request->input('periodId', $currentPeriod['periodId'] ?? null);

            // Fetch all submissions for the selected period
            $submissions = [];
            if ($selectedPeriodId) {
                $submissionsData = $this->graphql->query(GraphQLQueries::LIST_ALL_SUBMISSIONS, [
                    'filter' => ['periodId' => $selectedPeriodId],
                ]);
                $submissions = $submissionsData['listAllSubmissions'] ?? [];
            }

            // Fetch users to resolve employee names
            $usersData = $this->graphql->query(GraphQLQueries::LIST_USERS);
            $users = $usersData['listUsers']['items'] ?? [];
            $userMap = [];
            foreach ($users as $user) {
                $userMap[$user['userId']] = $user['fullName'] ?? $user['userId'];
            }

            // Build submission summary rows with chargeability
            $submissionRows = [];
            foreach ($submissions as $submission) {
                $employeeId = $submission['employeeId'] ?? '';

                // Compute totalHours from entries since submission-level totals
                // may not be updated when entries are added
                $computedTotalHours = 0;
                foreach ($submission['entries'] ?? [] as $entry) {
                    $computedTotalHours += (float) ($entry['totalHours'] ?? 0);
                }

                // Use computed total from entries if available, else fall back to submission field
                $totalHours = $computedTotalHours > 0
                    ? $computedTotalHours
                    : (float) ($submission['totalHours'] ?? 0);

                // Use submission-level chargeableHours (set by backend logic)
                // Falls back to totalHours if chargeableHours is 0 (all hours assumed chargeable)
                $chargeableHours = (float) ($submission['chargeableHours'] ?? 0);
                if ($chargeableHours == 0 && $totalHours > 0) {
                    $chargeableHours = $totalHours;
                }

                $chargeability = $totalHours > 0
                    ? round(($chargeableHours / $totalHours) * 100, 1)
                    : 0;

                $submissionRows[] = [
                    'employeeId' => $employeeId,
                    'employeeName' => $userMap[$employeeId] ?? $employeeId,
                    'chargeableHours' => $chargeableHours,
                    'totalHours' => $totalHours,
                    'currentChargeability' => $chargeability,
                    'ytdChargeability' => $chargeability, // YTD defaults to current period
                    'status' => $submission['status'] ?? '',
                ];
            }

            // Compute totals row
            $totals = $this->computeSubmissionTotals($submissionRows);

            return view('pages.reports.submission-summary', [
                'submissionRows' => $submissionRows,
                'totals' => $totals,
                'periods' => $periods,
                'selectedPeriodId' => $selectedPeriodId,
                'currentPeriod' => $currentPeriod,
                'error' => null,
            ]);
        } catch (AuthenticationException $e) {
            return redirect('/login')->withErrors(['auth' => $e->getMessage()]);
        } catch (Exception $e) {
            \Log::error('Submission summary load failed: ' . $e->getMessage());
            return view('pages.reports.submission-summary', [
                'submissionRows' => [],
                'totals' => $this->emptySubmissionTotals(),
                'periods' => [],
                'selectedPeriodId' => null,
                'currentPeriod' => null,
                'error' => 'Unable to load report data: ' . $e->getMessage(),
            ]);
        }
    }

    /**
     * Export Project Summary as PDF (AJAX endpoint).
     *
     * Calls getProjectSummaryReport via GraphQL and returns
     * a JSON response with the pre-signed download URL.
     */
    public function exportProjectPdf(Request $request): JsonResponse
    {
        try {
            $periodId = $request->input('periodId');

            $result = $this->graphql->query(GraphQLQueries::GET_PROJECT_SUMMARY_REPORT, [
                'periodId' => $periodId,
            ]);

            $report = $result['getProjectSummaryReport'] ?? null;

            if ($report && !empty($report['url'])) {
                return response()->json([
                    'success' => true,
                    'url' => $report['url'],
                    'expiresAt' => $report['expiresAt'] ?? null,
                ]);
            }

            return response()->json([
                'success' => false,
                'error' => 'No report URL returned from the API.',
            ]);
        } catch (AuthenticationException $e) {
            return response()->json(['success' => false, 'error' => 'Session expired. Please log in again.'], 401);
        } catch (Exception $e) {
            \Log::error('Project PDF export failed: ' . $e->getMessage());
            return response()->json([
                'success' => false,
                'error' => 'PDF export failed: ' . $e->getMessage(),
            ]);
        }
    }

    /**
     * Export Submission Summary as PDF (AJAX endpoint).
     *
     * Calls getTCSummaryReport via GraphQL with the authenticated
     * user's ID and returns a JSON response with the pre-signed download URL.
     */
    public function exportSubmissionPdf(Request $request): JsonResponse
    {
        try {
            $periodId = $request->input('periodId');
            $user = session('user');
            $techLeadId = $user['userId'] ?? '';

            $result = $this->graphql->query(GraphQLQueries::GET_TC_SUMMARY_REPORT, [
                'techLeadId' => $techLeadId,
                'periodId' => $periodId,
            ]);

            $report = $result['getTCSummaryReport'] ?? null;

            if ($report && !empty($report['url'])) {
                return response()->json([
                    'success' => true,
                    'url' => $report['url'],
                    'expiresAt' => $report['expiresAt'] ?? null,
                ]);
            }

            return response()->json([
                'success' => false,
                'error' => 'No report URL returned from the API.',
            ]);
        } catch (AuthenticationException $e) {
            return response()->json(['success' => false, 'error' => 'Session expired. Please log in again.'], 401);
        } catch (Exception $e) {
            \Log::error('Submission PDF export failed: ' . $e->getMessage());
            return response()->json([
                'success' => false,
                'error' => 'PDF export failed: ' . $e->getMessage(),
            ]);
        }
    }

    /**
     * Compute charged hours grouped by project code from submissions.
     *
     * Iterates through all submission entries and sums totalHours
     * per projectCode. Optionally filters to only specified project codes.
     *
     * @param array $submissions List of submission records
     * @param array|null $projectCodes Optional list of project codes to include
     * @return array<string, float> Map of projectCode => total charged hours
     */
    protected function computeChargedHoursByProject(array $submissions, ?array $projectCodes = null): array
    {
        $projectCodeSet = $projectCodes ? array_flip($projectCodes) : null;
        $charged = [];
        foreach ($submissions as $submission) {
            foreach ($submission['entries'] ?? [] as $entry) {
                $code = $entry['projectCode'] ?? '';
                if ($code === '') {
                    continue;
                }
                if ($projectCodeSet !== null && !isset($projectCodeSet[$code])) {
                    continue;
                }
                $charged[$code] = ($charged[$code] ?? 0) + (float) ($entry['totalHours'] ?? 0);
            }
        }
        return $charged;
    }

    /**
     * Compute totals row for project summary.
     *
     * @param array $rows List of project summary rows
     * @return array Totals with totalPlannedHours, totalChargedHours, overallUtilization
     */
    protected function computeProjectTotals(array $rows): array
    {
        $totalPlanned = 0;
        $totalCharged = 0;
        foreach ($rows as $row) {
            $totalPlanned += $row['plannedHours'];
            $totalCharged += $row['chargedHours'];
        }

        return [
            'totalPlannedHours' => $totalPlanned,
            'totalChargedHours' => $totalCharged,
            'overallUtilization' => $totalPlanned > 0
                ? round(($totalCharged / $totalPlanned) * 100, 1)
                : 0,
        ];
    }

    /**
     * Compute totals row for submission summary.
     *
     * @param array $rows List of submission summary rows
     * @return array Totals with totalChargeableHours, totalTotalHours, overallChargeability
     */
    protected function computeSubmissionTotals(array $rows): array
    {
        $totalChargeable = 0;
        $totalHours = 0;
        foreach ($rows as $row) {
            $totalChargeable += $row['chargeableHours'];
            $totalHours += $row['totalHours'];
        }

        return [
            'totalChargeableHours' => $totalChargeable,
            'totalTotalHours' => $totalHours,
            'overallChargeability' => $totalHours > 0
                ? round(($totalChargeable / $totalHours) * 100, 1)
                : 0,
        ];
    }

    /**
     * Return empty project totals for error states.
     */
    protected function emptyProjectTotals(): array
    {
        return [
            'totalPlannedHours' => 0,
            'totalChargedHours' => 0,
            'overallUtilization' => 0,
        ];
    }

    /**
     * Return empty submission totals for error states.
     */
    protected function emptySubmissionTotals(): array
    {
        return [
            'totalChargeableHours' => 0,
            'totalTotalHours' => 0,
            'overallChargeability' => 0,
        ];
    }
}
