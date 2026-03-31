<?php

namespace App\Http\Controllers;

use App\Services\GraphQLClient;
use App\Services\GraphQLQueries;
use Illuminate\Http\Request;
use Illuminate\Routing\Controller;

class ProjectController extends Controller
{
    public function index()
    {
        $graphql = new GraphQLClient();

        try {
            $result = $graphql->query(GraphQLQueries::LIST_PROJECTS);
            $projects = $result['listProjects']['items'] ?? [];
        } catch (\Exception $e) {
            return view('pages.admin.projects', [
                'projects' => [],
                'users' => [],
                'error' => 'Failed to load projects: ' . $e->getMessage(),
            ]);
        }

        // Fetch users for the Project Manager dropdown
        $users = [];
        try {
            $usersResult = $graphql->query(GraphQLQueries::LIST_USERS);
            $users = $usersResult['listUsers']['items'] ?? [];
        } catch (\Exception $e) {
            \Log::warning('Failed to load users for project form: ' . $e->getMessage());
        }

        return view('pages.admin.projects', [
            'projects' => $projects,
            'users' => $users,
            'userMap' => collect($users)->pluck('fullName', 'userId')->toArray(),
            'error' => null,
        ]);
    }

    public function store(Request $request)
    {
        $request->validate([
            'projectCode' => ['required', 'string', 'max:50', 'regex:/^[^=+\-@\t\r].*/'],
            'projectName' => ['required', 'string', 'max:255', 'regex:/^[^=+\-@\t\r].*/'],
            'startDate' => ['required', 'date'],
            'plannedHours' => ['required', 'numeric', 'min:0'],
            'projectManagerId' => ['nullable', 'string'],
        ], [
            'projectCode.regex' => 'Project code cannot start with =, +, -, or @ characters.',
            'projectName.regex' => 'Project name cannot start with =, +, -, or @ characters.',
        ]);

        $graphql = new GraphQLClient();

        try {
            $result = $graphql->mutate(GraphQLQueries::CREATE_PROJECT, [
                'input' => [
                    'projectCode' => $this->sanitizeFormulaChars($request->input('projectCode')),
                    'projectName' => $this->sanitizeFormulaChars($request->input('projectName')),
                    'startDate' => $request->input('startDate'),
                    'plannedHours' => (float) $request->input('plannedHours'),
                    'projectManagerId' => $request->input('projectManagerId'),
                ],
            ]);

            return response()->json(['success' => true, 'data' => $result['createProject'] ?? []]);
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
        
        // If string starts with formula characters, prefix with single quote
        if (preg_match('/^[=+\-@\t\r]/', $value)) {
            return "'" . $value;
        }
        
        return $value;
    }

    public function update(Request $request, string $id)
    {
        if ($request->has('projectName')) {
            $request->validate([
                'projectName' => ['string', 'max:255', 'regex:/^[^=+\-@\t\r].*/'],
            ], [
                'projectName.regex' => 'Project name cannot start with =, +, -, or @ characters.',
            ]);
        }
        if ($request->has('projectCode')) {
            $request->validate([
                'projectCode' => ['string', 'max:50', 'regex:/^[^=+\-@\t\r].*/'],
            ], [
                'projectCode.regex' => 'Project code cannot start with =, +, -, or @ characters.',
            ]);
        }

        $graphql = new GraphQLClient();

        $input = [];
        if ($request->has('projectCode')) $input['projectCode'] = $this->sanitizeFormulaChars($request->input('projectCode'));
        if ($request->has('projectName')) $input['projectName'] = $this->sanitizeFormulaChars($request->input('projectName'));
        if ($request->has('startDate')) $input['startDate'] = $request->input('startDate');
        if ($request->has('plannedHours')) $input['plannedHours'] = (float) $request->input('plannedHours');
        if ($request->has('projectManagerId')) $input['projectManagerId'] = $request->input('projectManagerId');
        if ($request->has('status')) $input['status'] = $request->input('status');

        try {
            $result = $graphql->mutate(GraphQLQueries::UPDATE_PROJECT, [
                'projectId' => $id,
                'input' => $input,
            ]);

            return response()->json(['success' => true, 'data' => $result['updateProject'] ?? []]);
        } catch (\Exception $e) {
            return response()->json(['success' => false, 'error' => $e->getMessage()], 422);
        }
    }

    public function destroy(string $id)
    {
        $graphql = new GraphQLClient();

        try {
            $graphql->mutate(GraphQLQueries::DELETE_PROJECT, [
                'projectId' => $id,
            ]);

            return response()->json(['success' => true]);
        } catch (\Exception $e) {
            return response()->json(['success' => false, 'error' => $e->getMessage()], 422);
        }
    }
}
