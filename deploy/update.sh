#!/usr/bin/env bash
# Pull the latest main and rebuild. The database, news cache and certificates live in volumes and survive.
set -euo pipefail
cd "$(dirname "$0")/.."
git pull --ff-only
compose=(docker compose -f docker-compose.yml -f deploy/docker-compose.server.yml --env-file deploy/.env)
if ! docker info >/dev/null 2>&1; then
  compose=(sudo "${compose[@]}")
fi
"${compose[@]}" up -d --build --wait
"${compose[@]}" ps
