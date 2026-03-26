<?php

namespace App\Services;

use Carbon\Carbon;
use InvalidArgumentException;

class TimesheetEntryMapper
{
    /**
     * Days of the week stored in the backend model (column order).
     */
    protected const DAY_COLUMNS = [
        'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday',
    ];

    /**
     * Working days used for chart data (Mon–Fri).
     */
    protected const WORKING_DAYS = [
        'monday', 'tuesday', 'wednesday', 'thursday', 'friday',
    ];

    /**
     * Flatten weekly entry rows into per-day FlattenedEntry arrays.
     *
     * Each backend entry row (one per project per week) is expanded into
     * individual day rows for every day that has hours > 0.
     *
     * @param array $entries Array of TimesheetEntry rows from GraphQL
     * @param string $weekStartDate ISO date of the week's Monday (e.g., "2026-06-15")
     * @return array Array of FlattenedEntry associative arrays
     */
    public function flattenEntries(array $entries, string $weekStartDate): array
    {
        $flattened = [];
        $weekStart = Carbon::parse($weekStartDate)->startOfDay();

        foreach ($entries as $entry) {
            foreach (self::DAY_COLUMNS as $day) {
                $hours = (float) ($entry[$day] ?? 0);

                if ($hours <= 0) {
                    continue;
                }

                $date = $this->getDateForDay($weekStart, $day);

                $flattened[] = [
                    'entryId'      => $entry['entryId'] ?? '',
                    'date'         => $date->format('Y-m-d'),
                    'dayOfWeek'    => $day,
                    'projectCode'  => $entry['projectCode'] ?? '',
                    'description'  => $entry['projectCode'] ?? '',
                    'chargedHours' => $hours,
                    'isEditable'   => !isset($entry['submissionStatus']) || $entry['submissionStatus'] !== 'Submitted',
                ];
            }
        }

        return $flattened;
    }

    /**
     * Determine the backend operation and build input for a timesheet entry action.
     *
     * Maps a user's date + hours input to the correct day-of-week field and decides
     * whether to add, update, or remove an entry row.
     *
     * @param string $projectCode The project code
     * @param string $date ISO date (e.g., "2026-06-18")
     * @param float $hours Hours to set (0 means delete that day)
     * @param array $existingEntries Current week's entry rows from GraphQL
     * @return array{operation: string, entryId?: string, input?: array}
     */
    public function mapToEntryInput(string $projectCode, string $date, float $hours, array $existingEntries): array
    {
        $dayOfWeek = $this->dateToDayOfWeek($date);
        $existingEntry = $this->findEntryByProject($projectCode, $existingEntries);

        // No existing row for this project — create a new one
        if ($existingEntry === null) {
            return [
                'operation' => 'add',
                'input'     => $this->buildEntryInput($projectCode, $dayOfWeek, $hours),
            ];
        }

        $entryId = $existingEntry['entryId'];

        // User is zeroing out this day
        if ($hours <= 0) {
            return $this->handleZeroHours($existingEntry, $dayOfWeek, $entryId);
        }

        // Update the existing row with new hours on the target day
        return [
            'operation' => 'update',
            'entryId'   => $entryId,
            'input'     => $this->buildEntryInputFromExisting($existingEntry, $dayOfWeek, $hours),
        ];
    }

    /**
     * Calculate the total hours across all entries for the week.
     *
     * @param array $entries Array of TimesheetEntry rows from GraphQL
     * @return float Total hours
     */
    public function calculateWeeklyTotal(array $entries): float
    {
        $total = 0.0;

        foreach ($entries as $entry) {
            foreach (self::DAY_COLUMNS as $day) {
                $total += (float) ($entry[$day] ?? 0);
            }
        }

        return round($total, 2);
    }

    /**
     * Calculate daily hour totals (Mon–Fri) across all entries for chart data.
     *
     * @param array $entries Array of TimesheetEntry rows from GraphQL
     * @return array{monday: float, tuesday: float, wednesday: float, thursday: float, friday: float}
     */
    public function calculateDailyTotals(array $entries): array
    {
        $totals = [];

        foreach (self::WORKING_DAYS as $day) {
            $totals[$day] = 0.0;
        }

        foreach ($entries as $entry) {
            foreach (self::WORKING_DAYS as $day) {
                $totals[$day] += (float) ($entry[$day] ?? 0);
            }
        }

        // Round each total
        foreach ($totals as $day => $hours) {
            $totals[$day] = round($hours, 2);
        }

        return $totals;
    }

