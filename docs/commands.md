# Manual de Comandos de Discord (Slash Commands)

El bot de Discord de Matefield utiliza **Slash Commands** (`/`) organizados bajo la arquitectura de **Entidades Primero**: `/<entidad> <acción>`.

> **Nota sobre Permisos:** 
> - Los comandos con la etiqueta `[Staff / Admin]` requieren permisos de Administrador o el rol administrativo configurado (`ADMIN_ROLE_ID`).
> - Los comandos con la etiqueta `[Público]` están disponibles para cualquier usuario del servidor.

---

## 👤 Jugadores y Cuentas (`/player`)
Vinculación oficial con Steam, gestión de perfiles y paneles de bienvenida.

- `/player link` `[Público / Staff]`
  - **Descripción**:
    - **Sin parámetros `[Público]`**: Genera un mensaje efímero con un botón interactivo `[🎮 Iniciar sesión con Steam]` mediante **Steam OpenID 2.0**. Al iniciar sesión en Valve, el bot verifica y vincula de forma 100% auténtica la cuenta de Steam con Discord, asignando de inmediato el rol de miembro verificado (`LINK_ROLE_ID`).
    - **Con parámetros `[Staff / Admin]`**: Permite a un administrador vincular manualmente un Steam ID a un usuario específico para soporte técnico.
  - **Parámetros**: `steam_id` *(opcional, solo admin)*, `usuario` *(opcional, solo admin)*.
- `/player link_channel` `[Staff / Admin]`
  - **Descripción**: Publica un panel oficial permanente con un botón interactivo `[🎮 Vincular mi cuenta de Steam]` en el canal especificado (o el actual). Cualquier miembro que presione el botón recibe instantáneamente su enlace privado de vinculación sin necesidad de escribir comandos.
  - **Parámetros**: `canal` *(opcional, canal de Discord)*.
- `/player unlink` `[Público / Staff]`
  - **Descripción**: Desvincula la cuenta de Steam asociada a Discord y revoca el rol verificado. Los administradores pueden desvincular a otros usuarios.
  - **Parámetros**: `usuario` *(opcional, solo admin)*.
- `/player view` `[Público / Staff]`
  - **Descripción**: Muestra la ficha de jugador con su Steam ID, nombre en juego, avatar, estado de vinculación y membresías.
- `/player edit` `[Staff / Admin]`
  - **Descripción**: Permite editar observaciones administrativas o apodo de un jugador.
- `/player memberships` `[Público / Staff]`
  - **Descripción**: Muestra el historial interactivo y paginado de membresías VIP del usuario o del jugador seleccionado.

---

## 🎟️ Membresías (`/membership`)

Gestión completa del ciclo de vida de membresías VIP, cupos y sincronizaciones.

- `/membership add` `[Staff / Admin]`
  - **Descripción**: Añade una membresía VIP a un jugador vinculado.
  - **Parámetros**:
    - `usuario` (Usuario de Discord)
    - `tipo` (Tipo de membresía: `VIP_COMUN`, `VIP_EXPRESS`, etc.)
    - `dias` *(opcional)*: Duración en días (0 = permanente, vacío = predeterminado de configuración).
    - `rol_especial` *(opcional)*: Rol especial adicional a asignar y guardar en base de datos.
    - `booster` *(opcional)*: Booleano (`True`/`False`). Si se omite, el bot detecta automáticamente si el usuario es Server Booster de Discord (`member.premium_since`).
- `/membership list` `[Staff / Admin]`
  - **Descripción**: Muestra la lista paginada e interactiva de todas las membresías activas e históricas, incluyendo tags de estado (`🟢 Activa` / `🔴 Inactiva`), roles especiales asignados y si es `⚡ Booster`.
- `/membership edit` `[Staff / Admin]`
  - **Descripción**: Edita los detalles de una membresía existente (duración, tipo, estado activo/inactivo o condición de booster). Si se modifica el `tipo` sin especificar `dias`, el sistema ajusta dinámicamente la fecha de vencimiento (`end_time`) de acuerdo a la duración del nuevo tipo (o permanente).
  - **Parámetros**: `id_membresia`, `dias` *(opcional)*, `tipo` *(opcional)*, `activa` *(opcional)*, `booster` *(opcional)*.
