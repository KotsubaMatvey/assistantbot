PYTHONPATH := price_lifestyle_bot
export PYTHONPATH

install:
	python -m pip install -e ".[dev]"

lint:
	python -m ruff check .
	python -m mypy price_lifestyle_bot/app

test:
	python -m pytest

migrate:
	alembic upgrade head

seed:
	python -m app.scripts.seed_stores

run-bot:
	python -m app.main

scrape:
	python -m app.scripts.scrape_once --store $(STORE) --limit $(LIMIT)

docker-up:
	docker compose up --build

docker-down:
	docker compose down

