# Assistant Bot

Telegram second brain assistant with local memory, operator-style commands,
automations, a Telegram Mini App control surface, and optional skills for home,
markets, budget and shopping.

The main product is no longer price comparison. Shopping and price tracking are
secondary skills. The default interaction is:

- write a thought, fact, task, decision or link as normal Telegram text;
- store it in local second brain memory;
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

- normal text capture without a command;
- `/capture <text>` and `/remember <text>` for explicit capture;
- `/memory <query>`, `/ask <question>`, `/context <topic>` for retrieval;
- `/today`, `/recent`, `/collections`, `/collection`, `/sources`;
- spaces, pins, people notes, decisions and reminders;
- local Markdown storage under `OBSIDIAN_VAULT_PATH`;
- local SQLite/FTS indexing for memory search.

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
- markets: `/markets`;
- shopping and prices: `/prices`, `/last`, `/watch_price`, `/price_alerts`.

## Telegram Mini App

The Mini App lives in `miniapp/` and is a Vite + React + TypeScript frontend.
It is now assistant-first:

- default tab: `Ассистент`;
- primary actions: `Status`, `Compact`, `New`, `Agenda`, `Today`, `Tasks`,
  `Recent`, `Sources`, `Skills`, `Morning`, `Assistants`;
- memory tab for second brain timeline;
- shopping and markets remain available as secondary tabs.

Mini App sends safe payloads through `Telegram.WebApp.sendData`. The backend
accepts command routing, assistant helper messages and explicit basket comparison
payloads. It does not execute arbitrary user-provided tools from Mini App.

Local Mini App development:

```bash
cd miniapp
npm install
npm run dev
```

Production build:

```bash
npm run build --prefix miniapp
```

Vercel deploy is expected to build `miniapp/` and publish `miniapp/dist`.
Use either a Vercel project with root directory `miniapp`, or the repository
root config in `vercel.json`.

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

The `bot` service is self-contained: it runs `alembic upgrade head`, then
`python -m app.scripts.seed_stores`, then starts polling.

Important: Docker build needs network access to PyPI when dependency layers are
not cached. Runtime can continue from an already built image, but clean rebuilds
need registry access.

## Configuration

Core environment:

```env
BOT_TOKEN=
DATABASE_URL=postgresql+asyncpg://postgres:postgres@postgres:5432/pricebot
REDIS_URL=redis://redis:6379/0
ENV=local
CITY=Бор
TIMEZONE=Europe/Moscow
OBSIDIAN_VAULT_PATH=assistantbotmemory
TG_MINI_APP_URL=https://assistantbot-olive.vercel.app/
ADMIN_TELEGRAM_IDS=[]
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

Memory commands and `/ask` are local and rule-based. External network access is
only used for explicit commands such as `/learn_url`, `/rss_digest`, market data
or scraping/admin refresh.

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
2. Run `docker compose up --build -d`.
3. Check `docker compose logs --tail=100 bot`.
4. Confirm Alembic head with `docker compose exec -T bot alembic current`.

Mini App:

1. Build `miniapp/`.
2. Deploy static output to Vercel.
3. Set `TG_MINI_APP_URL` to the HTTPS deployment URL.
4. Restart bot so `set_chat_menu_button` points Telegram to the current URL.
5. Verify with `Bot.get_chat_menu_button()`.

## Roadmap

- live Mini App state backed by backend API and Telegram initData verification;
- faster response pipeline for memory capture and retrieval;
- richer agenda and task triage;
- better compaction summaries and automatic memory flush;
- optional LLM-backed answers with explicit capability flags;
- production deployment docs for Vercel and Docker;
- shopping skill hardening as a secondary module.
