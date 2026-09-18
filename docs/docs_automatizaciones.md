# Automatizaciones y Procesos de Wardogs RCON

Este documento describe la arquitectura y los procesos automatizados que conectan la Base de Datos, el Servidor RCON de Wardogs y el Bot de Discord.

## 1. La Base de Datos como Fuente de Verdad

En este sistema, **la Base de Datos (DB) es la única fuente de la verdad**. Cualquier cambio en los permisos, membresías o roles de los jugadores debe registrarse en la Base de Datos para que sea reconocido por las automatizaciones.

- **Tabla `memberships`**: Almacena las compras, donaciones o beneficios otorgados a los jugadores (`steam_id`). 
- **Expiración**: Cada membresía tiene una fecha de inicio (`start_date`) y una fecha de fin (`end_date`). Si el `end_date` es `NULL`, la membresía es permanente (ej. Administradores).

## 2. Motor de Sincronización (API RCON)

El "Motor de Sincronización" reside en la API REST y se ejecuta cuando se llama al endpoint `POST /v1/db/sync_memberships`. 

Este proceso realiza las siguientes tareas en secuencia:
1. **Limpieza de Expirados**: Busca en la BD todas las membresías cuyo `end_date` haya pasado y las marca como inactivas (`is_active = False`).
2. **Reconstrucción de RCON**:
   - Obtiene la lista actual de *Reserved Slots* desde el servidor de Wardogs a través del protocolo RCON.
   - Agrega al servidor a todos los `steam_id` que tengan al menos una membresía activa en la BD.
   - **Remueve** del servidor a cualquier `steam_id` que no tenga membresías activas en la BD (incluso si fue agregado manualmente por un administrador directamente en el juego).
3. **Mapeo para Discord**: Retorna la lista de todos los jugadores activos (junto con sus tipos de membresía y IDs de Discord) y el diccionario de configuración de mapeo de roles (`ROLE_MAP_*`).

## 3. Bot de Discord (El Ejecutor)

El Bot de Discord tiene un proceso en segundo plano (un _background task_ llamado `membership_monitor`) que corre **cada 1 minuto**.

### Sincronización de Roles
1. El Bot hace una petición HTTP al Motor de Sincronización de la API.
2. La API se encarga de sincronizar el servidor RCON (ver punto 2) y le devuelve la lista de jugadores activos y el mapa de roles.
3. El Bot itera sobre todos los usuarios enlazados de Discord:
   - Revisa qué membresías activas tienen.
   - Busca en el servidor de Discord y les **asigna** los roles que les corresponden según el mapeo (`ROLE_MAP_*`).
   - Les **quita** los roles administrados que ya no deberían tener (debido a que su membresía expiró o fue revocada en la BD).

### Comandos de Configuración
Para que el Bot sepa qué rol dar para cada membresía de la BD, se utiliza el comando:
- `/map_membership_role <tipo_bd> <rol_discord>`
- Ejemplo: `/map_membership_role VIP_EXPRESS @VIP Express`

## 4. Otras Automatizaciones

### Match Monitor (Monitor de Partidas)
El Bot consulta el estado del servidor cada 10 segundos. Si detecta que una partida ha finalizado, busca en la tabla de resultados al jugador con más asesinatos (Kills) y automáticamente le regala 1 día de membresía "VIP_MVP_GIFT", insertando el registro en la BD y anunciándolo tanto en el RCON como en Discord.

### VIP Monitor
Cada 10 segundos, el Bot revisa la lista de jugadores conectados. Si detecta a un jugador nuevo y este tiene un "Mensaje de Bienvenida" configurado en la BD (beneficio VIP/Admin), el Bot envía ese mensaje en un "Broadcast" general en el juego.

## 5. Modo de Juego 50v50 y Auto-Teambalancing

El sistema cuenta con un motor dedicado (`mode_50v50_loop` en `sync_engine.py`) para convertir la experiencia tripartita estándar (33v33v33) en un enfrentamiento bipartito 50v50: **Valkyra (Rojo)** vs **Manticore (Verde)**, neutralizando la facción **Lonestar (Azul)**.

### A. Integración con RCON ServerSettings (`/v1/config`)
El juego bloquea por defecto unirse a equipos con exceso de jugadores mediante `bLockOverpopulatedTeamsConfig=true` en `ServerSettings.ini` (`[/Script/WDGame.WDGameStateSession]`).
- **Al activar 50v50**: El bot edita remotamente el archivo de configuración del servidor RCON fijando `bLockOverpopulatedTeamsConfig=false`. Esto permite que los equipos crezcan hasta 50+ jugadores sin que el motor de juego rechace las uniones ni las transferencias.
- **Al desactivar 50v50**: El bot restaura en RCON `bLockOverpopulatedTeamsConfig=true` y `OverpopulatedTeamThresholdConfig=1`.

