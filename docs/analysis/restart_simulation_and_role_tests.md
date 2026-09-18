# Reporte de Pruebas: Jerarquía de Roles DDD y Simulación de Reinicios Programados

Este informe documenta las pruebas exhaustivas realizadas en el entorno de desarrollo local sobre:
1. **Jerarquía y Resolución de Roles DDD** (con eliminación definitiva del rol ambiguo "Owner" y unificación en "ADMIN / SUPERVISOR").
2. **Llenado de Partida Masiva en RCON** (80 jugadores simultáneos distribuidos en facciones).
3. **Simulación de Reinicios Programados del Servidor** (análisis de comportamiento durante caída, resiliencia de datos y recuperación automática).

---

## 1. Pruebas de Roles con Usuarios de Prueba

### Objetivos Validados:
- Registrar roles con tipología de dominio:
  - `SYSTEM`: Roles administrativos (`ADMIN_TEST`, `SUPERVISOR_TEST`).
  - `VIP`: Roles de acceso prioritario (`VIP_TEST`).
  - `PUBLIC`: Roles comunes de comunidad (`PUBLIC_TEST`).
- Asignación de roles mediante **Código de Rol** y mediante **Discord Role ID**.
- Eliminación del rol "Owner": verificar que cualquier rol `SYSTEM` (e incluso registros antiguos con código `OWNER`) resuelva semánticamente a `ADMIN` como rol primario.

### Resultados de Ejecución:
- **Registro de Roles**:
  - `SUPERVISOR_TEST` (SYSTEM): ✅ HTTP 200
  - `ADMIN_TEST` (SYSTEM): ✅ HTTP 200
  - `VIP_TEST` (VIP): ✅ HTTP 200
  - `PUBLIC_TEST` (PUBLIC): ✅ HTTP 200
- **Asignación a Jugadores de Prueba**:
  - `Player A` (`76561198999000001` - Discord `999000001`): Asignado `SUPERVISOR_TEST`.
    - `active_role`: **`ADMIN`**
    - `special_roles`: `['SUPERVISOR_TEST']`
    - `is_owner`: No existe rol Owner; permisos administrativos unificados.
  - `Player B` (`76561198999000002` - Discord `999000002`): Asignado `VIP_TEST` vía Discord Role ID `333333333333333333`.
    - `active_role`: **`VIP`**
    - `special_roles`: `['VIP_TEST']`
  - `Player C` (`76561198999000003` - Discord `999000003`): Asignado rol legacy `OWNER_LEGACY` (SYSTEM).
    - `active_role`: **`ADMIN`** (verificación de retrocompatibilidad y erradicación del rol "Owner").

---

## 2. Simulación de Partida Masiva (80 Jugadores en RCON)

Se actualizó el emulador `mock_rcon` para simular una partida completa de 80 soldados distribuidos equitativamente entre las tres facciones del juego: `Lonestar`, `Manticore` y `Valkyre`.

### Métricas Observadas:
- **`GET /v1/status`**: Reportó `players: {"current": 80, "max": 100}`, `map: "Bakurani"`.
- **`GET /v1/players`**: Lista completa de 80 jugadores con telemetría en tiempo real (Kills, Deaths, Cash y Ping individual).
- **Consumo de la API**: `GET /api/v1/players` procesó los 80 jugadores en < 15ms sin problemas de memoria o serialización.
- **Monitores del Bot**: `Economy Monitor` rastreó el flujo de dinero de todos los soldados en la partida activa.

---

## 3. Simulación de Reinicios Programados del Servidor

Para replicar con precisión un reinicio programado de mantenimiento del servidor de juego, se apagó el contenedor RCON simulando la caída de red y el apagado del proceso de juego, observando el comportamiento durante la caída y tras el encendido.

### Fase 1: Pre-Reinicio (Servidor en Línea)
- Partida activa en mapa `Desert Strike` con 80 jugadores.
- `sync_memberships` y `sync_bans` operando con HTTP 200.
- Membresías VIP sincronizadas en la base de datos PostgreSQL.

### Fase 2: Caída del Servidor (Durante el Reinicio)
- **Acción**: `docker stop mock_rcon` (12 segundos de desconexión total).
- **Comportamiento de la API RCON**:
  - `sync_engine`: Capturó limpiamente `ClientConnectorDNSError` / `ConnectionRefusedError` en el bucle de polling.
  - El proceso FastAPI **permaneció en ejecución** sin crash ni bloqueos de hilos.
  - Los endpoints de base de datos (`/db/players`, `/db/memberships`) continuaron respondiendo con normalidad.
- **Comportamiento del Bot de Discord**:
  - `Match Monitor` y `VIP Monitor` registraron en log el error de conexión HTTP al consultar el servidor caído.
  - La conexión Gateway con Discord **no se cayó** ni se reinició el bot.
- **Integridad de Base de Datos**:
  - Cero pérdida o corrupción de datos en PostgreSQL.

### Fase 3: Encendido del Servidor (Recuperación Automática)
- **Acción**: `docker start mock_rcon`.
- **Detección Automática**:
  - En el siguiente ciclo de polling (segundo 10), `sync_engine` restableció la conexión HTTP/REST con el servidor RCON de forma totalmente autónoma.
  - Detectó la transición limpia de mapa (`Old map: Desert Strike, New map: Bakurani (Rotation 0)`).
  - `Match Monitor` del bot detectó inmediatamente la nueva partida `Bakurani_0` y actualizó los monitores.
  - `sync_memberships` reinyectó con éxito los slots reservados en la memoria del servidor de juego.
  - Cero intervención manual requerida.

---

## 4. Conclusión

El ecosistema demostró ser **100% resiliente** ante caídas y reinicios del servidor RCON:
- El modelo DDD unificado de roles simplifica la administración, eliminando inconsistencias previas de permisos.
- El sistema de polling y las tareas asíncronas de Discord toleran ventanas de desconexión sin degradar el bot.
- La recuperación de servicios tras un reinicio es inmediata y completamente automática.
