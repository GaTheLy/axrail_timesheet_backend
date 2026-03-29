<?php

use Illuminate\Foundation\Application;
use Illuminate\Foundation\Configuration\Exceptions;
use Illuminate\Foundation\Configuration\Middleware;

return Application::configure(basePath: dirname(__DIR__))
    ->withRouting(
        web: __DIR__.'/../routes/web.php',
    )
    ->withMiddleware(function (Middleware $middleware) {
        // Trust all proxies (CloudFront, EB load balancer) so Laravel
        // correctly detects HTTPS from X-Forwarded-Proto headers
        $middleware->trustProxies(at: '*');

        $middleware->alias([
            'cognito.auth' => \App\Http\Middleware\CognitoAuth::class,
            'role' => \App\Http\Middleware\RoleMiddleware::class,
        ]);
    })
    ->withExceptions(function (Exceptions $exceptions) {
        //
    })->create();
