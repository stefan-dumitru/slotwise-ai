#!/bin/sh
set -e
echo "API_BASE=${API_BASE:-http://localhost:8000}" > /usr/share/nginx/html/.env
exec nginx -g 'daemon off;'
