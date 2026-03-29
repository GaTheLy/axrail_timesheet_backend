<?php

namespace Tests\Feature;

use App\Services\SessionTrackerService;
use Aws\DynamoDb\DynamoDbClient;
use Aws\Result;
use Mockery;
use Tests\TestCase;

/**
 * Feature: single-device-login, Property 3: Session token overwrite on re-login
 *
 * Property 3: Session token overwrite on re-login — For any user who authenticates
 * twice in sequence, the Session_Tracker SHALL contain only the session token from
 * the second authentication, and the token from the first authentication SHALL no
 * longer be retrievable.
 *
 * **Validates: Requirements 1.3**
 *
 * Since no PHP PBT library is installed, this test uses randomized inputs across
 * 100 iterations to verify the property holds for arbitrary userId/token pairs.
 */
class SessionTokenOverwritePropertyTest extends TestCase
{
    private const ITERATIONS = 100;

    protected function tearDown(): void
    {
        Mockery::close();
        parent::tearDown();
    }

    /**
     * Property 3: For random userId and two random tokens, put both sequentially,
     * verify only the second is retrievable via getSessionToken.
     *
     * **Validates: Requirements 1.3**
     */
    public function test_second_put_overwrites_first_token_for_random_inputs(): void
    {
        for ($i = 0; $i < self::ITERATIONS; $i++) {
            $userId = $this->randomUserId();
            $firstToken = $this->randomSessionToken();
            $secondToken = $this->randomSessionToken();

            // Ensure the two tokens are distinct so the test is meaningful
            while ($secondToken === $firstToken) {
                $secondToken = $this->randomSessionToken();
            }

            // Track the latest item stored by putItem
            $storedItem = null;

            $mockClient = Mockery::mock(DynamoDbClient::class);

            $mockClient->shouldReceive('putItem')
                ->twice()
                ->withArgs(function (array $args) use (&$storedItem) {
                    $storedItem = $args['Item'] ?? null;
                    return true;
                })
                ->andReturn(new Result([]));

            // getItem returns whatever was last stored (simulating DynamoDB overwrite)
            $mockClient->shouldReceive('getItem')
                ->once()
                ->andReturnUsing(function () use (&$storedItem) {
                    return new Result([
                        'Item' => $storedItem,
                    ]);
                });

            $service = $this->buildServiceWithMockClient($mockClient);

            // First login — store first token
            $service->putSession($userId, $firstToken);

            // Second login — overwrite with second token
            $service->putSession($userId, $secondToken);

            // Retrieve — should return only the second token
            $retrievedToken = $service->getSessionToken($userId);

            $this->assertSame(
                $secondToken,
                $retrievedToken,
                "Iteration {$i}: Expected second token '{$secondToken}', " .
                "got '{$retrievedToken}' for userId='{$userId}'. " .
                "First token '{$firstToken}' should have been overwritten."
            );

            $this->assertNotSame(
                $firstToken,
                $retrievedToken,
                "Iteration {$i}: Retrieved token matches the first token '{$firstToken}' " .
                "instead of the second token '{$secondToken}'. Overwrite failed."
            );
        }
    }

    /**
     * Build a SessionTrackerService with a mocked DynamoDbClient injected via reflection.
     */
    private function buildServiceWithMockClient($mockClient): SessionTrackerService
    {
        config(['aws.region' => 'us-east-1']);
        config(['aws.session_tracker_table' => 'TestSessionTracker']);

        $service = new SessionTrackerService();

        $reflection = new \ReflectionClass($service);
        $clientProp = $reflection->getProperty('client');
        $clientProp->setAccessible(true);
        $clientProp->setValue($service, $mockClient);

        return $service;
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
}
