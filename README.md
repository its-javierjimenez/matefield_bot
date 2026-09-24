# Wardogs Server RCON Automation

Este proyecto es una solución integral para automatizar la gestión y monitoreo de un servidor de juegos a través de RCON. Permite registrar estadísticas de partidas, manejar roles VIP dinámicamente y ofrecer comandos de administración a través de Discord.

## Arquitectura del Proyecto

El sistema está construido con un enfoque de microservicios usando **Docker Compose**, lo que facilita el despliegue tanto en entornos locales (desarrollo) como en producción.

- **`api_rcon`** (FastAPI + SQLModel + AsyncPG): Es el núcleo del sistema. Se encarga de:
  - Comunicarse con uno o múltiples servidores de juego mediante RCON (`aiohttp`).
  - Polling periódico del estado del servidor para detectar cambios de mapas y resultados de partidas (`sync_engine`).
  - Proveer una API REST modularizada (`/api/v1`) para lectura y manipulación de la base de datos (jugadores, roles, membresías, estadísticas).
  - Gestionar pasarela de pagos y suscripciones vía **Tebex Webhooks** (`/api/v1/webhooks/tebex`).
  - Gestionar las migraciones de base de datos a través de **Alembic**.

- **`discord_bot`** (Hikari + Crescent): Un bot de Discord robusto que interactúa únicamente con la `api_rcon`.
  - Escucha eventos y comandos de los administradores en Discord.
  - Ejecuta automatizaciones programadas (ej. `[VIP Monitor]`, `[Match Monitor]`, alineación de roles DDD y desbaneos automáticos).

- **`postgres-db`** (PostgreSQL 15): Base de datos relacional del proyecto.
- **`rcon-mock`** (FastAPI): Un servidor de pruebas local que simula las respuestas del servidor RCON real, útil para desarrollo sin depender del servidor en vivo.

## Estructura de Directorios

```text
.
├── apps/
│   ├── api_rcon/       # Backend FastAPI, motor de sincronización y webhooks Tebex.
│   ├── discord_bot/    # Bot de Discord (Hikari + Crescent).
│   └── rcon_mock/      # Servidor mock de RCON para desarrollo.
├── packages/           # Dependencias internas compartidas (wardogs_schemas).
├── docs/               # Documentación técnica, manual de comandos y planes de migración.
├── backups/            # Backups de base de datos en SQL y CSV (ignorado por Git).
├── .env.local          # Variables de entorno para pruebas locales en Docker.
├── .env.dev            # Variables de entorno para servidor de desarrollo.
├── .env.prod           # Variables de entorno para producción.
├── docker-compose.local.yml # Orquestación local (con DB y mock RCON).
├── docker-compose.dev.yml   # Orquestación de desarrollo.
└── docker-compose.prod.yml  # Orquestación de producción.
```

## Requisitos Previos

- [Docker](https://www.docker.com/) y Docker Compose.
- [uv](https://github.com/astral-sh/uv) (Gestor de paquetes y dependencias Python ultrarrápido).
- Python 3.13+ (Si se desea correr fuera de Docker).

## Configuración y Despliegue

### 1. Variables de Entorno
Crea o edita los archivos `.env.local`, `.env.dev` o `.env.prod`. Utiliza `.env.example` como plantilla base.

```env
DISCORD_TOKEN=tu_token_de_discord
RCON_URL=http://rcon-mock:7776        # En prod: http://rcon-real:puerto
RCON_PASSWORD=tu_password_rcon
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/dbname
API_KEY=tu_api_key_secreta
API_BASE_URL=http://api_rcon:8000
STEAM_WEB_API_KEY=tu_steam_api_key
TEBEX_WEBHOOK_SECRET=tu_tebex_secret
TEBEX_API_KEY=tu_tebex_key
```

### 2. Levantar el Entorno Local
Ejecuta el siguiente comando en la raíz del proyecto para construir y levantar todos los servicios con base de datos local y mock RCON:

```bash
docker compose -f docker-compose.local.yml up -d --build
```

### 3. Levantar el Entorno de Producción
Para el entorno en vivo (conectado a la base de datos de producción y servidor RCON real):

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

## Base de Datos y Migraciones (Alembic)

La base de datos utiliza PostgreSQL y se maneja de forma asíncrona (`asyncpg`). Las migraciones del esquema se realizan mediante **Alembic**.

- **Ejecutar migraciones en local/contenedor**:
  ```bash
  uv run alembic upgrade head
  ```
- **Verificar que no haya discrepancias de esquema**:
  ```bash
  uv run alembic check
  ```

## Pruebas Automatizadas (Tests)

Todas las suites de tests de la API y del bot de Discord se ejecutan en conjunto desde la raíz:
```bash
uv run pytest
```

Esto ejecuta las 54 pruebas unitarias e integrales (CRUD, roles de dominio DDD, RCON INI, Tebex Webhooks, comandos de Discord y clientes HTTP).

## Motor de Sincronización Automática (Polling)
La aplicación incluye un motor en segundo plano (`sync_engine.py`) embebido en FastAPI que:
1. Consulta continuamente (polling) los endpoints RCON.
2. Compara el estado actual (ej. mapa) con el anterior para detectar transiciones (ej. partidas finalizadas).
3. Escribe eventos directamente en la base de datos (PostgreSQL), los cuales luego son leídos por los "Monitores" asíncronos programados en el bot de Discord.
