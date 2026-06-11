# Assistant Bot

Telegram second brain assistant with local memory, operator-style commands,
automations, a Telegram Mini App control surface, and optional skills for home,
markets, budget and shopping.

The main product is no longer price comparison. Shopping and price tracking are
secondary skills. The default interaction is:

- write naturally in Telegram chat for freeform conversation when an LLM provider is enabled;
- save facts and perform actions through explicit intent, for example
  `запомни ...`, `добавь задачу ...`, `напомни ...` or `потратил ...`;
- retrieve context through `/agenda`, `/today`, `/tasks`, `/recent`, `/context`,
  `/memory` and `/sources`;
- control the session through `/status`, `/new`, `/compact`, `/mode`, `/trace`
  and `/verbose`;
- open Mini App from the persistent Telegram button above the message field.

## Current UX

Telegram command menu intentionally exposes only:

- `/start`
- `/help`

All other commands are documented inside `/help`. This keeps the chat menu small
while preserving advanced operator commands for manual use.

When `TG_MINI_APP_URL` is configured, the bot sets a persistent Telegram
`web_app` menu button named `Mini App`. The current production URL is:

```text
https://assistantbot-olive.vercel.app/
```

## Core Capabilities

Second brain memory:

- explicit natural-language capture such as `запомни, что ...`;
- `/capture <text>` and `/remember <text>` for explicit capture;
- `/export_memory` sends the user's memory ZIP in Telegram; upload a ZIP with
  caption `/import_memory` to validate it or `/import_memory --apply` to import;
- `/memory <query>`, `/ask <question>`, `/context <topic>` for retrieval;
- `/today`, `/recent`, `/collections`, `/collection`, `/sources`;
- `/memory_tree`, `/memory_rebuild_tree`, `/memory_profile`,
  `/weekly_summary`, `/project_summary <project>`;
- `/source_add`, `/source_list`, `/source_sync`, `/source_delete`;
- spaces, pins, people notes, decisions and reminders;
- local Markdown storage under `OBSIDIAN_VAULT_PATH`;
- local SQLite/FTS indexing plus free semantic-lite memory search.

Operator controls:

- `/status` for current assistant state;
- `/new` for a new logical session;
- `/compact` for session summary;
- `/session_summary` for conversation summary;
- `/mode`, `/trace`, `/verbose`;
- `/assistant_capabilities`, `/assistants`, `/assistant_pick`;
- safe local tools behind explicit commands.

Automation and daily flow:

- `/agenda`, `/tasks`, `/today_tasks`;
- `/job_add`, `/jobs`, `/job_runs`, `/job_delete`;
- `/morning` for agenda, memory, market, pantry, budget and signal briefing;
- `/automations`, `/automation_enable`;
- `/rss_add`, `/rss_digest`, `/learn_url`.

Secondary skills:

- home and pantry: `/pantry`, `/pantry_add`, `/pantry_plan`, `/pantry_deals`;
- budget and receipts: `/receipt`, `/budget`, `/budget_set`, `/budget_plan`;
- family list: `/family_create`, `/family_join`, `/family_add`;
- markets: `/markets`, `/market_brief`;
- shopping and prices: `/prices`, `/last`, `/watch_price`, `/price_alerts`.

## Telegram Mini App

The Mini App lives in `miniapp/` and is a Vite + React + TypeScript frontend.
It is backed by a local API:

- bottom tabs: `Сегодня`, `Память`, `Бюджет`, `Чат`, `Ещё`;
- Today tab shows the week strip, next reminders and tasks with one-tap task
  completion, a unified quick-add (task/note/reminder) and recent notes;
- Memory tab reads real memory health, objects, unified sources and events
  with search and filters;
- Finance tab reads and writes local accounts, expenses, income,
  subscriptions and receipts through a single segmented add form;
- Chat tab is a memory-grounded assistant chat with local history;
- More tab keeps the secondary skills: basket comparison, market quotes and
  operator/service commands.

Mini App API requests verify fresh Telegram `initData` and enforce the bot
allowlist. In local development only, explicitly set
`MINI_APP_DEV_AUTH_ENABLED=true` to allow a loopback dev `user_id` query/header
for preview. API mutation/read routes are rate-limited per Mini App session in
the backend process.

