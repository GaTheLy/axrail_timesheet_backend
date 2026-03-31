<?php

namespace App\Http\Controllers;

use App\Services\GraphQLClient;
use App\Services\GraphQLQueries;
use Illuminate\Http\Request;
use Illuminate\Routing\Controller;

class DepartmentController extends Controller
{
    public function index()
    {
        $graphql = new GraphQLClient();

        try {
            $result = $graphql->query(GraphQLQueries::LIST_DEPARTMENTS);
            $departments = $result['listDepartments'] ?? [];
        } catch (\Exception $e) {
            return view('pages.admin.departments', [
                'departments' => [],
                'userMap' => [],
                'error' => 'Failed to load departments: ' . $e->getMessage(),
            ]);
        }

        // Build userId → fullName map for "Created By" column
        $userMap = [];
        try {
            $usersResult = $graphql->query(GraphQLQueries::LIST_USERS);
            foreach ($usersResult['listUsers']['items'] ?? [] as $u) {
                $userMap[$u['userId']] = $u['fullName'] ?? $u['userId'];
            }
        } catch (\Exception $e) {}

        return view('pages.admin.departments', [
            'departments' => $departments,
            'userMap' => $userMap,
            'error' => null,
        ]);
    }

    public function store(Request $request)
    {
        $request->validate([
            'departmentName' => ['required', 'string', 'max:255', 'regex:/^[^=+\-@\t\r].*/'],
        ], [
            'departmentName.regex' => 'Department name cannot start with =, +, -, or @ characters.',
        ]);

        $graphql = new GraphQLClient();

        try {
            $result = $graphql->mutate(GraphQLQueries::CREATE_DEPARTMENT, [
                'input' => [
                    'departmentName' => $this->sanitizeFormulaChars($request->input('departmentName')),
                ],
            ]);

            return response()->json(['success' => true, 'data' => $result['createDepartment'] ?? []]);
        } catch (\Exception $e) {
            return response()->json(['success' => false, 'error' => $e->getMessage()], 422);
        }
    }

    public function approve(string $id)
    {
        $graphql = new GraphQLClient();

        try {
            $result = $graphql->mutate(GraphQLQueries::APPROVE_DEPARTMENT, [
                'departmentId' => $id,
            ]);

            return response()->json(['success' => true, 'data' => $result['approveDepartment'] ?? []]);
        } catch (\Exception $e) {
            return response()->json(['success' => false, 'error' => $e->getMessage()], 422);
        }
    }

    public function reject(Request $request, string $id)
    {
        $graphql = new GraphQLClient();

        try {
            $result = $graphql->mutate(GraphQLQueries::REJECT_DEPARTMENT, [
                'departmentId' => $id,
                'reason' => $request->input('reason', ''),
            ]);

            return response()->json(['success' => true, 'data' => $result['rejectDepartment'] ?? []]);
        } catch (\Exception $e) {
            return response()->json(['success' => false, 'error' => $e->getMessage()], 422);
        }
    }

    public function destroy(string $id)
    {
        $graphql = new GraphQLClient();

        try {
            $graphql->mutate(GraphQLQueries::DELETE_DEPARTMENT, [
                'departmentId' => $id,
            ]);

            return response()->json(['success' => true]);
        } catch (\Exception $e) {
            return response()->json(['success' => false, 'error' => $e->getMessage()], 422);
        }
    }

    public function update(Request $request, string $id)
    {
        $request->validate([
            'departmentName' => ['required', 'string', 'max:255', 'regex:/^[^=+\-@\t\r].*/'],
        ], [
            'departmentName.regex' => 'Department name cannot start with =, +, -, or @ characters.',
        ]);

        $graphql = new GraphQLClient();

        try {
            $result = $graphql->mutate(GraphQLQueries::UPDATE_DEPARTMENT, [
                'departmentId' => $id,
                'input' => [
                    'departmentName' => $this->sanitizeFormulaChars($request->input('departmentName')),
                ],
            ]);

            return response()->json(['success' => true, 'data' => $result['updateDepartment'] ?? []]);
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
