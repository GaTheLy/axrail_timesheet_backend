<?php

return [

    /*
    |--------------------------------------------------------------------------
    | AWS Region
    |--------------------------------------------------------------------------
    |
    | The AWS region used for all AWS service calls (Cognito, AppSync, etc.).
    |
    */

    'region' => env('AWS_REGION', 'ap-southeast-1'),

    /*
    |--------------------------------------------------------------------------
    | AppSync GraphQL Endpoint
    |--------------------------------------------------------------------------
    |
    | The full URL of the AWS AppSync GraphQL API endpoint.
    |
    */

    'appsync_endpoint' => env('APPSYNC_ENDPOINT'),

    /*
    |--------------------------------------------------------------------------
    | Cognito User Pool ID
    |--------------------------------------------------------------------------
    |
    | The ID of the AWS Cognito User Pool used for authentication.
    |
    */

    'cognito_user_pool_id' => env('COGNITO_USER_POOL_ID'),

    /*
    |--------------------------------------------------------------------------
    | Cognito Client ID
    |--------------------------------------------------------------------------
    |
    | The app client ID registered in the Cognito User Pool.
    |
    */

    'cognito_client_id' => env('COGNITO_CLIENT_ID'),

    /*
    |--------------------------------------------------------------------------
    | Session Tracker DynamoDB Table
    |--------------------------------------------------------------------------
    |
    | The name of the DynamoDB table used for single-device login session
    | tracking. Follows the pattern: Timesheet_SessionTracker_{env}
    |
    */

    'session_tracker_table' => env('SESSION_TRACKER_TABLE'),

];