- `/membership remove` `[Staff / Admin]`
  - **Descripción**: Elimina una membresía permanentemente de la base de datos por su ID.
  - **Parámetros**: `id_membresia`.
- `/membership sync` `[Staff / Admin]`
  - **Descripción**: Fuerza una sincronización inmediata entre la base de datos, el servidor de Discord y los slots reservados de RCON.
- `/membership compensate_all` `[Staff / Admin]`
  - **Descripción**: Extiende masivamente todas las membresías activas por una cantidad determinada de días (útil para compensar caídas del servidor). *(Nota: En membresías de Tebex de compra única extiende su vigencia total; en suscripciones recurrentes de Tebex, el bot acumula los días compensados a favor del jugador para que no los pierda al renovar).*
  - **Parámetros**: `dias` (Número de días a añadir a cada membresía activa).
- `/membership extend` `[Staff / Admin]`
  - **Descripción**: Extiende una membresía individual específica por ID.
  - **Parámetros**: `id_membresia`, `dias`.
- `/membership export` `[Staff / Admin]`
  - **Descripción**: Genera bajo demanda un archivo CSV descargable con todas las membresías existentes y cuentas vinculadas (Discord ID, Steam ID, nickname, roles vinculados, tipo VIP, booster, fundador, vigencia y observaciones).
  - **Entrega**: Envía un Embed interactivo con botón de descarga directa servido desde la API (enlace firmado con token temporal válido por 30 minutos) para no sobrecargar Discord con archivos pesados.

---

## 👥 Roles DDD (`/roles`)
Catálogo de roles del sistema y asignación de roles especiales a jugadores.

- `/roles register` `[Staff / Admin]`
  - **Descripción**: Registra o actualiza la definición de un rol en la base de datos.
  - **Parámetros**:
    - `codigo`: Identificador en mayúsculas (ej: `ADMIN_MAIN`, `VIP_EXPRESS`, `SUPERVISOR`).
    - `nombre`: Nombre legible para humanos.
    - `rol_discord`: Rol de Discord asociado.
    - `tipo`: Clasificación de dominio (`SYSTEM`, `VIP`, `PUBLIC`, `SPECIAL`).
    - `prioridad` *(opcional)*: Jerarquía numérica del rol.
    - `cupo_maximo` *(opcional)*: Límite de miembros con este rol.
- `/roles list` `[Staff / Admin]`
  - **Descripción**: Lista todos los roles registrados en la base de datos con su código, tipo y mapeo de Discord.
- `/roles assign` `[Staff / Admin]`
  - **Descripción**: Asigna un rol registrado a un jugador vinculado en la base de datos.
  - **Parámetros**: `usuario`, `rol_especial`.
- `/roles remove` `[Staff / Admin]`
  - **Descripción**: Remueve un rol registrado de un jugador en la base de datos.
  - **Parámetros**: `usuario`, `rol_especial`.

---

## ⚙️ Roles Automáticos (`/role`)
Configuración de roles asignados por eventos del sistema (vinculación y moderación).

- `/role set_link` `[Staff / Admin]`
  - **Descripción**: Configura el rol de Discord que se otorga automáticamente cuando un usuario vincula su cuenta mediante `/player link` (y se revoca al desvincular con `/player unlink`). Al configurarse, **otorga el rol de inmediato y de forma retroactiva a todos los usuarios que ya estén vinculados** en el servidor de Discord. Omitir el parámetro desactiva el rol de vinculación.
  - **Parámetros**: `rol` *(opcional)*.
- `/role set_ban` `[Staff / Admin]`
  - **Descripción**: Configura el rol de Discord predeterminado que se otorga automáticamente al sancionar a un usuario con `/ban add` (y se remueve al desbanear con `/ban remove`). Omitir el parámetro desactiva el rol.
  - **Parámetros**: `rol` *(opcional)*.

---

## 👤 Jugadores (`/player`)
Gestión de perfil, vinculación de cuentas y mensajes in-game.

- `/player link` `[Público]`
  - **Descripción**: Vincula tu cuenta de Discord con tu Steam ID64 para habilitar la recepción automática de membresías y roles. Relación estricta 1:1: un Steam ID no puede ser vinculado a múltiples cuentas de Discord, ni una cuenta de Discord a múltiples cuentas de Steam (usa `/player unlink` primero si necesitas cambiarlo).
  - **Parámetros**: `steam_id` (Steam ID64 numérico de 17 dígitos), `usuario` *(opcional, Solo Staff / Admin)*: Permite a un administrador vincular a otro usuario.
