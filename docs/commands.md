# Wardogs RCON Discord Bot - Lista de Comandos

Este documento enumera todos los comandos disponibles (slash commands) en el bot de Discord de Wardogs. Los comandos están agrupados por dominios bajo un comando base (Group), siguiendo la convención de `[acción]_[entidad]`.

## 🎮 Match (/match) - En Vivo y Partidas Actuales
Estos comandos consultan e interactúan directamente con el servidor RCON para obtener información en tiempo real de la partida en curso.
- `/match status`: Muestra el estado actual de la partida, puntajes por equipo, mapa, tiempo restante y el estado del **Modo 50v50** (🟢 Activo, ⏳ Programado, o ⚪ Inactivo).
- `/match players`: Muestra a todos los jugadores actualmente en la partida agrupados por equipo.
- `/match leaderboard`: Muestra el top 10 de jugadores de la partida en curso (ordenados por kills).
- `/match player [steam_id_o_nombre]`: Muestra información en vivo de un jugador en la partida. **Incluye botones interactivos de administrador** para Kickear, Banear o Cambiar de Facción al instante.
- `/match logs`: *(Solo Admin)* Muestra los últimos 10 eventos del log de auditoría del servidor de juego.
- `/match mode50v50 [accion: Activar | Desactivar | Consultar]`: *(Solo Admin)* Administra el Modo 50v50 (Rojo vs Verde).
  - **Activar**: Desactiva el Team Balancing en RCON y programa el modo para la próxima partida o reinicio.
  - **Desactivar**: Restaura el Team Balancing en RCON (límite: 1). Si la partida ya está en curso, programa la desactivación para el próximo match (manteniendo el 50v50 actual hasta el final). Si no había iniciado, cancela inmediatamente.
  - **Consultar**: Muestra el estado detallado (`active`, `pending_enable`, `pending_disable`, `inactive`).
- `/match mode50v50_enable`: *(Solo Admin)* Acceso directo para activar/programar el modo 50v50.
- `/match mode50v50_disable`: *(Solo Admin)* Acceso directo para desactivar/cancelar el modo 50v50.
- `/match mode50v50_status`: Consulta rápida pública del estado del modo 50v50.


## 📊 Database (`/db`) - Estadísticas Históricas y Gestión
Estos comandos interactúan con la base de datos local y muestran información histórica o permiten administrar cuentas.
- `/db player [steam_id]`: Muestra el perfil histórico global de un jugador (Kills, Muertes, Dinero generado, bans) junto a su perfil de Steam.
- `/db players`: Lista todos los jugadores registrados en la base de datos (con menú interactivo paginado).
- `/db leaderboard`: Muestra el Top 15 histórico global de jugadores.
- `/db matches`: Muestra un historial de partidas registradas.
- `/db status`: Muestra el estado actual e historial de rotación de modos del servidor.
- `/db edit_player`: *(Solo Admin)* Modifica manualmente datos del perfil de un jugador.

**Gestión de Membresías (Roles VIP)**
- `/db add_membership [steam_id] [tipo]`: *(Solo Admin)* Otorga una membresía al jugador y el rol asociado en Discord. La duración en días es opcional; de no proveerse, se utilizará la duración configurada por defecto para ese rol (o 30 días si no hay configuración). Ingresar `0` asigna membresía permanente.
- `/db edit_membership`: *(Solo Admin)* Edita los días o estado de una membresía activa.
- `/db remove_membership`: *(Solo Admin)* Elimina una membresía de manera permanente.
- `/db memberships`: *(Solo Admin)* Lista todas las membresías activas.
- `/db add_special_role`: *(Solo Admin)* Añade un rol especial permanente a un jugador.
- `/db remove_special_role`: *(Solo Admin)* Remueve un rol especial permanente.

## 🔒 Reserved Slots (/reserved_slots) - Slots VIP (Admin)
Controla los accesos reservados directamente.
- `/reserved_slots list`: Muestra la lista de SteamIDs de los jugadores que tienen un slot reservado en el servidor RCON.
- `/reserved_slots add`: Agrega manualmente un SteamID a la lista blanca de slots reservados.
- `/reserved_slots remove`: Remueve manualmente un SteamID de los slots reservados.
- `/reserved_slots sync_status`: Monitoriza y contrasta el estado de las membresías de la Base de Datos contra la lista real de slots del RCON. Detecta desincronizaciones (Faltantes o Sobrantes).

## 🛠️ Server (/server) - Administración General (Admin)
Comandos administrativos directos al servidor.
- `/server announce [mensaje]`: Envía un mensaje global en pantalla a todos los jugadores del servidor de juego.
- `/server set_max_reserved [cantidad]`: Modifica dinámicamente el límite máximo de slots reservados permitidos (actualiza ServerSettings.ini remotamente).

## ⚙️ Config (/config) - Configuración del Bot (Admin)
Configura variables internas de comportamiento del bot y roles de Discord.
- `/config set_announcement_channel`: Asigna el canal de texto donde el bot publicará los anuncios automáticos (por ejemplo: anuncio del MVP o partidas terminadas).
- `/config set_match_channel`: Configura el canal donde se enviarán los resultados de las partidas.
- `/config set_admin_role`: Establece el rol de Discord que brindará permisos de administrador dentro del bot.
- `/config add_vip_role`: Añade un ID de rol a la lista de roles VIP permitidos.
- `/config remove_vip_role`: Remueve un rol de la lista de roles VIP.
- `/config vip_roles`: Lista qué roles están marcados como VIP.
- `/config map_role`: Vincula un nombre de membresía (ej. VIP_EXPRESS) a un ID de rol específico de Discord, para automatizar la entrega del rol.
- `/config unmap_role`: Elimina el mapeo configurado.
- `/config view_all`: Muestra un resumen general de todas las variables, canales y mapeos guardados.
- `/config add_whitelist`: Añade un usuario a la Whitelist para que el bot no le quite roles.
- `/config remove_whitelist`: Remueve un usuario de la Whitelist.
- `/config whitelist`: Lista los usuarios en la Whitelist de sincronización.

## 👤 Player (/player) - Comandos Públicos / Usuarios
Comandos orientados a los jugadores del Discord de Wardogs.
- `/player link [steam_id]`: Vincula tu usuario de Discord con tu SteamID para sincronización automática.
- `/player unlink`: Desvincula tu cuenta de Discord de Steam.
- `/player profile`: Muestra tu perfil, Steam ID vinculado y membresías activas.
- `/player set_welcome_message [mensaje]`: Si posees una membresía VIP o ADMIN activa, te permite configurar el mensaje automático (máx 60 caracteres) que saldrá en la pantalla del servidor del juego cada vez que ingreses a jugar. Incluye vista previa interactiva.

## 🛠️ Admin (/admin) - Comandos DEV / Especiales
- `/admin sync_memberships`: *(Solo Admin / DEV)* Escanea todos los usuarios vinculados del servidor y, si tienen un rol de Discord mapeado, les otorga/renueva su membresía en la base de datos de acuerdo a la configuración. Ideal para pruebas o migraciones.
