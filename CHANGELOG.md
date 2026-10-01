# Changelog

Todos los cambios notables en este proyecto serán documentados en este archivo.

El formato se basa en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/)
y este proyecto se adhiere a [Semantic Versioning (SemVer 2.0.0)](https://semver.org/lang/es/).

---

## [1.4.0] - 2026-10-01

### Agregado
- **Motor Multi-RCON para Producción**:
  - Soporte completo para múltiples instancias de servidores de juego mediante la tabla `rcon_servers`.
  - Scoping inteligente de sincronización: membresías globales (`server_id = NULL`) se aplican a todos los servidores activos; membresías específicas (`server_id = N`) se sincronizan únicamente con el servidor asignado.
  - Mecanismo de fallback transparente a credenciales de entorno `.env` en caso de no existir servidores registrados en base de datos.
  - Concurrencia controlada con cerraduras asíncronas (`_config_lock`) por servidor para evitar sobreescrituras en `ServerSettings.ini`.
- **Sistema de Puntos y Recompensas**:
  - Nuevo servicio `RewardsService` con acumulación de puntos, redención de beneficios y entrega inmediata de roles verificados.
  - Suite de pruebas de simulación de ejecuciones concurrentes y verificaciones de integridad financiera.
- **Vinculación Segura de Steam desde Discord**:
  - Flujo seguro de vinculación mediante interacción de Discord con tokens firmados de corta duración.
  - Redirección a URLs limpias tras el callback de Steam OpenID evitando exposición de tokens en el historial del navegador.
  - Enlace al canal de soporte oficial (`DISCORD_REQUEST_HELP_CHANNEL_URL`) en pantallas de error contextual.
- **Documentación de Configuración (.env.example)**:
  - Reestructuración integral y documentación exhaustiva de variables de entorno segmentadas en: `API`, `BOT` y `AMBOS` (compartidas).

### Cambiado
- **Control de Tareas en Segundo Plano**:
  - Ciclos de mantenimiento asíncronos en `lifespan` de FastAPI con cancelación limpia y apagado coordinado del pool de conexiones RCON.
- **Configuración Centralizada**:
  - Consolidación de variables en `SecuritySettings` en `src/config/security.py` para prevenir accesos tempranos no inicializados de `os.environ`.

### Corregido
- **Mocks de Pruebas Unitarias**:
  - Corrección en `test_steam_auth.py` para parchear atributos en el singleton `ENVIRONMENT_SETTINGS.SECURITY_SETTINGS` en lugar de variables de entorno volátiles.
  - Compatibilidad de aserciones en `test_interaction_link.py` para códigos de estado de autenticación.
- **Estabilidad de la Suite de Tests**:
  - Cobertura total alcanzada con **100% de pruebas aprobadas** en `api_rcon` y `discord_bot`.

---

## [1.3.0] - 2026-09-26

### Agregado
- **Identidad Visual MATEFIELD en Steam Auth**:
  - Integración de activos oficiales: `BANNER_ICONO_SERVIDOR.png`, `BANNER_FONDO_INVITACION.png` y `steam_icon_black.png`.
  - Estética táctica militar moderna con paleta oscura carbón (`#0f1115`) y verde táctico (`#22c55e`).
  - Montaje de rutas `/static` y `/api/static` en FastAPI para distribución de recursos estáticos.
  - Plantillas interactivas `success_callback.html` y `error_callback.html` con copiado de Steam ID y diagnóstico contextual.
- **Binding de Datos Reales de Usuario**:
  - Token HMAC-SHA256 extendido con metadatos de usuario (`discord_username`, `discord_tag`, `discord_avatar`).
  - Fallback asíncrono hacia la API REST de Discord para resolución de perfiles y avatares.
  - Captura y persistencia de perfiles reales de Steam Community (`personaname`, `avatarfull`).
- **Servicio `AuthPageService`**:
  - Desacoplamiento de la renderización HTML con caché en memoria y resolución de plantillas.

---

## [1.2.0] - 2026-09-24

### Agregado
- **Sincronización RCON y Concurrencia**:
  - Implementación de `_config_lock` (`asyncio.Lock`) en `RCONClient` para serializar modificaciones atómicas en `ServerSettings.ini`.
  - Soporte de slots reservados sin limitación artificial (136+ VIPs garantizados).
  - Detección directa de baneos vía endpoint nativo `GET /v1/bans` del servidor Wardogs.
- **Ciclo de Vida de Suscripciones Tebex**:
  - Manejo del evento `recurring-payment.ended` manteniendo membresía activa hasta agotar la fecha prepagada (`end_time > now`).
  - Revocación estricta reservada para eventos de contracargo o disputas bancarias (`payment.refunded`, `payment.dispute.lost`).
  - Idempotencia en procesamiento de webhooks con registro transaccional en `payment_records`.
- **Modelo de Dominio (DDD)**:
  - Separación estricta entre Membresías (slots temporales en juego) y Roles (identidad en Discord y permisos del sistema).
  - Unificación de jerarquía administrativa bajo la tipología `SYSTEM` (eliminando rol legacy Owner).
  - Asociación de `membership_types` a `roles.id` con soporte de doble precio (`base_price_usd` y `price_usd`).
  - Preservación de roles especiales honoríficos (`special_role_id`) inmunes a la expiración de membresías.
- **Backups Automatizados**:
  - Volcados completos PostgreSQL cada 12 horas en `backups/sql/` con retención rotativa y actualización de enlace `latest.sql`.
