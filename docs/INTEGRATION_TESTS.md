# Guía de Testing de Integración e Infallibilidad

Esta guía documenta la suite de pruebas de integración desarrollada para certificar el funcionamiento infalible del ecosistema Matefield Bot.

## 1. Resumen de la Suite

- **Total de pruebas automatizadas**: 72 pruebas (55 en `api_rcon` + 17 en `discord_bot`).
- **Tiempo total de ejecución**: < 3.5 segundos.
- **Tasa de éxito**: 100% (72/72 aprobadas).
- **Framework**: `pytest` + `pytest-asyncio` + `unittest.mock` (sin fixtures pesadas, minimalista y determinista).

---

## 2. Pruebas de Integración Críticas (`test_integration_infallibility.py`)

Ubicación: `apps/api_rcon/tests/test_integration_infallibility.py`

### 2.1. Concurrencia RCON y Mutex de Configuración (`test_concurrent_vip_and_ban_sync_atomicity`)
- **Escenario**: 136 miembros VIP activos en la base de datos sincronizan simultáneamente con una tarea en segundo plano que sincroniza 50 baneos en el archivo `ServerSettings.ini`.
- **Qué valida**:
  - El mutex `_config_lock` serializa todas las lecturas y escrituras de configuración.
  - Ninguna escritura intermedia trunca los 136 slots reservados ni desconfigura los baneos.
  - El archivo final contiene todos los 136 VIPs y los 50 baneos intactos, sin corrupción de saltos de línea (`\r\n`).

### 2.2. Prevención de Resurrección de Baneos (`test_unban_player_prevents_resurrection_and_cleans_rcon`)
- **Escenario**: Un jugador desbaneado formalmente por la administración (`unban_player`) todavía figura en el listado residual del servidor RCON cuando se dispara la sincronización automática periódica (`sync_bans`).
- **Qué valida**:
  - La API detecta que el jugador fue desbaneado previamente en base de datos (`unbanned_at != None`).
  - No resucita el baneo como activo en la base de datos.
  - Invoca el endpoint nativo `DELETE /v1/bans/{steamId}` en el servidor de juego para purgar el residuo.

### 2.3. Ciclo de Compra Tebex de Extremo a Extremo (`test_e2e_tebex_purchase_to_discord_sync_payload`)
- **Escenario**: Recepción de un webhook firmado `payment.completed` con payload anidado de Tebex.
- **Qué valida**:
  - Verificación estricta de firma HMAC-SHA256.
  - Creación atómica del perfil `Player` y asignación de la membresía con `tebex_transaction_id`.
  - La sincronización posterior `sync_memberships_logic()` retorna la carga útil lista para que el bot de Discord asigne los roles de suscriptor.
  - Comprobación de idempotencia: un reenvío con el mismo `transaction_id` no duplica los beneficios.

### 2.4. Cancelación de Suscripción con Período Pagado Remanente (`test_e2e_recurring_cancellation_preserves_active_period`)
- **Escenario**: Un usuario con suscripción recurrente mensual cancela su débito en Tebex (`recurring-payment.ended`) faltando 20 días de vigencia prepaga.
- **Qué valida**:
  - La membresía **no** se anula inmediatamente.
  - Se mantiene activa (`is_active = True`) hasta la fecha `end_time` acordada.
  - Los slots de RCON y roles en Discord permanecen activos hasta su expiración programada.

### 2.5. Preservación de VIPs de DB en Comandos Directos de Servidor (`test_server_service_add_remove_reserved_slot_preserves_db_vips`)
- **Escenario**: Un administrador agrega o retira un slot reservado manual mediante `/admin slot add/remove`.
- **Qué valida**:
  - `ServerService` consulta la base de datos PostgreSQL para incluir y combinar todos los miembros activos registrados.
  - Asegura que las adiciones o remociones puntuales no descarten a los miembros VIP existentes en la base de datos al regenerar la lista de `DefaultReservedPlayerIds`.

---

## 3. Pruebas de Monitores de Discord (`test_integration_tasks.py`)

Ubicación: `apps/discord_bot/tests/test_integration_tasks.py`

### 3.1. Soporte Multi-Guild en Expiración de Baneos (`test_check_expired_bans_multi_guild`)
- **Qué valida**: Cuando un baneo expira en la base de datos, `check_expired_bans` desbanea en la API y remueve los roles de sanción y restituye el rol de desbaneo en **todas** las guilds donde opera el bot, no solo en la primera del diccionario de caché.

### 3.2. Sincronización y Reconciliación de Roles de Ban (`test_sync_ban_roles_assigns_and_revokes`)
- **Qué valida**: `sync_ban_roles` asigna el rol permanente de veto y revoca de forma cruzada el rol previo de perdón (`BAN_UNSET_ROLE_ID`).

### 3.3. Sincronización de Membresías y Respeto de Whitelist (`test_membership_monitor_syncs_roles_and_respects_whitelist`)
- **Qué valida**:
  - `membership_monitor` retira roles de membresías vencidas y añade roles de membresías activas.
  - Los usuarios registrados en `SYNC_WHITELIST` son omitidos y protegidos de cualquier despojo de roles.
  - Los roles especiales permanentes y los roles de verificación (`LINK_ROLE_ID`) jamás son removidos por la sincronización de suscripciones temporales.

---

## 4. Ejecución de las Pruebas

Para correr la suite completa en el entorno de desarrollo local:

```bash
# 1. Pruebas de API RCON y Servicios
uv run pytest apps/api_rcon/tests/

# 2. Pruebas de Discord Bot y Tareas de Sincronización
uv run pytest apps/discord_bot/tests/

# 3. Ejecución directa con salida detallada
uv run pytest -v apps/api_rcon/tests/test_integration_infallibility.py
uv run pytest -v apps/discord_bot/tests/test_integration_tasks.py
```
