<?php

namespace App\Http\Controllers;

use App\Services\GraphQLClient;
use App\Services\GraphQLQueries;
use Illuminate\Http\Request;
use Illuminate\Routing\Controller;

class UserManagementController extends Controller
{
    /**
     * Display the User Management page with all users.
     */
    public function index(Request $request)
    {
        $graphql = new GraphQLClient();

        // Fetch users
        $users = [];
        try {
            $result = $graphql->query(GraphQLQueries::LIST_USERS_FULL);
            $users = $result['listUsers']['items'] ?? [];
        } catch (\Exception $e) {
            try {
                $result = $graphql->query(GraphQLQueries::LIST_USERS_MINIMAL);
                $users = $result['listUsers']['items'] ?? [];
            } catch (\Exception $e2) {
                return view('pages.user-management', [
                    'users' => [],
                    'departments' => [],
                    'positions' => [],
                    'error' => 'Failed to load users: ' . $e2->getMessage(),
                ]);
            }
        }

        // Fetch departments and positions for dropdowns
        $departments = [];
        $positions = [];
        try {
            $deptResult = $graphql->query(GraphQLQueries::LIST_DEPARTMENTS);
            $departments = $deptResult['listDepartments'] ?? [];
        } catch (\Exception $e) {}
        try {
            $posResult = $graphql->query(GraphQLQueries::LIST_POSITIONS);
            $positions = $posResult['listPositions'] ?? [];
        } catch (\Exception $e) {}

        return view('pages.user-management', [
            'users' => $users,
            'departments' => $departments,
            'positions' => $positions,
            'error' => null,
        ]);
    }

    /**
     * Create a new user via GraphQL mutation.
     */
    public function store(Request $request)
    {
        $graphql = new GraphQLClient();

        $input = [
            'email'        => $request->input('email'),
            'fullName'     => $request->input('fullName'),
            'userType'     => 'user',
            'role'         => 'Employee',
            'positionId'   => $request->input('positionId', ''),
            'departmentId' => $request->input('departmentId', ''),
        ];

        try {
            $result = $graphql->mutate(GraphQLQueries::CREATE_USER, [
                'input' => $input,
            ]);

            return response()->json(['success' => true, 'data' => $result['createUser'] ?? []]);
        } catch (\Exception $e) {
            return response()->json(['success' => false, 'error' => $e->getMessage()], 422);
        }
    }

    /**
     * Update a user via GraphQL mutation.
     */
    public function update(Request $request, string $userId)
    {
        $graphql = new GraphQLClient();

        $input = array_filter([
            'fullName'     => $request->input('fullName'),
            'email'        => $request->input('email'),
            'positionId'   => $request->input('positionId'),
            'departmentId' => $request->input('departmentId'),
        ], fn($v) => $v !== null);

        try {
            $result = $graphql->mutate(GraphQLQueries::UPDATE_USER, [
                'userId' => $userId,
                'input'  => $input,
            ]);

            return response()->json(['success' => true, 'data' => $result['updateUser'] ?? []]);
        } catch (\Exception $e) {
            return response()->json(['success' => false, 'error' => $e->getMessage()], 422);
        }
    }

    /**
     * Delete a user via GraphQL mutation.
     */
    public function destroy(string $userId)
    {
        $graphql = new GraphQLClient();

        try {
            $graphql->mutate(GraphQLQueries::DELETE_USER, [
                'userId' => $userId,
            ]);

            return response()->json(['success' => true]);
        } catch (\Exception $e) {
            return response()->json(['success' => false, 'error' => $e->getMessage()], 422);
        }
    }

    /**
     * Approve a user via GraphQL mutation.
     */
    public function approve(string $userId)
    {
        $graphql = new GraphQLClient();

        try {
            $result = $graphql->mutate(GraphQLQueries::APPROVE_USER, [
                'userId' => $userId,
            ]);

            return response()->json(['success' => true, 'data' => $result['approveUser'] ?? []]);
        } catch (\Exception $e) {
            return response()->json(['success' => false, 'error' => $e->getMessage()], 422);
        }
    }

    /**
     * Reject a user via GraphQL mutation.
     */
    public function reject(Request $request, string $userId)
    {
        $graphql = new GraphQLClient();

        try {
            $result = $graphql->mutate(GraphQLQueries::REJECT_USER, [
                'userId' => $userId,
                'reason' => $request->input('reason', ''),
            ]);

            return response()->json(['success' => true, 'data' => $result['rejectUser'] ?? []]);
        } catch (\Exception $e) {
            return response()->json(['success' => false, 'error' => $e->getMessage()], 422);
        }
    }

    /**
     * Activate a user via GraphQL mutation.
     */
    public function activate(string $userId)
    {
        $graphql = new GraphQLClient();

        try {
            $result = $graphql->mutate(GraphQLQueries::ACTIVATE_USER, [
                'userId' => $userId,
            ]);

            return response()->json(['success' => true, 'data' => $result['activateUser'] ?? []]);
        } catch (\Exception $e) {
            return response()->json(['success' => false, 'error' => $e->getMessage()], 422);
        }
    }

    /**
     * Deactivate a user via GraphQL mutation.
     */
    public function deactivate(string $userId)
    {
        $graphql = new GraphQLClient();

        try {
            $result = $graphql->mutate(GraphQLQueries::DEACTIVATE_USER, [
                'userId' => $userId,
            ]);

            return response()->json(['success' => true, 'data' => $result['deactivateUser'] ?? []]);
        } catch (\Exception $e) {
            return response()->json(['success' => false, 'error' => $e->getMessage()], 422);
        }
    }


}
