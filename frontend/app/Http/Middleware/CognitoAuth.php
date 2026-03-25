<?php

namespace App\Http\Middleware;

use App\Services\CognitoAuthService;
use Closure;
use Exception;
use Illuminate\Http\Request;
use Symfony\Component\HttpFoundation\Response;

class CognitoAuth
{
    protected CognitoAuthService $cognitoAuth;

    public function __construct(CognitoAuthService $cognitoAuth)
    {
        $this->cognitoAuth = $cognitoAuth;
    }

    /**
     * Handle an incoming request.
     *
     * Checks for a valid access token in the session. If the token is expired,
     * attempts a refresh using the stored refresh token. If refresh fails or
     * no session exists, redirects to /login.
     *
     * Also extracts custom:userType and custom:role from the ID token and
     * adjusts session lifetime based on the "Remember this device" flag.
     */
    public function handle(Request $request, Closure $next): Response
    {
        $session = $request->session();

        // Check if user has an active session with tokens
        if (!$session->has('accessToken') || !$session->has('refreshToken')) {
            return redirect('/login');
        }

        $tokenExpiry = $session->get('tokenExpiry', 0);

        // If token is expired, attempt refresh
        if ($tokenExpiry <= time()) {
            $refreshToken = $session->get('refreshToken');

            if (!$refreshToken) {
                $session->flush();
                return redirect('/login');
            }

            try {
                $result = $this->cognitoAuth->refreshTokens($refreshToken);

                // Update session with new tokens
                $session->put('accessToken', $result['accessToken']);
                $session->put('idToken', $result['idToken']);
                $session->put('tokenExpiry', $result['tokenExpiry']);
                $session->put('user', $result['user']);
            } catch (Exception $e) {
                $session->flush();
                return redirect('/login');
            }
        }

        // Extract custom:userType and custom:role from ID token and store in session
        $idToken = $session->get('idToken');
        if ($idToken) {
            $claims = $this->cognitoAuth->parseIdToken($idToken);
            $user = $session->get('user', []);
            $user['userType'] = $claims['custom:userType'] ?? $user['userType'] ?? '';
            $user['role'] = $claims['custom:role'] ?? $user['role'] ?? '';
            $session->put('user', $user);
        }

        // Set session lifetime based on "Remember this device" flag
        if ($session->get('rememberDevice', false)) {
            // 30-day session lifetime (in minutes) for remembered devices
            config(['session.lifetime' => 43200]);
        }

        return $next($request);
    }
}
