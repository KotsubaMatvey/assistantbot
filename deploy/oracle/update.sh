#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${ROOT_DIR}"

git pull

docker run --rm \
  -v "${ROOT_DIR}/miniapp:/app" \
  -w /app \
  node:22-alpine \
  sh -c "npm ci && npm run build"

docker compose up --build -d
docker compose logs --tail=80 bot
