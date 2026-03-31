#!/bin/bash
cd /var/app/current

# Clear Laravel caches
php artisan optimize:clear

# Truncate large log files (over 50MB)
find /var/app/current/storage/logs -name "*.log" -size +50M -exec truncate -s 0 {} \;

# Rebuild optimized cache
php artisan config:cache
php artisan route:cache
php artisan view:cache
