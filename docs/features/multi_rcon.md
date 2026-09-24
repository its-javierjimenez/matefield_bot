# Gestión Multi-Servidor RCON

El sistema de **Multi-RCON** de Matefield permite conectar, monitorizar y administrar $N$ servidores de juego de forma simultánea desde una única base de datos PostgreSQL y un bot centralizado de Discord.

---

## 1. Arquitectura y Almacenamiento en Base de Datos

Cada servidor RCON se persiste en la tabla `rcon_servers` gestionada vía Alembic (`g3c4d5e6a7b8_add_rcon_servers_table`):

| Campo | Tipo | Descripción |
| :--- | :--- | :--- |
| `id` | `INTEGER` (PK) | Identificador único del servidor. |
| `name` | `VARCHAR(120)` | Nombre descriptivo (personalizado o autocompletado del RCON). |
| `ip` | `VARCHAR(255)` | Dirección IP o dominio del host del juego. |
| `port` | `INTEGER` | Puerto donde escucha el servicio RCON. |
| `password` | `VARCHAR(255)` | Contraseña administrativa RCON. |
| `scheme` | `VARCHAR(10)` | Protocolo (`http` o `https`, default `http`). |
| `is_active` | `BOOLEAN` | Si está activo para sincronizaciones periódicas (default `True`). |
| `is_default` | `BOOLEAN` | Si es el servidor predeterminado para consultas unitarias (default `False`). |
| `created_at` | `DATETIME` | Marca de tiempo UTC de registro. |
| `updated_at` | `DATETIME` | Marca de tiempo UTC de última modificación. |

### Propiedad `base_url`
El modelo calcula dinámicamente la URL base: `{scheme}://{ip}:{port}`.

---

## 2. Pool de Conexiones (`RCONManager`)

Para optimizar el uso de recursos y evitar crear múltiples sesiones HTTP innecesarias:
- `RCONManager.get_client(base_url, password)`: Mantiene un pool en memoria indexado por `(base_url, password)`.
- `RCONManager.get_all_active_servers(session)`: Retorna la lista de tuplas `(RconServer, RCONClient)` de todos los servidores activos.
- `RCONManager.get_default_server(session)`: Retorna el servidor marcado con `is_default=True` o el primer activo disponible.

### Retrocompatibilidad transparente con `.env`
Si la tabla `rcon_servers` está vacía (por ejemplo, en despliegues iniciales o servidores locales sin configurar), `RCONManager` realiza un fallback automático utilizando `RCON_URL` y `RCON_PASSWORD` definidos en las variables de entorno (`.env`), garantizando que ninguna funcionalidad preexistente se rompa.

---

## 3. Sincronización Distribuida y Tolerancia a Fallos

Tanto las **membresías VIP (slots reservados)** como los **baneos de jugadores** se sincronizan en **todos** los servidores RCON activos:

1. **VIP Reserved Slots (`MembershipsService.sync_memberships_logic`)**:
   - Obtiene todos los Steam IDs con membresía activa en la base de datos.
   - Itera por cada servidor RCON activo y actualiza `DefaultReservedPlayerIds`.
   - Si un servidor está temporalmente apagado o no responde, se captura la excepción individualmente, se registra el error y se continúa sincronizando el resto de la flota.
2. **Baneos (`BansService.sync_bans` y `ban_player`)**:
   - **Absorción**: Consulta los baneos existentes en todos los servidores RCON y absorbe en la base de datos cualquier veto que no estuviera registrado.
   - **Propagación**: Distribuye la lista combinada de baneos hacia todos los servidores RCON activos.
   - **Baneo en tiempo real**: Cuando un moderador ejecuta un ban, se expulsa/veta al jugador en todos los servidores activos simultáneamente.

---

## 4. Endpoints de la API REST (`/api/v1/rcon-servers`)

| Método | Endpoint | Descripción |
| :--- | :--- | :--- |
| `GET` | `/api/v1/rcon-servers` | Lista todos los servidores RCON registrados en BD. |
| `POST` | `/api/v1/rcon-servers` | Registra un nuevo servidor. Si se omite `name`, consulta el status del RCON para autocompletar el nombre real del servidor. |
| `GET` | `/api/v1/rcon-servers/{id}` | Obtiene los detalles de un servidor específico. |
| `PUT` | `/api/v1/rcon-servers/{id}` | Modifica parámetros (IP, puerto, contraseña, estado, default, etc.). |
| `DELETE` | `/api/v1/rcon-servers/{id}` | Elimina un servidor de la base de datos. |
| `POST` | `/api/v1/rcon-servers/{id}/test` | Ejecuta un ping diagnóstico (latencia, mapa, jugadores online, estado de conexión). |
| `POST` | `/api/v1/rcon-servers/sync-all` | Dispara la sincronización manual inmediata de VIPs y baneos en toda la flota de servidores. |

---

## 5. Comandos de Discord (`/rcon`)

Todos los comandos requieren rol de Administrador (`admin_only`):

- **`/rcon list`**: Muestra tarjetas interactivas con todos los servidores configurados, sus URLs, IDs, estado (`🟢 Activo` / `🔴 Inactivo`) y si es predeterminado (`⭐`).
- **`/rcon add ip puerto password [nombre] [esquema] [activo] [default]`**: Da de alta un servidor. Si no escribes nombre, el bot contacta al servidor y le pone automáticamente el nombre del juego.
- **`/rcon test server_id`**: Diagnóstico instantáneo con latencia en milisegundos, mapa en curso y cantidad de jugadores actuales sobre máximos.
- **`/rcon edit server_id [nombre] [ip] [puerto] [password] [esquema] [activo] [default]`**: Modifica cualquier configuración de un servidor existente.
- **`/rcon remove server_id`**: Borra el servidor de la base de datos.
- **`/rcon sync_all`**: Fuerza la sincronización de slots VIP y baneos en todos los servidores activos y devuelve un resumen visual.
