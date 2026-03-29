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
 * Feature: single-device-login, Property 5: Mismatched session token terminates session
 *
 * Property 5: Mismatched session token terminates session — For any authenticated
 * request where the sessionToken in the Laravel session does not match the sessionToken
 * in the Session_Tracker for that user, the CognitoAuth middleware SHALL call
 * globalSignOut with the stale access token, flush the Laravel session, and redirect
 * to /login with a stale-session flash message.
 *
 * **Validates: Requirements 3.3, 3.4, 6.1**
 *
 * Since no PHP PBT library is installed, this test uses randomized inputs across
 * 100 iterations to verify the property holds for arbitrary mismatched token pairs.
 */
class MismatchedSessionTokenPropertyTest extends TestCase
{
    private const ITERATIONS = 100;

    protected function tearDown(): void
    {
        Mockery::close();
        parent::tearDown();
    }

    /**
     * Property 5: For random non-matching token pairs, verify middleware calls
     * globalSignOut, flushes session, and redirects to /login with stale_session flash.
     *
     * **Validates: Requirements 3.3, 3.4, 6.1**
     */
    public function test_mismatched_session_token_terminates_session_for_random_inputs(): void
    {
        for ($i = 0; $i < self::ITERATIONS; $i++) {
            $userId = $this->randomUserId();
            $sessionToken = $this->randomSessionToken();
            $accessToken = 'access-' . bin2hex(random_bytes(16));
            $refreshToken = 'refresh-' . bin2hex(random_bytes(16));
            $idToken = $this->buildFakeIdToken($userId);

            // Generate a different stored token, regenerate if they happen to match
            $storedToken = $this->randomSessionToken();
            while ($storedToken === $sessionToken) {
                $storedToken = $this->randomSessionToken();
            }

            // Mock CognitoAuthService — parseIdToken should NOT be called (session flushed before)
            $cognitoService = Mockery::mock(CognitoAuthService::class);
            // globalSignOut MUST be called with the stale access token
            $cognitoService->shouldReceive('globalSignOut')
                ->once()
                ->with($accessToken);

            // Mock SessionTrackerService — returns a DIFFERENT token (mismatched)
            $trackerService = Mockery::mock(SessionTrackerService::class);
            $trackerService->shouldReceive('getSessionToken')
                ->with($userId)
                ->andReturn($storedToken);

            $this->app->instance(SessionTrackerService::class, $trackerService);

            $middleware = new CognitoAuth($cognitoService);

            $request = Request::create('/dashboard', 'GET');
            $request->setLaravelSession(app('session.store'));

            // Set up a valid authenticated session with a DIFFERENT sessionToken than stored
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

            // Property assertion: middleware MUST NOT call $next (request should be terminated)
            $this->assertFalse(
                $nextCalled,
                "Iteration {$i}: Middleware should NOT allow request when session token mismatches. " .
                "userId='{$userId}', sessionToken='{$sessionToken}', storedToken='{$storedToken}'."
            );

            // Verify response is a redirect (302) to /login
            $this->assertEquals(
                302,
                $response->getStatusCode(),
                "Iteration {$i}: Expected 302 redirect, got {$response->getStatusCode()}. " .
                "userId='{$userId}'."
            );

            $this->assertStringContains(
                '/login',
                $response->headers->get('Location', ''),
                "Iteration {$i}: Expected redirect to /login. " .
                "Got Location: '{$response->headers->get('Location')}'."
            );

            // Verify session was flushed (sessionToken should no longer be present)
            $this->assertNull(
                $request->session()->get('sessionToken'),
                "Iteration {$i}: Session token should be flushed after mismatch detection."
            );

            $this->assertNull(
                $request->session()->get('accessToken'),
                "Iteration {$i}: Access token should be flushed after mismatch detection."
            );

            // Verify stale_session flash message is set
            $this->assertNotNull(
                $request->session()->get('stale_session'),
                "Iteration {$i}: stale_session flash message should be set after mismatch. " .
                "userId='{$userId}'."
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

    /**
     * Helper: assert string contains substring (compatible with PHPUnit versions).
     */
    private function assertStringContains(string $needle, string $haystack, string $message = ''): void
    {
        $this->assertTrue(
            str_contains($haystack, $needle),
            $message ?: "Failed asserting that '{$haystack}' contains '{$needle}'."
        );
    }
}
