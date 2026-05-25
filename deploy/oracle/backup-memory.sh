#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BACKUP_DIR="${HOME}/assistantbot-backups"
SECRETS_FILE="${ROOT_DIR}/deploy-secrets.env"

if [ -f "${SECRETS_FILE}" ]; then
  set -a
  # shellcheck disable=SC1090
  . "${SECRETS_FILE}"
  set +a
fi

if [ -z "${ADMIN_BACKUP_ENCRYPTION_KEY:-}" ]; then
  echo "ADMIN_BACKUP_ENCRYPTION_KEY is required for encrypted memory snapshots." >&2
  exit 1
fi

mkdir -p "${BACKUP_DIR}"

tar -czf - -C "${ROOT_DIR}" assistantbotmemory | \
  openssl enc -aes-256-cbc -pbkdf2 -salt \
    -pass env:ADMIN_BACKUP_ENCRYPTION_KEY \
    -out "${BACKUP_DIR}/assistantbotmemory-$(date +%F-%H%M%S).tar.gz.enc"

ls -lh "${BACKUP_DIR}" | tail -n 5