Local Mini App development:

```bash
ENV=local MINI_APP_DEV_AUTH_ENABLED=true TG_MINI_APP_URL=http://127.0.0.1:5173 python -m app.scripts.serve_mini_app_api
cd miniapp
npm install
VITE_MINI_APP_API_BASE_URL=http://127.0.0.1:8080 VITE_MINI_APP_DEV_USER_ID=123 npm run dev
```

Production build:

```bash
npm run build --prefix miniapp
```

Vercel deploy is expected to build `miniapp/` and publish `miniapp/dist`.
Use either a Vercel project with root directory `miniapp`, or the repository
root config in `vercel.json`.

For a self-hosted production deployment, `Caddyfile` serves `miniapp/dist`,
proxies `/api/*` to the bot service, and obtains HTTPS certificates:

```bash
npm run build --prefix miniapp
MINI_APP_DOMAIN=assistant.example.com docker compose --profile production up --build -d
```

Set `TG_MINI_APP_URL=https://assistant.example.com/` for that deployment.

## Local Backend Setup

Requires Python 3.11.

```bash
python -m pip install -e ".[dev]"
cp .env.example .env
```

Create a Telegram bot through BotFather and set:

```env
BOT_TOKEN=123456:token
```

For a local database outside Docker:

```env
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/pricebot
```

Run migrations and seed secondary shopping stores:

```bash
alembic upgrade head
python -m app.scripts.seed_stores
```

Run the bot:

```bash
python -m app.main
```

## Docker

```bash
docker compose up --build
```

Compose starts:

- `postgres`
- `redis`
- `bot`

PostgreSQL, Redis and the direct Mini App API host port bind to `127.0.0.1`
only. `POSTGRES_PASSWORD` and `DATABASE_URL` are required by Compose; replace
the example password before first startup and URL-encode special characters in
`DATABASE_URL`. Publish the Mini App through the HTTPS `gateway` profile
instead of exposing these ports.

The `bot` service is self-contained: it runs `alembic upgrade head`, then
`python -m app.scripts.seed_stores`, then starts polling.

Important: Docker build needs network access to PyPI when dependency layers are
not cached. Runtime can continue from an already built image, but clean rebuilds
need registry access.

## Configuration

Core environment:

```env
BOT_TOKEN=
POSTGRES_PASSWORD=replace-with-a-long-random-password
DATABASE_URL=postgresql+asyncpg://postgres:replace-with-a-long-random-password@postgres:5432/pricebot
REDIS_URL=redis://redis:6379/0
ENV=local
CITY=Бор
TIMEZONE=Europe/Moscow
OBSIDIAN_VAULT_PATH=assistantbotmemory
TG_MINI_APP_URL=https://assistantbot-olive.vercel.app/
MINI_APP_DEV_AUTH_ENABLED=false
MINI_APP_INIT_DATA_MAX_AGE_SECONDS=3600
MINI_APP_RATE_LIMIT_PER_MINUTE=120
MINI_APP_DOMAIN=assistant.example.com
ADMIN_TELEGRAM_IDS=[]
ADMIN_BACKUP_ENABLED=false
ADMIN_BACKUP_INTERVAL_HOURS=24
ADMIN_BACKUP_ENCRYPTION_KEY=
MEDIA_ENABLED=false
MEDIA_API_BASE_URL=https://openrouter.ai/api/v1
MEDIA_API_KEY=
MEDIA_STT_MODEL=openai/whisper-large-v3
MEDIA_VISION_MODEL=
```

Assistant security:

```env
ASSISTANT_ACCESS_MODE=pairing
ASSISTANT_APPROVAL_TTL_MINUTES=30
ASSISTANT_PAIRING_TTL_MINUTES=15
ASSISTANT_CONTEXT_VISIBILITY=allowlist
ASSISTANT_GROUP_TRIGGER_POLICY=mention
ASSISTANT_DEFAULT_MODE=secretary
```

Optional free cloud LLM pool:

