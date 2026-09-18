# Motor de Partidas (Match Engine)

El **Motor de Partidas** es el subsistema encargado de mantener una réplica exacta del estado del servidor de juego en la base de datos. Está implementado principalmente en `apps/api_rcon/src/sync_engine.py`.

## Funcionamiento General (Polling)

Dado que los servidores de juego no siempre emiten Webhooks o eventos Push para todas las acciones, el motor utiliza un modelo de **Polling** resiliente.

Cada 10 segundos, la función `poll_rcon()` se ejecuta en segundo plano y realiza consultas al servidor mediante RCON:
1. Pide la información global del servidor (Mapa actual, índices de rotación).
2. Pide la lista detallada de jugadores (Kills, Deaths, Facciones).

## Ciclo de Vida de una Partida

### 1. Inicio de Partida
El motor mantiene en memoria el ID de la partida actual (`current_match_id`). Si detecta que no hay partida activa, crea un nuevo registro en la tabla `Match` con el nombre del mapa actual y establece el `start_time`.

### 2. Actualización de Estadísticas (Stats)
Durante cada ciclo de polling (10 segundos):
- Se actualizan las estadísticas de los equipos (`MatchTeamStats`) calculando los puntajes basados en las métricas de los jugadores y tickets reportados por RCON.
- Se actualizan las estadísticas individuales (`MatchPlayerStats`). Si un jugador nuevo aparece en el servidor, se inserta; si ya existe, se actualizan sus `kills`, `deaths` y tiempo jugado (`PlayerSession`).

### 3. Condiciones de Fin de Partida
El motor verifica constantemente si la partida debe terminar. Existen tres condiciones de cierre:

1. **Límite de Puntos (Score Cap)**:
   - Se lee el límite máximo desde la configuración de la base de datos (`SCORE_CAP`, por defecto 100).
   - Si un equipo alcanza o supera este límite, la partida se declara terminada.
   - **Victoria**: Se asigna automáticamente el `winning_team_id` al equipo que alcanzó el límite y se establece el `end_time`.

2. **Rotación por Tiempo o Admin**:
   - El motor compara el índice de rotación actual reportado por RCON (`rotation_index`) con el índice guardado en memoria.
   - Si difieren, significa que el servidor cambió de mapa (ya sea porque concluyó el tiempo o se forzó el cambio).
   - **Victoria**: El motor selecciona al equipo con mayor puntaje, lo designa como ganador y establece el `end_time`.

3. **Cierre Forzado (Emergency Close)**:
   - En caso de reinicios abruptos de la API, las partidas abiertas sin cerrar son finalizadas limpiamente para evitar superposiciones con la siguiente partida.

## Monitoreo de Hackers (Live KPM)

Asociado a las partidas, existe un sistema en el bot de Discord (`hacker_monitor_task`) que aprovecha las estadísticas en tiempo real:
- Los Admins pueden iniciar un monitoreo sobre un jugador sospechoso mediante `/hacker monitor`.
- El bot guarda las `kills` actuales del jugador y el tiempo de inicio.
- Cada 5 segundos, calcula las **Kills Per Minute (KPM)**.
- El panel de Discord se actualiza en vivo con colores indicativos (Rojo si supera umbrales anormales).
