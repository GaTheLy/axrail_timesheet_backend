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
     *                  middleware('role:employee'), middleware('role:pm'),
     *                  middleware('role:admin_or_pm')
     *
     * Role hierarchy (userType = user | admin | superadmin;
     *                 role/position = Employee | Tech_Lead | Project_Manager):
     * - 'superadmin'   → only userType 'superadmin'
     * - 'admin'        → userType 'admin' or 'superadmin'
     * - 'employee'     → all authenticated users (any userType)
     * - 'pm'           → userType 'user' with role 'Tech_Lead' or 'Project_Manager'
     * - 'admin_or_pm'  → admin/superadmin OR pm-qualified users
     *
     * @param  string  $requiredRole  The role parameter passed via middleware (e.g., 'admin')
     */
    public function handle(Request $request, Closure $next, string $requiredRole): Response
    {
        $user = $request->session()->get('user', []);
        $userType = $user['userType'] ?? '';

        if (!$this->isAuthorized($userType, $requiredRole, $user)) {
            return redirect('/dashboard')->with('error', 'You do not have permission to access that page.');
        }

        return $next($request);
    }

    /**
     * Determine if the user's type (and role, where applicable) satisfies the required role.
     */
    protected function isAuthorized(string $userType, string $requiredRole, array $user = []): bool
    {
        return match ($requiredRole) {
            'superadmin' => $userType === 'superadmin',
            'admin' => in_array($userType, ['admin', 'superadmin'], true),
            'employee' => in_array($userType, ['user', 'admin', 'superadmin'], true),
            'pm' => $userType === 'user'
                    && in_array($user['role'] ?? '', ['Tech_Lead', 'Project_Manager'], true),
            'admin_or_pm' => in_array($userType, ['admin', 'superadmin'], true)
                    || ($userType === 'user'
                        && in_array($user['role'] ?? '', ['Tech_Lead', 'Project_Manager'], true)),
            default => false,
        };
    }
}
