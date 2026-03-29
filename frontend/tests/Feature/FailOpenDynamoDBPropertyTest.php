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
 * Feature: single-device-login, Property 8: Fail-open on DynamoDB unavailability
 *
 * Property 8: Fail-open on DynamoDB unavailability — For any authenticated request
 * where the Session_Tracker DynamoDB table is unreachable (throws an exception),
 * the CognitoAuth middleware SHALL allow the request to proceed without flushing
 * the session.
 *
 * **Validates: Requirements 8.1**
 *
 * Since no PHP PBT library is installed, this test uses randomized inputs across
 * 100 iterations to verify the property holds for arbitrary requests with simulated
 * DynamoDB failures.
 */
class FailOpenDynamoDBPropertyTest extends TestCase
{
    private const ITERATIONS = 100;

    protected function tearDown(): void
    {
        Mockery::close();
        parent::tearDown();
    }

    /**
     * Property 8: For random requests with simulated DynamoDB failures,
     * verify request proceeds (calls $next and returns 200) and session
     * remains intact.
     *
     * **Validates: Requirements 8.1**
     */
    public function test_fail_open_on_dynamodb_unavailability_for_random_inputs(): void
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

            // Mock SessionTrackerService — throws Exception (DynamoDB unreachable)
            $trackerService = Mockery::mock(SessionTrackerService::class);
            $trackerService->shouldReceive('getSessionToken')
                ->with($userId)
                ->andThrow(new \Exception('DynamoDB is unreachable'));

            $this->app->instance(SessionTrackerService::class, $trackerService);

            $middleware = new CognitoAuth($cognitoService);

            $request = Request::create('/dashboard', 'GET');
            $request->setLaravelSession(app('session.store'));

            // Set up a valid authenticated session
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

            // Property assertion: middleware MUST call $next (fail-open, allow request through)
            $this->assertTrue(
                $nextCalled,
                "Iteration {$i}: Middleware should allow request when DynamoDB is unreachable (fail-open). " .
                "userId='{$userId}', sessionToken='{$sessionToken}'."
            );

            // Verify response is from the next handler, not a redirect
            $this->assertEquals(
                200,
                $response->getStatusCode(),
                "Iteration {$i}: Expected 200 from next handler, got {$response->getStatusCode()}. " .
                "userId='{$userId}'."
            );

            // Verify session was NOT flushed (sessionToken still present)
            $this->assertEquals(
                $sessionToken,
                $request->session()->get('sessionToken'),
                "Iteration {$i}: Session token should remain intact when DynamoDB is unreachable."
            );

            // Verify accessToken still present (session not flushed)
            $this->assertEquals(
                $accessToken,
                $request->session()->get('accessToken'),
                "Iteration {$i}: Access token should remain intact when DynamoDB is unreachable."
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
