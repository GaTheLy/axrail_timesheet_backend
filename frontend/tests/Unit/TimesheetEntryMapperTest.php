<?php

namespace Tests\Unit;

use App\Services\TimesheetEntryMapper;
use PHPUnit\Framework\TestCase;

class TimesheetEntryMapperTest extends TestCase
{
    protected TimesheetEntryMapper $mapper;

    protected function setUp(): void
    {
        parent::setUp();
        $this->mapper = new TimesheetEntryMapper();
    }

    // ---------------------------------------------------------------
    // flattenEntries
    // ---------------------------------------------------------------

    public function test_flatten_entries_produces_per_day_rows(): void
    {
        $entries = [
            [
                'entryId'     => 'entry-1',
                'projectCode' => 'PROJ-001',
                'projectName' => 'Project Alpha',
                'monday'      => 8.0,
                'tuesday'     => 4.5,
                'wednesday'   => 0,
                'thursday'    => 0,
                'friday'      => 7.0,
                'saturday'    => 0,
                'sunday'      => 0,
            ],
        ];

        // Week starting Monday 2026-06-15
        $result = $this->mapper->flattenEntries($entries, '2026-06-15');

        $this->assertCount(3, $result);

        $this->assertEquals('2026-06-15', $result[0]['date']);
        $this->assertEquals('monday', $result[0]['dayOfWeek']);
        $this->assertEquals(8.0, $result[0]['chargedHours']);
        $this->assertEquals('PROJ-001', $result[0]['projectCode']);

        $this->assertEquals('2026-06-16', $result[1]['date']);
        $this->assertEquals('tuesday', $result[1]['dayOfWeek']);
        $this->assertEquals(4.5, $result[1]['chargedHours']);

        $this->assertEquals('2026-06-19', $result[2]['date']);
        $this->assertEquals('friday', $result[2]['dayOfWeek']);
        $this->assertEquals(7.0, $result[2]['chargedHours']);
    }

    public function test_flatten_entries_excludes_zero_hour_days(): void
    {
        $entries = [
            [
                'entryId'     => 'entry-1',
                'projectCode' => 'PROJ-001',
                'projectName' => 'Test',
                'monday'      => 0,
                'tuesday'     => 0,
                'wednesday'   => 3.0,
                'thursday'    => 0,
                'friday'      => 0,
                'saturday'    => 0,
                'sunday'      => 0,
            ],
        ];

        $result = $this->mapper->flattenEntries($entries, '2026-06-15');

        $this->assertCount(1, $result);
        $this->assertEquals('wednesday', $result[0]['dayOfWeek']);
        $this->assertEquals(3.0, $result[0]['chargedHours']);
    }

    public function test_flatten_entries_empty_array_returns_empty(): void
    {
        $result = $this->mapper->flattenEntries([], '2026-06-15');
        $this->assertEmpty($result);
    }

    public function test_flatten_entries_marks_submitted_as_not_editable(): void
    {
        $entries = [
            [
                'entryId'          => 'entry-1',
                'projectCode'      => 'PROJ-001',
                'projectName'      => 'Test',
                'submissionStatus' => 'Submitted',
                'monday'           => 8.0,
                'tuesday'          => 0,
                'wednesday'        => 0,
                'thursday'         => 0,
                'friday'           => 0,
                'saturday'         => 0,
                'sunday'           => 0,
            ],
        ];

        $result = $this->mapper->flattenEntries($entries, '2026-06-15');

        $this->assertCount(1, $result);
        $this->assertFalse($result[0]['isEditable']);
    }

    // ---------------------------------------------------------------
    // mapToEntryInput
    // ---------------------------------------------------------------

    public function test_map_new_project_returns_add_operation(): void
    {
        $result = $this->mapper->mapToEntryInput('PROJ-NEW', '2026-06-18', 4.5, []);

        $this->assertEquals('add', $result['operation']);
        $this->assertArrayNotHasKey('entryId', $result);
        $this->assertEquals('PROJ-NEW', $result['input']['projectCode']);
        $this->assertEquals(4.5, $result['input']['wednesday']);
        $this->assertEquals(0, $result['input']['monday']);
        $this->assertEquals(0, $result['input']['friday']);
    }

    public function test_map_existing_project_returns_update_operation(): void
    {
        $existing = [
            [
                'entryId'     => 'entry-1',
                'projectCode' => 'PROJ-001',
                'monday'      => 8.0,
                'tuesday'     => 0,
                'wednesday'   => 0,
                'thursday'    => 0,
                'friday'      => 0,
                'saturday'    => 0,
                'sunday'      => 0,
            ],
        ];

        $result = $this->mapper->mapToEntryInput('PROJ-001', '2026-06-18', 4.5, $existing);

        $this->assertEquals('update', $result['operation']);
        $this->assertEquals('entry-1', $result['entryId']);
        $this->assertEquals(8.0, $result['input']['monday']);
        $this->assertEquals(4.5, $result['input']['wednesday']);
    }

