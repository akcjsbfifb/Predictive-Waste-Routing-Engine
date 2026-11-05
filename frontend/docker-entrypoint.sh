#!/bin/sh
set -e
cd /app
if [ ! -x node_modules/.bin/next ] || [ package-lock.json -nt node_modules/.package-lock.json ]; then
  npm ci
fi
exec "$@"
