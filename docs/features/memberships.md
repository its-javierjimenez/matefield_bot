# Membresías y Roles de Dominio (DDD)

El sistema maneja los privilegios de los usuarios utilizando el principio de **Separation of Concerns** (Separación de Responsabilidades). Existen dos conceptos clave que no deben mezclarse: las **Membresías** (beneficios in-game como slots reservados) y los **Roles de Dominio** (jerarquía, identidad y permisos de administración).

## 1. Membresías VIP (Beneficios en Juego)

Las membresías otorgan beneficios técnicos dentro del servidor de juego, primordialmente el acceso a **Reserved Slots** (saltarse la cola de espera de conexión).

- **Tipos de Membresía**: Definidas libremente por los administradores (ej: `VIP_COMUN`, `VIP_EXPRESS`, `VIP_BOOST_COM`). Permite asignar distintos niveles o duraciones independientemente de si el jugador es donador directo o booster.
- **Tabla en BD**: `memberships`. Posee:
  - `start_date` (`start_time`) y `end_date` (`end_time` - NULL para permanente).
  - `is_active`: Flag booleano de vigencia.
  - `is_booster`: Flag booleano que indica si la membresía corresponde a un Server Booster (Nitro) de Discord. Permite auditar qué membresías son producto de boosts y cuáles de compras directas.
  - `role_granted_id` (`special_role_id`): Relación opcional a un rol especial adicional de la tabla `roles`.
- **Detección y Gestión de Boosters (Nitro)**:
  - Al otorgar una membresía (`/membership add`), el parámetro `booster` es opcional. Si se omite, el bot consulta directamente el estado del usuario en Discord (`member.premium_since is not None`) y marca automáticamente la casilla. Si el administrador prefiere forzar un valor específico (`True` o `False`), puede sobreescribirlo manualmente.
  - Se puede modificar el estado de booster en cualquier momento con `/membership edit`.
  - El listado `/membership list` identifica visualmente con el tag `⚡ Booster` a los miembros correspondientes.
- **Sincronización RCON**: 
  - La API de RCON posee el endpoint de sincronización `/v1/db/sync_memberships`.
  - Este endpoint lee **únicamente** los `steam_id` que tienen membresías activas (`is_active == True`) y los sincroniza contra los Reserved Slots nativos del servidor de juego.
  - Si un administrador requiere saltar la cola, se le otorga una membresía VIP permanente con `end_time = NULL`.

## 2. Roles de Dominio (Permisos e Identidad)

Los roles determinan la jerarquía de un usuario dentro del bot y la comunidad de Discord, así como sus facultades de administración.

- **Modelo Nativo**: Se almacenan en la tabla `roles` (`code`, `name`, `role_type`, `discord_role_id`) y se asocian a los jugadores mediante la tabla `player_roles`.
- **Tipología**:
  - `SYSTEM`: Administradores y Supervisores. Tienen acceso total a los comandos administrativos.
  - `VIP`: Roles que acompañan a las membresías pagas o donaciones.
  - `PUBLIC`: Roles cosméticos o informativos para la comunidad.
  - `SPECIAL`: Roles conmemorativos o de eventos especiales.
- **Unificación Administrativa**:
  - No existe distinción funcional entre "Owner" y "Admin". Todo el equipo con permisos de gestión se organiza bajo la categoría administrativa **ADMIN / SUPERVISOR**.

## 3. Comandos de Gestión (Entidades Primero)

- `/membership add <usuario> <tipo> <dias> [observacion]`: Otorga una nueva membresía.
- `/membership list`: Lista todas las membresías activas y pasadas.
- `/membership edit <id_membresia> ...`: Edita una membresía existente.
- `/membership remove <id_membresia>`: Elimina una membresía.
- `/membership sync`: Fuerza la sincronización inmediata de roles y slots.
- `/membership export`: Exporta bajo demanda todas las membresías a CSV con URL de descarga directa desde la API.
- `/roles register <codigo> <nombre> <rol_discord> <tipo>`: Registra o actualiza un rol en la base de datos.
- `/roles list`: Consulta todos los roles registrados en el sistema.
- `/roles assign <usuario> <rol>`: Asigna un rol especial a un jugador.
- `/roles remove <usuario> <rol>`: Remueve un rol especial de un jugador.

## 4. Sincronización Bidireccional de Discord

El bot de Discord reconcilia los roles de los usuarios de forma autónoma mediante la tarea `membership_monitor` (cada 60 segundos):
1. El bot solicita el estado actualizado de membresías a `/v1/db/sync_memberships`.
2. La API desactiva cualquier membresía vencida (`end_time < now`) y actualiza los slots reservados de RCON.
3. El bot compara los roles que cada usuario de Discord posee actualmente en el servidor contra lo que la base de datos dictamina.
4. Otorga los roles faltantes y remueve los roles que hayan expirado.
5. **Whitelist de Protección**: Los usuarios configurados en `/whitelist` nunca son despojados de sus roles por el monitor automático.

## 5. Exportación y Resguardo de Datos

- **Backups Automáticos en VPS**: La API RCON ejecuta una rutina periódica en segundo plano (`db_backup_loop`) cada 12 horas que genera un volcado transaccional completo en formato SQL estándar en `data/backups/` (`backup_<timestamp>.sql` y `latest.sql`) aplicando una política de retención automática de 14 días.
- **Exportación CSV On-Demand (`/membership export`)**: Genera de forma asíncrona un archivo CSV (`memberships_export_<timestamp>.csv`) con codificación UTF-8 con BOM (`utf-8-sig`) para compatibilidad nativa con Microsoft Excel y Google Sheets. El bot devuelve un enlace firmado con token HMAC-SHA256 válido por 30 minutos, permitiendo la descarga directa desde la API sin saturar Discord con transferencias de archivos pesados.
