<?php

namespace App\Http\Controllers;

use App\Services\CognitoAuthService;
use App\Services\SessionTrackerService;
use Illuminate\Http\Request;
use Illuminate\Routing\Controller;
use Illuminate\Support\Facades\Log;
use Exception;

class AuthController extends Controller
{
    protected CognitoAuthService $cognitoAuth;

    public function __construct(CognitoAuthService $cognitoAuth)
    {
        $this->cognitoAuth = $cognitoAuth;
    }

    /**
     * Show the login page.
     */
    public function showLogin()
    {
        return view('pages.login');
    }

    /**
     * Handle login form submission.
     * Validates credentials, authenticates via Cognito, stores tokens in session.
     */
    public function login(Request $request)
    {
        $request->validate([
            'email'    => 'required|email',
            'password' => 'required|string',
        ]);

        try {
            $result = $this->cognitoAuth->authenticate(
                $request->input('email'),
                $request->input('password'),
                $request->boolean('remember')
            );

            // Handle NEW_PASSWORD_REQUIRED challenge
            if (isset($result['challenge']) && $result['challenge'] === 'NEW_PASSWORD_REQUIRED') {
                $request->session()->put('cognito_session', $result['session']);
                $request->session()->put('cognito_email', $request->input('email'));
                $request->session()->put('cognito_challenge_params', $result['challengeParams'] ?? []);

                return redirect('/force-change-password');
            }

            // Store tokens in session
            $request->session()->put('accessToken', $result['accessToken']);
            $request->session()->put('idToken', $result['idToken']);
            $request->session()->put('refreshToken', $result['refreshToken']);
            $request->session()->put('tokenExpiry', $result['tokenExpiry']);

            // Store user info in session
            $request->session()->put('user', $result['user']);
            $request->session()->put('rememberDevice', $request->boolean('remember'));

            // Generate and store session token for single-device login enforcement
            $sessionToken = bin2hex(random_bytes(32));
            $request->session()->put('sessionToken', $sessionToken);

            try {
                $sessionTracker = app(SessionTrackerService::class);
                $sessionTracker->putSession($result['user']['userId'], $sessionToken);
            } catch (Exception $e) {
                Log::error('Failed to store session token in DynamoDB: ' . $e->getMessage());
            }

            return redirect()->intended('/dashboard');
        } catch (Exception $e) {
            return back()->withErrors([
                'auth' => 'The credentials you entered are invalid. Please try again.',
            ])->withInput($request->only('email', 'remember'));
        }
    }

    /**
     * Handle logout. Signs out globally from Cognito using admin API to revoke
     * ALL refresh tokens for the user, then flushes the Laravel session.
     */
    public function logout(Request $request)
    {
        try {
            $user = $request->session()->get('user');
            if ($user && isset($user['email'])) {
                $this->cognitoAuth->adminGlobalSignOut($user['email']);
            }
        } catch (Exception $e) {
            // Continue with logout even if Cognito sign-out fails
        }

        // Delete session tracker entry before flushing (userId won't be available after flush)
        try {
            $userId = $request->session()->get('user.userId');
            if ($userId) {
                $sessionTracker = app(SessionTrackerService::class);
                $sessionTracker->deleteSession($userId);
            }
        } catch (Exception $e) {
            Log::error('Failed to delete session tracker entry on logout: ' . $e->getMessage());
        }

        $request->session()->flush();

        return redirect('/login');
    }


    /**
     * Show the forgot password form.
     */
    public function showForgotPassword()
    {
        return view('pages.forgot-password');
    }

    /**
     * Handle forgot password form submission.
     * Initiates the Cognito forgot-password flow.
     * Always returns a uniform response to prevent account enumeration.
     */
    public function forgotPassword(Request $request)
    {
        $request->validate([
            'email' => 'required|email',
        ]);

        $email = strtolower($request->input('email'));

        try {
            $this->cognitoAuth->forgotPassword($email);
        } catch (Exception $e) {
            \Log::warning('Forgot password failed for email: ' . $email . ' — ' . $e->getMessage());
        }

        return redirect('/reset-password')
            ->with('email', $email)
            ->with('status', 'If an account exists with that email, we have sent a verification code.');
    }

    /**
     * Show the reset password form.
     * Only accessible after a valid forgot-password flow (session flash check).
     */
    public function showResetPassword(Request $request)
    {
        if (!$request->session()->has('email')) {
            return redirect('/forgot-password');
        }

        return view('pages.reset-password');
    }

    /**
     * Handle password reset with verification code.
     */
    public function resetPassword(Request $request)
    {
        $request->validate([
            'email'        => 'required|email',
            'code'         => 'required|string',
            'password'     => 'required|string|min:8|confirmed',
        ]);

        $email = strtolower($request->input('email'));

        try {
            $this->cognitoAuth->confirmForgotPassword(
                $email,
                $request->input('code'),
                $request->input('password')
            );

            return redirect('/login')
                ->with('status', 'Your password has been reset successfully. Please sign in.');
        } catch (Exception $e) {
            return back()->withErrors([
                'auth' => 'Unable to reset your password. Please check your verification code and try again.',
            ])->withInput($request->only('email'));
        }
    }

    /**
     * Show the force change password form.
     */
    public function showForceChangePassword(Request $request)
    {
        if (!$request->session()->has('cognito_session')) {
            return redirect('/login');
        }

        return view('pages.force-change-password');
    }

    /**
     * Handle force change password submission.
     */
    public function forceChangePassword(Request $request)
    {
        $request->validate([
            'name'     => 'required|string|min:1',
            'password' => 'required|string|min:8|confirmed',
        ]);

        $session = $request->session()->get('cognito_session');
        $email = $request->session()->get('cognito_email');
        $challengeParams = $request->session()->get('cognito_challenge_params', []);

        if (!$session || !$email) {
            return redirect('/login')->withErrors([
                'auth' => 'Your session has expired. Please sign in again.',
            ]);
        }

        try {
            $result = $this->cognitoAuth->respondToNewPasswordChallenge(
                $email,
                $request->input('password'),
                $session,
                $challengeParams,
                $request->input('name')
            );

            // Clean up challenge session data
            $request->session()->forget(['cognito_session', 'cognito_email', 'cognito_challenge_params']);

            // Store tokens in session
            $request->session()->put('accessToken', $result['accessToken']);
            $request->session()->put('idToken', $result['idToken']);
            $request->session()->put('refreshToken', $result['refreshToken']);
            $request->session()->put('tokenExpiry', $result['tokenExpiry']);
            $request->session()->put('user', $result['user']);

            // Generate and store session token for single-device login enforcement
            $sessionToken = bin2hex(random_bytes(32));
            $request->session()->put('sessionToken', $sessionToken);

            try {
                $sessionTracker = app(SessionTrackerService::class);
                $sessionTracker->putSession($result['user']['userId'], $sessionToken);
            } catch (Exception $e) {
                Log::error('Failed to store session token in DynamoDB: ' . $e->getMessage());
            }

            return redirect('/dashboard');
        } catch (Exception $e) {
            return back()->withErrors([
                'auth' => $e->getMessage(),
            ]);
        }
    }
}
