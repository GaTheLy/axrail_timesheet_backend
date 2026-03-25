<?php

use App\Http\Controllers\AuthController;
use App\Http\Controllers\DashboardController;
use App\Http\Controllers\HistoryController;
use App\Http\Controllers\SettingsController;
use App\Http\Controllers\TimesheetController;
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
Route::post('/forgot-password', [AuthController::class, 'forgotPassword'])->name('password.email');
Route::get('/reset-password', [AuthController::class, 'showResetPassword'])->name('password.reset');
Route::post('/reset-password', [AuthController::class, 'resetPassword'])->name('password.update');

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
    Route::post('/timesheet/entry', [TimesheetController::class, 'storeEntry'])->name('timesheet.store');
    Route::put('/timesheet/entry/{entryId}', [TimesheetController::class, 'updateEntry'])->name('timesheet.update');
    Route::delete('/timesheet/entry/{entryId}', [TimesheetController::class, 'destroyEntry'])->name('timesheet.destroy');
    Route::get('/timesheet/projects', [TimesheetController::class, 'listProjects'])->name('timesheet.projects');

    // History routes
    Route::get('/timesheet/history', [HistoryController::class, 'index'])->name('history');
    Route::get('/timesheet/history/filter', [HistoryController::class, 'filter'])->name('history.filter');

    // Settings routes
    Route::get('/settings', [SettingsController::class, 'index'])->name('settings');
    Route::post('/settings/avatar', [SettingsController::class, 'uploadAvatar'])->name('settings.avatar');
    Route::post('/settings/password', [SettingsController::class, 'changePassword'])->name('settings.password');
});
