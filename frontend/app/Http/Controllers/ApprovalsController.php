<?php

namespace App\Http\Controllers;

use App\Services\GraphQLClient;
use App\Services\GraphQLQueries;
use Illuminate\Http\Request;
use Illuminate\Routing\Controller;

class ApprovalsController extends Controller
{
    /**
     * Display the approvals page with all pending entities.
     *
     * Fetches projects, departments, and positions via GraphQL,
     * filters client-side by approval_status === 'Pending_Approval',
     * and renders the tabbed approvals view.
     *
     * GET /admin/approvals
     */
    public function index()
    {
        $user = session('user');
        if (!$user || ($user['userType'] ?? '') !== 'superadmin') {
            return redirect('/dashboard');
        }

        $graphql = new GraphQLClient();

        $pendingProjects = [];
        $pendingDepartments = [];
        $pendingPositions = [];

        // Fetch and filter projects
        try {
            $result = $graphql->query(GraphQLQueries::LIST_PROJECTS);
            $projects = $result['listProjects']['items'] ?? [];
            $pendingProjects = array_values(array_filter($projects, function ($item) {
                return ($item['approval_status'] ?? '') === 'Pending_Approval';
            }));
        } catch (\Exception $e) {
            \Log::warning('Approvals: failed to load projects: ' . $e->getMessage());
        }

        // Fetch and filter departments
        try {
            $result = $graphql->query(GraphQLQueries::LIST_DEPARTMENTS);
            $departments = $result['listDepartments'] ?? [];
            $pendingDepartments = array_values(array_filter($departments, function ($item) {
                return ($item['approval_status'] ?? '') === 'Pending_Approval';
            }));
        } catch (\Exception $e) {
            \Log::warning('Approvals: failed to load departments: ' . $e->getMessage());
        }

        // Fetch and filter positions
        try {
            $result = $graphql->query(GraphQLQueries::LIST_POSITIONS);
            $positions = $result['listPositions'] ?? [];
            $pendingPositions = array_values(array_filter($positions, function ($item) {
                return ($item['approval_status'] ?? '') === 'Pending_Approval';
            }));
        } catch (\Exception $e) {
            \Log::warning('Approvals: failed to load positions: ' . $e->getMessage());
        }

        // Build userId → fullName map for "Created By" column
        $userMap = [];
        try {
            $result = $graphql->query(GraphQLQueries::LIST_USERS);
            foreach ($result['listUsers']['items'] ?? [] as $u) {
                $userMap[$u['userId']] = $u['fullName'] ?? $u['userId'];
            }
        } catch (\Exception $e) {}

        return view('pages.admin.approvals', [
            'pendingProjects' => $pendingProjects,
            'pendingDepartments' => $pendingDepartments,
            'pendingPositions' => $pendingPositions,
            'userMap' => $userMap,
        ]);
    }

    /**
     * Approve a pending entity.
     *
     * Maps the $type parameter to the correct GraphQL approve mutation
     * and entity ID variable name.
     *
     * POST /admin/approvals/{type}/{id}/approve
     */
    public function approve(string $type, string $id)
    {
        $user = session('user');
        if (!$user || ($user['userType'] ?? '') !== 'superadmin') {
            return response()->json(['success' => false, 'error' => 'Unauthorized'], 403);
        }

        $mutationMap = [
            'department' => ['mutation' => GraphQLQueries::APPROVE_DEPARTMENT, 'idKey' => 'departmentId', 'resultKey' => 'approveDepartment'],
            'position'   => ['mutation' => GraphQLQueries::APPROVE_POSITION,   'idKey' => 'positionId',   'resultKey' => 'approvePosition'],
            'project'    => ['mutation' => GraphQLQueries::APPROVE_PROJECT,    'idKey' => 'projectId',    'resultKey' => 'approveProject'],
        ];

        if (!isset($mutationMap[$type])) {
            return response()->json(['success' => false, 'error' => 'Invalid entity type'], 422);
        }

        $config = $mutationMap[$type];
        $graphql = new GraphQLClient();

        try {
            $result = $graphql->mutate($config['mutation'], [
                $config['idKey'] => $id,
            ]);

            return response()->json(['success' => true, 'data' => $result[$config['resultKey']] ?? []]);
        } catch (\Exception $e) {
            return response()->json(['success' => false, 'error' => $e->getMessage()], 422);
        }
    }

    /**
     * Reject a pending entity with a reason.
     *
     * Maps the $type parameter to the correct GraphQL reject mutation
     * and includes the rejection reason from the request body.
     *
     * POST /admin/approvals/{type}/{id}/reject
     */
    public function reject(Request $request, string $type, string $id)
    {
        $user = session('user');
        if (!$user || ($user['userType'] ?? '') !== 'superadmin') {
            return response()->json(['success' => false, 'error' => 'Unauthorized'], 403);
        }

        $mutationMap = [
            'department' => ['mutation' => GraphQLQueries::REJECT_DEPARTMENT, 'idKey' => 'departmentId', 'resultKey' => 'rejectDepartment'],
            'position'   => ['mutation' => GraphQLQueries::REJECT_POSITION,   'idKey' => 'positionId',   'resultKey' => 'rejectPosition'],
            'project'    => ['mutation' => GraphQLQueries::REJECT_PROJECT,    'idKey' => 'projectId',    'resultKey' => 'rejectProject'],
        ];

        if (!isset($mutationMap[$type])) {
            return response()->json(['success' => false, 'error' => 'Invalid entity type'], 422);
        }

        $config = $mutationMap[$type];
        $reason = $request->input('reason', '');
        $graphql = new GraphQLClient();

        try {
            $result = $graphql->mutate($config['mutation'], [
                $config['idKey'] => $id,
                'reason' => $reason,
            ]);

            return response()->json(['success' => true, 'data' => $result[$config['resultKey']] ?? []]);
        } catch (\Exception $e) {
            return response()->json(['success' => false, 'error' => $e->getMessage()], 422);
        }
    }
}
