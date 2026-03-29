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
 * Feature: single-device-login, Property 4: Matching session token allows request
 *
 * Property 4: Matching session token allows request — For any authenticated request
 * where the sessionToken in the Laravel session matches the sessionToken in the
 * Session_Tracker for that user, the CognitoAuth middleware SHALL allow the request
 * to proceed to the next handler.
 *
 * **Validates: Requirements 3.2**
 *
 * Since no PHP PBT library is installed, this test uses randomized inputs across
 * 100 iterations to verify the property holds for arbitrary matching token pairs.
 */
class MatchingSessionTokenPropertyTest extends TestCase
{
    private const ITERATIONS = 100;

    protected function tearDown(): void
    {
        Mockery::close();
        parent::tearDown();
    }

    /**
     * Property 4: For random matching token pairs, verify middleware passes
     * request through (calls $next and returns 200).
     *
     * **Validates: Requirements 3.2**
     */
    public function test_matching_session_token_allows_request_for_random_inputs(): void
    {
        for ($i = 0; $i < self::ITERATIONS; $i++) {
            $userId = $this->randomUserId();
            $sessionToken = $this->randomSessionToken();
            $accessToken = 'access-' . bin2hex(random_bytes(16));
            $refreshToken = 'refresh-' . bin2hex(random_bytes(16));
            $idToken = $this->buildFakeIdToken($userId);

            // Mock CognitoAuthService — parseIdToken is called on the idToken
            $cognitoService = Mockery::mock(CognitoAuthService::class);
            $cognitoService->shouldReceive('parseIdToken')
                ->with($idToken)
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

            // Set up a valid authenticated session with matching sessionToken
            $request->session()->put('accessToken', $accessToken);
            $request->session()->put('refreshToken', $refreshToken);
            $request->session()->put('tokenExpiry', time() + 3600);
            $request->session()->put('idToken', $idToken);
            $request->session()->put('user', ['userId' => $userId]);
            $request->session()->put('sessionToken', $sessionToken);

            $nextCalled = false;
            $response = $middleware->handle($request, function ($req) use (&$nextCalled) {
                $nextCalled = true;
                return new Response('OK', 200);
            });

            // Property assertion: middleware MUST call $next (allow request through)
            $this->assertTrue(
                $nextCalled,
                "Iteration {$i}: Middleware should allow request when session token matches. " .
                "userId='{$userId}', sessionToken='{$sessionToken}'."
            );

            // Verify response is from the next handler, not a redirect
            $this->assertEquals(
                200,
                $response->getStatusCode(),
                "Iteration {$i}: Expected 200 from next handler, got {$response->getStatusCode()}. " .
                "userId='{$userId}'."
            );

            // Verify session was NOT flushed (tokens still present)
            $this->assertEquals(
                $sessionToken,
                $request->session()->get('sessionToken'),
                "Iteration {$i}: Session token should remain intact after matching validation."
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
