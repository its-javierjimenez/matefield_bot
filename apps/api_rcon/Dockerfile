FROM python:3.13-slim
# Nota: python 3.14.1 podria no estar publicado estable, usamos 3.14-rc-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Instalar dependencias del workspace
COPY pyproject.toml uv.lock ./
COPY packages packages
RUN uv sync --frozen --no-install-project

# Instalar app
COPY apps/api_rcon apps/api_rcon
RUN uv sync --frozen

WORKDIR /app/apps/api_rcon

# Exponer puerto de la API
EXPOSE 8000

# Entrypoint usando UV
CMD ["uv", "run", "--package", "api_rcon", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
