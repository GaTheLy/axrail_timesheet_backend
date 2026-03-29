<?php

namespace Tests\Feature;

use App\Services\SessionTrackerService;
use Aws\DynamoDb\DynamoDbClient;
use Aws\Result;
use Mockery;
use Tests\TestCase;

/**
 * Feature: single-device-login, Property 6: Logout deletes session tracker entry
 *
 * Property 6: Logout deletes session tracker entry — For any user who logs out via
 * the Auth_Controller, the Session_Tracker SHALL no longer contain an entry for that
 * user's ID.
 *
 * **Validates: Requirements 4.1**
 *
 * Since no PHP PBT library is installed, this test uses randomized inputs across
 * 100 iterations to verify the property holds for arbitrary userId/sessionToken pairs.
 */
class SessionTokenDeletePropertyTest extends TestCase
{
    private const ITERATIONS = 100;

    protected function tearDown(): void
    {
        Mockery::close();
        parent::tearDown();
    }

    /**
     * Property 6: For random userId, put a session then delete, verify
     * getSessionToken returns null.
     *
     * **Validates: Requirements 4.1**
     */
    public function test_delete_removes_session_so_get_returns_null_for_random_inputs(): void
    {
        for ($i = 0; $i < self::ITERATIONS; $i++) {
            $userId = $this->randomUserId();
            $sessionToken = $this->randomSessionToken();

            $deleted = false;

            $mockClient = Mockery::mock(DynamoDbClient::class);

            // putItem stores the session
            $mockClient->shouldReceive('putItem')
                ->once()
                ->andReturn(new Result([]));

            // deleteItem marks the record as deleted
            $mockClient->shouldReceive('deleteItem')
                ->once()
                ->withArgs(function (array $args) use (&$deleted, $userId) {
                    $deleted = true;
                    // Verify deleteItem is called with the correct userId key
                    return isset($args['Key']['userId']['S'])
                        && $args['Key']['userId']['S'] === $userId;
                })
                ->andReturn(new Result([]));

            // After deleteItem, getItem returns empty result (no Item key)
            $mockClient->shouldReceive('getItem')
                ->once()
                ->andReturnUsing(function () use (&$deleted) {
                    if ($deleted) {
                        return new Result([]);
                    }
                    // Should not reach here in normal flow
                    return new Result(['Item' => ['sessionToken' => ['S' => 'unexpected']]]);
                });

            $service = $this->buildServiceWithMockClient($mockClient);

            // Put a session
            $service->putSession($userId, $sessionToken);

            // Delete the session (simulates logout)
            $service->deleteSession($userId);

            // Verify getSessionToken returns null after deletion
            $retrievedToken = $service->getSessionToken($userId);

            $this->assertNull(
                $retrievedToken,
                "Iteration {$i}: Expected null after deleting session for userId='{$userId}', " .
                "but got '{$retrievedToken}'."
            );

            $this->assertTrue(
                $deleted,
                "Iteration {$i}: deleteItem was not called for userId='{$userId}'."
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
