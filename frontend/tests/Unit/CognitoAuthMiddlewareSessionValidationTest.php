<?php

namespace Tests\Unit;

use App\Http\Middleware\CognitoAuth;
use App\Services\CognitoAuthService;
use App\Services\SessionTrackerService;
use Illuminate\Http\Request;
use Illuminate\Http\Response;
use Mockery;
use Tests\TestCase;
use Exception;

/**
 * Unit tests for CognitoAuth Middleware session validation (single-device login).
 *
 * Validates: Requirements 3.1, 3.2, 3.3, 3.4, 6.1, 7.1, 7.2, 7.3, 8.1
 */
class CognitoAuthMiddlewareSessionValidationTest extends TestCase
{
    private string $testUserId = 'a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d';
    private string $testAccessToken = 'test-access-token';
    private string $testRefreshToken = 'test-refresh-token';
    private string $testSessionToken = 'aabbccdd11223344aabbccdd11223344aabbccdd11223344aabbccdd11223344';

    protected function tearDown(): void
    {
        Mockery::close();
        parent::tearDown();
    }

    /**
     * Build a fake JWT-like idToken for parseIdToken mock.
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
     * Set up a request with a valid authenticated session.
     */
    private function buildAuthenticatedRequest(
        ?string $sessionToken = null,
        ?string $accessToken = null,
        ?int $tokenExpiry = null
    ): Request {
        $request = Request::create('/dashboard', 'GET');
        $request->setLaravelSession(app('session.store'));

        $request->session()->put('accessToken', $accessToken ?? $this->testAccessToken);
        $request->session()->put('refreshToken', $this->testRefreshToken);
        $request->session()->put('tokenExpiry', $tokenExpiry ?? time() + 3600);
        $request->session()->put('idToken', $this->buildFakeIdToken($this->testUserId));
        $request->session()->put('user', ['userId' => $this->testUserId]);

        if ($sessionToken !== null) {
            $request->session()->put('sessionToken', $sessionToken);
        }

        return $request;
    }

    /**
     * Create a CognitoAuthService mock that expects parseIdToken to be called.
     */
    private function mockCognitoWithParseIdToken(): CognitoAuthService
    {
        $cognitoService = Mockery::mock(CognitoAuthService::class);
        $cognitoService->shouldReceive('parseIdToken')
            ->andReturn([
                'sub' => $this->testUserId,
                'custom:userType' => 'employee',
                'custom:role' => 'user',
            ]);
        return $cognitoService;
    }

    /**
     * Test 1: Middleware allows request when tokens match.
     *
     * Validates: Requirements 3.1, 3.2
     */
    public function test_middleware_allows_request_when_tokens_match(): void
    {
        $cognitoService = $this->mockCognitoWithParseIdToken();

        $trackerService = Mockery::mock(SessionTrackerService::class);
        $trackerService->shouldReceive('getSessionToken')
            ->with($this->testUserId)
            ->once()
            ->andReturn($this->testSessionToken);
        $this->app->instance(SessionTrackerService::class, $trackerService);

        $middleware = new CognitoAuth($cognitoService);
        $request = $this->buildAuthenticatedRequest($this->testSessionToken);

        $nextCalled = false;
        $response = $middleware->handle($request, function ($req) use (&$nextCalled) {
            $nextCalled = true;
            return new Response('OK', 200);
        });

        $this->assertTrue($nextCalled, 'Middleware should call $next when tokens match');
        $this->assertEquals(200, $response->getStatusCode());
        $this->assertEquals(
            $this->testSessionToken,
            $request->session()->get('sessionToken'),
            'Session token should remain intact'
        );
    }

    /**
     * Test 2: Middleware flushes session and redirects when tokens mismatch.
     *
     * Validates: Requirements 3.3, 6.1
     */
    public function test_middleware_flushes_session_and_redirects_when_tokens_mismatch(): void
    {
        $storedToken = 'different_token_from_another_device_00000000000000000000000000000000';

        $cognitoService = Mockery::mock(CognitoAuthService::class);
        $cognitoService->shouldReceive('globalSignOut')
            ->once()
            ->with($this->testAccessToken);

        $trackerService = Mockery::mock(SessionTrackerService::class);
        $trackerService->shouldReceive('getSessionToken')
            ->with($this->testUserId)
            ->once()
            ->andReturn($storedToken);
        $this->app->instance(SessionTrackerService::class, $trackerService);

        $middleware = new CognitoAuth($cognitoService);
        $request = $this->buildAuthenticatedRequest($this->testSessionToken);

        $nextCalled = false;
        $response = $middleware->handle($request, function ($req) use (&$nextCalled) {
            $nextCalled = true;
            return new Response('OK', 200);
        });

        $this->assertFalse($nextCalled, 'Middleware should NOT call $next when tokens mismatch');
        $this->assertEquals(302, $response->getStatusCode());
        $this->assertStringContainsString('/login', $response->headers->get('Location', ''));
        $this->assertNull(
            $request->session()->get('accessToken'),
            'Session should be flushed after mismatch'
        );
    }

