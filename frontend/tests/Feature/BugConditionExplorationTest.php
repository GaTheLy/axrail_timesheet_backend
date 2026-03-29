<?php

namespace Tests\Feature;

use App\Http\Controllers\AuthController;
use App\Services\CognitoAuthService;
use Aws\CognitoIdentityProvider\CognitoIdentityProviderClient;
use Aws\Exception\AwsException;
use Aws\Command;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Route;
use Mockery;
use Tests\TestCase;

/**
 * Bug Condition Exploration Tests
 *
 * These tests encode the EXPECTED (fixed) behavior for three security vulnerabilities
 * found during penetration testing. On UNFIXED code, these tests are EXPECTED TO FAIL,
 * which confirms the bugs exist.
 *
 * **Validates: Requirements 1.1, 1.2, 1.4, 1.5, 1.6**
 *
 * Property 1: Bug Condition — Logout Session Persistence & Forgot-Password Enumeration
 */
class BugConditionExplorationTest extends TestCase
{
    protected function tearDown(): void
    {
        Mockery::close();
        parent::tearDown();
    }

    // ---------------------------------------------------------------
    // Bug Condition 1: Logout does NOT call AdminUserGlobalSignOut
    // ---------------------------------------------------------------

    /**
     * Test that logout() calls AdminUserGlobalSignOut with UserPoolId and Username.
     *
     * On UNFIXED code, this FAILS because logout() calls GlobalSignOut with AccessToken instead.
     * This confirms Bug Condition 1.1/1.2: concurrent sessions survive logout.
     *
     * **Validates: Requirements 1.1, 1.2**
     *
     * @dataProvider logoutUserProvider
     */
    public function test_logout_calls_admin_global_sign_out(string $email, string $accessToken): void
    {
        $service = Mockery::mock(CognitoAuthService::class)->makePartial();

        // We expect adminGlobalSignOut to be called with the user's email
        $service->shouldReceive('adminGlobalSignOut')
            ->once()
            ->with($email)
            ->andReturn(true);

        // The buggy globalSignOut should NOT be called
        $service->shouldNotReceive('globalSignOut');

        $controller = new AuthController($service);

        $request = Request::create('/logout', 'POST');
        $request->setLaravelSession(app('session.store'));
        $request->session()->put('accessToken', $accessToken);
        $request->session()->put('user', ['email' => $email]);

        $response = $controller->logout($request);

        // Verify session is flushed and redirect goes to /login
        $this->assertEquals(302, $response->getStatusCode());
        $this->assertStringContains('/login', $response->getTargetUrl());
    }

    /**
     * Data provider for logout test — multiple user scenarios.
     */
    public static function logoutUserProvider(): array
    {
        return [
            'regular user'    => ['user@example.com', 'access-token-abc-123'],
            'admin user'      => ['admin@example.com', 'access-token-admin-456'],
            'superadmin user' => ['superadmin@example.com', 'access-token-super-789'],
        ];
    }

    // ---------------------------------------------------------------
    // Bug Condition 2: Forgot-password returns divergent responses
    // ---------------------------------------------------------------

    /**
     * Test that forgotPassword() returns identical redirect for success and exception paths.
     *
     * On UNFIXED code, this FAILS because:
     * - Success: redirects to /reset-password with "We have sent a verification code..."
     * - Exception: redirects back to /forgot-password with "Unable to process your request..."
     *
     * The EXPECTED (fixed) behavior is: both paths redirect to /reset-password with the
     * same generic message.
     *
     * **Validates: Requirements 1.4, 1.5**
     *
     * @dataProvider forgotPasswordEmailProvider
     */
    public function test_forgot_password_returns_uniform_response_for_all_emails(
        string $email,
        bool $cognitoThrowsException
    ): void {
        $service = Mockery::mock(CognitoAuthService::class);

        if ($cognitoThrowsException) {
            $service->shouldReceive('forgotPassword')
                ->with($email)
                ->andThrow(new \Exception('User does not exist.'));
        } else {
            $service->shouldReceive('forgotPassword')
                ->with($email)
                ->andReturn([
                    'deliveryMedium' => 'EMAIL',
                    'destination'    => '***' . substr($email, 3),
                ]);
        }

        $controller = new AuthController($service);

        $request = Request::create('/forgot-password', 'POST', ['email' => $email]);
        $request->setLaravelSession(app('session.store'));

        $response = $controller->forgotPassword($request);

        // EXPECTED: Always redirect to /reset-password (not back to /forgot-password)
        $this->assertEquals(302, $response->getStatusCode());
        $this->assertStringContains('/reset-password', $response->getTargetUrl(),
            "Expected redirect to /reset-password for email '{$email}' " .
            ($cognitoThrowsException ? '(exception path)' : '(success path)') .
            ", but got: " . $response->getTargetUrl()
        );

        // EXPECTED: Generic message that doesn't reveal account existence
        $session = $response->getSession();
        $flashData = $session ? $session->all() : [];
        $statusMessage = $flashData['status'] ?? $flashData['_flash']['new']['status'] ?? '';

        // The message should be the generic one, not the specific success/error message
        if (!empty($statusMessage)) {
            $this->assertStringContains(
                'If an account exists',
                $statusMessage,
                "Expected generic message for email '{$email}', got: {$statusMessage}"
            );
        }
    }

