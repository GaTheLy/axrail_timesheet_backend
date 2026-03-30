<?php

namespace App\Services;

use Aws\DynamoDb\DynamoDbClient;
use Aws\DynamoDb\Exception\DynamoDbException;

class SessionTrackerService
{
    protected DynamoDbClient $client;
    protected string $tableName;

    public function __construct()
    {
        $this->client = new DynamoDbClient([
            'region'  => config('aws.region'),
            'version' => 'latest',
        ]);
        $this->tableName = config('aws.session_tracker_table') ?? '';

        if (empty($this->tableName)) {
            \Illuminate\Support\Facades\Log::warning('SESSION_TRACKER_TABLE is not configured — single-device login enforcement is disabled');
        }
    }

    /**
     * Write or overwrite the active session token for a user.
     *
     * @param string $userId Cognito sub (user ID)
     * @param string $sessionToken Cryptographically random token
     * @return void
     * @throws DynamoDbException on DynamoDB failure (caller handles)
     */
    public function putSession(string $userId, string $sessionToken): void
    {
        $now = new \DateTimeImmutable('now', new \DateTimeZone('UTC'));
        $ttl = $now->getTimestamp() + (30 * 24 * 60 * 60); // 30 days from now

        $this->client->putItem([
            'TableName' => $this->tableName,
            'Item' => [
                'userId'         => ['S' => $userId],
                'sessionToken'   => ['S' => $sessionToken],
                'loginTimestamp'  => ['S' => $now->format('c')],
                'ttl'            => ['N' => (string) $ttl],
            ],
        ]);
    }

    /**
     * Retrieve the active session token for a user.
     *
     * @param string $userId
     * @return string|null The stored sessionToken, or null if not found
     * @throws DynamoDbException on DynamoDB failure (caller handles)
     */
    public function getSessionToken(string $userId): ?string
    {
        $result = $this->client->getItem([
            'TableName' => $this->tableName,
            'Key' => [
                'userId' => ['S' => $userId],
            ],
        ]);

        if (!isset($result['Item'])) {
            return null;
        }

        return $result['Item']['sessionToken']['S'] ?? null;
    }

    /**
     * Delete the session tracker entry for a user.
     *
     * @param string $userId
     * @return void
     * @throws DynamoDbException on DynamoDB failure (caller handles)
     */
    public function deleteSession(string $userId): void
    {
        $this->client->deleteItem([
            'TableName' => $this->tableName,
            'Key' => [
                'userId' => ['S' => $userId],
            ],
        ]);
    }
}
