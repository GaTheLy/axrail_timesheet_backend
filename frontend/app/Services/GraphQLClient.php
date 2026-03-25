<?php

namespace App\Services;

use Exception;
use GuzzleHttp\Client;
use GuzzleHttp\Exception\ConnectException;
use GuzzleHttp\Exception\RequestException;
use Illuminate\Auth\AuthenticationException;

class GraphQLClient
{
    protected Client $httpClient;
    protected string $endpoint;
    protected int $maxRetries;

    public function __construct(?Client $httpClient = null, ?string $endpoint = null, int $maxRetries = 2)
    {
        $this->httpClient = $httpClient ?? new Client(['timeout' => 30]);
        $this->endpoint = $endpoint ?? config('aws.appsync_endpoint');
        $this->maxRetries = $maxRetries;
    }

    /**
     * Execute a GraphQL query.
     *
     * @param string $query The GraphQL query string
     * @param array $variables Query variables
     * @return array The 'data' portion of the GraphQL response
     * @throws AuthenticationException If the server returns 401/403
     * @throws Exception If the response contains GraphQL errors
     */
    public function query(string $query, array $variables = []): array
    {
        return $this->execute($query, $variables);
    }

    /**
     * Execute a GraphQL mutation.
     *
     * @param string $mutation The GraphQL mutation string
     * @param array $variables Mutation variables
     * @return array The 'data' portion of the GraphQL response
     * @throws AuthenticationException If the server returns 401/403
     * @throws Exception If the response contains GraphQL errors
     */
    public function mutate(string $mutation, array $variables = []): array
    {
        return $this->execute($mutation, $variables);
    }

    /**
     * Execute a GraphQL request with retry logic for transient failures.
     *
     * @param string $query The GraphQL query or mutation string
     * @param array $variables Variables for the operation
     * @return array The 'data' portion of the GraphQL response
     * @throws AuthenticationException
     * @throws Exception
     */
    protected function execute(string $query, array $variables): array
    {
        $attempt = 0;

        while (true) {
            try {
                $response = $this->httpClient->post($this->endpoint, [
                    'headers' => [
                        'Content-Type'  => 'application/json',
                        'Authorization' => session('accessToken', ''),
                    ],
                    'json' => [
                        'query'     => $query,
                        'variables' => (object) $variables,
                    ],
                ]);

                $body = json_decode($response->getBody()->getContents(), true);

                if (isset($body['errors']) && !empty($body['errors'])) {
                    $firstError = $body['errors'][0]['message'] ?? 'An unknown GraphQL error occurred';
                    throw new Exception($firstError);
                }

                return $body['data'] ?? [];

            } catch (RequestException $e) {
                $statusCode = $e->hasResponse() ? $e->getResponse()->getStatusCode() : null;

                // Auth errors should not be retried
                if ($statusCode === 401 || $statusCode === 403) {
                    throw new AuthenticationException('Your session has expired. Please log in again.');
                }

                // Retry on 5xx server errors
                if ($statusCode !== null && $statusCode >= 500 && $attempt < $this->maxRetries) {
                    $attempt++;
                    usleep($this->getBackoffDelay($attempt));
                    continue;
                }

                throw new Exception('API request failed: ' . $e->getMessage());

            } catch (ConnectException $e) {
                // Retry on network/connection errors
                if ($attempt < $this->maxRetries) {
                    $attempt++;
                    usleep($this->getBackoffDelay($attempt));
                    continue;
                }

                throw new Exception('Unable to connect to the API. Please check your network and try again.');
            }
        }
    }

    /**
     * Calculate exponential backoff delay in microseconds.
     *
     * @param int $attempt The current retry attempt (1-based)
     * @return int Delay in microseconds
     */
    protected function getBackoffDelay(int $attempt): int
    {
        // Exponential backoff: 500ms, 1000ms
        return (int) (pow(2, $attempt - 1) * 500000);
    }
}