    /**
     * Data provider for forgot-password test — valid and invalid emails.
     */
    public static function forgotPasswordEmailProvider(): array
    {
        return [
            'valid registered email (success)'       => ['registered@example.com', false],
            'invalid email (Cognito throws)'         => ['nonexistent@example.com', true],
            'another valid email (success)'          => ['another.user@company.com', false],
            'another invalid email (Cognito throws)' => ['fake@nowhere.org', true],
        ];
    }

    /**
     * Test that success and exception paths produce IDENTICAL responses.
     *
     * This directly compares the two paths side-by-side. On UNFIXED code, the redirect
     * destinations differ (success → /reset-password, exception → /forgot-password).
     *
     * **Validates: Requirements 1.4, 1.5**
     */
    public function test_forgot_password_success_and_error_paths_have_same_redirect(): void
    {
        // SUCCESS path: Cognito succeeds
        $successService = Mockery::mock(CognitoAuthService::class);
        $successService->shouldReceive('forgotPassword')
            ->with('test@example.com')
            ->andReturn(['deliveryMedium' => 'EMAIL', 'destination' => '***t@example.com']);

        $successController = new AuthController($successService);
        $successRequest = Request::create('/forgot-password', 'POST', ['email' => 'test@example.com']);
        $successRequest->setLaravelSession(app('session.store'));
        $successResponse = $successController->forgotPassword($successRequest);

        // EXCEPTION path: Cognito throws
        $errorService = Mockery::mock(CognitoAuthService::class);
        $errorService->shouldReceive('forgotPassword')
            ->with('test@example.com')
            ->andThrow(new \Exception('UserNotFoundException'));

        $errorController = new AuthController($errorService);
        $errorRequest = Request::create('/forgot-password', 'POST', ['email' => 'test@example.com']);
        $errorRequest->setLaravelSession(app('session.store'));
        $errorResponse = $errorController->forgotPassword($errorRequest);

        // EXPECTED: Both redirect to the SAME URL
        $this->assertEquals(
            $successResponse->getTargetUrl(),
            $errorResponse->getTargetUrl(),
            "Success path redirects to '{$successResponse->getTargetUrl()}' but error path " .
            "redirects to '{$errorResponse->getTargetUrl()}'. These MUST be identical to prevent " .
            "account enumeration."
        );
    }

    // ---------------------------------------------------------------
    // Bug Condition 3: No rate limiting on POST /forgot-password
    // ---------------------------------------------------------------

    /**
     * Test that POST /forgot-password has throttle middleware applied.
     *
     * On UNFIXED code, this FAILS because no throttle middleware exists on the route.
     *
     * **Validates: Requirements 1.6**
     */
    public function test_forgot_password_route_has_throttle_middleware(): void
    {
        $routes = Route::getRoutes();
        $forgotPasswordRoute = null;

        foreach ($routes as $route) {
            if ($route->uri() === 'forgot-password' && in_array('POST', $route->methods())) {
                $forgotPasswordRoute = $route;
                break;
            }
        }

        $this->assertNotNull($forgotPasswordRoute, 'POST /forgot-password route not found');

        $middleware = $forgotPasswordRoute->gatherMiddleware();

        $hasThrottle = false;
        foreach ($middleware as $m) {
            if (str_contains($m, 'throttle')) {
                $hasThrottle = true;
                break;
            }
        }

        $this->assertTrue(
            $hasThrottle,
            "POST /forgot-password route must have throttle middleware to prevent automated " .
            "enumeration. Current middleware: [" . implode(', ', $middleware) . "]"
        );
    }

    // ---------------------------------------------------------------
    // Helper
    // ---------------------------------------------------------------

    /**
     * Custom assertion for string containment with a message.
     */
    protected function assertStringContains(string $needle, string $haystack, string $message = ''): void
    {
        $this->assertTrue(
            str_contains($haystack, $needle),
            $message ?: "Failed asserting that '{$haystack}' contains '{$needle}'."
        );
    }
}