### B. Ciclo de Vida Diferido (`[NEXT MATCH]`)
Los cambios en `ServerSettings.ini` solo son procesados por el servidor de juego al comenzar una nueva partida o tras un reinicio del servidor (`[NEXT MATCH]`). Por ello, el bot implementa un ciclo de vida de 4 estados en la tabla `bot_config` (`MODE_50V50_STATE`):
1. `pending_enable`: El admin activa el modo. El RCON ya queda configurado con team balancing desactivado. La automatización espera al siguiente cambio de mapa/reinicio para arrancar.
2. `active`: La nueva partida inició. El motor de balanceo del bot está activamente balanceando jugadores cada 6 segundos.
3. `pending_disable`: El admin desactiva el modo mientras hay una partida 50v50 en curso. RCON se restaura a `true`. Para no romper la partida a mitad de juego, la automatización del bot sigue activa hasta que concluya el round.
4. `inactive`: Modo completamente apagado. Se entra aquí automáticamente al iniciar el siguiente match tras `pending_disable`, o de forma inmediata si se cancela mientras estaba en `pending_enable`.

### C. Algoritmo de Balanceo y Sellado Estilo ARMA (cada 6 segundos)
1. **Detección Dinámica de Facción**: Inspecciona `status.factionScores` en cada ciclo para identificar los nombres exactos en vivo (`Valkyra`, `Manticore`, `Lonestar`).
2. **Sellado de Equipos Estilo ARMA (Prohibición de Cambio Voluntario)**:
   - Los equipos quedan sellados durante toda la partida. Ningún jugador tiene permitido cambiarse de bando a voluntad.
   - Si un jugador intenta cambiarse manualmente mediante el menú del juego, el bot detecta de inmediato la discrepancia entre su equipo asignado (`assigned_faction`) y su nueva facción.
   - **Reversión Inmediata**: El bot ejecuta `switch_faction` revirtiendo al jugador a su equipo asignado y le envía un whisper directo:
     > *"Cambio de equipo no permitido durante la partida."*
3. **Paso 1 - Eliminación y Asimilación de Lonestar (Azul)**:
   - Todos los jugadores en Azul son transferidos inmediatamente al equipo con menor población entre Rojo y Verde.
   - **Whisper de Asignación**: Se le envía un mensaje privado por RCON informándole:
     > *"Se te ha asignado al equipo {target_faction}."*
   - **Tratamiento como Originales**: Quedan registrados como miembros oficiales de esa facción. Al entrar en combate y ganar dinero/bajas, adquieren exactamente la misma inmunidad que un veterano original. Si intentan cambiarse al otro equipo, el sellado ARMA los bloquea y revierte.
4. **Paso 2 - Auto-Teambalancing Rojo vs Verde**: Como el balanceo interno del juego está desactivado, si la diferencia poblacional entre Rojo y Verde es $\ge 2$:
   - Se calculan $\lfloor\text{diferencia}/2\rfloor$ jugadores a transferir del equipo mayoritario al minoritario.
   - **Regla de Inmunidad Absoluta para Combatientes y Veteranos**:
     - Todo jugador que ya haya combatido (`cash > 0` o `kills + deaths > 0`) es **100% INMUNE** a ser forzado al equipo rival si otros abandonan la partida.
     - Si el equipo mayoritario tiene 50 jugadores y todos son veteranos con combate activo, **NO SE MUEVE A NADIE**. El desbalance se resuelve pacíficamente conforme ingresen nuevos jugadores al servidor.
   - **Únicos Candidatos Elegibles para Balancear**:
     - **Recién Ingresados**: Quienes acaban de conectar/spawnear en base y tienen **\$0 cash y 0 K/D** (aún no han pisado la zona de combate, por lo que no pierden progreso alguno). Se ordenan por tiempo de llegada más reciente.
   - **Whisper de Balanceo**: Al mover a un recién ingresado por desbalance, el bot le notifica:
     > *"Se te ha asignado al equipo {target_faction} para balancear la partida."*
   - **Protecciones Incondicionales**:
     - Nunca se tocan ni se envían mensajes a jugadores en facción `White` o `None` (espectadores o en pantalla de carga).
     - Cooldown estricto de 60 segundos por jugador tras una transferencia para evitar oscilaciones (*ping-pong*).
     - Umbral $\Delta < 2$: No se mueve a nadie en diferencias de 1 jugador (ej: 50 vs 49).

### D. Resiliencia de Estadísticas ante Cambios de Equipo
El motor de sincronización (`poll_rcon` en `sync_engine.py`) asegura que las estadísticas de partida nunca se corrompan ni se pierdan al ser transferido o cambiar de equipo:
- **Reseteo por Servidor de Juego**: Si el servidor de juego reinicia `kills` o `deaths` a 0 al cambiar de facción, el motor detecta la caída (`raw_kills < last_raw_kills`), acumula la diferencia en un offset en memoria y sigue sumando las nuevas bajas.
- **Persistencia sin Duplicación**: Si el servidor de juego preserva los contadores, el motor actualiza los números directamente sin duplicar estadísticas.
- **Preservación de Dinero (`cash_earned`)**: Registra la marca máxima histórica (*high watermark*) durante la partida, impidiendo que el valor disminuya al comprar tanques, armas o cambiar de equipo.

