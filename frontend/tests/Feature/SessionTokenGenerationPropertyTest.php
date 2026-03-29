<?php

namespace Tests\Feature;

use App\Http\Controllers\AuthController;
use App\Services\CognitoAuthService;
use App\Services\SessionTrackerService;
use Illuminate\Http\Request;
use Mockery;
use Tests\TestCase;

/**
 * Feature: single-device-login, Property 1: Session token generation on any auth flow
 *
 * Property 1: Session token generation on any auth flow — For any successful
 * authentication flow (login or force-change-password), the Laravel session SHALL
 * contain a sessionToken value that is a non-empty, 64-character hexadecimal string.
 *
 * **Validates: Requirements 1.1, 2.1**
 *
 * Since no PHP PBT library is installed, this test uses randomized inputs across
 * 100 iterations to verify the property holds for arbitrary credentials.
 */
class SessionTokenGenerationPropertyTest extends TestCase
{
    private const ITERATIONS = 100;
    private const SESSION_TOKEN_PATTERN = '/^[0-9a-f]{64}$/';

    protected function tearDown(): void
    {
        Mockery::close();
        parent::tearDown();
    }

    /**
     * Property 1 (login flow): For any successful login, the session contains
     * a non-empty 64-character hex sessionToken.
     *
     * **Validates: Requirements 1.1**
     */
    public function test_login_generates_valid_session_token_for_random_credentials(): void
    {
        for ($i = 0; $i < self::ITERATIONS; $i++) {
            $email = $this->randomEmail();
            $password = $this->randomPassword();
            $userId = $this->randomUserId();
            $accessToken = $this->randomHex(40);
            $idToken = $this->randomHex(40);
            $refreshToken = $this->randomHex(40);

            $cognitoService = Mockery::mock(CognitoAuthService::class);
            $cognitoService->shouldReceive('authenticate')
                ->once()
                ->andReturn([
                    'accessToken'  => $accessToken,
                    'idToken'      => $idToken,
                    'refreshToken' => $refreshToken,
                    'tokenExpiry'  => time() + 3600,
                    'user'         => [
                        'userId'   => $userId,
                        'email'    => $email,
                        'fullName' => 'Test User',
                        'userType' => 'employee',
                        'role'     => 'user',
                    ],
                ]);

            // Mock SessionTrackerService to avoid DynamoDB calls
            $sessionTracker = Mockery::mock(SessionTrackerService::class);
            $sessionTracker->shouldReceive('putSession')->once();
            $this->app->instance(SessionTrackerService::class, $sessionTracker);

            $controller = new AuthController($cognitoService);

            $request = Request::create('/login', 'POST', [
                'email'    => $email,
                'password' => $password,
            ]);
            $request->setLaravelSession(app('session.store'));

            $controller->login($request);

            $sessionToken = $request->session()->get('sessionToken');

            $this->assertNotNull(
                $sessionToken,
                "Iteration {$i}: sessionToken is null after login with email='{$email}'."
            );

            $this->assertNotEmpty(
                $sessionToken,
                "Iteration {$i}: sessionToken is empty after login with email='{$email}'."
            );

            $this->assertMatchesRegularExpression(
                self::SESSION_TOKEN_PATTERN,
                $sessionToken,
                "Iteration {$i}: sessionToken '{$sessionToken}' is not a valid 64-char hex string " .
                "after login with email='{$email}'."
            );

            Mockery::close();
        }
    }

    /**
     * Property 1 (force-change-password flow): For any successful force-change-password,
     * the session contains a non-empty 64-character hex sessionToken.
     *
     * **Validates: Requirements 2.1**
     */
    public function test_force_change_password_generates_valid_session_token_for_random_credentials(): void
    {
        for ($i = 0; $i < self::ITERATIONS; $i++) {
            $email = $this->randomEmail();
            $password = $this->randomPassword();
            $name = $this->randomName();
            $userId = $this->randomUserId();
            $accessToken = $this->randomHex(40);
            $idToken = $this->randomHex(40);
            $refreshToken = $this->randomHex(40);
            $session = $this->randomHex(20);

            $cognitoService = Mockery::mock(CognitoAuthService::class);
            $cognitoService->shouldReceive('respondToNewPasswordChallenge')
                ->once()
                ->andReturn([
                    'accessToken'  => $accessToken,
                    'idToken'      => $idToken,
                    'refreshToken' => $refreshToken,
                    'tokenExpiry'  => time() + 3600,
                    'user'         => [
                        'userId'   => $userId,
                        'email'    => $email,
                        'fullName' => $name,
                        'userType' => 'employee',
                        'role'     => 'user',
                    ],
                ]);

            // Mock SessionTrackerService to avoid DynamoDB calls
            $sessionTracker = Mockery::mock(SessionTrackerService::class);
            $sessionTracker->shouldReceive('putSession')->once();
            $this->app->instance(SessionTrackerService::class, $sessionTracker);

            $controller = new AuthController($cognitoService);

            $request = Request::create('/force-change-password', 'POST', [
                'name'                  => $name,
                'password'              => $password,
                'password_confirmation' => $password,
            ]);
            $request->setLaravelSession(app('session.store'));

            // Set up the challenge session data that forceChangePassword expects
            $request->session()->put('cognito_session', $session);
            $request->session()->put('cognito_email', $email);
            $request->session()->put('cognito_challenge_params', []);

            $controller->forceChangePassword($request);

            $sessionToken = $request->session()->get('sessionToken');

            $this->assertNotNull(
                $sessionToken,
                "Iteration {$i}: sessionToken is null after force-change-password with email='{$email}'."
            );

            $this->assertNotEmpty(
                $sessionToken,
                "Iteration {$i}: sessionToken is empty after force-change-password with email='{$email}'."
            );

            $this->assertMatchesRegularExpression(
                self::SESSION_TOKEN_PATTERN,
                $sessionToken,
                "Iteration {$i}: sessionToken '{$sessionToken}' is not a valid 64-char hex string " .
                "after force-change-password with email='{$email}'."
            );

            Mockery::close();
        }
    }

    /**
     * Generate a random email address.
     */
    private function randomEmail(): string
    {
        $localPart = bin2hex(random_bytes(random_int(3, 12)));
        $domains = ['example.com', 'test.org', 'mail.net', 'company.io', 'dev.co'];
        return $localPart . '@' . $domains[array_rand($domains)];
    }

    /**
     * Generate a random password (8-20 chars, alphanumeric + special).
     */
    private function randomPassword(): string
    {
        $length = random_int(8, 20);
        return bin2hex(random_bytes($length));
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
     * Generate a random name string.
     */
    private function randomName(): string
    {
        $firstNames = ['Alice', 'Bob', 'Charlie', 'Diana', 'Eve', 'Frank', 'Grace', 'Hank'];
        $lastNames = ['Smith', 'Jones', 'Brown', 'Wilson', 'Taylor', 'Clark', 'Lee', 'Hall'];
        return $firstNames[array_rand($firstNames)] . ' ' . $lastNames[array_rand($lastNames)];
    }

    /**
     * Generate a random hex string of the given byte length.
     */
    private function randomHex(int $bytes): string
    {
        return bin2hex(random_bytes($bytes));
    }
}
