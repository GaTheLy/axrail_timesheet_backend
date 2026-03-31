<?php

namespace App\Services;

use Aws\CognitoIdentityProvider\CognitoIdentityProviderClient;
use Aws\Exception\AwsException;
use Exception;

class CognitoAuthService
{
    protected CognitoIdentityProviderClient $client;
    protected string $clientId;
    protected string $userPoolId;

    public function __construct()
    {
        $this->client = new CognitoIdentityProviderClient([
            'region'  => config('aws.region'),
            'version' => 'latest',
        ]);
        $this->clientId = config('aws.cognito_client_id');
        $this->userPoolId = config('aws.cognito_user_pool_id');
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
    
        /**
         * Authenticate a user with email and password using Cognito USER_PASSWORD_AUTH flow.
         *
         * @param string $email
         * @param string $password
         * @param bool $rememberDevice
         * @return array
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

                // Handle NEW_PASSWORD_REQUIRED challenge
                $challengeName = $result->get('ChallengeName');
                if ($challengeName === 'NEW_PASSWORD_REQUIRED') {
                    return [
                        'challenge'        => 'NEW_PASSWORD_REQUIRED',
                        'session'          => $result->get('Session'),
                        'challengeParams'  => $result->get('ChallengeParameters') ?? [],
                    ];
                }

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
         * Respond to the NEW_PASSWORD_REQUIRED challenge.
         *
         * @param string $email
         * @param string $newPassword
         * @param string $session
         * @return array
         * @throws Exception
         */
        public function respondToNewPasswordChallenge(string $email, string $newPassword, string $session, array $challengeParams = [], ?string $name = null): array
        {
            try {
                $challengeResponses = [
                    'USERNAME'     => $email,
                    'NEW_PASSWORD' => $newPassword,
                ];

                // Non-mutable attributes that must NOT be sent back in challenge response
                $immutableAttrs = ['sub', 'email_verified', 'phone_number_verified', 'identities', 'email'];

                // Cognito returns userAttributes as a JSON string with existing values.
                // Only pass back mutable attributes.
                $userAttrsJson = $challengeParams['userAttributes'] ?? '{}';
                $userAttrs = json_decode($userAttrsJson, true) ?? [];

                foreach ($userAttrs as $key => $value) {
                    if ($value !== null && $value !== '' && !in_array($key, $immutableAttrs, true)) {
                        $challengeResponses['userAttributes.' . $key] = $value;
                    }
                }

                // Set name from form input (required attribute that may be missing)
                if ($name !== null) {
                    $challengeResponses['userAttributes.name'] = $name;
                }

                $result = $this->client->respondToAuthChallenge([
                    'ClientId'             => $this->clientId,
                    'ChallengeName'        => 'NEW_PASSWORD_REQUIRED',
                    'Session'              => $session,
                    'ChallengeResponses'   => $challengeResponses,
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
                \Illuminate\Support\Facades\Log::error('Force change password failed', [
                    'code' => $e->getAwsErrorCode(),
                    'message' => $e->getAwsErrorMessage(),
                    'email' => $email,
                ]);
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
        $email = strtolower($email);

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
        $email = strtolower($email);

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
     * Sign out the user globally from all devices using admin API.
     * This revokes ALL refresh tokens for the user regardless of token state.
     *
     * @param string $username The Cognito username (email) of the user
     * @return bool
     * @throws Exception
     */
    public function adminGlobalSignOut(string $username): bool
    {
        try {
            $this->client->adminUserGlobalSignOut([
                'UserPoolId' => $this->userPoolId,
                'Username'   => $username,
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
        $code = $e->getAwsErrorCode();
        $message = $e->getAwsErrorMessage() ?? '';

        // Session expired during challenge flow
        if ($code === 'NotAuthorizedException' && str_contains($message, 'Invalid session')) {
            return 'Your session has expired. Please sign in again to restart the password change.';
        }

        return match ($code) {
            'NotAuthorizedException'        => 'Invalid credentials. Please check your email and password.',
            'UserNotFoundException'          => 'Invalid credentials. Please check your email and password.',
            'UserNotConfirmedException'      => 'Your account has not been confirmed. Please check your email for a confirmation link.',
            'PasswordResetRequiredException' => 'You must reset your password before signing in.',
            'CodeMismatchException'          => 'The verification code is incorrect. Please try again.',
            'ExpiredCodeException'           => 'The verification code has expired. Please request a new one.',
            'InvalidPasswordException'       => 'The password does not meet the required policy. It must be at least 8 characters with uppercase, lowercase, number, and symbol.',
            'InvalidParameterException'      => 'The password does not meet the required policy. It must be at least 8 characters with uppercase, lowercase, number, and symbol.',
            'LimitExceededException'         => 'Too many attempts. Please try again later.',
            'TooManyRequestsException'       => 'Too many requests. Please try again later.',
            default                          => 'An authentication error occurred: ' . ($message ?: 'Please try again.'),
        };
    }
}