    public function test_map_zero_hours_with_other_days_returns_update(): void
    {
        $existing = [
            [
                'entryId'     => 'entry-1',
                'projectCode' => 'PROJ-001',
                'monday'      => 8.0,
                'tuesday'     => 4.0,
                'wednesday'   => 0,
                'thursday'    => 0,
                'friday'      => 0,
                'saturday'    => 0,
                'sunday'      => 0,
            ],
        ];

        $result = $this->mapper->mapToEntryInput('PROJ-001', '2026-06-15', 0, $existing);

        $this->assertEquals('update', $result['operation']);
        $this->assertEquals('entry-1', $result['entryId']);
        $this->assertEquals(0, $result['input']['monday']);
        $this->assertEquals(4.0, $result['input']['tuesday']);
    }

    public function test_map_zero_hours_last_day_returns_remove(): void
    {
        $existing = [
            [
                'entryId'     => 'entry-1',
                'projectCode' => 'PROJ-001',
                'monday'      => 8.0,
                'tuesday'     => 0,
                'wednesday'   => 0,
                'thursday'    => 0,
                'friday'      => 0,
                'saturday'    => 0,
                'sunday'      => 0,
            ],
        ];

        $result = $this->mapper->mapToEntryInput('PROJ-001', '2026-06-15', 0, $existing);

        $this->assertEquals('remove', $result['operation']);
        $this->assertEquals('entry-1', $result['entryId']);
        $this->assertArrayNotHasKey('input', $result);
    }

    public function test_map_date_to_correct_day_of_week(): void
    {
        // 2026-06-15 is Monday, 2026-06-16 is Tuesday, ..., 2026-06-19 is Friday
        $days = [
            '2026-06-15' => 'monday',
            '2026-06-16' => 'tuesday',
            '2026-06-17' => 'wednesday',
            '2026-06-18' => 'thursday',
            '2026-06-19' => 'friday',
            '2026-06-20' => 'saturday',
            '2026-06-21' => 'sunday',
        ];

        foreach ($days as $date => $expectedDay) {
            $result = $this->mapper->mapToEntryInput('PROJ-001', $date, 2.0, []);
            $this->assertEquals(2.0, $result['input'][$expectedDay], "Failed for date {$date} -> {$expectedDay}");
        }
    }

    // ---------------------------------------------------------------
    // calculateWeeklyTotal
    // ---------------------------------------------------------------

    public function test_calculate_weekly_total_sums_all_days(): void
    {
        $entries = [
            [
                'monday' => 8.0, 'tuesday' => 4.5, 'wednesday' => 0,
                'thursday' => 0, 'friday' => 7.0, 'saturday' => 0, 'sunday' => 0,
            ],
            [
                'monday' => 0, 'tuesday' => 3.0, 'wednesday' => 6.0,
                'thursday' => 0, 'friday' => 0, 'saturday' => 0, 'sunday' => 0,
            ],
        ];

        $this->assertEquals(28.5, $this->mapper->calculateWeeklyTotal($entries));
    }

    public function test_calculate_weekly_total_empty_entries(): void
    {
        $this->assertEquals(0.0, $this->mapper->calculateWeeklyTotal([]));
    }

    // ---------------------------------------------------------------
    // calculateDailyTotals
    // ---------------------------------------------------------------

    public function test_calculate_daily_totals_returns_mon_to_fri(): void
    {
        $entries = [
            [
                'monday' => 8.0, 'tuesday' => 4.5, 'wednesday' => 0,
                'thursday' => 2.0, 'friday' => 7.0, 'saturday' => 3.0, 'sunday' => 1.0,
            ],
        ];

        $totals = $this->mapper->calculateDailyTotals($entries);

        $this->assertCount(5, $totals);
        $this->assertEquals(8.0, $totals['monday']);
        $this->assertEquals(4.5, $totals['tuesday']);
        $this->assertEquals(0.0, $totals['wednesday']);
        $this->assertEquals(2.0, $totals['thursday']);
        $this->assertEquals(7.0, $totals['friday']);
        $this->assertArrayNotHasKey('saturday', $totals);
        $this->assertArrayNotHasKey('sunday', $totals);
    }

    public function test_calculate_daily_totals_sums_across_entries(): void
    {
        $entries = [
            [
                'monday' => 4.0, 'tuesday' => 0, 'wednesday' => 0,
                'thursday' => 0, 'friday' => 0, 'saturday' => 0, 'sunday' => 0,
            ],
            [
                'monday' => 3.5, 'tuesday' => 0, 'wednesday' => 0,
                'thursday' => 0, 'friday' => 0, 'saturday' => 0, 'sunday' => 0,
            ],
        ];

        $totals = $this->mapper->calculateDailyTotals($entries);
        $this->assertEquals(7.5, $totals['monday']);
    }

    public function test_calculate_daily_totals_empty_entries(): void
    {
        $totals = $this->mapper->calculateDailyTotals([]);

        $this->assertCount(5, $totals);
        foreach ($totals as $hours) {
            $this->assertEquals(0.0, $hours);
        }
    }
}
