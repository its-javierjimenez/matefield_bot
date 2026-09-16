# Wardogs Server RCON Automation

Este proyecto es una solución integral para automatizar la gestión y monitoreo de un servidor de juegos a través de RCON. Permite registrar estadísticas de partidas, manejar roles VIP dinámicamente y ofrecer comandos de administración a través de Discord.

## Arquitectura del Proyecto

El sistema está construido con un enfoque de microservicios usando **Docker Compose**, lo que facilita el despliegue tanto en entornos locales (desarrollo) como en producción.

- **`api_rcon`** (FastAPI + SQLModel + AsyncPG): Es el núcleo del sistema. Se encarga de:
  - Comunicarse con el servidor de juegos mediante RCON (`aiohttp`).
  - Polling periódico del estado del servidor para detectar cambios de mapas y resultados de partidas (`sync_engine`).
  - Proveer una API REST para lectura y manipulación de la base de datos (jugadores, roles, membresías, estadísticas).
  - Gestionar las migraciones de base de datos a través de **Alembic**.

- **`discord_bot`** (Hikari + Crescent): Un bot de Discord robusto que interactúa únicamente con la `api_rcon`.
  - Escucha eventos y comandos de los administradores en Discord.
  - Ejecuta automatizaciones programadas (ej. `[Sync]`, `[VIP Monitor]`, `[Match Monitor]`) que orquestan lógica de negocio, reaccionando a los datos recogidos por la API.

- **`postgres-db`** (PostgreSQL 15): Base de datos relacional del proyecto.
- **`rcon-mock`** (FastAPI): Un servidor de pruebas local que simula las respuestas del servidor RCON real, útil para desarrollo sin depender del servidor en vivo.

## Estructura de Directorios

```text
.
├── apps/
│   ├── api_rcon/       # Backend FastAPI y motor de sincronización.
│   ├── discord_bot/    # Bot de Discord (Hikari).
│   └── rcon_mock/      # Servidor mock de RCON para desarrollo.
├── packages/           # Dependencias internas compartidas (ej. esquemas Pydantic).
├── docs/               # Documentación adicional y archivos de referencia.
├── .env.dev            # Variables de entorno para desarrollo.
├── .env.prod           # Variables de entorno para producción.
├── docker-compose.yml       # Orquestación de contenedores (Entorno Local).
└── docker-compose.prod.yml  # Orquestación de contenedores (Producción).
```

## Requisitos Previos

- [Docker](https://www.docker.com/) y Docker Compose.
- [uv](https://github.com/astral-sh/uv) (Opcional, para manejo de dependencias Python locales).
- Python 3.13+ (Si se desea correr fuera de Docker).

## Configuración y Despliegue

### 1. Variables de Entorno
Crea o edita los archivos `.env.dev` (para desarrollo) y `.env.prod` (para producción). Utiliza el archivo `.env.example` como plantilla.

```env
DISCORD_TOKEN=tu_token_de_discord
RCON_URL=http://rcon-mock:7776        # En prod: http://rcon-real:puerto
RCON_PASSWORD=tu_password_rcon
DATABASE_URL=postgresql+asyncpg://postgres:password@postgres-db:5432/wardogs
API_KEY=test-api-key
API_BASE_URL=http://api_rcon:8000
```

### 2. Levantar el Entorno (Local / Desarrollo)
Ejecuta el siguiente comando en la raíz del proyecto para construir y levantar todos los servicios usando el `rcon-mock`:

```bash
docker compose up -d --build
```

Esto levantará los contenedores de `api_rcon`, `discord_bot`, `postgres_db` y `rcon_mock`.
Al iniciar, el contenedor de `api_rcon` ejecutará automáticamente `alembic upgrade head`, garantizando que la base de datos PostgreSQL siempre esté actualizada.

### 3. Levantar el Entorno (Producción)
Para el entorno en vivo (conectado a la base de datos de prod y al servidor RCON real):

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

## Base de Datos y Migraciones (Alembic)

La base de datos utiliza PostgreSQL y se maneja de forma asíncrona (`asyncpg`). Las migraciones del esquema se realizan mediante **Alembic**.

- **Ejecutar migraciones manualmente en local**:
  ```bash
  uv run alembic upgrade head
  ```
- **Crear una nueva migración** (después de cambiar los modelos en `db.py`):
  ```bash
  $env:DATABASE_URL="postgresql+asyncpg://postgres:password@localhost:5432/wardogs"
  $env:PYTHONPATH="apps/api_rcon"
  cd apps/api_rcon
  uv run alembic revision --autogenerate -m "Descripción de la migración"
  ```
  *(Nota: Alembic requiere que el motor se inicialice, por lo que es vital pasar las variables de entorno temporalmente).*

## Desarrollo y Pruebas (Tests)

Las pruebas unitarias y de integración de la API están construidas con `pytest` y utilizan una base de datos en memoria SQLite.

Para correr los tests localmente:
```bash
cd apps/api_rcon
$env:PYTHONPATH="." 
uv run pytest
```

Esto probará los endpoints CRUD y los componentes lógicos del motor de RCON.

## Motor de Sincronización Automática (Polling)
La aplicación incluye un motor en segundo plano (`sync_engine.py`) embebido en FastAPI que:
1. Consulta continuamente (polling) los endpoints RCON.
2. Compara el estado actual (ej. mapa) con el anterior para detectar transiciones (ej. partidas finalizadas).
3. Escribe eventos directamente en la base de datos (PostgreSQL), los cuales luego son leídos por los "Monitores" asíncronos programados en el bot de Discord.
