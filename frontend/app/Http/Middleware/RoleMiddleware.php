<?php

namespace App\Http\Middleware;

use Closure;
use Illuminate\Http\Request;
use Symfony\Component\HttpFoundation\Response;

class RoleMiddleware
{
    /**
     * Handle an incoming request.
     *
     * Checks the authenticated user's role (from session) against the required
     * role parameter. Redirects unauthorized users to the dashboard with an
     * error flash message.
     *
     * Usage in routes: middleware('role:admin'), middleware('role:superadmin'),
     *                  middleware('role:employee')
     *
     * Role hierarchy:
     * - 'superadmin' → only userType 'superadmin'
     * - 'admin'      → userType 'admin' or 'superadmin'
     * - 'employee'   → all authenticated users (any userType)
     *
     * @param  string  $requiredRole  The role parameter passed via middleware (e.g., 'admin')
     */
    public function handle(Request $request, Closure $next, string $requiredRole): Response
    {
        $user = $request->session()->get('user', []);
        $userType = $user['userType'] ?? '';

        if (!$this->isAuthorized($userType, $requiredRole)) {
            return redirect('/dashboard')->with('error', 'You do not have permission to access that page.');
        }

        return $next($request);
    }

    /**
     * Determine if the user's type satisfies the required role.
     */
    protected function isAuthorized(string $userType, string $requiredRole): bool
    {
        return match ($requiredRole) {
            'superadmin' => $userType === 'superadmin',
            'admin' => in_array($userType, ['admin', 'superadmin'], true),
            'employee' => in_array($userType, ['user', 'admin', 'superadmin'], true),
            default => false,
        };
    }
}
