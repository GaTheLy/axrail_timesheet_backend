<?php

namespace App\Providers;

use Illuminate\Cache\RateLimiting\Limit;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\RateLimiter;
use Illuminate\Support\ServiceProvider;

class AppServiceProvider extends ServiceProvider
{
    /**
     * Register any application services.
     */
    public function register(): void
    {
        //
    }

    /**
     * Bootstrap any application services.
     */
    public function boot(): void
    {
        // Force HTTPS when behind a proxy (CloudFront, load balancer)
        if ($this->app->environment('production', 'staging') || request()->header('X-Forwarded-Proto') === 'https') {
            \Illuminate\Support\Facades\URL::forceScheme('https');
        }

        $this->configureRateLimiting();
    }

    /**
     * Configure rate limiters for the application.
     */
    protected function configureRateLimiting(): void
    {
        // Rate limiter for password reset verification code attempts
        // Limits by email + IP combination to prevent brute-force attacks
        RateLimiter::for('password-reset', function (Request $request) {
            $email = strtolower($request->input('email', ''));
            $ip = $request->ip();
            
            return [
                // 5 attempts per email per minute
                Limit::perMinute(5)->by('email:' . $email)->response(function () {
                    return response()->json([
                        'message' => 'Too many password reset attempts. Please try again later.',
                    ], 429);
                }),
                // 10 attempts per IP per minute (to catch distributed attacks)
                Limit::perMinute(10)->by('ip:' . $ip)->response(function () {
                    return response()->json([
                        'message' => 'Too many requests from this location. Please try again later.',
                    ], 429);
                }),
            ];
        });

        // Rate limiter for forgot password requests
        RateLimiter::for('forgot-password', function (Request $request) {
            $email = strtolower($request->input('email', ''));
            $ip = $request->ip();
            
            return [
                // 3 attempts per email per 5 minutes
                Limit::perMinutes(5, 3)->by('email:' . $email),
                // 10 attempts per IP per 5 minutes
                Limit::perMinutes(5, 10)->by('ip:' . $ip),
            ];
        });
    }
}
