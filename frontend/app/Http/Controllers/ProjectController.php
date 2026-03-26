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
            'error' => null,
        ]);
    }

    public function store(Request $request)
    {
        $graphql = new GraphQLClient();

        try {
            $result = $graphql->mutate(GraphQLQueries::CREATE_PROJECT, [
                'input' => [
                    'projectCode' => $request->input('projectCode'),
                    'projectName' => $request->input('projectName'),
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

    public function update(Request $request, string $id)
    {
        $graphql = new GraphQLClient();

        $input = [];
        if ($request->has('projectName')) $input['projectName'] = $request->input('projectName');
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
