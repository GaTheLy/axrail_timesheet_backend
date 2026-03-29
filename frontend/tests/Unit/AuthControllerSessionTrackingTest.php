<?php

namespace Tests\Unit;

use App\Http\Controllers\AuthController;
use App\Services\CognitoAuthService;
use App\Services\SessionTrackerService;
use Illuminate\Http\Request;
use Mockery;
use Tests\TestCase;
use Exception;

/**
 * Unit tests for AuthController session tracking integration.
 *
 * Validates: Requirements 1.1, 1.2, 2.1, 2.2, 4.1, 4.2, 8.2
 */
class AuthControllerSessionTrackingTest extends TestCase
{
    private const SESSION_TOKEN_PATTERN = '/^[0-9a-f]{64}$/';

    private string $testUserId = 'a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d';
    private string $testEmail = 'testuser@example.com';
    private string $testPassword = 'SecurePass123!';

    protected function tearDown(): void
    {
        Mockery::close();
        parent::tearDown();
    }

    /**
     * Test login stores a 64-char hex sessionToken in the session.
     *
     * Validates: Requirement 1.1
     */
    public function test_login_stores_64_char_hex_session_token_in_session(): void
    {
        $cognitoService = $this->mockSuccessfulLogin();
        $sessionTracker = Mockery::mock(SessionTrackerService::class);
        $sessionTracker->shouldReceive('putSession')->once();
        $this->app->instance(SessionTrackerService::class, $sessionTracker);

        $controller = new AuthController($cognitoService);
        $request = $this->buildLoginRequest();

        $controller->login($request);

        $sessionToken = $request->session()->get('sessionToken');
        $this->assertNotNull($sessionToken, 'sessionToken should be stored in session after login');
        $this->assertMatchesRegularExpression(
            self::SESSION_TOKEN_PATTERN,
            $sessionToken,
            "sessionToken '{$sessionToken}' should be a 64-char hex string"
        );
    }

    /**
     * Test login calls putSession with correct userId and the token from session.
     *
     * Validates: Requirement 1.2
     */
    public function test_login_calls_put_session_with_correct_user_id_and_token(): void
    {
        $cognitoService = $this->mockSuccessfulLogin();

        $capturedUserId = null;
        $capturedToken = null;

        $sessionTracker = Mockery::mock(SessionTrackerService::class);
        $sessionTracker->shouldReceive('putSession')
            ->once()
            ->withArgs(function ($userId, $token) use (&$capturedUserId, &$capturedToken) {
                $capturedUserId = $userId;
                $capturedToken = $token;
                return true;
            });
        $this->app->instance(SessionTrackerService::class, $sessionTracker);

        $controller = new AuthController($cognitoService);
        $request = $this->buildLoginRequest();

        $controller->login($request);

        $this->assertSame(
            $this->testUserId,
            $capturedUserId,
            'putSession should be called with the authenticated userId'
        );
        $this->assertSame(
            $request->session()->get('sessionToken'),
            $capturedToken,
            'putSession should be called with the same token stored in session'
        );
    }

    /**
     * Test force-change-password stores a sessionToken in session.
     *
     * Validates: Requirement 2.1
     */
    public function test_force_change_password_stores_session_token_in_session(): void
    {
        $cognitoService = $this->mockSuccessfulForceChangePassword();
        $sessionTracker = Mockery::mock(SessionTrackerService::class);
        $sessionTracker->shouldReceive('putSession')->once();
        $this->app->instance(SessionTrackerService::class, $sessionTracker);

        $controller = new AuthController($cognitoService);
        $request = $this->buildForceChangePasswordRequest();

        $controller->forceChangePassword($request);

        $sessionToken = $request->session()->get('sessionToken');
        $this->assertNotNull($sessionToken, 'sessionToken should be stored in session after force-change-password');
        $this->assertMatchesRegularExpression(
            self::SESSION_TOKEN_PATTERN,
            $sessionToken,
            "sessionToken '{$sessionToken}' should be a 64-char hex string"
        );
    }

    /**
     * Test logout calls deleteSession with correct userId.
     *
     * Validates: Requirement 4.1
     */
    public function test_logout_calls_delete_session_with_correct_user_id(): void
    {
        $cognitoService = Mockery::mock(CognitoAuthService::class);
        $cognitoService->shouldReceive('adminGlobalSignOut')->once();

        $capturedUserId = null;

        $sessionTracker = Mockery::mock(SessionTrackerService::class);
        $sessionTracker->shouldReceive('deleteSession')
            ->once()
            ->withArgs(function ($userId) use (&$capturedUserId) {
                $capturedUserId = $userId;
                return true;
            });
        $this->app->instance(SessionTrackerService::class, $sessionTracker);

        $controller = new AuthController($cognitoService);
        $request = $this->buildLogoutRequest();

        $controller->logout($request);

        $this->assertSame(
            $this->testUserId,
            $capturedUserId,
            'deleteSession should be called with the logged-in userId'
        );
    }

