FROM ghcr.io/astral-sh/uv:0.12.2 AS uv

FROM python:3.11.9-slim-bookworm AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH" \
    DAGSTER_HOME=/opt/dagster/dagster_home

RUN groupadd --system --gid 10001 rider360 \
    && useradd --system --uid 10001 --gid rider360 --home-dir /opt/rider360 rider360 \
    && mkdir -p /app /opt/dagster/dagster_home /opt/dagster/dagster_cloud /tmp/rider360 \
    && chown -R rider360:rider360 /app /opt/dagster /tmp/rider360

COPY --from=uv /uv /uvx /bin/
WORKDIR /app
COPY --chown=rider360:rider360 pyproject.toml uv.lock README.md LICENSE ./
RUN uv sync --frozen --no-dev --no-install-project

COPY --chown=rider360:rider360 . .
RUN uv sync --frozen --no-dev \
    && DBT_PROFILES_DIR=/app uv run --no-sync dbt parse --no-partial-parse \
    && cp deploy/dagster/dagster.yaml /opt/dagster/dagster_home/dagster.yaml \
    && cp deploy/dagster/dagster.cloud.yaml /opt/dagster/dagster_cloud/dagster.yaml

USER rider360
EXPOSE 8080
CMD ["dagster-webserver", "--host", "0.0.0.0", "--port", "8080", "--module-name", "rider360.orchestration.definitions"]
