<?php

namespace App\Http\Controllers;

use App\Services\CognitoAuthService;
use Illuminate\Http\Request;
use Illuminate\Routing\Controller;
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

            return redirect()->intended('/dashboard');
        } catch (Exception $e) {
            return back()->withErrors([
                'auth' => 'The credentials you entered are invalid. Please try again.',
            ])->withInput($request->only('email', 'remember'));
        }
    }

    /**
     * Handle logout. Signs out globally from Cognito, flushes session.
     */
    public function logout(Request $request)
    {
        try {
            $accessToken = $request->session()->get('accessToken');
            if ($accessToken) {
                $this->cognitoAuth->globalSignOut($accessToken);
            }
        } catch (Exception $e) {
            // Continue with logout even if Cognito sign-out fails
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
     */
    public function forgotPassword(Request $request)
    {
        $request->validate([
            'email' => 'required|email',
        ]);

        try {
            $this->cognitoAuth->forgotPassword($request->input('email'));

            return redirect('/reset-password')
                ->with('email', $request->input('email'))
                ->with('status', 'We have sent a verification code to your email address.');
        } catch (Exception $e) {
            return back()->withErrors([
                'auth' => 'Unable to process your request. Please try again.',
            ])->withInput();
        }
    }

    /**
     * Show the reset password form.
     */
    public function showResetPassword()
    {
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

        try {
            $this->cognitoAuth->confirmForgotPassword(
                $request->input('email'),
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

            return redirect('/dashboard');
        } catch (Exception $e) {
            return back()->withErrors([
                'auth' => $e->getMessage(),
            ]);
        }
    }
}
