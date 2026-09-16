# Goal: Estabilización Arquitectónica para v0.1 (Single Source of Truth)

Has hecho una excelente pregunta. Al auditar la arquitectura, encontré que **SÍ existen flujos que chocan** y que, de no solucionarse, causarán problemas de rendimiento severos en tu servidor de juego (Hell Let Loose) y confusión en los usuarios.

## User Review Required

> [!CAUTION]
> **Bombardeo de peticiones al RCON (Riesgo Crítico):**
> Actualmente, la API no tiene caché. Esto significa que cada vez que alguien le pide datos, va y le pregunta al servidor del juego. 
> Tienes varios procesos corriendo a la vez:
> 1. pi_rcon/sync_engine.py pide datos cada 10 segundos.
> 2. El bot (match_monitor) pide datos cada 10 segundos.
> 3. El bot (ip_monitor) pide datos cada 10 segundos.
> 4. El bot (hacker_monitor) pide datos cada 5 segundos.
>
> **Resultado:** Tu servidor HLL está recibiendo entre 6 y 8 peticiones HTTP externas cada 10 segundos. Si el servidor se pone lento, estas peticiones se van a acumular y la API colapsará por timeout.

> [!IMPORTANT]
> **Duplicación de Comandos:**
> Como mencionaste antes, existen comandos que hacen lo mismo pero están programados doble, en particular los comandos para ver perfiles (/link, /profile vs los comandos de administrador en database.py). Mantener el código duplicado hará que si agregamos algo nuevo (ej. una nueva estadística), tengamos que editarlo en 2 lugares distintos.

## Proposed Changes

Para que la versión 0.1 sea 100% estable y "clean", propongo lo siguiente:

### 1. Implementar Caché en el Cliente RCON (pi_rcon)
El motor interno de la API (RCONClient) debe actuar como un embudo. Implementaré una caché en memoria de **5 segundos**. 
Si el bot hace 10 peticiones en el mismo segundo, la API solo irá al servidor HLL 1 sola vez, y le devolverá la misma respuesta instantánea a los 10 procesos. Esto protegerá tu servidor de juego.

#### [MODIFY] pps/api_rcon/src/connections/apis/rcon.py
- Agregar caché de tiempo (TTLCache o lógica simple con syncio) a los métodos get_status() y get_players().

### 2. Limpieza de Comandos Redundantes (discord_bot)
Unificaremos la forma en que se muestran los perfiles de los jugadores.
Actualmente en ccount.py tienes /link, /unlink y /profile. 
Nos aseguraremos de que /profile sea la única fuente de verdad para ver estadísticas y rangos, eliminando visualizaciones de perfil redundantes que los administradores usaban internamente.

#### [MODIFY] pps/discord_bot/src/plugins/account.py
#### [MODIFY] pps/discord_bot/src/plugins/database.py
- Eliminar código repetido de visualización de perfiles.
- Hacer que los administradores usen el /profile estándar.

### 3. Sincronización de Roles (Ya arreglado)
El choque de flujos de roles (donde se borraban roles de fundadores al caducar VIPs) **ya está resuelto y estable** gracias a los cambios que hicimos en la sesión anterior.

## Verification Plan

- Iniciar el bot y la API.
- Observar los logs de la API para confirmar que las llamadas al RCON se redujeron a solo 1 por cada 5 segundos, independientemente de los loops del bot.
- Confirmar que los comandos de perfil del bot devuelven la información unificada sin chocar.
