<?php

use App\Http\Controllers\AuthController;
use App\Http\Controllers\DashboardController;
use App\Http\Controllers\HistoryController;
use App\Http\Controllers\SettingsController;
use App\Http\Controllers\ReportsController;
use App\Http\Controllers\TimesheetController;
use App\Http\Controllers\ApprovalsController;
use App\Http\Controllers\UserManagementController;
use Illuminate\Support\Facades\Route;

/*
|--------------------------------------------------------------------------
| Auth Routes (public — no middleware)
|--------------------------------------------------------------------------
*/

Route::get('/login', [AuthController::class, 'showLogin'])->name('login');
Route::post('/login', [AuthController::class, 'login']);
Route::post('/logout', [AuthController::class, 'logout'])->name('logout');
Route::get('/forgot-password', [AuthController::class, 'showForgotPassword'])->name('password.request');
Route::post('/forgot-password', [AuthController::class, 'forgotPassword'])->middleware('throttle:forgot-password')->name('password.email');
Route::get('/reset-password', [AuthController::class, 'showResetPassword'])->name('password.reset');
Route::post('/reset-password', [AuthController::class, 'resetPassword'])->middleware('throttle:password-reset')->name('password.update');
Route::get('/force-change-password', [AuthController::class, 'showForceChangePassword'])->name('password.force');
Route::post('/force-change-password', [AuthController::class, 'forceChangePassword'])->name('password.force.update');

/*
|--------------------------------------------------------------------------
| Redirect root to dashboard
|--------------------------------------------------------------------------
*/

Route::get('/', function () {
    return redirect('/dashboard');
});

/*
|--------------------------------------------------------------------------
| Authenticated Routes (protected by CognitoAuth middleware)
|--------------------------------------------------------------------------
*/

Route::middleware('cognito.auth')->group(function () {
    Route::get('/dashboard', [DashboardController::class, 'index'])->name('dashboard');

    // Timesheet routes
    Route::get('/timesheet', [TimesheetController::class, 'index'])->name('timesheet');
    Route::get('/timesheet/submissions/{submissionId}', [TimesheetController::class, 'showSubmission'])->name('timesheet.submission');
    Route::post('/timesheet/entry', [TimesheetController::class, 'storeEntry'])->name('timesheet.store');
    Route::put('/timesheet/entry/{entryId}', [TimesheetController::class, 'updateEntry'])->name('timesheet.update');
    Route::delete('/timesheet/entry/{entryId}', [TimesheetController::class, 'destroyEntry'])->name('timesheet.destroy');
    Route::get('/timesheet/projects', [TimesheetController::class, 'listProjects'])->name('timesheet.projects');

    // History routes
    Route::get('/timesheet/history', [HistoryController::class, 'index'])->name('history');
    Route::get('/timesheet/history/filter', [HistoryController::class, 'filter'])->name('history.filter');

    // Settings routes
    Route::get('/settings', [SettingsController::class, 'index'])->name('settings');
    // Avatar upload disabled for security (CWE-434 - Unrestricted File Upload)
    Route::post('/settings/password', [SettingsController::class, 'changePassword'])->name('settings.password');

    // Reports (accessible by PM roles and admin/superadmin)
    Route::middleware('role:admin_or_pm')->group(function () {
        Route::get('/reports/project-summary', [ReportsController::class, 'projectSummary'])->name('reports.project-summary');
        Route::get('/reports/submission-summary', [ReportsController::class, 'submissionSummary'])->name('reports.submission-summary');
        Route::get('/reports/project-summary/export', [ReportsController::class, 'exportProjectPdf'])->name('reports.project-summary.export');
        Route::get('/reports/submission-summary/export', [ReportsController::class, 'exportSubmissionPdf'])->name('reports.submission-summary.export');
    });

    // Admin routes (admin/superadmin only)
    Route::middleware('role:admin')->group(function () {
        Route::get('/admin/users', [UserManagementController::class, 'index'])->name('admin.users');
        Route::post('/admin/users', [UserManagementController::class, 'store'])->name('admin.users.store');
        Route::put('/admin/users/{userId}', [UserManagementController::class, 'update'])->name('admin.users.update');
        Route::delete('/admin/users/{userId}', [UserManagementController::class, 'destroy'])->name('admin.users.destroy');
        Route::post('/admin/users/{userId}/approve', [UserManagementController::class, 'approve'])->name('admin.users.approve');
        Route::post('/admin/users/{userId}/reject', [UserManagementController::class, 'reject'])->name('admin.users.reject');
        Route::post('/admin/users/{userId}/activate', [UserManagementController::class, 'activate'])->name('admin.users.activate');
        Route::post('/admin/users/{userId}/deactivate', [UserManagementController::class, 'deactivate'])->name('admin.users.deactivate');
        Route::get('/admin/departments', [\App\Http\Controllers\DepartmentController::class, 'index'])->name('admin.departments');
        Route::post('/admin/departments', [\App\Http\Controllers\DepartmentController::class, 'store'])->name('admin.departments.store');
        Route::put('/admin/departments/{id}', [\App\Http\Controllers\DepartmentController::class, 'update'])->name('admin.departments.update');
        Route::delete('/admin/departments/{id}', [\App\Http\Controllers\DepartmentController::class, 'destroy'])->name('admin.departments.destroy');
        Route::post('/admin/departments/{id}/approve', [\App\Http\Controllers\DepartmentController::class, 'approve'])->name('admin.departments.approve');
        Route::post('/admin/departments/{id}/reject', [\App\Http\Controllers\DepartmentController::class, 'reject'])->name('admin.departments.reject');
        Route::get('/admin/positions', [\App\Http\Controllers\PositionController::class, 'index'])->name('admin.positions');
        Route::post('/admin/positions', [\App\Http\Controllers\PositionController::class, 'store'])->name('admin.positions.store');
        Route::put('/admin/positions/{id}', [\App\Http\Controllers\PositionController::class, 'update'])->name('admin.positions.update');
        Route::delete('/admin/positions/{id}', [\App\Http\Controllers\PositionController::class, 'destroy'])->name('admin.positions.destroy');
        Route::post('/admin/positions/{id}/approve', [\App\Http\Controllers\PositionController::class, 'approve'])->name('admin.positions.approve');
        Route::post('/admin/positions/{id}/reject', [\App\Http\Controllers\PositionController::class, 'reject'])->name('admin.positions.reject');
        Route::get('/admin/projects', [\App\Http\Controllers\ProjectController::class, 'index'])->name('admin.projects');
        Route::post('/admin/projects', [\App\Http\Controllers\ProjectController::class, 'store'])->name('admin.projects.store');
        Route::put('/admin/projects/{id}', [\App\Http\Controllers\ProjectController::class, 'update'])->name('admin.projects.update');
        Route::delete('/admin/projects/{id}', [\App\Http\Controllers\ProjectController::class, 'destroy'])->name('admin.projects.destroy');

        // Approvals routes (superadmin guard enforced in controller)
        Route::get('/admin/approvals', [ApprovalsController::class, 'index'])->name('admin.approvals');
        Route::post('/admin/approvals/{type}/{id}/approve', [ApprovalsController::class, 'approve'])->name('admin.approvals.approve');
        Route::post('/admin/approvals/{type}/{id}/reject', [ApprovalsController::class, 'reject'])->name('admin.approvals.reject');
    });
});
