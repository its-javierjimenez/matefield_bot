FROM python:3.13-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Instalar dependencias del workspace
COPY pyproject.toml uv.lock ./
COPY packages packages
COPY apps apps
RUN uv sync --frozen

WORKDIR /app/apps/discord_bot

# Entrypoint usando UV
CMD ["uv", "run", "--package", "discord_bot", "python", "-m", "src.main"]
