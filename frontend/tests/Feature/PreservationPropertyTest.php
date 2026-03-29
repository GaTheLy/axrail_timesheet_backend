<?php

namespace Tests\Feature;

use App\Http\Controllers\AuthController;
use App\Http\Middleware\CognitoAuth;
use App\Services\CognitoAuthService;
use Illuminate\Http\Request;
use Illuminate\Http\Response;
use Mockery;
use Tests\TestCase;

/**
 * Preservation Property Tests
 *
 * These tests capture the EXISTING correct behavior of authentication, session,
 * and password flows on UNFIXED code. They must continue to PASS after the
 * security fixes are applied, confirming no regressions.
 *
 * Property 2: Preservation — Authentication, Session, and Password Flow Preservation
 *
 * **Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.6, 3.7**
 */
class PreservationPropertyTest extends TestCase
{
    protected function tearDown(): void
    {
        Mockery::close();
        parent::tearDown();
    }

    // ---------------------------------------------------------------
    // Preservation 1: Login with valid credentials stores tokens and
    //                  redirects to /dashboard
    // Validates: Requirement 3.1
    // ---------------------------------------------------------------

    /**
     * For all valid credential inputs, login produces session with tokens
     * and redirects to /dashboard.
     *
     * **Validates: Requirements 3.1**
     *
     * @dataProvider validCredentialsProvider
     */
    public function test_login_with_valid_credentials_stores_tokens_and_redirects_to_dashboard(
        string $email,
        string $password,
        bool $remember
    ): void {
        $fakeAccessToken = 'access-token-' . md5($email);
        $fakeIdToken = $this->buildFakeIdToken($email);
        $fakeRefreshToken = 'refresh-token-' . md5($email);
        $fakeExpiry = time() + 3600;

        $service = Mockery::mock(CognitoAuthService::class);
        $service->shouldReceive('authenticate')
            ->once()
            ->with($email, $password, $remember)
            ->andReturn([
                'accessToken'  => $fakeAccessToken,
                'idToken'      => $fakeIdToken,
                'refreshToken' => $fakeRefreshToken,
                'tokenExpiry'  => $fakeExpiry,
                'user'         => [
                    'userId'   => 'sub-' . md5($email),
                    'email'    => $email,
                    'fullName' => 'Test User',
                    'userType' => 'employee',
                    'role'     => 'user',
                ],
            ]);

        $controller = new AuthController($service);

        $request = Request::create('/login', 'POST', [
            'email'    => $email,
            'password' => $password,
            'remember' => $remember,
        ]);
        $request->setLaravelSession(app('session.store'));

        $response = $controller->login($request);

        // Assert redirect to /dashboard
        $this->assertEquals(302, $response->getStatusCode());
        $this->assertStringContainsString('/dashboard', $response->getTargetUrl());

        // Assert tokens stored in session
        $this->assertEquals($fakeAccessToken, $request->session()->get('accessToken'));
        $this->assertEquals($fakeIdToken, $request->session()->get('idToken'));
        $this->assertEquals($fakeRefreshToken, $request->session()->get('refreshToken'));
        $this->assertEquals($fakeExpiry, $request->session()->get('tokenExpiry'));

        // Assert user info stored in session
        $user = $request->session()->get('user');
        $this->assertIsArray($user);
        $this->assertEquals($email, $user['email']);
    }

    /**
     * Data provider: various valid credential combinations.
     */
    public static function validCredentialsProvider(): array
    {
        return [
            'regular employee'          => ['employee@company.com', 'Password123!', false],
            'admin with remember'       => ['admin@company.com', 'Adm1nP@ss!', true],
            'superadmin no remember'    => ['superadmin@company.com', 'Sup3r$ecure', false],
            'user with special chars'   => ['user+test@example.org', 'P@$$w0rd!#', true],
            'long email'                => ['very.long.email.address@subdomain.example.com', 'LongP@ss1!', false],
        ];
    }

    // ---------------------------------------------------------------
    // Preservation 2: Single-session logout flushes session and
    //                  redirects to /login
    // Validates: Requirement 3.2
    // ---------------------------------------------------------------

