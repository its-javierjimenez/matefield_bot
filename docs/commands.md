# Manual de Comandos de Discord (Slash Commands)

El bot de Discord de Matefield utiliza **Slash Commands** (`/`) organizados bajo la arquitectura de **Entidades Primero**: `/<entidad> <acción>`.

> **Nota sobre Permisos:** 
> - Los comandos con la etiqueta `[Staff / Admin]` requieren permisos de Administrador o el rol administrativo configurado (`ADMIN_ROLE_ID`).
> - Los comandos con la etiqueta `[Público]` están disponibles para cualquier usuario del servidor.

---

## 🎟️ Membresías (`/membership`)
Gestión completa del ciclo de vida de membresías VIP, cupos y sincronizaciones.

- `/membership add` `[Staff / Admin]`
  - **Descripción**: Añade una membresía VIP a un jugador vinculado.
  - **Parámetros**:
    - `usuario` (Usuario de Discord)
    - `tipo` (Tipo de membresía: `VIP_COMUN`, `VIP_EXPRESS`, `VIP_PERMANENTE`, etc.)
    - `dias` (Duración en días. Dejar en 0 o vacío para permanente)
    - `observacion` *(opcional)*: Nota de auditoría o motivo de compra.
- `/membership list` `[Staff / Admin]`
  - **Descripción**: Muestra la lista paginada e interactiva de todas las membresías activas e históricas en el sistema.
- `/membership edit` `[Staff / Admin]`
  - **Descripción**: Edita los detalles de una membresía existente (tipo, fecha de expiración, estado activo/inactivo).
  - **Parámetros**: `id_membresia`, `nuevo_tipo` *(opcional)*, `dias_adicionales` *(opcional)*, `activo` *(opcional)*.
- `/membership remove` `[Staff / Admin]`
  - **Descripción**: Elimina una membresía permanentemente de la base de datos por su ID.
  - **Parámetros**: `id_membresia`.
- `/membership sync` `[Staff / Admin]`
  - **Descripción**: Fuerza una sincronización inmediata entre la base de datos, el servidor de Discord y los slots reservados de RCON.
- `/membership compensate_all` `[Staff / Admin]`
  - **Descripción**: Extiende masivamente todas las membresías activas por una cantidad determinada de días (útil para compensar caídas del servidor).
  - **Parámetros**: `dias` (Número de días a añadir a cada membresía activa).
- `/membership extend` `[Staff / Admin]`
  - **Descripción**: Extiende una membresía individual específica por ID.
  - **Parámetros**: `id_membresia`, `dias`.

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

## 👤 Jugadores (`/player`)
Gestión de perfil, vinculación de cuentas y mensajes in-game.

- `/player link` `[Público]`
  - **Descripción**: Vincula tu cuenta de Discord con tu Steam ID64 para habilitar la recepción automática de membresías y roles.
  - **Parámetros**: `steam_id` (Steam ID64 numérico de 17 dígitos).
- `/player unlink` `[Público]`
  - **Descripción**: Desvincula tu cuenta de Discord de tu Steam ID.
- `/player profile` `[Público]`
  - **Descripción**: Muestra tu perfil histórico de jugador (Kills, Deaths, K/D, Cash generado, Membresías activas y Roles).
  - **Parámetros**: `usuario` *(opcional)*: Permite a los administradores consultar el perfil de otro jugador.
- `/player welcome_message_set` `[VIP / Staff]`
  - **Descripción**: Configura tu mensaje personalizado de saludo. El bot lo anunciará en un broadcast global dentro del juego cada vez que te conectes al servidor.
  - **Parámetros**: `mensaje` (Máximo 60 caracteres).
- `/player list` `[Staff / Admin]`
  - **Descripción**: Lista todos los jugadores registrados en el sistema de manera paginada.
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
  - **Descripción**: Banea a un jugador en el servidor de juego vía RCON y registra la sanción en la base de datos (con asignación de rol de castigo en Discord si está vinculado).
  - **Parámetros**: `steam_id`, `duracion_dias` (0 para permanente), `motivo`.
- `/ban remove` `[Staff / Admin]`
  - **Descripción**: Desbanea a un jugador en el servidor de juego y remueve los roles de sanción en Discord.
  - **Parámetros**: `steam_id`, `motivo`.
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
