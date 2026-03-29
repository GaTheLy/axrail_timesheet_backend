<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Sign In — TimeFlow</title>
    <link rel="stylesheet" href="{{ asset('css/app.css') }}">
    <style>
        *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
            color: #e2e8f0;
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
        }

        .login-container {
            width: 100%;
            max-width: 420px;
            padding: 0 1rem;
        }

        .login-brand {
            text-align: center;
            margin-bottom: 2rem;
        }

        .login-brand .logo {
            display: inline-flex;
            align-items: center;
            gap: 0.5rem;
            font-size: 1.75rem;
            font-weight: 700;
            color: #f8fafc;
            letter-spacing: -0.025em;
        }

        .login-brand .logo .logo-icon {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            width: 40px;
            height: 40px;
            background: #3b82f6;
            border-radius: 10px;
            font-size: 1.25rem;
        }

        .login-brand p {
            color: #94a3b8;
            margin-top: 0.5rem;
            font-size: 0.9rem;
        }

        .login-card {
            background: #1e293b;
            border: 1px solid #334155;
            border-radius: 12px;
            padding: 2rem;
        }

        .login-card h2 {
            font-size: 1.25rem;
            font-weight: 600;
            color: #f1f5f9;
            margin-bottom: 1.5rem;
        }

        .alert {
            padding: 0.75rem 1rem;
            border-radius: 8px;
            font-size: 0.875rem;
            margin-bottom: 1rem;
        }

        .alert-error {
            background: rgba(239, 68, 68, 0.1);
            border: 1px solid rgba(239, 68, 68, 0.3);
            color: #fca5a5;
        }

        .alert-success {
            background: rgba(34, 197, 94, 0.1);
            border: 1px solid rgba(34, 197, 94, 0.3);
            color: #86efac;
        }

        .form-group {
            margin-bottom: 1.25rem;
        }

        .form-group label {
            display: block;
            font-size: 0.875rem;
            font-weight: 500;
            color: #cbd5e1;
            margin-bottom: 0.375rem;
        }

        .form-group input[type="email"],
        .form-group input[type="password"] {
            width: 100%;
            padding: 0.625rem 0.75rem;
            background: #0f172a;
            border: 1px solid #334155;
            border-radius: 8px;
            color: #f1f5f9;
            font-size: 0.9rem;
            transition: border-color 0.2s;
        }

        .form-group input:focus {
            outline: none;
            border-color: #3b82f6;
            box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.15);
        }

        .form-group input::placeholder {
            color: #64748b;
        }

        .form-options {
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 1.5rem;
            font-size: 0.85rem;
        }

        .form-options label {
            display: flex;
            align-items: center;
            gap: 0.5rem;
            color: #94a3b8;
            cursor: pointer;
        }

        .form-options input[type="checkbox"] {
            width: 16px;
            height: 16px;
            accent-color: #3b82f6;
            cursor: pointer;
        }

        .form-options a {
            color: #3b82f6;
            text-decoration: none;
            font-weight: 500;
        }

        .form-options a:hover {
            color: #60a5fa;
            text-decoration: underline;
        }

        .btn-signin {
            width: 100%;
            padding: 0.7rem;
            background: #3b82f6;
            color: #fff;
            border: none;
            border-radius: 8px;
            font-size: 0.95rem;
            font-weight: 600;
            cursor: pointer;
            transition: background 0.2s;
        }

        .btn-signin:hover {
            background: #2563eb;
        }

        .btn-signin:active {
            background: #1d4ed8;
        }

        .login-footer {
            text-align: center;
            margin-top: 2rem;
            font-size: 0.8rem;
            color: #64748b;
        }
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
            <h2>Sign in to your account</h2>

            @if (session('stale_session'))
                <div class="alert alert-error" role="alert">
                    {{ session('stale_session') }}
                </div>
            @endif

            @if ($errors->has('auth'))
                <div class="alert alert-error" role="alert">
                    {{ $errors->first('auth') }}
                </div>
            @endif

            @if (session('status'))
                <div class="alert alert-success" role="status">
                    {{ session('status') }}
                </div>
            @endif

            <form method="POST" action="/login">
                @csrf

                <div class="form-group">
                    <label for="email">Email address</label>
                    <input
                        type="email"
                        id="email"
                        name="email"
                        value="{{ old('email') }}"
                        placeholder="you@company.com"
                        required
                        autocomplete="email"
                    >
                </div>

                <div class="form-group">
                    <label for="password">Password</label>
                    <input
                        type="password"
                        id="password"
                        name="password"
                        placeholder="Enter your password"
                        required
                        autocomplete="current-password"
                    >
                </div>

                <div class="form-options">
                    <label for="remember">
                        <input
                            type="checkbox"
                            id="remember"
                            name="remember"
                            value="1"
                            {{ old('remember') ? 'checked' : '' }}
                        >
                        Remember this device
                    </label>
                    <a href="/forgot-password">Forgot password?</a>
                </div>

                <button type="submit" class="btn-signin">Sign In</button>
            </form>
        </div>

        <footer class="login-footer">
            &copy; 2026 Team Alpha
        </footer>
    </main>
</body>
</html>
