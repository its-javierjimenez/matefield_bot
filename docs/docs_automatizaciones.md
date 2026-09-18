# Automatizaciones y Procesos de Wardogs RCON

Este documento describe los procesos automatizados en segundo plano que conectan la Base de Datos PostgreSQL, el Servidor RCON de Wardogs y el Bot de Discord.

## 1. La Base de Datos como Fuente de Verdad

En este sistema, **la Base de Datos (DB) es la única fuente de la verdad**. Cualquier cambio en los permisos, membresías o roles de los jugadores debe registrarse en la Base de Datos para que sea reconocido por las automatizaciones.

- **Tabla `memberships`**: Almacena las compras, donaciones o beneficios otorgados a los jugadores (`steam_id`).
- **Expiración**: Cada membresía tiene una fecha de inicio (`start_time`) y una fecha de fin (`end_time`). Si el `end_time` es `NULL`, la membresía es permanente (ej. Administradores).

## 2. Motor de Sincronización (API RCON)

El "Motor de Sincronización" reside en la API REST y se ejecuta cuando se llama al endpoint `POST /v1/db/sync_memberships`. 

Este proceso realiza las siguientes tareas en secuencia:
1. **Limpieza de Expirados**: Busca en la BD todas las membresías cuyo `end_time` haya pasado y las marca como inactivas (`is_active = False`).
2. **Reconstrucción de RCON**:
   - Obtiene la lista actual de *Reserved Slots* desde el servidor de Wardogs a través del protocolo RCON.
   - Agrega al servidor a todos los `steam_id` que tengan al menos una membresía activa en la BD.
   - **Remueve** del servidor a cualquier `steam_id` que no tenga membresías activas en la BD (incluso si fue agregado manualmente de forma directa en el juego).
3. **Mapeo para Discord**: Retorna la lista de todos los jugadores activos (junto con sus tipos de membresía y IDs de Discord) y el diccionario de configuración de mapeo de roles (`role_maps`).

## 3. Bot de Discord (El Reconciliador)

El Bot de Discord tiene un proceso en segundo plano (un _background task_ llamado `membership_monitor`) que corre **cada 60 segundos**.

### Sincronización de Roles
1. El Bot hace una petición HTTP al Motor de Sincronización de la API.
2. La API se encarga de sincronizar el servidor RCON (ver punto 2) y le devuelve la lista de jugadores activos y el mapa de roles.
3. El Bot itera sobre todos los usuarios enlazados de Discord:
   - Revisa qué membresías activas tienen.
   - Busca en el servidor de Discord y les **asigna** los roles que les corresponden según el mapeo (`ROLE_MAP_*` / `role_maps`).
   - Les **quita** los roles administrados que ya no deberían tener (debido a que su membresía expiró o fue revocada en la BD).

### Whitelist de Protección
Cualquier usuario incluido en `/whitelist` es omitido por el reconciliador, garantizando que el bot nunca le retire roles de Discord por error.

## 4. Otras Automatizaciones

### Match Monitor (Monitor de Partidas)
El Bot consulta el estado del servidor cada 10 segundos. Si detecta que una partida ha finalizado, busca en la tabla de resultados al jugador con más asesinatos (MVP) y automáticamente le regala 1 día de membresía "VIP_MVP_GIFT", insertando el registro en la BD y anunciándolo tanto en el RCON como en Discord.

### VIP Monitor (Mensajes de Bienvenida)
Cada 10 segundos, el Bot revisa la lista de jugadores conectados. Si detecta a un jugador nuevo y este tiene un "Mensaje de Bienvenida" configurado en la BD (beneficio VIP/Admin configurado con `/player welcome_message_set`), el Bot envía ese mensaje en un broadcast general in-game.
