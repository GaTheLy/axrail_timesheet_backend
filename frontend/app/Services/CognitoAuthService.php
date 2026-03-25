<?php

namespace App\Services;

use Aws\CognitoIdentityProvider\CognitoIdentityProviderClient;
use Aws\Exception\AwsException;
use Exception;

class CognitoAuthService
{
    protected CognitoIdentityProviderClient $client;
    protected string $clientId;

    public function __construct()
    {
        $this->client = new CognitoIdentityProviderClient([
            'region'  => config('aws.region'),
            'version' => 'latest',
        ]);
        $this->clientId = config('aws.cognito_client_id');
    }

    /**
     * Authenticate a user with email and password using Cognito USER_PASSWORD_AUTH flow.
     *
     * @param string $email
     * @param string $password
     * @param bool $rememberDevice
     * @return array{accessToken: string, idToken: string, refreshToken: string, tokenExpiry: int, user: array}
     * @throws Exception
     */
    public function authenticate(string $email, string $password, bool $rememberDevice = false): array
    {
        try {
            $result = $this->client->initiateAuth([
                'AuthFlow'       => 'USER_PASSWORD_AUTH',
                'ClientId'       => $this->clientId,
                'AuthParameters' => [
                    'USERNAME' => $email,
                    'PASSWORD' => $password,
                ],
            ]);

            $authResult = $result->get('AuthenticationResult');

            $idTokenClaims = $this->parseIdToken($authResult['IdToken']);

            return [
                'accessToken'  => $authResult['AccessToken'],
                'idToken'      => $authResult['IdToken'],
                'refreshToken' => $authResult['RefreshToken'] ?? null,
                'tokenExpiry'  => time() + ($authResult['ExpiresIn'] ?? 3600),
                'user'         => [
                    'userId'   => $idTokenClaims['sub'] ?? '',
                    'email'    => $idTokenClaims['email'] ?? '',
                    'fullName' => $idTokenClaims['name'] ?? '',
                    'userType' => $idTokenClaims['custom:userType'] ?? '',
                    'role'     => $idTokenClaims['custom:role'] ?? '',
                ],
            ];
        } catch (AwsException $e) {
            throw new Exception($this->mapCognitoError($e));
        }
    }

    /**
     * Refresh tokens using the Cognito REFRESH_TOKEN_AUTH flow.
     *
     * @param string $refreshToken
     * @return array{accessToken: string, idToken: string, tokenExpiry: int, user: array}
     * @throws Exception
     */
    public function refreshTokens(string $refreshToken): array
    {
        try {
            $result = $this->client->initiateAuth([
                'AuthFlow'       => 'REFRESH_TOKEN_AUTH',
                'ClientId'       => $this->clientId,
                'AuthParameters' => [
                    'REFRESH_TOKEN' => $refreshToken,
                ],
            ]);

            $authResult = $result->get('AuthenticationResult');

            $idTokenClaims = $this->parseIdToken($authResult['IdToken']);

            return [
                'accessToken' => $authResult['AccessToken'],
                'idToken'     => $authResult['IdToken'],
                'tokenExpiry' => time() + ($authResult['ExpiresIn'] ?? 3600),
                'user'        => [
                    'userId'   => $idTokenClaims['sub'] ?? '',
                    'email'    => $idTokenClaims['email'] ?? '',
                    'fullName' => $idTokenClaims['name'] ?? '',
                    'userType' => $idTokenClaims['custom:userType'] ?? '',
                    'role'     => $idTokenClaims['custom:role'] ?? '',
                ],
            ];
        } catch (AwsException $e) {
            throw new Exception($this->mapCognitoError($e));
        }
    }

    /**
     * Initiate the forgot password flow for a user.
     *
     * @param string $email
     * @return array{deliveryMedium: string, destination: string}
     * @throws Exception
     */
    public function forgotPassword(string $email): array
    {
        try {
            $result = $this->client->forgotPassword([
                'ClientId' => $this->clientId,
                'Username' => $email,
            ]);

            $delivery = $result->get('CodeDeliveryDetails') ?? [];

            return [
                'deliveryMedium' => $delivery['DeliveryMedium'] ?? 'EMAIL',
                'destination'    => $delivery['Destination'] ?? '',
            ];
        } catch (AwsException $e) {
            throw new Exception($this->mapCognitoError($e));
        }
    }

    /**
     * Confirm a forgot password request with the verification code and new password.
     *
     * @param string $email
     * @param string $code
     * @param string $newPassword
     * @return bool
     * @throws Exception
     */
    public function confirmForgotPassword(string $email, string $code, string $newPassword): bool
    {
        try {
            $this->client->confirmForgotPassword([
                'ClientId'         => $this->clientId,
                'Username'         => $email,
                'ConfirmationCode' => $code,
                'Password'         => $newPassword,
            ]);

            return true;
        } catch (AwsException $e) {
            throw new Exception($this->mapCognitoError($e));
        }
    }

    /**
     * Change the password for an authenticated user.
     *
     * @param string $accessToken
     * @param string $oldPassword
     * @param string $newPassword
     * @return bool
     * @throws Exception
     */
    public function changePassword(string $accessToken, string $oldPassword, string $newPassword): bool
    {
        try {
            $this->client->changePassword([
                'AccessToken'      => $accessToken,
                'PreviousPassword' => $oldPassword,
                'ProposedPassword' => $newPassword,
            ]);

            return true;
        } catch (AwsException $e) {
            throw new Exception($this->mapCognitoError($e));
        }
    }

    /**
     * Sign out the user globally from all devices.
     *
     * @param string $accessToken
     * @return bool
     * @throws Exception
     */
    public function globalSignOut(string $accessToken): bool
    {
        try {
            $this->client->globalSignOut([
                'AccessToken' => $accessToken,
            ]);

            return true;
        } catch (AwsException $e) {
            throw new Exception($this->mapCognitoError($e));
        }
    }

    /**
     * Parse a JWT ID token and extract claims.
     *
     * @param string $idToken
     * @return array
     */
    public function parseIdToken(string $idToken): array
    {
        $parts = explode('.', $idToken);

        if (count($parts) !== 3) {
            return [];
        }

        $payload = $parts[1];
        // Add padding for base64url decoding
        $payload = str_replace(['-', '_'], ['+', '/'], $payload);
        $decoded = base64_decode($payload, true);

        if ($decoded === false) {
            return [];
        }

        $claims = json_decode($decoded, true);

        return is_array($claims) ? $claims : [];
    }

    /**
     * Map AWS Cognito exceptions to user-friendly error messages.
     *
     * @param AwsException $e
     * @return string
     */
    protected function mapCognitoError(AwsException $e): string
    {
        return match ($e->getAwsErrorCode()) {
            'NotAuthorizedException'       => 'Invalid credentials. Please check your email and password.',
            'UserNotFoundException'         => 'Invalid credentials. Please check your email and password.',
            'UserNotConfirmedException'     => 'Your account has not been confirmed. Please check your email for a confirmation link.',
            'PasswordResetRequiredException' => 'You must reset your password before signing in.',
            'CodeMismatchException'         => 'The verification code is incorrect. Please try again.',
            'ExpiredCodeException'          => 'The verification code has expired. Please request a new one.',
            'InvalidPasswordException'      => 'The password does not meet the required policy. It must be at least 8 characters with uppercase, lowercase, number, and symbol.',
            'LimitExceededException'        => 'Too many attempts. Please try again later.',
            'TooManyRequestsException'      => 'Too many requests. Please try again later.',
            default                         => 'An authentication error occurred. Please try again.',
        };
    }
}
