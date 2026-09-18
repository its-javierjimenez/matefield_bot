FROM python:3.13-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Instalar dependencias del workspace
COPY pyproject.toml uv.lock ./
COPY packages packages
COPY apps apps
RUN uv sync --frozen

WORKDIR /app/apps/rcon_mock

# Exponer puerto del mock
EXPOSE 7776

# Entrypoint usando UV
CMD ["uv", "run", "--package", "rcon-mock", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "7776"]
