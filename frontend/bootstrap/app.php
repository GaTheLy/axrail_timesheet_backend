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

        // Restrict trusted hosts to prevent Host Header Injection (CWE-644)
        // Only accept requests with valid Host headers matching our domains
        $middleware->trustHosts(at: [
            '^.+\.elasticbeanstalk\.com$',
            '^.+\.cloudfront\.net$',
            '^.+\.amazonaws\.com$',
            '^localhost$',
            '^127\.0\.0\.1$',
        ]);

        // Exclude login from CSRF verification for pen testing
        // TODO: Remove after penetration testing is complete
        $middleware->validateCsrfTokens(except: [
            'login',
        ]);

        $middleware->alias([
            'cognito.auth' => \App\Http\Middleware\CognitoAuth::class,
            'role' => \App\Http\Middleware\RoleMiddleware::class,
        ]);
    })
    ->withExceptions(function (Exceptions $exceptions) {
        //
    })->create();
