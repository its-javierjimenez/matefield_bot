# Membresías y Roles de Sistema

El sistema maneja los privilegios de los usuarios utilizando el principio de **Separation of Concerns** (Separación de Responsabilidades). Existen dos conceptos clave que no deben mezclarse: las Membresías (beneficios en el juego) y los Roles de Sistema (permisos de administración).

## 1. Membresías VIP (Beneficios en Juego)

Las membresías otorgan beneficios físicos dentro del servidor de juego, primordialmente los **Reserved Slots** (saltarse la cola de conexión).

- **Tipos de Membresía**: Definidas libremente por los administradores (ej: `VIP_COMUN`, `VIP_EXPRESS`, `VIP_BOOST_COM`).
- **Tabla en BD**: `memberships`. Tienen una fecha de inicio (`start_time`), una de fin (`end_time`) y un flag booleano de actividad (`is_active`).
- **Sincronización RCON**: 
  - La API de RCON posee un endpoint `/db/rcon_sync_status`.
  - Este endpoint lee **únicamente** los `steam_id` que tienen `is_active == True` y los sincroniza contra los Reserved Slots nativos del servidor de juego.
  - No importa si el jugador es Admin o Dueño; si no tiene una membresía VIP activa, no ocupará un slot reservado. (Si un admin requiere saltar la cola, se le otorga una membresía VIP permanente).

## 2. Roles de Sistema (Permisos de Administración)

Los roles de sistema determinan la jerarquía de un usuario dentro del bot y la base de datos, otorgándoles permisos para ejecutar comandos administrativos.

- **Nativos y Desacoplados**: Se almacenan en la tabla `roles` y se asignan a los jugadores mediante la tabla pivote `player_roles`.
- **Identificadores Literales vs Discord IDs**:
  - Originalmente, los roles se mapeaban usando exclusivamente el ID numérico del rol de Discord (ej: `1546690312762564648`).
  - Para evitar acoplamientos estrictos con Discord, la API es capaz de resolver el string `ADMIN` u `OWNER` leyendo la tabla de configuraciones (`BotConfig`).
  - Cuando un Admin de Discord ejecuta comandos, la API verifica si su ID de Rol coincide con la clave `ADMIN_ROLE_ID` de la base de datos. De ser así, el bot lo trata nativamente como un administrador.

## 3. Sincronización Bidireccional de Discord

El ecosistema mantiene los roles de Discord de los usuarios sincronizados de forma autónoma con su estado en la base de datos.

### Tarea de Monitoreo (`membership_monitor`)
1. El bot de Discord hace una petición HTTP a `/db/sync_memberships` cada 60 segundos.
2. La API evalúa qué membresías VIP acaban de expirar (basado en `end_time` vs la hora actual UTC). A estas se les marca `is_active = False`.
3. La API retorna un JSON masivo con los `discord_id` y las membresías / roles activos de todos los usuarios vinculados.
4. El bot de Discord lee sus configuraciones internas de "Mapeo de Roles" (ej: `ROLE_MAP_VIP_COMUN = 1234567`).
5. Compara los roles mapeados que el usuario *debería* tener según la base de datos, contra los roles que el usuario *realmente* tiene en el servidor de Discord.
6. Si faltan roles, se los otorga. Si tiene roles expirados/revocados, se los quita automáticamente.

### Whitelisting
Para evitar que el bot elimine roles a usuarios especiales (ej: bots u otros admins), existe un sistema de Whitelist (`SYNC_WHITELIST` en `BotConfig`). Cualquier ID de Discord en esta lista será totalmente ignorado por el ciclo de sincronización de roles (ni se le añaden ni se le quitan roles de Discord).
