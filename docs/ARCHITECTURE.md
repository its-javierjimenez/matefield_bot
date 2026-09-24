# Arquitectura del Ecosistema Matefield Bot

El ecosistema de Matefield Bot está compuesto por microservicios desacoplados pero estrechamente integrados. Este diseño permite separar las preocupaciones ("Separation of Concerns") entre la gestión de la lógica de juego, la persistencia en base de datos y la interfaz de usuario en Discord.

## Componentes Principales

### 1. API RCON (`apps/api_rcon`)
Es el núcleo central de operaciones del sistema. Desarrollada con **FastAPI** y **SQLModel** asíncrono sobre PostgreSQL (`asyncpg`).
- **Motor de Sincronización (`sync_engine.py`)**: Monitorea de forma continua el servidor de juego mediante el protocolo RCON para extraer telemetría en tiempo real: estado de la partida, recuento de jugadores, asesinatos y cierres de ronda.
- **API REST (`router.py`)**: Expone endpoints seguros (protegidos por el guard de encabezado `X-API-Key`) para que el bot de Discord gestione membresías, sincronice roles, consulte perfiles y procese sanciones disciplinarias.
- **Cliente RCON (`client.py`)**: Maneja la conexión con el servidor RCON oficial de Wardogs (puerto 7776 por defecto) mediante peticiones HTTP Bearer o sockets directos para ejecutar comandos de servidor.

### 2. Discord Bot (`apps/discord_bot`)
Es la capa de presentación y control para la comunidad y el equipo administrativo. Desarrollada en **Python 3.12+** utilizando **Hikari** y el framework de comandos **Crescent**.
- **Comandos de Entidad Primero (`plugins/`)**: Organizados por entidades de dominio (`account.py`, `admin.py`, `config.py`, `database.py`, `match.py`).
- **Tareas Automatizadas (`tasks.py`)**: 
  - `membership_monitor`: Tarea en segundo plano (cada 60s) que consulta a la API las membresías activas y reconcilia los roles en el servidor de Discord, otorgando o revocando accesos según el estado en la base de datos.
  - `hacker_monitor_task`: Monitorea activamente las "Kills Per Minute" (KPM) de un jugador bajo sospecha, actualizando un panel interactivo en Discord.

### 3. Emulador RCON (`apps/rcon_mock`)
Servidor mock en FastAPI que emula la API RCON de Wardogs. Permite levantar entornos de desarrollo y pruebas completos (`docker-compose.local.yml`) con fidelidad total al comportamiento de producción.

## Flujo de Comunicación y Seguridad

1. La comunicación entre el Bot de Discord y la API RCON se realiza exclusivamente a través de HTTP/REST con el encabezado:
   `X-API-Key: <TOKEN>`
2. El bot de Discord lee este token desde sus variables de entorno e inyecta la cabecera en cada solicitud mediante `ApiClient` (`api_client.py`).
3. El servidor RCON está protegido mediante autenticación `Authorization: Bearer <RCON_PASSWORD>`.

## Esquema de Base de Datos (PostgreSQL 15 + SQLModel)

El sistema utiliza **PostgreSQL 15** administrado mediante migraciones de **Alembic** y el ORM asíncrono **SQLModel**.

### Entidades de Dominio
- **Player**: Identidad central. Vincula el `steam_id` (juego) con el `discord_id` de la comunidad.
- **Membership**: Registra las suscripciones VIP (`VIP_COMUN`, `VIP_EXPRESS`, etc.) con fechas `start_time`, `end_time` y vigencia `is_active`. Incluye el indicador `is_booster` para trazabilidad de donaciones/mejoras de Discord Nitro y vinculación opcional a roles especiales (`special_role_id`). Define el derecho prioritario a slots reservados en el servidor de juego.
- **Role / PlayerRole**: Sistema de roles DDD. Almacena roles de sistema (`SYSTEM`), roles VIP (`VIP`), públicos (`PUBLIC`) y especiales (`SPECIAL`) asociados a IDs de rol de Discord. La jerarquía de administración está unificada bajo **ADMIN / SUPERVISOR**.
- **Match**: Historial de partidas disputadas (ID UUID, mapa, fecha de inicio, fin y equipo vencedor).
- **MatchTeamStats / MatchPlayerStats**: Registro detallado de puntuaciones por equipo y rendimiento individual (kills, deaths, cash) consolidado al finalizar cada partida.
- **PlayerBan**: Registro histórico de baneos coordinados RCON-Discord.
- **BotConfig**: Almacén clave-valor para configuraciones dinámicas (`ADMIN_ROLE_ID`, IDs de canales, etc.).