    /**
     * For all single-session logout inputs, session is flushed and
     * redirect goes to /login.
     *
     * **Validates: Requirements 3.2**
     *
     * @dataProvider logoutSessionProvider
     */
    public function test_logout_flushes_session_and_redirects_to_login(
        string $accessToken,
        string $email
    ): void {
        $service = Mockery::mock(CognitoAuthService::class);

        // After fix, adminGlobalSignOut is called with the user's email
        $service->shouldReceive('adminGlobalSignOut')
            ->with($email)
            ->andReturn(true);

        $controller = new AuthController($service);

        $request = Request::create('/logout', 'POST');
        $request->setLaravelSession(app('session.store'));
        $request->session()->put('accessToken', $accessToken);
        $request->session()->put('refreshToken', 'refresh-' . md5($email));
        $request->session()->put('user', ['email' => $email]);
        $request->session()->put('idToken', 'id-token-123');

        $response = $controller->logout($request);

        // Assert redirect to /login
        $this->assertEquals(302, $response->getStatusCode());
        $this->assertStringContainsString('/login', $response->getTargetUrl());

        // Assert session is flushed (no tokens remain)
        $this->assertNull($request->session()->get('accessToken'));
        $this->assertNull($request->session()->get('refreshToken'));
        $this->assertNull($request->session()->get('user'));
    }

    /**
     * Data provider: various session states for logout.
     */
    public static function logoutSessionProvider(): array
    {
        return [
            'regular user session'    => ['access-token-regular-123', 'user@company.com'],
            'admin user session'      => ['access-token-admin-456', 'admin@company.com'],
            'superadmin user session' => ['access-token-super-789', 'superadmin@company.com'],
            'long-lived token'        => ['access-token-longlived-abc', 'persistent@company.com'],
        ];
    }

    // ---------------------------------------------------------------
    // Preservation 3: forgotPassword with valid email calls Cognito
    //                  forgotPassword API (code delivery still happens)
    // Validates: Requirement 3.3
    // ---------------------------------------------------------------

    /**
     * For all valid email inputs to forgotPassword, Cognito forgotPassword
     * API is called and code delivery still happens.
     *
     * **Validates: Requirements 3.3**
     *
     * @dataProvider validForgotPasswordEmailProvider
     */
    public function test_forgot_password_calls_cognito_api_for_valid_emails(
        string $email,
        string $deliveryMedium,
        string $maskedDestination
    ): void {
        $service = Mockery::mock(CognitoAuthService::class);

        // Cognito forgotPassword API must be called with the email
        $service->shouldReceive('forgotPassword')
            ->once()
            ->with($email)
            ->andReturn([
                'deliveryMedium' => $deliveryMedium,
                'destination'    => $maskedDestination,
            ]);

        $controller = new AuthController($service);

        $request = Request::create('/forgot-password', 'POST', ['email' => $email]);
        $request->setLaravelSession(app('session.store'));

        $response = $controller->forgotPassword($request);

        // Assert redirect happens (to /reset-password on success path in unfixed code)
        $this->assertEquals(302, $response->getStatusCode());
        $this->assertStringContainsString('/reset-password', $response->getTargetUrl());
    }

    /**
     * Data provider: valid emails that succeed in Cognito.
     */
    public static function validForgotPasswordEmailProvider(): array
    {
        return [
            'standard email'     => ['user@company.com', 'EMAIL', '***r@company.com'],
            'admin email'        => ['admin@company.com', 'EMAIL', '***n@company.com'],
            'subdomain email'    => ['user@sub.example.com', 'EMAIL', '***r@sub.example.com'],
            'plus-tagged email'  => ['user+tag@company.com', 'EMAIL', '***r+tag@company.com'],
        ];
    }

    // ---------------------------------------------------------------
    // Preservation 4: resetPassword with valid code calls
    //                  confirmForgotPassword and redirects to /login
    // Validates: Requirement 3.4
    // ---------------------------------------------------------------

    /**
     * For all valid code + password inputs to resetPassword,
     * confirmForgotPassword is called and redirect goes to /login.
     *
     * **Validates: Requirements 3.4**
     *
     * @dataProvider validResetPasswordProvider
     */
    public function test_reset_password_calls_confirm_and_redirects_to_login(
        string $email,
        string $code,
        string $newPassword
    ): void {
        $service = Mockery::mock(CognitoAuthService::class);

        // confirmForgotPassword must be called with correct params
        $service->shouldReceive('confirmForgotPassword')
            ->once()
            ->with($email, $code, $newPassword)
            ->andReturn(true);

        $controller = new AuthController($service);

        $request = Request::create('/reset-password', 'POST', [
            'email'                 => $email,
            'code'                  => $code,
            'password'              => $newPassword,
            'password_confirmation' => $newPassword,
        ]);
        $request->setLaravelSession(app('session.store'));

        $response = $controller->resetPassword($request);

        // Assert redirect to /login
        $this->assertEquals(302, $response->getStatusCode());
        $this->assertStringContainsString('/login', $response->getTargetUrl());

        // Assert success message is flashed
        $session = $request->session();
        $this->assertNotEmpty($session->get('status'));
        $this->assertStringContainsString('reset successfully', $session->get('status'));
    }

