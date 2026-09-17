# Arquitectura del Ecosistema Matefield Bot

El ecosistema de Matefield Bot está compuesto por dos aplicaciones independientes pero fuertemente integradas. Este diseño de microservicios permite separar las preocupaciones ("Separation of Concerns") entre la gestión de la lógica de juego y la interfaz de usuario en Discord.

## Componentes Principales

### 1. API RCON (`apps/api_rcon`)
Es el corazón del sistema. Desarrollada con **FastAPI**, esta aplicación actúa como el puente entre la base de datos central y el servidor de juego.
- **Motor de Sincronización (`sync_engine.py`)**: Un bucle en segundo plano que realiza "polling" constante al servidor de juego mediante RCON para extraer estadísticas en tiempo real, muertes, inicios y fines de partida.
- **API REST (`router.py`)**: Expone endpoints seguros (protegidos por API Key) para que el bot de Discord consulte perfiles, estadísticas, verifique membresías y procese baneos.
- **Gestión de RCON (`client.py`)**: Maneja la conexión directa (Raw Sockets) con el protocolo RCON del servidor de juego para enviar comandos (`AdminKick`, `AdminBan`, `AdminForceRoleChange`, etc.).

### 2. Discord Bot (`apps/discord_bot`)
Es la capa de presentación y control administrativo. Desarrollada en **Python** utilizando **Hikari** y el framework de comandos **Crescent**.
- **Comandos Desacoplados (`plugins/`)**: Organizado en módulos (Account, Admin, Config, Database, Match).
- **Tareas Automatizadas (`tasks.py`)**: 
  - `membership_monitor`: Consulta a la API qué roles VIP tienen los jugadores en la base de datos y sincroniza automáticamente esos roles en los usuarios del servidor de Discord.
  - `hacker_monitor_task`: Monitorea activamente las "Kills Per Minute" (KPM) de un jugador sospechoso y actualiza un panel en vivo en Discord.

## Flujo de Comunicación y Seguridad

La comunicación entre el Bot de Discord y la API RCON se realiza exclusivamente a través de HTTP/REST. 
Para asegurar que nadie externo pueda manipular la base de datos o el servidor de juego, la API requiere un encabezado de autorización:
`X-API-Key: <TOKEN>`

El bot de Discord lee este token de su archivo `.env` e inyecta el encabezado en cada petición HTTP que realiza mediante su cliente interno `ApiClient` (`api_client.py`).

## Esquema de Base de Datos (SQLite + SQLModel)

El sistema utiliza una base de datos relacional (SQLite por defecto en desarrollo) orquestada mediante **SQLModel** (una combinación de SQLAlchemy y Pydantic).

### Entidades Principales
- **Player**: La identidad central. Vincula el `steam_id` (juego) con el `discord_id`.
- **Membership**: Registra las compras o asignaciones VIP (`VIP_COMUN`, `VIP_EXPRESS`). Incluye fechas de expiración.
- **Role / PlayerRole**: Sistema de roles nativo. Administra permisos del sistema (ej: `ADMIN`, `OWNER`) y roles históricos.
- **Match**: Registro de una partida (Mapa, Inicio, Fin, Equipo Ganador).
- **MatchTeamStats / MatchPlayerStats**: Registro de estadísticas de puntuación por equipo y rendimiento individual (Kills, Deaths) generados por el motor de sincronización.
- **PlayerBan**: Registro histórico y activo de baneos, incluyendo el Admin que lo emitió y el motivo.
- **BotConfig**: Almacén clave-valor para configuraciones dinámicas (ej: `ADMIN_ROLE_ID`, mapeos de roles).