- `/player unlink` `[Público]`
  - **Descripción**: Desvincula tu cuenta de Discord de tu Steam ID y revoca los roles asociados. Solo actúa sobre la cuenta del usuario que lo invoca; el parámetro opcional `usuario` está estrictamente restringido a administradores.
  - **Parámetros**: `usuario` *(opcional, Solo Staff / Admin)*: Permite a un administrador desvincular a otro usuario.
- `/player profile` `[Público]`
  - **Descripción**: Muestra tu perfil histórico de jugador (Kills, Deaths, K/D, Cash generado, Membresías activas y Roles).
  - **Parámetros**: `usuario` *(opcional)*: Permite a los administradores consultar el perfil de otro jugador.
- `/player welcome_message_set` `[VIP / Staff]`
  - **Descripción**: Configura tu mensaje personalizado de saludo. El bot lo anunciará en un broadcast global dentro del juego cada vez que te conectes al servidor.
  - **Parámetros**: `mensaje` (Máximo 60 caracteres).
- `/player list` `[Staff / Admin]`
  - **Descripción**: Lista todos los jugadores registrados en el sistema de manera paginada.
- `/player memberships` `[Público / Staff]`
  - **Descripción**: Muestra el historial completo de membresías de un usuario de Discord de forma paginada e interactiva con botones (◀ Anterior / Siguiente ▶). Muestra ID, Steam ID, tipo, fechas de inicio y fin, estado (`🟢 Activa` / `🔴 Inactiva`), rol especial y estado de sincronización con RCON.
  - **Parámetros**: `usuario` (Usuario de Discord).
- `/player edit` `[Staff / Admin]`
  - **Descripción**: Permite a un administrador editar información de un jugador vinculado (Steam ID, Discord ID, observaciones).

---

## 🖥️ Servidor RCON (`/server`)
Control directo del servidor de juego en tiempo real mediante RCON.

- `/server status` `[Público]`
  - **Descripción**: Muestra el estado en vivo del servidor: mapa actual, jugadores conectados por equipo, tiempo de partida y rotación de mapas programada.
- `/server announce` `[Staff / Admin]`
  - **Descripción**: Envía un mensaje broadcast en pantalla que verán todos los jugadores conectados al servidor de juego.
  - **Parámetros**: `mensaje`.
- `/server set_max_reserved` `[Staff / Admin]`
  - **Descripción**: Modifica dinámicamente el límite máximo de slots reservados configurados en el servidor de juego.
  - **Parámetros**: `cantidad`.
- `/server logs` `[Staff / Admin]`
  - **Descripción**: Muestra los últimos eventos de auditoría y comandos ejecutados sobre el servidor.

---

## ⚔️ Partida en Curso (`/match`)
Telemetría de la ronda actual de juego.

- `/match status` `[Público]`
  - **Descripción**: Consulta el marcador en vivo de la partida, puntuación por equipo y mapa actual.
- `/match players` `[Público]`
  - **Descripción**: Muestra la lista de todos los jugadores conectados en la partida actual distribuidos por facción.
- `/match leaderboard` `[Público]`
  - **Descripción**: Muestra el Top 10 de jugadores con mejor rendimiento en la partida en curso.
- `/match player_info` `[Staff / Admin]`
  - **Descripción**: Muestra información detallada en vivo de un jugador en la partida (kills, muertes, ping, equipo, Steam ID).
  - **Parámetros**: `steam_id` o `nombre`.

---

## 🔨 Baneos y Moderación (`/ban` y `/ban_role`)
Sistema coordinado de sanciones entre RCON y Discord.

- `/ban add` `[Staff / Admin]`
  - **Descripción**: Banea a un jugador en el servidor de juego vía RCON o en Discord. Si se pasa un `@usuario` de Discord vinculado, busca automáticamente su Steam ID.
  - **Parámetros**: `usuario` (opcional si se especifica Steam ID), `steam_id` (opcional si se especifica usuario, admite mención o ID), `reason` (motivo), `dias` (duración en días, 0 = permanente), `solo_discord` (si es `True`, solo asigna el rol de baneo configurado sin sincronizar RCON).
