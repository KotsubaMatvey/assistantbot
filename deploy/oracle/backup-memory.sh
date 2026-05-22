#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BACKUP_DIR="${HOME}/assistantbot-backups"
mkdir -p "${BACKUP_DIR}"

tar -czf "${BACKUP_DIR}/assistantbotmemory-$(date +%F-%H%M%S).tar.gz" \
  -C "${ROOT_DIR}" assistantbotmemory

ls -lh "${BACKUP_DIR}" | tail -n 5