    /**
     * Data provider: valid reset password inputs.
     */
    public static function validResetPasswordProvider(): array
    {
        return [
            'standard reset'       => ['user@company.com', '123456', 'NewP@ssw0rd!'],
            'admin reset'          => ['admin@company.com', '654321', 'Adm1nN3w!@#'],
            'long code'            => ['user@example.org', '999888', 'L0ngP@$$word!'],
            'complex password'     => ['test@company.com', '111222', 'C0mpl3x!@#$%^'],
        ];
    }

    // ---------------------------------------------------------------
    // Preservation 5: CognitoAuth middleware refreshes expired tokens
    //                  using stored refresh token
    // Validates: Requirement 3.7
    // ---------------------------------------------------------------

    /**
     * For all requests with expired but refreshable tokens, middleware
     * refreshes the token and allows the request to proceed.
     *
     * **Validates: Requirements 3.7**
     *
     * @dataProvider expiredTokenSessionProvider
     */
    public function test_middleware_refreshes_expired_tokens_and_allows_request(
        string $expiredAccessToken,
        string $refreshToken,
        string $email
    ): void {
        $newAccessToken = 'new-access-' . md5($email);
        $newIdToken = $this->buildFakeIdToken($email);
        $newExpiry = time() + 3600;

        $service = Mockery::mock(CognitoAuthService::class);

        // Middleware should call refreshTokens with the stored refresh token
        $service->shouldReceive('refreshTokens')
            ->once()
            ->with($refreshToken)
            ->andReturn([
                'accessToken' => $newAccessToken,
                'idToken'     => $newIdToken,
                'tokenExpiry' => $newExpiry,
                'user'        => [
                    'userId'   => 'sub-' . md5($email),
                    'email'    => $email,
                    'fullName' => 'Test User',
                    'userType' => 'employee',
                    'role'     => 'user',
                ],
            ]);

        $service->shouldReceive('parseIdToken')
            ->with($newIdToken)
            ->andReturn([
                'sub'              => 'sub-' . md5($email),
                'email'            => $email,
                'name'             => 'Test User',
                'custom:userType'  => 'employee',
                'custom:role'      => 'user',
            ]);

        $middleware = new CognitoAuth($service);

        $request = Request::create('/dashboard', 'GET');
        $request->setLaravelSession(app('session.store'));

        // Set up expired token session
        $request->session()->put('accessToken', $expiredAccessToken);
        $request->session()->put('refreshToken', $refreshToken);
        $request->session()->put('tokenExpiry', time() - 100); // expired
        $request->session()->put('idToken', 'old-id-token');
        $request->session()->put('user', ['email' => $email]);

        $nextCalled = false;
        $response = $middleware->handle($request, function ($req) use (&$nextCalled) {
            $nextCalled = true;
            return new Response('OK', 200);
        });

        // Assert the request was allowed through (next was called)
        $this->assertTrue($nextCalled, 'Middleware should allow request through after token refresh');

        // Assert tokens were updated in session
        $this->assertEquals($newAccessToken, $request->session()->get('accessToken'));
        $this->assertEquals($newIdToken, $request->session()->get('idToken'));
        $this->assertEquals($newExpiry, $request->session()->get('tokenExpiry'));
    }

    /**
     * Data provider: various expired token sessions.
     */
    public static function expiredTokenSessionProvider(): array
    {
        return [
            'regular user expired token'    => ['expired-access-123', 'refresh-token-abc', 'user@company.com'],
            'admin user expired token'      => ['expired-access-456', 'refresh-token-def', 'admin@company.com'],
            'superadmin expired token'      => ['expired-access-789', 'refresh-token-ghi', 'superadmin@company.com'],
        ];
    }

    // ---------------------------------------------------------------
    // Preservation 6: NEW_PASSWORD_REQUIRED challenge flow completes
    //                  correctly via respondToAuthChallenge
    // Validates: Requirement 3.6
    // ---------------------------------------------------------------