- `/ban remove` `[Staff / Admin]`
  - **Descripción**: Desbanea a un jugador en el servidor de juego y remueve los roles de sanción en Discord. Admite `@usuario` vinculado o `steam_id`.
  - **Parámetros**: `usuario` (opcional si se especifica Steam ID), `steam_id` (opcional si se especifica usuario), `solo_discord` (solo remueve rol de ban en Discord).
- `/ban list` `[Staff / Admin]`
  - **Descripción**: Muestra la lista de sanciones activas e históricas registradas en el sistema.
- `/ban_role map` `[Staff / Admin]`
  - **Descripción**: Vincula una duración de baneo en días con un rol de castigo específico de Discord.
  - **Parámetros**: `dias`, `rol`.
- `/ban_role unmap` `[Staff / Admin]`
  - **Descripción**: Elimina el mapeo de rol para una duración de baneo.
  - **Parámetros**: `dias`.
- `/ban_role list` `[Staff / Admin]`
  - **Descripción**: Muestra todos los mapeos de roles de sanción configurados.

---

## 🔒 Slots Reservados y Cupos (`/reserved_slots` y `/quota`)

- `/reserved_slots list` `[Staff / Admin]`
  - **Descripción**: Consulta directamente al servidor RCON la lista de Steam IDs cargados en la memoria de slots reservados.
- `/reserved_slots add` `[Staff / Admin]`
  - **Descripción**: Agrega manualmente un Steam ID a la lista de slots reservados del servidor RCON.
  - **Parámetros**: `steam_id`.
- `/reserved_slots remove` `[Staff / Admin]`
  - **Descripción**: Remueve un Steam ID de la lista de slots reservados del servidor RCON.
  - **Parámetros**: `steam_id`.
- `/reserved_slots sync_status` `[Staff / Admin]`
  - **Descripción**: Compara los slots reservados cargados en RCON contra los usuarios VIP activos en la base de datos, detectando discrepancias o desincronizaciones.
- `/quota list` `[Staff / Admin]`
  - **Descripción**: Muestra la ocupación actual de cupos de cada tipo de membresía frente a su límite máximo permitido.
- `/quota set` `[Staff / Admin]`
  - **Descripción**: Configura el cupo máximo de jugadores permitidos para un tipo de membresía.
  - **Parámetros**: `tipo_membresia`, `limite`.

---

## 🏆 Tablas de Clasificación (`/leaderboard`)

- `/leaderboard list` `[Público]`
  - **Descripción**: Muestra el Top 15 histórico general de jugadores registrados en la base de datos.
  - **Parámetros**:
    - `metrica`: Opción para clasificar por `Kills`, `Muertes`, o `Dinero Generado (cash_earned)`.

---

## 🛡️ Lista Blanca (`/whitelist`)
Protege cuentas para que el sincronizador de Discord nunca les remueva roles.

- `/whitelist add` `[Staff / Admin]`
  - **Descripción**: Añade un usuario de Discord a la lista blanca protegida.
  - **Parámetros**: `usuario`.
- `/whitelist remove` `[Staff / Admin]`
  - **Descripción**: Remueve un usuario de Discord de la lista blanca protegida.
  - **Parámetros**: `usuario`.
- `/whitelist list` `[Staff / Admin]`
  - **Descripción**: Muestra los usuarios actualmente protegidos en la lista blanca.

---

## ⚙️ Configuración del Bot (`/config`)

- `/config announcement_channel` `[Staff / Admin]`
  - **Descripción**: Configura el canal de Discord donde se enviarán los anuncios globales del sistema.
  - **Parámetros**: `canal`.
- `/config match_channel` `[Staff / Admin]`
  - **Descripción**: Configura el canal de Discord donde se publicarán los resúmenes y el MVP de las partidas finalizadas.
  - **Parámetros**: `canal`.
- `/config list` `[Staff / Admin]`
  - **Descripción**: Muestra un resumen general de todas las variables y canales configurados en la base de datos.

---

## 📡 Servidores RCON (`/rcon`)
Gestión dinámica y conexión simultánea a múltiples servidores RCON en base de datos.

- `/rcon list` `[Staff / Admin]`
  - **Descripción**: Muestra todos los servidores RCON registrados, con su estado (`🟢 Activo` / `🔴 Inactivo`), dirección HTTP/HTTPS, ID y si es el servidor predeterminado (`⭐`). Si la base de datos no tiene servidores registrados, muestra el fallback de `.env`.
