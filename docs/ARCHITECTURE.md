# Matefield Bot — Arquitectura y Reglas de Diseño

## Principios de Diseño de Comandos Discord

Los comandos de Discord deben tratarse como endpoints REST. Un recurso, un comando.

### Regla: No duplicar comandos
- Si un comando público ya existe (ej: `/player link`), **no crear otro comando paralelo** en `/db` que haga lo mismo.
- En su lugar, agregar un **parámetro opcional** al comando existente (ej: `@usuario`) que solo funcione para admins (verificado con `check_is_admin`).

### Regla: Inputs por @Usuario, no por Steam ID
- Los comandos de admin que operan sobre jugadores deben aceptar `@Usuario` de Discord como input primario.
- El bot resuelve internamente el Steam ID vía `get_player_by_discord()`.
- El Steam ID solo se pide cuando el jugador **no está vinculado** (caso extremo).

### Regla: No hardcodear opciones de datos dinámicos
- **NUNCA** reemplazar un selector dinámico (como `hikari.Role`) con un dropdown hardcodeado de strings.
- Los roles especiales son **roles de Discord** (Fundador, Admin custom, etc.). El sistema guarda el **Discord Role ID** en la tabla `roles`.
- Si se necesita un desplegable de opciones, debe alimentarse de la base de datos o del servidor de Discord, nunca de una lista estática en el código.

---

## Sistema de Roles y Jerarquía

### Dos tipos de roles completamente distintos:

#### 1. Roles de Configuración del Bot (`bot_config`)
- Se configuran con `/set_admin_role`, `/add_vip_role`, etc.
- Le dicen al bot **quién tiene permisos** para ejecutar comandos admin en Discord.
- Viven en la tabla `bot_config` como pares clave-valor.
- Ejemplo: `ADMIN_ROLE_ID = 123456789` → cualquier usuario con ese rol de Discord puede usar comandos admin.

#### 2. Roles Especiales de Jugador (`roles` + `player_roles`)
- Se asignan con `/db add_special_role @Usuario @RolDiscord`.
- Son roles permanentes (Fundador, etc.) que se guardan en la base de datos del juego.
- La tabla `roles` almacena `id` + `name` donde `name` = **Discord Role ID** (string numérico).
- La tabla `player_roles` relaciona `steam_id` ↔ `role_id`.

### Cálculo de active_role (para welcome messages)

En `router.py`, el endpoint `get_player_by_steam` calcula el `primary_role` así:

1. Agrega tipos de membresía activas (ej: VIP_COMUN, VIP_EXPRESS)
2. Agrega roles especiales (ej: `1546690312762564648` = ID del rol Fundador)
3. Jerarquía por substring matching: OWNER > ADMIN > VIP

> **PROBLEMA CONOCIDO:** Los roles especiales se guardan como Discord Role IDs numéricos
> (ej: `1546690312762564648`). El substring matching contra `ADMIN` o `OWNER` nunca va a
> matchear un ID numérico. Esto significa que un jugador con rol especial de Fundador + membresía
> VIP_COMUN siempre aparecerá como VIP en el welcome message, incluso si el rol de Discord
> debería darle mayor jerarquía.

---

## Tablas Críticas

- `bot_config`: Config del bot (roles admin, VIP, canal de logs) — **NO TRUNCAR** rompe toda la sincronización
- `players`: Registro de jugadores y vinculación Discord↔Steam — **NO TRUNCAR**
- `memberships`: Membresías activas/expiradas — **NO TRUNCAR**
- `roles`: Definición de roles especiales (name = Discord Role ID) — **NO TRUNCAR**
- `player_roles`: Asignación de roles especiales a jugadores — **NO TRUNCAR**

---

## Flujo de Welcome Messages

1. `vip_monitor` (en `tasks.py`) detecta nuevo jugador conectado al servidor.
2. Consulta `get_player_by_steam(steam_id)` al API.
3. El API devuelve `active_role` y `custom_welcome_message`.
4. Si ambos existen, envía broadcast: `El {active_role} {nombre} se conectó: "{mensaje}"`
5. Cooldown de 5 minutos para evitar spam en reconexiones/rotaciones de mapa.
 
---

## Motor de Modo 50v50 (`mode_50v50_loop`)

1. Tarea asíncrona permanente en `sync_engine.py` con cadencia de **6 segundos**.
2. Lee `MODE_50V50_STATE` de `bot_config` (`active` o `pending_disable`).
3. Transfiere jugadores de Lonestar (Azul) al menor de Valkyra (Rojo) y Manticore (Verde).
4. Auto-balancea Rojo vs Verde cuando la diferencia $\ge 2$, transfiriendo a los jugadores con menor dinero ($0$ cash primero) y menor actividad.
5. Sincronizado con el ciclo de vida de mapas de RCON mediante activación y desactivación diferida (`pending_enable` y `pending_disable`).