    /**
     * NEW_PASSWORD_REQUIRED challenge flow for new users completes
     * correctly via respondToAuthChallenge.
     *
     * **Validates: Requirements 3.6**
     *
     * @dataProvider newPasswordChallengeProvider
     */
    public function test_new_password_challenge_flow_completes_correctly(
        string $email,
        string $newPassword,
        string $name
    ): void {
        $fakeSession = 'cognito-session-' . md5($email);
        $fakeAccessToken = 'new-access-' . md5($email);
        $fakeIdToken = $this->buildFakeIdToken($email);
        $fakeRefreshToken = 'new-refresh-' . md5($email);
        $fakeExpiry = time() + 3600;

        $service = Mockery::mock(CognitoAuthService::class);

        $service->shouldReceive('respondToNewPasswordChallenge')
            ->once()
            ->with($email, $newPassword, $fakeSession, [], $name)
            ->andReturn([
                'accessToken'  => $fakeAccessToken,
                'idToken'      => $fakeIdToken,
                'refreshToken' => $fakeRefreshToken,
                'tokenExpiry'  => $fakeExpiry,
                'user'         => [
                    'userId'   => 'sub-' . md5($email),
                    'email'    => $email,
                    'fullName' => $name,
                    'userType' => 'employee',
                    'role'     => 'user',
                ],
            ]);

        $controller = new AuthController($service);

        $request = Request::create('/force-change-password', 'POST', [
            'name'                  => $name,
            'password'              => $newPassword,
            'password_confirmation' => $newPassword,
        ]);
        $request->setLaravelSession(app('session.store'));

        // Set up challenge session data (as login would have set it)
        $request->session()->put('cognito_session', $fakeSession);
        $request->session()->put('cognito_email', $email);
        $request->session()->put('cognito_challenge_params', []);

        $response = $controller->forceChangePassword($request);

        // Assert redirect to /dashboard
        $this->assertEquals(302, $response->getStatusCode());
        $this->assertStringContainsString('/dashboard', $response->getTargetUrl());

        // Assert tokens stored in session
        $this->assertEquals($fakeAccessToken, $request->session()->get('accessToken'));
        $this->assertEquals($fakeIdToken, $request->session()->get('idToken'));
        $this->assertEquals($fakeRefreshToken, $request->session()->get('refreshToken'));

        // Assert challenge session data is cleaned up
        $this->assertNull($request->session()->get('cognito_session'));
        $this->assertNull($request->session()->get('cognito_email'));
    }

    /**
     * Data provider: new password challenge scenarios.
     */
    public static function newPasswordChallengeProvider(): array
    {
        return [
            'new employee'    => ['newuser@company.com', 'N3wP@ssw0rd!', 'John Doe'],
            'new admin'       => ['newadmin@company.com', 'Adm1nP@ss!#', 'Jane Admin'],
            'new superadmin'  => ['newsuper@company.com', 'Sup3r$ecure!', 'Super Admin'],
        ];
    }

    // ---------------------------------------------------------------
    // Preservation 7: Login with NEW_PASSWORD_REQUIRED challenge
    //                  redirects to /force-change-password
    // Validates: Requirement 3.6
    // ---------------------------------------------------------------

    /**
     * When Cognito returns NEW_PASSWORD_REQUIRED challenge, login redirects
     * to /force-change-password and stores challenge data in session.
     *
     * **Validates: Requirements 3.6**
     *
     * @dataProvider newPasswordChallengeLoginProvider
     */
    public function test_login_with_new_password_challenge_redirects_correctly(
        string $email,
        string $password
    ): void {
        $fakeSession = 'challenge-session-' . md5($email);

        $service = Mockery::mock(CognitoAuthService::class);
        $service->shouldReceive('authenticate')
            ->once()
            ->with($email, $password, false)
            ->andReturn([
                'challenge'       => 'NEW_PASSWORD_REQUIRED',
                'session'         => $fakeSession,
                'challengeParams' => ['userAttributes' => '{"email":"' . $email . '"}'],
            ]);

        $controller = new AuthController($service);

        $request = Request::create('/login', 'POST', [
            'email'    => $email,
            'password' => $password,
        ]);
        $request->setLaravelSession(app('session.store'));

        $response = $controller->login($request);

        // Assert redirect to /force-change-password
        $this->assertEquals(302, $response->getStatusCode());
        $this->assertStringContainsString('/force-change-password', $response->getTargetUrl());

        // Assert challenge data stored in session
        $this->assertEquals($fakeSession, $request->session()->get('cognito_session'));
        $this->assertEquals($email, $request->session()->get('cognito_email'));
    }

    /**
     * Data provider: new user login scenarios triggering password challenge.
     */
    public static function newPasswordChallengeLoginProvider(): array
    {
        return [
            'new employee login'   => ['newemployee@company.com', 'TempP@ss1!'],
            'new admin login'      => ['newadmin@company.com', 'TempAdm1n!'],
        ];
    }

    // ---------------------------------------------------------------
    // Helper
    // ---------------------------------------------------------------

    /**
     * Build a fake JWT ID token with the given email for testing.
     */
    private function buildFakeIdToken(string $email): string
    {
        $header = base64_encode(json_encode(['alg' => 'RS256', 'typ' => 'JWT']));
        $payload = base64_encode(json_encode([
            'sub'              => 'sub-' . md5($email),
            'email'            => $email,
            'name'             => 'Test User',
            'custom:userType'  => 'employee',
            'custom:role'      => 'user',
        ]));
        $signature = base64_encode('fake-signature');

        return $header . '.' . $payload . '.' . $signature;
    }
}