- `/rcon add` `[Staff / Admin]`
  - **Descripción**: Registra un nuevo servidor RCON en la base de datos. Si no se especifica nombre, se conecta al servidor y autocompleta el nombre obtenido desde su status.
  - **Parámetros**: `ip`, `puerto`, `password`, `nombre` *(opcional)*, `esquema` *(http/https, default: http)*, `activo` *(default: True)*, `default` *(default: False)*.
- `/rcon test` `[Staff / Admin]`
  - **Descripción**: Ejecuta un diagnóstico en tiempo real contra un servidor RCON específico por ID: verifica conectividad, latencia en ms, mapa actual y jugadores conectados.
  - **Parámetros**: `server_id`.
- `/rcon edit` `[Staff / Admin]`
  - **Descripción**: Actualiza los parámetros de un servidor RCON (nombre, IP, puerto, contraseña, esquema, estado activo o predeterminado).
  - **Parámetros**: `server_id`, `nombre` *(opcional)*, `ip` *(opcional)*, `puerto` *(opcional)*, `password` *(opcional)*, `esquema` *(opcional)*, `activo` *(opcional)*, `default` *(opcional)*.
- `/rcon remove` `[Staff / Admin]`
  - **Descripción**: Elimina permanentemente un servidor RCON de la base de datos.
  - **Parámetros**: `server_id`.
- `/rcon sync_all` `[Staff / Admin]`
  - **Descripción**: Fuerza la sincronización inmediata de slots VIP y listas de baneos en todos los servidores RCON activos de forma distribuida y tolerante a fallos.

---

## 🎭 Roles del Sistema (`/role`)
Configuración de roles automáticos para vinculación y moderación en Discord.

- `/role set_link` `[Staff / Admin]`
  - **Descripción**: Configura el rol que se otorga automáticamente al vincular una cuenta (`/player link`) y lo asigna retroactivamente en segundo plano a todos los usuarios vinculados.
  - **Parámetros**: `rol` *(opcional, omitir para desactivar)*.
- `/role set_ban` `[Staff / Admin]`
  - **Descripción**: Configura el rol de castigo que se otorga automáticamente al banear a un usuario con `/ban add`.
  - **Parámetros**: `rol` *(opcional, omitir para desactivar)*.
- `/role unset_ban` `[Staff / Admin]`
  - **Descripción**: Configura el rol que se remueve automáticamente al banear a un usuario y se le restituye al ser desbaneado (actúa como switch inverso con el rol de baneo).
  - **Parámetros**: `rol` *(opcional, omitir para desactivar)*.
- `/unban` `[Staff / Admin]`
  - **Descripción**: Comando directo equivalente a `/ban remove` para desbanear por Discord (`@usuario`) o Steam ID, removiendo el rol de ban y restituyendo el rol de `unset_ban`.

---

## 📦 Tipos y Paquetes de Membresía (`/membership_type`)
Gestión dinámica del catálogo de membresías VIP, precios en USD, modalidad de cobro y cupos.

- `/membership_type list` `[Staff / Admin]`
  - **Descripción**: Muestra un Embed interactivo con todos los paquetes configurados, incluyendo precio, modalidad (pago único / mensualidad), duración por defecto, cupos ocupados vs máximos, servidor asignado y rol de Discord.
- `/membership_type create` `[Staff / Admin]`
  - **Descripción**: Registra un nuevo paquete de membresía en la base de datos.
  - **Parámetros**: `codigo`, `nombre`, `precio` *(USD)*, `dias` *(duración por defecto, 0 = permanente)*, `cupo` *(opcional: límite de compras simultáneas)*, `rol` *(rol de Discord a otorgar)*, `servidor` *(opcional: vincular a un servidor RCON específico)*, `facturacion` *(`ONE_TIME` o `RECURRING`)*, `descripcion` *(opcional)*.
- `/membership_type edit` `[Staff / Admin]`
  - **Descripción**: Edita parámetros de un paquete existente (nombre, precio, días, cupos, rol, servidor, facturación o estado activo/inactivo).
  - **Parámetros**: `tipo_id`, `nombre`, `precio`, `dias`, `cupo`, `rol`, `servidor`, `facturacion`, `activo`.
