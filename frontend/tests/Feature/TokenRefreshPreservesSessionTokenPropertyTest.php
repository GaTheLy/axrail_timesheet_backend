<?php

namespace Tests\Feature;

use App\Http\Middleware\CognitoAuth;
use App\Services\CognitoAuthService;
use App\Services\SessionTrackerService;
use Illuminate\Http\Request;
use Illuminate\Http\Response;
use Mockery;
use Tests\TestCase;

/**
 * Feature: single-device-login, Property 7: Token refresh preserves session token
 *
 * Property 7: Token refresh preserves session token (Invariant) — For any authenticated
 * request where the access token is expired and a token refresh succeeds, the sessionToken
 * in the Laravel session SHALL remain unchanged after the refresh operation.
 *
 * **Validates: Requirements 7.1**
 *
 * Since no PHP PBT library is installed, this test uses randomized inputs across
 * 100 iterations to verify the property holds for arbitrary session states with expired tokens.
 */
class TokenRefreshPreservesSessionTokenPropertyTest extends TestCase
{
    private const ITERATIONS = 100;

    protected function tearDown(): void
    {
        Mockery::close();
        parent::tearDown();
    }

    /**
     * Property 7: For random session states with expired tokens, verify sessionToken
     * is unchanged after middleware runs (token refresh + session validation).
     *
     * **Validates: Requirements 7.1**
     */
    public function test_token_refresh_preserves_session_token_for_random_inputs(): void
    {
        for ($i = 0; $i < self::ITERATIONS; $i++) {
            $userId = $this->randomUserId();
            $sessionToken = $this->randomSessionToken();
            $accessToken = 'access-' . bin2hex(random_bytes(16));
            $refreshToken = 'refresh-' . bin2hex(random_bytes(16));
            $idToken = $this->buildFakeIdToken($userId);

            // New tokens returned after refresh
            $newAccessToken = 'access-new-' . bin2hex(random_bytes(16));
            $newIdToken = $this->buildFakeIdToken($userId);

            // Mock CognitoAuthService — refreshTokens succeeds with new tokens
            $cognitoService = Mockery::mock(CognitoAuthService::class);
            $cognitoService->shouldReceive('refreshTokens')
                ->once()
                ->with($refreshToken)
                ->andReturn([
                    'accessToken' => $newAccessToken,
                    'idToken'     => $newIdToken,
                    'tokenExpiry' => time() + 3600,
                    'user'        => [
                        'userId'   => $userId,
                        'email'    => 'user@example.com',
                        'fullName' => 'Test User',
                        'userType' => 'employee',
                        'role'     => 'user',
                    ],
                ]);

            // parseIdToken is called after session validation on the new idToken
            $cognitoService->shouldReceive('parseIdToken')
                ->with($newIdToken)
                ->andReturn([
                    'sub' => $userId,
                    'custom:userType' => 'employee',
                    'custom:role' => 'user',
                ]);

            // Mock SessionTrackerService — returns the SAME token (matching)
            $trackerService = Mockery::mock(SessionTrackerService::class);
            $trackerService->shouldReceive('getSessionToken')
                ->with($userId)
                ->andReturn($sessionToken);

            $this->app->instance(SessionTrackerService::class, $trackerService);

            $middleware = new CognitoAuth($cognitoService);

            $request = Request::create('/dashboard', 'GET');
            $request->setLaravelSession(app('session.store'));

            // Set up session with EXPIRED token (time() - 100) to trigger refresh
            $request->session()->put('accessToken', $accessToken);
            $request->session()->put('refreshToken', $refreshToken);
            $request->session()->put('tokenExpiry', time() - 100);
            $request->session()->put('idToken', $idToken);
            $request->session()->put('user', ['userId' => $userId]);
            $request->session()->put('sessionToken', $sessionToken);

            $nextCalled = false;
            $response = $middleware->handle($request, function ($req) use (&$nextCalled) {
                $nextCalled = true;
                return new Response('OK', 200);
            });

            // Property assertion: sessionToken MUST remain unchanged after refresh
            $this->assertEquals(
                $sessionToken,
                $request->session()->get('sessionToken'),
                "Iteration {$i}: sessionToken must be preserved after token refresh. " .
                "userId='{$userId}', expected sessionToken='{$sessionToken}', " .
                "got='" . $request->session()->get('sessionToken') . "'."
            );

            // Verify middleware allowed the request through (refresh succeeded + tokens match)
            $this->assertTrue(
                $nextCalled,
                "Iteration {$i}: Middleware should allow request after successful token refresh " .
                "with matching session token. userId='{$userId}'."
            );

            $this->assertEquals(
                200,
                $response->getStatusCode(),
                "Iteration {$i}: Expected 200 from next handler after token refresh, " .
                "got {$response->getStatusCode()}. userId='{$userId}'."
            );

            // Verify access token was updated (refresh happened)
            $this->assertEquals(
                $newAccessToken,
                $request->session()->get('accessToken'),
                "Iteration {$i}: accessToken should be updated after refresh. userId='{$userId}'."
            );
        }
    }

    /**
     * Generate a random UUID-like userId (simulating Cognito sub).
     */
    private function randomUserId(): string
    {
        return sprintf(
            '%04x%04x-%04x-%04x-%04x-%04x%04x%04x',
            random_int(0, 0xffff), random_int(0, 0xffff),
            random_int(0, 0xffff),
            random_int(0, 0x0fff) | 0x4000,
            random_int(0, 0x3fff) | 0x8000,
            random_int(0, 0xffff), random_int(0, 0xffff), random_int(0, 0xffff)
        );
    }

    /**
     * Generate a random 64-character hex session token (matching bin2hex(random_bytes(32))).
     */
    private function randomSessionToken(): string
    {
        return bin2hex(random_bytes(32));
    }

    /**
     * Build a fake JWT-like idToken that parseIdToken can decode.
     */
    private function buildFakeIdToken(string $userId): string
    {
        $header = base64_encode(json_encode(['alg' => 'RS256', 'typ' => 'JWT']));
        $payload = base64_encode(json_encode([
            'sub' => $userId,
            'custom:userType' => 'employee',
            'custom:role' => 'user',
        ]));
        $signature = base64_encode('fake-signature');

        return "{$header}.{$payload}.{$signature}";
    }
}
