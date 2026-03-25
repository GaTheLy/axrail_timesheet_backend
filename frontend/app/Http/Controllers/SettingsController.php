<?php

namespace App\Http\Controllers;

use App\Services\CognitoAuthService;
use App\Services\GraphQLClient;
use Exception;
use Illuminate\Auth\AuthenticationException;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Routing\Controller;

class SettingsController extends Controller
{
    protected GraphQLClient $graphql;
    protected CognitoAuthService $cognito;

    public function __construct(GraphQLClient $graphql, CognitoAuthService $cognito)
    {
        $this->graphql = $graphql;
        $this->cognito = $cognito;
    }

    /**
     * Render the settings page with user profile and departments.
     */
    public function index()
    {
        $user = session('user');

        try {
            // Fetch user profile
            $userData = $this->graphql->query(
                'query GetUser($userId: ID!) { getUser(userId: $userId) { userId email fullName departmentId avatarUrl } }',
                ['userId' => $user['userId'] ?? '']
            );
            $profile = $userData['getUser'] ?? [];

            // Fetch departments for dropdown
            $deptData = $this->graphql->query(
                'query ListDepartments { listDepartments { departmentId name } }'
            );
            $departments = $deptData['listDepartments'] ?? [];

            return view('pages.settings', [
                'profile' => $profile,
                'departments' => $departments,
                'error' => null,
            ]);
        } catch (AuthenticationException $e) {
            return redirect('/login')->withErrors(['auth' => $e->getMessage()]);
        } catch (Exception $e) {
            return view('pages.settings', [
                'profile' => [
                    'userId' => $user['userId'] ?? '',
                    'email' => $user['email'] ?? '',
                    'fullName' => $user['fullName'] ?? '',
                ],
                'departments' => [],
                'error' => 'Unable to load settings. Please try again.',
            ]);
        }
    }

    /**
     * Handle avatar image upload and storage (AJAX).
     */
    public function uploadAvatar(Request $request): JsonResponse
    {
        $request->validate([
            'avatar' => 'required|image|mimes:jpeg,png,jpg,gif|max:2048',
        ]);

        try {
            $file = $request->file('avatar');
            $user = session('user');
            $filename = ($user['userId'] ?? 'user') . '_' . time() . '.' . $file->getClientOriginalExtension();

            $path = $file->storeAs('public/avatars', $filename);
            $url = asset('storage/avatars/' . $filename);

            return response()->json([
                'success' => true,
                'message' => 'Avatar uploaded successfully.',
                'avatarUrl' => $url,
            ]);
        } catch (Exception $e) {
            return response()->json([
                'success' => false,
                'message' => 'Failed to upload avatar. Please try again.',
            ], 500);
        }
    }

    /**
     * Change the user's password via Cognito (AJAX).
     *
     * Validates password match and policy before calling Cognito.
     */
    public function changePassword(Request $request): JsonResponse
    {
        $currentPassword = $request->input('current_password', '');
        $newPassword = $request->input('new_password', '');
        $confirmPassword = $request->input('confirm_password', '');

        // Validate passwords match
        if ($newPassword !== $confirmPassword) {
            return response()->json([
                'success' => false,
                'message' => 'New password and confirmation do not match.',
            ], 422);
        }

        // Validate password policy: min 8 chars, uppercase, lowercase, digit, symbol
        if (!$this->meetsPasswordPolicy($newPassword)) {
            return response()->json([
                'success' => false,
                'message' => 'Password must be at least 8 characters and include an uppercase letter, a lowercase letter, a digit, and a symbol.',
            ], 422);
        }

        try {
            $accessToken = session('accessToken', '');
            $this->cognito->changePassword($accessToken, $currentPassword, $newPassword);

            return response()->json([
                'success' => true,
                'message' => 'Password changed successfully.',
            ]);
        } catch (Exception $e) {
            return response()->json([
                'success' => false,
                'message' => $e->getMessage(),
            ], 400);
        }
    }

    /**
     * Check if a password meets the Cognito password policy.
     *
     * Policy: minimum 8 characters, at least one uppercase letter,
     * one lowercase letter, one digit, and one symbol.
     */
    protected function meetsPasswordPolicy(string $password): bool
    {
        if (strlen($password) < 8) {
            return false;
        }
        if (!preg_match('/[A-Z]/', $password)) {
            return false;
        }
        if (!preg_match('/[a-z]/', $password)) {
            return false;
        }
        if (!preg_match('/[0-9]/', $password)) {
            return false;
        }
        if (!preg_match('/[^A-Za-z0-9]/', $password)) {
            return false;
        }

        return true;
    }
}