    /**
     * Test logout succeeds even when deleteSession throws an exception (fail-open).
     *
     * Validates: Requirement 4.2
     */
    public function test_logout_succeeds_when_delete_session_throws_exception(): void
    {
        $cognitoService = Mockery::mock(CognitoAuthService::class);
        $cognitoService->shouldReceive('adminGlobalSignOut')->once();

        $sessionTracker = Mockery::mock(SessionTrackerService::class);
        $sessionTracker->shouldReceive('deleteSession')
            ->once()
            ->andThrow(new Exception('DynamoDB is unreachable'));
        $this->app->instance(SessionTrackerService::class, $sessionTracker);

        $controller = new AuthController($cognitoService);
        $request = $this->buildLogoutRequest();

        $response = $controller->logout($request);

        // Logout should still redirect to /login despite the exception
        $this->assertEquals(302, $response->getStatusCode());
        $this->assertStringContains('/login', $response->headers->get('Location'));
    }

    /**
     * Test login succeeds when putSession throws an exception (fail-open, DynamoDB unreachable).
     *
     * Validates: Requirement 8.2
     */
    public function test_login_succeeds_when_put_session_throws_exception(): void
    {
        $cognitoService = $this->mockSuccessfulLogin();

        $sessionTracker = Mockery::mock(SessionTrackerService::class);
        $sessionTracker->shouldReceive('putSession')
            ->once()
            ->andThrow(new Exception('DynamoDB is unreachable'));
        $this->app->instance(SessionTrackerService::class, $sessionTracker);

        $controller = new AuthController($cognitoService);
        $request = $this->buildLoginRequest();

        $response = $controller->login($request);

        // Login should still succeed — redirect to dashboard
        $this->assertEquals(302, $response->getStatusCode());
        $this->assertStringContains('/dashboard', $response->headers->get('Location'));

        // Session token should still be stored in the Laravel session
        $sessionToken = $request->session()->get('sessionToken');
        $this->assertNotNull($sessionToken, 'sessionToken should be in session even when DynamoDB fails');
        $this->assertMatchesRegularExpression(
            self::SESSION_TOKEN_PATTERN,
            $sessionToken,
            'sessionToken should still be a valid 64-char hex string'
        );
    }

    // ── Helper methods ──────────────────────────────────────────────────

    private function mockSuccessfulLogin(): CognitoAuthService
    {
        $cognitoService = Mockery::mock(CognitoAuthService::class);
        $cognitoService->shouldReceive('authenticate')
            ->once()
            ->andReturn([
                'accessToken'  => 'test-access-token',
                'idToken'      => 'test-id-token',
                'refreshToken' => 'test-refresh-token',
                'tokenExpiry'  => time() + 3600,
                'user'         => [
                    'userId'   => $this->testUserId,
                    'email'    => $this->testEmail,
                    'fullName' => 'Test User',
                    'userType' => 'employee',
                    'role'     => 'user',
                ],
            ]);
        return $cognitoService;
    }

    private function mockSuccessfulForceChangePassword(): CognitoAuthService
    {
        $cognitoService = Mockery::mock(CognitoAuthService::class);
        $cognitoService->shouldReceive('respondToNewPasswordChallenge')
            ->once()
            ->andReturn([
                'accessToken'  => 'test-access-token',
                'idToken'      => 'test-id-token',
                'refreshToken' => 'test-refresh-token',
                'tokenExpiry'  => time() + 3600,
                'user'         => [
                    'userId'   => $this->testUserId,
                    'email'    => $this->testEmail,
                    'fullName' => 'Test User',
                    'userType' => 'employee',
                    'role'     => 'user',
                ],
            ]);
        return $cognitoService;
    }

    private function buildLoginRequest(): Request
    {
        $request = Request::create('/login', 'POST', [
            'email'    => $this->testEmail,
            'password' => $this->testPassword,
        ]);
        $request->setLaravelSession(app('session.store'));
        return $request;
    }

    private function buildForceChangePasswordRequest(): Request
    {
        $request = Request::create('/force-change-password', 'POST', [
            'name'                  => 'Test User',
            'password'              => $this->testPassword,
            'password_confirmation' => $this->testPassword,
        ]);
        $request->setLaravelSession(app('session.store'));

        // Set up the challenge session data that forceChangePassword expects
        $request->session()->put('cognito_session', 'test-cognito-session');
        $request->session()->put('cognito_email', $this->testEmail);
        $request->session()->put('cognito_challenge_params', []);

        return $request;
    }

    private function buildLogoutRequest(): Request
    {
        $request = Request::create('/logout', 'POST');
        $request->setLaravelSession(app('session.store'));

        // Set up session data that logout expects
        $request->session()->put('user', [
            'userId' => $this->testUserId,
            'email'  => $this->testEmail,
        ]);
        $request->session()->put('accessToken', 'test-access-token');
        $request->session()->put('sessionToken', 'existing-session-token');

        return $request;
    }

    /**
     * Custom assertion for string containment (compatible with PHPUnit 10+).
     */
    private function assertStringContains(string $needle, ?string $haystack): void
    {
        $this->assertNotNull($haystack);
        $this->assertStringContainsString($needle, $haystack);
    }
}
