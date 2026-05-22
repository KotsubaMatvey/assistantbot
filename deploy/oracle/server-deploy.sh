#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SECRETS_FILE="${ROOT_DIR}/deploy-secrets.env"

if [ ! -f "${SECRETS_FILE}" ]; then
  echo "Missing ${SECRETS_FILE}. Create it from deploy/oracle/deploy.env.example." >&2
  exit 1
fi

set -a
# shellcheck disable=SC1090
. "${SECRETS_FILE}"
set +a

if [ -z "${BOT_TOKEN:-}" ] || [ -z "${DOMAIN:-}" ] || [ -z "${ADMIN_TELEGRAM_IDS:-}" ]; then
  echo "BOT_TOKEN, DOMAIN and ADMIN_TELEGRAM_IDS are required in deploy-secrets.env." >&2
  exit 1
fi

CITY="${CITY:-Bor}"
TIMEZONE="${TIMEZONE:-Europe/Moscow}"

install_docker() {
  if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
    return
  fi

  sudo apt-get update
  sudo apt-get install -y ca-certificates curl git
  sudo install -m 0755 -d /etc/apt/keyrings
  sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
  sudo chmod a+r /etc/apt/keyrings/docker.asc

  . /etc/os-release
  codename="${UBUNTU_CODENAME:-$VERSION_CODENAME}"
  arch="$(dpkg --print-architecture)"

  sudo tee /etc/apt/sources.list.d/docker.sources >/dev/null <<EOF
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: ${codename}
Components: stable
Architectures: ${arch}
Signed-By: /etc/apt/keyrings/docker.asc
EOF

  sudo apt-get update
  sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
  sudo usermod -aG docker "$USER" || true
}

write_env() {
  cat > "${ROOT_DIR}/.env" <<EOF
BOT_TOKEN=${BOT_TOKEN}
DATABASE_URL=postgresql+asyncpg://postgres:postgres@postgres:5432/pricebot
REDIS_URL=redis://redis:6379/0
ENV=production
CITY=${CITY}
TIMEZONE=${TIMEZONE}
OBSIDIAN_VAULT_PATH=/app/assistantbotmemory
ASSISTANT_ACCESS_MODE=pairing
ASSISTANT_APPROVAL_TTL_MINUTES=30
ASSISTANT_PAIRING_TTL_MINUTES=15
ASSISTANT_CONTEXT_VISIBILITY=allowlist
ASSISTANT_GROUP_TRIGGER_POLICY=mention
ASSISTANT_DEFAULT_MODE=secretary
LLM_ENABLED=false
LLM_CLOUD_CONTEXT_ALLOWED=false
LLM_CONTEXT_MODE=snippets
TG_MINI_APP_URL=https://${DOMAIN}/
MINI_APP_API_ENABLED=true
MINI_APP_API_HOST=0.0.0.0
MINI_APP_API_PORT=8080
MINI_APP_STATIC_DIR=miniapp/dist
BOT_ENABLED_FEATURES=all
BOT_DISABLED_FEATURES=
LIVE_PRICE_REFRESH_ENABLED=false
LIVE_PRICE_REFRESH_LIMIT_PER_QUERY=10
ENABLE_PLAYWRIGHT=false
ADMIN_TELEGRAM_IDS=${ADMIN_TELEGRAM_IDS}
EOF
}

build_miniapp() {
  docker run --rm \
    -v "${ROOT_DIR}/miniapp:/app" \
    -w /app \
    node:22-alpine \
    sh -c "npm ci && npm run build"
}

start_stack() {
  cd "${ROOT_DIR}"
  docker compose up --build -d
}

start_caddy() {
  sed "s/\${DOMAIN}/${DOMAIN}/g" "${ROOT_DIR}/deploy/oracle/Caddyfile.template" > "${ROOT_DIR}/Caddyfile"

  docker rm -f assistantbot-caddy >/dev/null 2>&1 || true
  docker run -d \
    --name assistantbot-caddy \
    --restart unless-stopped \
    --network host \
    -v "${ROOT_DIR}/Caddyfile:/etc/caddy/Caddyfile:ro" \
    -v caddy_data:/data \
    -v caddy_config:/config \
    caddy:2
}

verify() {
  cd "${ROOT_DIR}"
  docker compose ps
  docker compose logs --tail=80 bot
  curl -fsS http://127.0.0.1:8080/api/health
  echo
  curl -fsS "https://${DOMAIN}/api/health"
  echo
}

install_docker
write_env
build_miniapp
start_stack
start_caddy
verify

echo "Deployment complete: https://${DOMAIN}/"
