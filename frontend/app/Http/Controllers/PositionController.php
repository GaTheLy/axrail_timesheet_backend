<?php

namespace App\Http\Controllers;

use App\Services\GraphQLClient;
use App\Services\GraphQLQueries;
use Illuminate\Http\Request;
use Illuminate\Routing\Controller;

class PositionController extends Controller
{
    public function index()
    {
        $graphql = new GraphQLClient();

        try {
            $result = $graphql->query(GraphQLQueries::LIST_POSITIONS);
            $positions = $result['listPositions'] ?? [];
        } catch (\Exception $e) {
            return view('pages.admin.positions', [
                'positions' => [],
                'departments' => [],
                'error' => 'Failed to load positions: ' . $e->getMessage(),
            ]);
        }

        $departments = [];
        try {
            $deptResult = $graphql->query(GraphQLQueries::LIST_DEPARTMENTS);
            $departments = $deptResult['listDepartments'] ?? [];
        } catch (\Exception $e) {}

        return view('pages.admin.positions', [
            'positions' => $positions,
            'departments' => $departments,
            'error' => null,
        ]);
    }

    public function store(Request $request)
    {
        $request->validate([
            'positionName' => ['required', 'string', 'max:255', 'regex:/^[^=+\-@\t\r].*/'],
        ], [
            'positionName.regex' => 'Position name cannot start with =, +, -, or @ characters.',
        ]);

        $graphql = new GraphQLClient();

        $input = ['positionName' => $this->sanitizeFormulaChars($request->input('positionName'))];
        $departmentId = $request->input('departmentId');
        if ($departmentId) $input['departmentId'] = $departmentId;

        try {
            $result = $graphql->mutate(GraphQLQueries::CREATE_POSITION, ['input' => $input]);
            return response()->json(['success' => true, 'data' => $result['createPosition'] ?? []]);
        } catch (\Exception $e) {
            return response()->json(['success' => false, 'error' => $e->getMessage()], 422);
        }
    }

    public function approve(string $id)
    {
        $graphql = new GraphQLClient();

        try {
            $result = $graphql->mutate(GraphQLQueries::APPROVE_POSITION, [
                'positionId' => $id,
            ]);

            return response()->json(['success' => true, 'data' => $result['approvePosition'] ?? []]);
        } catch (\Exception $e) {
            return response()->json(['success' => false, 'error' => $e->getMessage()], 422);
        }
    }

    public function reject(Request $request, string $id)
    {
        $graphql = new GraphQLClient();

        try {
            $result = $graphql->mutate(GraphQLQueries::REJECT_POSITION, [
                'positionId' => $id,
                'reason' => $request->input('reason', ''),
            ]);

            return response()->json(['success' => true, 'data' => $result['rejectPosition'] ?? []]);
        } catch (\Exception $e) {
            return response()->json(['success' => false, 'error' => $e->getMessage()], 422);
        }
    }

    public function destroy(string $id)
    {
        $graphql = new GraphQLClient();

        try {
            $graphql->mutate(GraphQLQueries::DELETE_POSITION, [
                'positionId' => $id,
            ]);

            return response()->json(['success' => true]);
        } catch (\Exception $e) {
            return response()->json(['success' => false, 'error' => $e->getMessage()], 422);
        }
    }

    public function update(Request $request, string $id)
    {
        $request->validate([
            'positionName' => ['required', 'string', 'max:255', 'regex:/^[^=+\-@\t\r].*/'],
        ], [
            'positionName.regex' => 'Position name cannot start with =, +, -, or @ characters.',
        ]);

        $graphql = new GraphQLClient();

        $input = ['positionName' => $this->sanitizeFormulaChars($request->input('positionName'))];
        $departmentId = $request->input('departmentId');
        if ($departmentId !== null) $input['departmentId'] = $departmentId;

        try {
            $result = $graphql->mutate(GraphQLQueries::UPDATE_POSITION, [
                'positionId' => $id,
                'input' => $input,
            ]);

            return response()->json(['success' => true, 'data' => $result['updatePosition'] ?? []]);
        } catch (\Exception $e) {
            return response()->json(['success' => false, 'error' => $e->getMessage()], 422);
        }
    }

    /**
     * Sanitize string to prevent CSV formula injection.
     * Prefixes dangerous characters with a single quote to neutralize formulas.
     */
    private function sanitizeFormulaChars(?string $value): ?string
    {
        if ($value === null) {
            return null;
        }
        
        if (preg_match('/^[=+\-@\t\r]/', $value)) {
            return "'" . $value;
        }
        
        return $value;
    }

}
