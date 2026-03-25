<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="csrf-token" content="{{ csrf_token() }}">
    <title>@yield('title', 'TimeFlow')</title>
    <link rel="stylesheet" href="{{ asset('css/app.css') }}">
</head>
<body>
    {{-- Loading spinner overlay for AJAX requests --}}
    <div id="loading-overlay" class="loading-overlay" style="display: none;" aria-hidden="true">
        <div class="loading-spinner">
            <div class="spinner"></div>
            <span class="loading-text">Loading&hellip;</span>
        </div>
    </div>

    <div class="app-layout">
        {{-- Sidebar navigation --}}
        @include('components.sidebar')

        {{-- Main content area --}}
        <main class="main-content" role="main">
            @yield('content')
        </main>
    </div>

    <script src="{{ asset('js/app.js') }}"></script>
    @stack('scripts')
</body>
</html>
