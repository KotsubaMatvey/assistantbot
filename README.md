# Price Lifestyle Bot

Telegram-бот для сравнения публичных цен на продукты в магазинах города Бор,
Нижегородская область.

Пользователь отправляет список товаров, бот обновляет цены по выбранным магазинам,
сравнивает последние сохранённые цены в базе и отвечает:

- где дешевле купить каждый товар;
- где выгоднее купить всю корзину в одном магазине;
- какой вариант дешевле при покупке в разных магазинах;
- какие цены обычные, акционные или по карте.

Важно: бот не гарантирует цену на кассе. Цены берутся с сайтов магазинов и могут отличаться
из-за региона, выбранного магазина, наличия товара, карты лояльности или изменения акции.
В каждом ответе с ценами выводится дисклеймер.

## MVP-магазины

- Smart / Сладкая жизнь — `smart.swnn.ru`
- Магнит — `magnit.ru`
- SPAR / EUROSPAR — `myspar.ru`
- Пятёрочка — `5ka.ru`
- Fix Price — `fix-price.com`

Текущий статус scraper-адаптеров: `partial`.

Причина: сайты могут требовать региональный или магазинный контекст, JavaScript, cookies или
сессию. MVP не обходит CAPTCHA, авторизацию и защиту. Адаптеры используют публичный HTML,
мягкие retries и короткие паузы. Playwright отключён по умолчанию и включается только через
`ENABLE_PLAYWRIGHT=true`.

## Локальный запуск

Требуется Python 3.12.

```bash
python -m pip install -e ".[dev]"
cp .env.example .env
```

Создайте Telegram-бота через BotFather и заполните:

```env
BOT_TOKEN=123456:token
```

Для локальной БД вне Docker измените `DATABASE_URL`, например:

```env
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/pricebot
```

## Docker

```bash
docker compose up --build
```

Compose поднимает:

- `postgres`
- `redis`
- `bot`

Перед запуском bot-сервиса нужен `.env` с `BOT_TOKEN`.

## Миграции

```bash
alembic upgrade head
```

Миграция создаёт таблицы:

- users, user_settings
- stores
- products, store_products
- price_snapshots
- baskets, basket_items
- scrape_runs

## Seed Stores

```bash
python -m app.scripts.seed_stores
```

Команда добавляет 5 магазинов MVP для города `Бор`.

## Scraping

Один магазин:

```bash
python -m app.scripts.scrape_once --store smart --limit 50
```

Все магазины:

```bash
python -m app.scripts.refresh_prices --all
```

Через Makefile:

```bash
make scrape STORE=smart LIMIT=50
```

Scraper сохраняет `StoreProduct` и новый `PriceSnapshot`. История цен не перезаписывается.

## Telegram-команды

- `/start` — приветствие, инструкция, выбор магазинов и карт.
- `/help` — примеры списков.
- `/settings` — магазины, карты лояльности, режим сравнения.
- `/remember <заметка>` — сохранить заметку в Obsidian-память.
- `/memory <запрос>` — найти заметку в Obsidian-памяти.
- `/ask <вопрос>` — ответить на вопрос по сохранённой памяти.
- `/learn_url <ссылка>` — прочитать страницу и сохранить краткую заметку в память.
- `/rss_add <ссылка>` — добавить RSS/Atom-ленту.
- `/rss_digest` — прочитать RSS/Atom-подписки и сохранить дайджест в память.
- `/prices молоко 2.5 1 л; яйца C1 10 шт` — сравнение.
- Обычный текст без команды трактуется как список покупок.

## Obsidian-память

По умолчанию память хранится в папке `assistantbotmemory`. Путь можно изменить:

```env
OBSIDIAN_VAULT_PATH=E:\assistantbot\assistantbotmemory
```

Бот пишет Markdown-файлы в структуру `inbox`, `users/<telegram_id>/notes`,
`users/<telegram_id>/daily`, `users/<telegram_id>/baskets` и `profile.md`.
Заметки классифицируются локальными правилами: факт, предпочтение, задача, ссылка или корзина.
Поиск `/memory` и ответ `/ask` работают локально по словам, синонимам и тегам, без внешних AI API.
Команды `/learn_url` и `/rss_digest` ходят в интернет только по явному запросу пользователя.

Admin-команды доступны только Telegram ID из `ADMIN_TELEGRAM_IDS`:

- `/admin_refresh_prices`
- `/admin_status`
- `/admin_scrape_store <store_slug>`
- `/admin_diag`
- `/admin_backup`
- `/admin_logs`
- `/admin_deploy_check`
- `/admin_scraper_diag <store_slug> [query]`

## Тесты и качество

```bash
make test
make lint
```

Unit-тесты не ходят в интернет. Интеграционные тесты для реальных сайтов должны быть помечены
`@pytest.mark.integration`.

## Как добавить магазин

1. Добавить store в `DEFAULT_STORES`.
2. Создать adapter в `app/scrapers/<store>.py`.
3. Зарегистрировать его в `app/scrapers/registry.py`.
4. Scraper должен возвращать `list[ScrapedProduct]`.
5. Добавить fixture-based contract test без интернета.
6. Описать ограничения сайта в README.

## Ограничения scraping

- CAPTCHA не обходится.
- Авторизация не обходится.
- Приватные API и ключи не используются.
- Перед сравнением бот пробует обновить цены по товарам из пользовательского запроса.
- Соблюдаются короткие timeout, retry с backoff и паузы между seed-запросами.
- Если публичный HTML нестабилен, adapter остаётся `partial`.

## Roadmap

- история цен;
- уведомления о скидках;
- домашние списки покупок;
- избранные товары;
- семейный список;
- сканирование чеков;
- сканирование штрихкодов;
- бюджет на продукты.
