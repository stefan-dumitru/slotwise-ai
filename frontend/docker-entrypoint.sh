#!/bin/sh
set -e
echo "API_BASE=${API_BASE:-http://localhost:8000}" > /usr/share/nginx/html/.env
export PORT="${PORT:-80}"
envsubst '$PORT' < /etc/nginx/templates/default.conf.template > /etc/nginx/conf.d/default.conf
exec nginx -g 'daemon off;'