```env
LLM_ENABLED=false
LLM_CLOUD_CONTEXT_ALLOWED=false
LLM_CONTEXT_MODE=snippets
LLM_PROVIDER_ORDER=groq,cerebras,openrouter,mistral,github_models,zai,nvidia,llm7,ovh,siliconflow
LLM_GROQ_API_KEY=
LLM_CEREBRAS_API_KEY=
LLM_OPENROUTER_API_KEY=
LLM_MISTRAL_API_KEY=
LLM_GITHUB_MODELS_TOKEN=
LLM_ZAI_API_KEY=
LLM_NVIDIA_API_KEY=
LLM_LLM7_API_KEY=
LLM_OVH_API_KEY=
LLM_SILICONFLOW_API_KEY=
```

When `LLM_ENABLED=true`, ordinary chat messages that are not recognized as
explicit local actions are answered through the first available configured cloud
provider and automatically fall through to the next model/provider on
quota/rate-limit errors. Freeform replies keep a short rolling conversation
history (per user, stored locally, reset with `/new`) so the dialogue stays
coherent. They are not implicitly stored in memory. `/ask` can
also use an LLM for memory-grounded answers, but memory context is not sent to
cloud providers unless `LLM_CLOUD_CONTEXT_ALLOWED=true`; otherwise `/ask` keeps
the existing local rule-based answer. `LLM_CONTEXT_MODE` accepts `none`,
`snippets`, `redacted`, or `full`. For providers not covered by the built-in
presets, set `LLM_PROVIDER_SPECS_JSON` to a JSON list of OpenAI-compatible
endpoints. Built-in `LLM_*_MODEL` values may contain a comma-separated model
fallback list.

Feature flags:

```env
BOT_ENABLED_FEATURES=all
BOT_DISABLED_FEATURES=
```

Known feature names:

- `onboarding`
- `settings`
- `memory`
- `lifestyle`
- `markets`
- `miniapp`
- `shopping`
- `admin`

Example trimmed assistant-only profile:

```env
BOT_ENABLED_FEATURES=onboarding,memory,lifestyle,miniapp
BOT_DISABLED_FEATURES=
```

Shopping speed controls:

```env
LIVE_PRICE_REFRESH_ENABLED=false
LIVE_PRICE_REFRESH_LIMIT_PER_QUERY=10
PRICE_FRESHNESS_HOURS=24
SCRAPE_INTERVAL_HOURS=12
ENABLE_PLAYWRIGHT=false
```

`LIVE_PRICE_REFRESH_ENABLED=false` is the default because second brain responses
should stay fast. Use `/prices` and admin refresh commands when shopping data is
needed.

## Database

Current Alembic head:

```text
0002_bot_sessions
```

Migrations create:

- `users`, `user_settings`
- `stores`
- `products`, `store_products`
- `price_snapshots`
- `baskets`, `basket_items`
- `scrape_runs`
- `bot_sessions`, `bot_messages`

`bot_sessions` and `bot_messages` back interaction logging and logical session
history.

## Memory Storage

By default memory is stored in `assistantbotmemory/`. The bot writes Markdown and
local metadata under:

- `inbox`
- `users/<telegram_id>/notes`
- `users/<telegram_id>/daily`
- `users/<telegram_id>/baskets`
- `profile.md`

Local actions and memory search stay local and rule-based. With `LLM_ENABLED=true`,
freeform chat messages may be sent to the configured cloud LLM provider; memory
snippets are sent only under the separate `LLM_CLOUD_CONTEXT_ALLOWED=true`
setting. Other external network use includes `/learn_url`, `/rss_digest`,
market data and scraping/admin refresh.

## Shopping Skill

Shopping remains available, but it is not the primary product mode.

Supported store seeds:

- Smart / Сладкая жизнь — `smart.swnn.ru`
- Магнит — `magnit.ru`
- SPAR / EUROSPAR — `myspar.ru`
- Пятёрочка — `5ka.ru`
- Fix Price — `fix-price.com`

Scraper adapters are `partial`. The bot does not guarantee checkout prices:
public website data can differ by region, store, loyalty card, availability and
promotion timing.

Manual scraping:

```bash
python -m app.scripts.scrape_once --store smart --limit 50
python -m app.scripts.refresh_prices --all
make scrape STORE=smart LIMIT=50
```

