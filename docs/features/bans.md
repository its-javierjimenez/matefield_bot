# Sistema de Baneos

El sistema de baneos de Matefield permite a los administradores expulsar y vetar temporal o permanentemente a jugadores tanto del servidor de Discord (vía roles) como del servidor de juego de manera sincronizada.

## Flujo de Sanción (Baneo)

1. **Ejecución desde Discord**: Un Administrador utiliza el comando `/admin ban` indicando el usuario de Discord, el motivo del baneo, y la duración (Temporal o Permanente).
2. **Resolución de Perfil**: El bot busca en la base de datos el `steam_id` asociado a la cuenta de Discord del infractor.
3. **Registro en Base de Datos**: Se crea un nuevo registro en la tabla `PlayerBan` con:
   - `steam_id` del jugador.
   - `reason` (Motivo provisto por el admin).
   - `banned_by` (ID de Discord del administrador que emitió la orden).
   - `start_time` y `end_time` (si es temporal).
   - `is_active` establecido en `True`.
4. **Ejecución RCON**: La API envía inmediatamente el comando de baneo al servidor de juego mediante el socket RCON (`AdminBan <SteamID> <Duración> <Motivo>`).
5. **Asignación de Roles de Castigo**: 
   - El sistema lee las configuraciones de baneo (ej: `BAN_ROLE_PERMANENT` o `BAN_ROLE_TEMPORARY`) para buscar los IDs de los roles de castigo.
   - El bot de Discord le asigna automáticamente el rol de baneo al usuario, lo que típicamente le retira permisos de ver o hablar en el servidor.
6. **Notificación Pública**: Se envía un mensaje embed al canal público de baneos documentando la infracción, el jugador y el administrador responsable.

## Mapeos de Duración de Baneo (Ban Roles)

Para manejar distintos niveles de castigo visual en Discord (ej: "Baneado Permanente" vs "Suspendido 3 Días"), el bot permite configurar mapeos de duración a roles.

- Los comandos `/config ban map` y `/config ban unmap` permiten vincular duraciones específicas (en días) con un Rol de Discord en particular.
- Si un usuario es baneado por 30 días, el sistema buscará si existe una configuración de baneo para 30 días, y de ser así, le otorgará ese rol de castigo específico.
- Para baneos permanentes, se utiliza la duración `0` o `-1`.

## Perdones y Expiración (Pardons)

### Expiración Automática
- Cuando el `end_time` de un baneo temporal es alcanzado, el registro `PlayerBan` podría ser procesado por una tarea programada para marcarlo como `is_active = False` y retirar el rol de baneo de Discord. (Nota: En servidores de juego, los baneos temporales suelen expirar automáticamente en el propio motor del juego).

### Perdón Manual (Unban)
- Un Administrador puede ejecutar el comando `/admin pardon` sobre un usuario.
- El bot ejecuta el comando de desbaneo por RCON, cambia el estado del registro `PlayerBan` a `is_active = False`, y le retira el rol de castigo de Discord, restaurando sus permisos habituales.
