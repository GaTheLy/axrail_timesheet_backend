<?php

namespace App\Http\Controllers;

use App\Services\GraphQLClient;
use App\Services\TimesheetEntryMapper;
use Exception;
use Illuminate\Auth\AuthenticationException;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Routing\Controller;

class HistoryController extends Controller
{
    protected GraphQLClient $graphql;
    protected TimesheetEntryMapper $mapper;

    public function __construct(GraphQLClient $graphql, TimesheetEntryMapper $mapper)
    {
        $this->graphql = $graphql;
        $this->mapper = $mapper;
    }

    /**
     * Render the history page with all past submissions flattened into per-day entries.
     */
    public function index()
    {
        try {
            $allEntries = $this->fetchAllFlattenedEntries();
            $weeklyTotal = $this->calculateTotalFromFlattened($allEntries);

            return view('pages.history', [
                'entries' => $allEntries,
                'totalEntries' => count($allEntries),
                'weeklyTotal' => $weeklyTotal,
                'error' => null,
            ]);
        } catch (AuthenticationException $e) {
            return redirect('/login')->withErrors(['auth' => $e->getMessage()]);
        } catch (Exception $e) {
            \Log::error('History load failed: ' . $e->getMessage());
            return view('pages.history', [
                'entries' => [],
                'totalEntries' => 0,
                'weeklyTotal' => 0,
                'error' => 'Unable to load history data. Please try again.',
            ]);
        }
    }

    /**
     * Filter history entries by date range (AJAX).
     */
    public function filter(Request $request): JsonResponse
    {
        $request->validate([
            'start_date' => 'required|date',
            'end_date' => 'required|date|after_or_equal:start_date',
        ]);

        try {
            $startDate = $request->input('start_date');
            $endDate = $request->input('end_date');

            $allEntries = $this->fetchAllFlattenedEntries();
            $filtered = $this->filterEntriesByDateRange($allEntries, $startDate, $endDate);
            $weeklyTotal = $this->calculateTotalFromFlattened($filtered);

            return response()->json([
                'success' => true,
                'data' => $filtered,
                'count' => count($filtered),
                'weeklyTotal' => $weeklyTotal,
            ]);
        } catch (AuthenticationException $e) {
            return response()->json(['error' => 'Session expired. Please log in again.'], 401);
        } catch (Exception $e) {
            return response()->json(['error' => $e->getMessage()], 500);
        }
    }

    /**
     * Fetch all submissions and flatten their entries into per-day rows.
     *
     * For each submission, the period's startDate is needed to correctly
     * map day-of-week columns to calendar dates via flattenEntries().
     *
     * @return array Array of FlattenedEntry associative arrays
     */
    protected function fetchAllFlattenedEntries(): array
    {
        // Fetch all submissions (no filter)
        $submissionData = $this->graphql->query(
            'query ListMySubmissions { listMySubmissions { submissionId periodId status entries { entryId projectCode monday tuesday wednesday thursday friday saturday sunday } } }'
        );

        $submissions = $submissionData['listMySubmissions'] ?? [];

        if (empty($submissions)) {
            return [];
        }

        // Fetch all periods to map periodId → startDate
        $periodData = $this->graphql->query(
            'query ListTimesheetPeriods { listTimesheetPeriods { periodId startDate endDate } }'
        );

        $periods = $periodData['listTimesheetPeriods'] ?? [];
        $periodMap = [];
        foreach ($periods as $period) {
            $periodMap[$period['periodId']] = $period['startDate'];
        }

        // Flatten entries from all submissions
        $allEntries = [];
        foreach ($submissions as $submission) {
            $periodId = $submission['periodId'] ?? '';
            $startDate = $periodMap[$periodId] ?? null;

            if (!$startDate) {
                continue;
            }

            $entries = $submission['entries'] ?? [];
            $flattened = $this->mapper->flattenEntries($entries, $startDate);
            $allEntries = array_merge($allEntries, $flattened);
        }

        // Sort by date descending (most recent first)
        usort($allEntries, function ($a, $b) {
            return strcmp($b['date'], $a['date']);
        });

        return $allEntries;
    }

    /**
     * Filter flattened entries to only those within the given date range.
     *
     * @param array $entries Array of FlattenedEntry arrays
     * @param string $startDate ISO date (e.g., "2026-06-01")
     * @param string $endDate ISO date (e.g., "2026-06-30")
     * @return array Filtered entries
     */
    protected function filterEntriesByDateRange(array $entries, string $startDate, string $endDate): array
    {
        return array_values(array_filter($entries, function ($entry) use ($startDate, $endDate) {
            $entryDate = $entry['date'] ?? '';
            return $entryDate >= $startDate && $entryDate <= $endDate;
        }));
    }

    /**
     * Calculate total hours from flattened entries.
     *
     * @param array $flattenedEntries Array of FlattenedEntry arrays
     * @return float Total charged hours
     */
    protected function calculateTotalFromFlattened(array $flattenedEntries): float
    {
        $total = 0.0;
        foreach ($flattenedEntries as $entry) {
            $total += (float) ($entry['chargedHours'] ?? 0);
        }
        return round($total, 2);
    }
}
