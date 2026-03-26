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
                'error' => 'Failed to load positions: ' . $e->getMessage(),
            ]);
        }

        return view('pages.admin.positions', [
            'positions' => $positions,
            'error' => null,
        ]);
    }

    public function store(Request $request)
    {
        $graphql = new GraphQLClient();

        $input = ['positionName' => $request->input('positionName')];
        $desc = $request->input('description');
        if ($desc) $input['description'] = $desc;

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
        $graphql = new GraphQLClient();

        $input = ['positionName' => $request->input('positionName')];
        $desc = $request->input('description');
        if ($desc !== null) $input['description'] = $desc;

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

}