Scrapers do not bypass CAPTCHA, authentication or private APIs.

## Admin Commands

Admin commands require a Telegram ID from `ADMIN_TELEGRAM_IDS`:

- `/admin_status`
- `/admin_diag`
- `/admin_doctor`
- `/admin_secret_scan`
- `/admin_audit`
- `/admin_onboarding`
- `/admin_refresh_prices`
- `/admin_scrape_store <store_slug>`
- `/admin_scraper_diag <store_slug> [query]`
- `/admin_backup`
- `/admin_logs`
- `/admin_deploy_check`
- `/llm_status`
- `/llm_models`
- `/llm_reset [provider]`
- `/llm_test [prompt]`

Set `ASSISTANT_ACCESS_MODE=admin_only` for a private personal deployment. In
that mode only IDs listed in `ADMIN_TELEGRAM_IDS` may use either chat actions
or the Mini App; pairing and the stored allowlist are ignored.

`/admin_backup` creates an archive containing the local memory vault and a
PostgreSQL dump, then sends it to the administrator for secure off-host storage.
Set `ADMIN_BACKUP_ENCRYPTION_KEY` to a Fernet key before enabling scheduled
backups; the produced `.zip.enc` archive cannot be opened without that key.
Restore is a local administrative operation and is dry-run by default:

```bash
python -m app.scripts.restore_backup backups/assistantbot-backup-YYYYMMDD-HHMMSS.zip.enc
python -m app.scripts.restore_backup backups/assistantbot-backup-YYYYMMDD-HHMMSS.zip.enc --apply
```

On apply, the former vault is retained beside the restored one as
`assistantbotmemory.pre-restore-*`. Take a current backup before applying a
restore because `pg_restore` replaces database contents. For a Docker
deployment, stop `bot` before apply and run restore from the host against the
localhost PostgreSQL port; the vault bind-mount must not be replaced from
inside the running container. The host must have `pg_restore` installed.
Set `ADMIN_BACKUP_ENABLED=true` only after defining `ADMIN_TELEGRAM_IDS` and
`ADMIN_BACKUP_ENCRYPTION_KEY`; the scheduler will then send the encrypted full
backup to the listed administrators every `ADMIN_BACKUP_INTERVAL_HOURS`.

For chat-first operation, configure `LLM_ENABLED=true` for freeform dialogue
and use explicit phrases such as `запомни ...` for memory writes. Enable
`MEDIA_ENABLED=true` after configuring a media provider and a vision model.
Voice commands and extracted receipts are shown for confirmation before any
task, reminder, or expense is stored. Daily briefings are configured in chat,
for example: `присылай утреннюю сводку в 8` and
`каждый вечер в 20:30 подводи итоги`.

## Tests And Quality

```bash
python -m pytest
python -m ruff check .
npm run build --prefix miniapp
```

Unit tests should not depend on internet access. Real website tests must be
marked with `@pytest.mark.integration`.

## Deployment Checklist

Backend:

1. Set `.env`.
2. Set `MINI_APP_DOMAIN` and `TG_MINI_APP_URL=https://<domain>/`.
3. Run `docker compose --profile production up --build -d`.
4. Check `curl https://<domain>/api/health` and configure external uptime monitoring for it.
5. Check `docker compose logs --tail=100 bot gateway`.
6. Confirm Alembic head with `docker compose exec -T bot alembic current`.
7. Generate `ADMIN_BACKUP_ENCRYPTION_KEY`, run `/admin_backup`, keep the encrypted archive and key separately off-host, and validate it with the restore CLI.
8. Enable `ADMIN_BACKUP_ENABLED=true` after downloading and validating the manual backup.

Mini App:

1. Build `miniapp/`.
2. Let the production `gateway` serve `miniapp/dist` over HTTPS.
3. Restart bot so `set_chat_menu_button` points Telegram to the current URL.
4. Verify with `Bot.get_chat_menu_button()`.

## Roadmap

- faster response pipeline for memory capture and retrieval;
- richer agenda and task triage;
- better compaction summaries and automatic memory flush;
- optional LLM-backed answers with explicit capability flags;
- shopping skill hardening as a secondary module.