    /**
     * Test 3: Middleware calls globalSignOut before flushing on mismatch.
     *
     * Validates: Requirements 3.4
     */
    public function test_middleware_calls_global_sign_out_before_flushing_on_mismatch(): void
    {
        $storedToken = 'different_token_from_another_device_00000000000000000000000000000000';

        $globalSignOutCalled = false;
        $accessTokenPassedToSignOut = null;

        $cognitoService = Mockery::mock(CognitoAuthService::class);
        $cognitoService->shouldReceive('globalSignOut')
            ->once()
            ->withArgs(function ($token) use (&$globalSignOutCalled, &$accessTokenPassedToSignOut) {
                $globalSignOutCalled = true;
                $accessTokenPassedToSignOut = $token;
                return true;
            });

        $trackerService = Mockery::mock(SessionTrackerService::class);
        $trackerService->shouldReceive('getSessionToken')
            ->with($this->testUserId)
            ->once()
            ->andReturn($storedToken);
        $this->app->instance(SessionTrackerService::class, $trackerService);

        $middleware = new CognitoAuth($cognitoService);
        $request = $this->buildAuthenticatedRequest($this->testSessionToken);

        $middleware->handle($request, function ($req) {
            return new Response('OK', 200);
        });

        $this->assertTrue($globalSignOutCalled, 'globalSignOut should be called on mismatch');
        $this->assertEquals(
            $this->testAccessToken,
            $accessTokenPassedToSignOut,
            'globalSignOut should receive the stale access token'
        );
    }

    /**
     * Test 4: Middleware redirects with stale_session flash message on mismatch.
     *
     * Validates: Requirements 6.1
     */
    public function test_middleware_redirects_with_stale_session_flash_on_mismatch(): void
    {
        $storedToken = 'different_token_from_another_device_00000000000000000000000000000000';

        $cognitoService = Mockery::mock(CognitoAuthService::class);
        $cognitoService->shouldReceive('globalSignOut')->once();

        $trackerService = Mockery::mock(SessionTrackerService::class);
        $trackerService->shouldReceive('getSessionToken')
            ->with($this->testUserId)
            ->once()
            ->andReturn($storedToken);
        $this->app->instance(SessionTrackerService::class, $trackerService);

        $middleware = new CognitoAuth($cognitoService);
        $request = $this->buildAuthenticatedRequest($this->testSessionToken);

        $response = $middleware->handle($request, function ($req) {
            return new Response('OK', 200);
        });

        $this->assertEquals(302, $response->getStatusCode());

        // The flash message is set via ->with() on the redirect, which stores it in session
        $staleMessage = $request->session()->get('stale_session');
        $this->assertNotNull($staleMessage, 'stale_session flash message should be set on mismatch');
        $this->assertStringContainsString(
            'another device',
            $staleMessage,
            'Flash message should mention logging in from another device'
        );
    }

    /**
     * Test 5: Middleware allows request when DynamoDB throws an exception (fail-open).
     *
     * Validates: Requirements 8.1
     */
    public function test_middleware_allows_request_when_dynamodb_throws_exception(): void
    {
        $cognitoService = $this->mockCognitoWithParseIdToken();

        $trackerService = Mockery::mock(SessionTrackerService::class);
        $trackerService->shouldReceive('getSessionToken')
            ->with($this->testUserId)
            ->once()
            ->andThrow(new Exception('DynamoDB is unreachable'));
        $this->app->instance(SessionTrackerService::class, $trackerService);

        $middleware = new CognitoAuth($cognitoService);
        $request = $this->buildAuthenticatedRequest($this->testSessionToken);

        $nextCalled = false;
        $response = $middleware->handle($request, function ($req) use (&$nextCalled) {
            $nextCalled = true;
            return new Response('OK', 200);
        });

        $this->assertTrue($nextCalled, 'Middleware should call $next when DynamoDB throws (fail-open)');
        $this->assertEquals(200, $response->getStatusCode());
        $this->assertEquals(
            $this->testSessionToken,
            $request->session()->get('sessionToken'),
            'Session should remain intact on DynamoDB failure'
        );
    }

    /**
     * Test 6: Middleware skips validation when sessionToken is missing from session (legacy session).
     *
     * Validates: Requirements 7.1
     */
    public function test_middleware_skips_validation_when_session_token_missing(): void
    {
        $cognitoService = $this->mockCognitoWithParseIdToken();

        // SessionTrackerService should NOT be called at all for legacy sessions
        $trackerService = Mockery::mock(SessionTrackerService::class);
        $trackerService->shouldNotReceive('getSessionToken');
        $this->app->instance(SessionTrackerService::class, $trackerService);

        $middleware = new CognitoAuth($cognitoService);

        // Build request WITHOUT sessionToken in session (legacy session)
        $request = $this->buildAuthenticatedRequest(null);

        $nextCalled = false;
        $response = $middleware->handle($request, function ($req) use (&$nextCalled) {
            $nextCalled = true;
            return new Response('OK', 200);
        });

        $this->assertTrue($nextCalled, 'Middleware should call $next for legacy sessions without sessionToken');
        $this->assertEquals(200, $response->getStatusCode());
    }

    /**
     * Test 7: Middleware skips validation when token refresh fails and session is already flushed.
     *
     * Validates: Requirements 7.3
     */
    public function test_middleware_skips_validation_when_token_refresh_fails(): void
    {
        $cognitoService = Mockery::mock(CognitoAuthService::class);
        $cognitoService->shouldReceive('refreshTokens')
            ->once()
            ->andThrow(new Exception('Token refresh failed'));

        // SessionTrackerService should NOT be called when session is already flushed
        $trackerService = Mockery::mock(SessionTrackerService::class);
        $trackerService->shouldNotReceive('getSessionToken');
        $this->app->instance(SessionTrackerService::class, $trackerService);

        $middleware = new CognitoAuth($cognitoService);

        // Build request with an EXPIRED token to trigger refresh
        $request = $this->buildAuthenticatedRequest($this->testSessionToken, $this->testAccessToken, time() - 100);

        $nextCalled = false;
        $response = $middleware->handle($request, function ($req) use (&$nextCalled) {
            $nextCalled = true;
            return new Response('OK', 200);
        });

        $this->assertFalse($nextCalled, 'Middleware should NOT call $next when token refresh fails');
        $this->assertEquals(302, $response->getStatusCode());
        $this->assertStringContainsString('/login', $response->headers->get('Location', ''));
    }
}
