<?php

namespace Tests\Feature;

use App\Services\SessionTrackerService;
use Aws\DynamoDb\DynamoDbClient;
use Aws\Result;
use Mockery;
use Tests\TestCase;

/**
 * Feature: single-device-login, Property 2: Session token round-trip persistence
 *
 * Property 2: Session token round-trip persistence — For any successful authentication
 * flow and any user ID, the sessionToken stored in the Laravel session SHALL equal the
 * sessionToken retrieved from the Session_Tracker DynamoDB table for that user ID, and
 * the record SHALL contain a valid loginTimestamp and a ttl value approximately 30 days
 * in the future.
 *
 * **Validates: Requirements 1.2, 2.2, 5.2, 5.3**
 *
 * Since no PHP PBT library is installed, this test uses randomized inputs across
 * 100 iterations to verify the property holds for arbitrary userId/sessionToken pairs.
 */
class SessionTokenRoundTripPropertyTest extends TestCase
{
    private const ITERATIONS = 100;
    private const TTL_30_DAYS = 30 * 24 * 60 * 60;
    private const TTL_TOLERANCE_SECONDS = 5;

    protected function tearDown(): void
    {
        Mockery::close();
        parent::tearDown();
    }

    /**
     * Property 2: For random userId and sessionToken values, putSession then
     * getSessionToken returns the same token, with valid loginTimestamp and ttl.
     *
     * **Validates: Requirements 1.2, 2.2, 5.2, 5.3**
     */
    public function test_put_then_get_returns_same_session_token_for_random_inputs(): void
    {
        for ($i = 0; $i < self::ITERATIONS; $i++) {
            $userId = $this->randomUserId();
            $sessionToken = $this->randomSessionToken();

            // Storage to capture what putItem receives
            $capturedItem = null;

            $mockClient = Mockery::mock(DynamoDbClient::class);

            $mockClient->shouldReceive('putItem')
                ->once()
                ->withArgs(function (array $args) use (&$capturedItem) {
                    $capturedItem = $args['Item'] ?? null;
                    return true;
                })
                ->andReturn(new Result([]));

            // getItem returns whatever was captured from putItem
            $mockClient->shouldReceive('getItem')
                ->once()
                ->andReturnUsing(function () use (&$capturedItem) {
                    return new Result([
                        'Item' => $capturedItem,
                    ]);
                });

            $service = $this->buildServiceWithMockClient($mockClient);

            $beforeTimestamp = time();
            $service->putSession($userId, $sessionToken);
            $afterTimestamp = time();

            $retrievedToken = $service->getSessionToken($userId);

            // Round-trip: retrieved token must equal the original
            $this->assertSame(
                $sessionToken,
                $retrievedToken,
                "Iteration {$i}: Round-trip failed for userId='{$userId}'. " .
                "Expected token '{$sessionToken}', got '{$retrievedToken}'."
            );

            // Verify the stored item has all required attributes (Req 5.2)
            $this->assertNotNull($capturedItem, "Iteration {$i}: putItem was not called with an Item.");
            $this->assertArrayHasKey('userId', $capturedItem, "Iteration {$i}: Missing 'userId' attribute.");
            $this->assertArrayHasKey('sessionToken', $capturedItem, "Iteration {$i}: Missing 'sessionToken' attribute.");
            $this->assertArrayHasKey('loginTimestamp', $capturedItem, "Iteration {$i}: Missing 'loginTimestamp' attribute.");
            $this->assertArrayHasKey('ttl', $capturedItem, "Iteration {$i}: Missing 'ttl' attribute.");

            // Verify userId and sessionToken values match input
            $this->assertSame($userId, $capturedItem['userId']['S'], "Iteration {$i}: Stored userId mismatch.");
            $this->assertSame($sessionToken, $capturedItem['sessionToken']['S'], "Iteration {$i}: Stored sessionToken mismatch.");

            // Verify loginTimestamp is a valid ISO 8601 string (Req 5.2)
            $storedTimestamp = $capturedItem['loginTimestamp']['S'];
            $parsedTime = \DateTimeImmutable::createFromFormat(\DateTimeInterface::ATOM, $storedTimestamp);
            $this->assertNotFalse(
                $parsedTime,
                "Iteration {$i}: loginTimestamp '{$storedTimestamp}' is not valid ISO 8601."
            );

            // Verify ttl is approximately 30 days in the future (Req 5.3)
            $storedTtl = (int) $capturedItem['ttl']['N'];
            $expectedTtlMin = $beforeTimestamp + self::TTL_30_DAYS - self::TTL_TOLERANCE_SECONDS;
            $expectedTtlMax = $afterTimestamp + self::TTL_30_DAYS + self::TTL_TOLERANCE_SECONDS;
            $this->assertGreaterThanOrEqual(
                $expectedTtlMin,
                $storedTtl,
                "Iteration {$i}: TTL {$storedTtl} is too far in the past (expected >= {$expectedTtlMin})."
            );
            $this->assertLessThanOrEqual(
                $expectedTtlMax,
                $storedTtl,
                "Iteration {$i}: TTL {$storedTtl} is too far in the future (expected <= {$expectedTtlMax})."
            );
        }
    }

    /**
     * Build a SessionTrackerService with a mocked DynamoDbClient injected via reflection.
     */
    private function buildServiceWithMockClient($mockClient): SessionTrackerService
    {
        // Set config so constructor doesn't fail
        config(['aws.region' => 'us-east-1']);
        config(['aws.session_tracker_table' => 'TestSessionTracker']);

        $service = new SessionTrackerService();

        // Replace the internal client with our mock via reflection
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
