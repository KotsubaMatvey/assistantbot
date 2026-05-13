FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/price_lifestyle_bot

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential curl \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
RUN python -c "import tomllib; data=tomllib.load(open('pyproject.toml','rb')); deps=data['build-system']['requires'] + data['project']['dependencies']; print('\n'.join(deps))" > /tmp/requirements.txt \
    && pip install --no-cache-dir -r /tmp/requirements.txt

COPY price_lifestyle_bot ./price_lifestyle_bot
COPY alembic ./alembic
COPY alembic.ini ./alembic.ini

RUN pip install --no-cache-dir --no-build-isolation --no-deps -e .

CMD ["python", "-m", "app.main"]
