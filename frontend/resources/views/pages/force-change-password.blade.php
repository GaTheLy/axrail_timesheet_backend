<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Set New Password — TimeFlow</title>
    <link rel="stylesheet" href="{{ asset('css/app.css') }}">
    <style>
        *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

        body {
            font-family: var(--font-family);
            background: var(--color-body-bg);
            color: var(--color-text-primary);
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
        }

        .login-container { width: 100%; max-width: 420px; padding: 0 1rem; }

        .login-brand { text-align: center; margin-bottom: 2rem; }
        .login-brand .logo {
            display: inline-flex; align-items: center; gap: 0.5rem;
            font-size: 1.75rem; font-weight: 700; color: var(--color-text-primary); letter-spacing: -0.025em;
        }
        .login-brand .logo .logo-icon {
            display: inline-flex; align-items: center; justify-content: center;
            width: 40px; height: 40px; background: var(--color-primary); border-radius: 10px; font-size: 1.25rem;
        }
        .login-brand p { color: var(--color-text-secondary); margin-top: 0.5rem; font-size: 0.9rem; }

        .login-card {
            background: var(--color-surface);
            border-radius: var(--radius-lg); box-shadow: var(--shadow-md); padding: 2rem;
        }
        .login-card h2 { font-size: 1.25rem; font-weight: 600; color: var(--color-text-primary); margin-bottom: 0.5rem; }
        .login-card .subtitle { color: var(--color-text-secondary); font-size: 0.875rem; margin-bottom: 1.5rem; }

        .alert { padding: 0.75rem 1rem; border-radius: 8px; font-size: 0.875rem; margin-bottom: 1rem; }
        .alert-error { background: #fef2f2; border: 1px solid #fecaca; color: #991b1b; }

        .form-group { margin-bottom: 1.25rem; }
        .form-group label { display: block; font-size: 0.875rem; font-weight: 500; color: var(--color-text-secondary); margin-bottom: 0.375rem; }
        .form-group input {
            width: 100%; padding: 0.625rem 0.75rem; background: var(--color-surface);
            border: 1px solid var(--color-border); border-radius: 8px; color: var(--color-text-primary); font-size: 0.9rem; transition: border-color 0.2s;
        }
        .form-group input:focus { outline: none; border-color: var(--color-primary); box-shadow: 0 0 0 3px var(--color-primary-light); }
        .form-group input::placeholder { color: #64748b; }

        .btn-primary {
            width: 100%; padding: 0.7rem; background: var(--color-primary); color: #fff;
            border: none; border-radius: 8px; font-size: 0.95rem; font-weight: 600; cursor: pointer; transition: background 0.2s;
        }
        .btn-primary:hover { background: var(--color-primary-hover); }

        .login-footer { text-align: center; margin-top: 2rem; font-size: 0.8rem; color: var(--color-text-secondary); }
    </style>
</head>
<body>
    <main class="login-container" role="main">
        <div class="login-brand">
            <div class="logo">
                <span class="logo-icon" aria-hidden="true">⏱</span>
                TimeFlow
            </div>
            <p>Workforce Portal</p>
        </div>

        <div class="login-card">
            <h2>Set a new password</h2>
            <p class="subtitle">Your account requires a password change before you can continue.</p>

            @if ($errors->has('auth'))
                <div class="alert alert-error" role="alert">
                    {{ $errors->first('auth') }}
                </div>
            @endif

            <form method="POST" action="/force-change-password">
                @csrf

                <div class="form-group">
                    <label for="name">Full name</label>
                    <input
                        type="text"
                        id="name"
                        name="name"
                        placeholder="Enter your full name"
                        required
                        autocomplete="name"
                    >
                </div>

                <div class="form-group">
                    <label for="password">New password</label>
                    <input
                        type="password"
                        id="password"
                        name="password"
                        placeholder="Min 8 characters"
                        required
                        autocomplete="new-password"
                        minlength="8"
                    >
                </div>

                <div class="form-group">
                    <label for="password_confirmation">Confirm new password</label>
                    <input
                        type="password"
                        id="password_confirmation"
                        name="password_confirmation"
                        placeholder="Re-enter your new password"
                        required
                        autocomplete="new-password"
                        minlength="8"
                    >
                </div>

                <button type="submit" class="btn-primary">Set Password & Sign In</button>
            </form>
        </div>

        <footer class="login-footer">
            &copy; 2026 Team Alpha
        </footer>
    </main>
</body>
</html>