    /**
     * Handle zeroing out a day field — either update or remove the entire row.
     *
     * @param array $existingEntry The existing entry row
     * @param string $dayOfWeek The day to zero out
     * @param string $entryId The entry ID
     * @return array
     */
    protected function handleZeroHours(array $existingEntry, string $dayOfWeek, string $entryId): array
    {
        // Check if any other day still has hours after zeroing this one
        $hasOtherHours = false;

        foreach (self::DAY_COLUMNS as $day) {
            if ($day === $dayOfWeek) {
                continue;
            }
            if ((float) ($existingEntry[$day] ?? 0) > 0) {
                $hasOtherHours = true;
                break;
            }
        }

        if (!$hasOtherHours) {
            // Last day with hours — remove the entire row
            return [
                'operation' => 'remove',
                'entryId'   => $entryId,
            ];
        }

        // Other days still have hours — zero out just this day
        return [
            'operation' => 'update',
            'entryId'   => $entryId,
            'input'     => $this->buildEntryInputFromExisting($existingEntry, $dayOfWeek, 0),
        ];
    }

    /**
     * Build a fresh TimesheetEntryInput with hours on one day and zeros elsewhere.
     *
     * @param string $projectCode
     * @param string $dayOfWeek
     * @param float $hours
     * @return array
     */
    protected function buildEntryInput(string $projectCode, string $dayOfWeek, float $hours): array
    {
        $input = ['projectCode' => $projectCode];

        foreach (self::DAY_COLUMNS as $day) {
            $input[$day] = ($day === $dayOfWeek) ? $hours : 0;
        }

        return $input;
    }

    /**
     * Build a TimesheetEntryInput from an existing entry, overriding one day's hours.
     *
     * @param array $existingEntry
     * @param string $dayOfWeek
     * @param float $hours
     * @return array
     */
    protected function buildEntryInputFromExisting(array $existingEntry, string $dayOfWeek, float $hours): array
    {
        $input = ['projectCode' => $existingEntry['projectCode']];

        foreach (self::DAY_COLUMNS as $day) {
            $input[$day] = ($day === $dayOfWeek) ? $hours : (float) ($existingEntry[$day] ?? 0);
        }

        return $input;
    }

    /**
     * Map an ISO date string to its day-of-week column name.
     *
     * @param string $date ISO date (e.g., "2026-06-18")
     * @return string Day name (e.g., "wednesday")
     * @throws InvalidArgumentException If the date cannot be parsed
     */
    protected function dateToDayOfWeek(string $date): string
    {
        try {
            return strtolower(Carbon::parse($date)->format('l'));
        } catch (\Exception $e) {
            throw new InvalidArgumentException("Invalid date: {$date}");
        }
    }

    /**
     * Get the calendar date for a given day-of-week relative to the week start (Monday).
     *
     * @param Carbon $weekStart The Monday of the week
     * @param string $day Day column name (e.g., "wednesday")
     * @return Carbon
     */
    protected function getDateForDay(Carbon $weekStart, string $day): Carbon
    {
        $dayOffsets = [
            'monday'    => 0,
            'tuesday'   => 1,
            'wednesday' => 2,
            'thursday'  => 3,
            'friday'    => 4,
            'saturday'  => 5,
            'sunday'    => 6,
        ];

        $offset = $dayOffsets[$day] ?? 0;

        return $weekStart->copy()->addDays($offset);
    }

    /**
     * Find an existing entry row for a given project code.
     *
     * @param string $projectCode
     * @param array $entries
     * @return array|null The matching entry or null
     */
    protected function findEntryByProject(string $projectCode, array $entries): ?array
    {
        foreach ($entries as $entry) {
            if (($entry['projectCode'] ?? '') === $projectCode) {
                return $entry;
            }
        }

        return null;
    }
}
