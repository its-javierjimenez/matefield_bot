# Sistema de Baneos y Moderación

El sistema de moderación y sanciones de Matefield permite expulsar y vetar a infractores de forma coordinada tanto en el servidor de juego (vía RCON) como en la comunidad de Discord (mediante roles de castigo).

## Flujo de Sanción (`/ban add`)

1. **Ejecución desde Discord**: Un Administrador utiliza el comando `/ban add` indicando el `steam_id` del jugador, la duración en días (0 para permanente) y el motivo.
2. **Registro en Base de Datos**: Se crea un nuevo registro en la tabla `PlayerBan` con:
   - `steam_id`: Identificador Steam del sancionado.
   - `reason`: Motivo provisto por el administrador.
   - `banned_by`: ID de Discord del administrador actuante.
   - `start_time` y `end_time` (si es temporal).
   - `is_active = True`.
3. **Ejecución RCON**: La API envía la orden de veto al servidor de juego mediante el comando nativo `AdminBan <SteamID> <Duración> <Motivo>`.
4. **Asignación de Roles de Castigo en Discord**: 
   - El bot busca si el jugador sancionado está vinculado a una cuenta de Discord.
   - Si está vinculado, consulta los mapeos configurados con `/ban_role map` para la duración asignada y aplica automáticamente el rol de castigo correspondiente al usuario en Discord.

## Mapeos de Roles de Castigo (`/ban_role`)

Para diferenciar visualmente las sanciones en Discord (ej: "Baneado Permanente" vs "Suspendido 3 Días"):
- `/ban_role map <dias> <rol>`: Vincula una duración en días con un rol específico de Discord.
- `/ban_role unmap <dias>`: Desvincula el rol asociado a una duración.
- `/ban_role list`: Muestra la configuración actual de roles de sanción.

## Desbaneo y Perdón (`/ban remove`)

1. Un administrador ejecuta el comando `/ban remove <steam_id> <motivo>`.
2. La API envía el comando de desbloqueo al servidor de juego por RCON.
3. El registro en la base de datos se actualiza a `is_active = False`.
4. El bot de Discord retira cualquier rol de castigo asociado a la cuenta de Discord vinculada al Steam ID.
