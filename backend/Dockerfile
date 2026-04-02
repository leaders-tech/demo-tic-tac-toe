# This file builds the production backend image for Docker and Dokploy.
# Edit this file when backend runtime packages, ports, or container startup rules change.
# Copy a stage pattern here when you add another small Python service image.
FROM python:3.14-slim-trixie AS builder

COPY --from=ghcr.io/astral-sh/uv:0.10.4 /uv /uvx /bin/

ENV UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY backend ./backend

FROM python:3.14-slim-trixie AS runtime

ENV PATH="/opt/venv/bin:${PATH}" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN groupadd --gid 10001 app && \
    useradd --uid 10001 --gid 10001 --create-home --shell /usr/sbin/nologin app && \
    mkdir -p /data && \
    chown -R app:app /app /data

COPY --from=builder /opt/venv /opt/venv
COPY --from=builder /app/backend /app/backend

USER app

EXPOSE 8081

CMD ["python", "-m", "backend.main"]
