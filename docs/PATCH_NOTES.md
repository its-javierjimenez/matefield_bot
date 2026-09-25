# 📋 Matefield Bot & API RCON — Patch Notes

**Versión:** 1.2.0 (Producción)  
**Fecha:** 24 de Septiembre, 2026  
**Rama:** `main` / `dev`

---

## 🚀 Resumen Ejecutivo

Esta actualización introduce mejoras críticas de estabilidad, concurrencia y seguridad en la sincronización entre la Base de Datos, el servidor de juego Wardogs (RCON) y Discord. Además, se culmina la integración de pagos automatizados con Tebex, la vinculación fluida de cuentas mediante Steam OpenID y el soporte para servidores múltiples (Multi-RCON).

---

## 🛠️ Correcciones Críticas y Estabilidad

### 🔒 Concurrencia RCON: Fin a la limitación de 128 VIPs
- **Causa resuelta:** La sincronización de membresías y la sincronización de baneos corrían de forma concurrente cada 5 minutos, sobrescribiéndose mutuamente el archivo `ServerSettings.ini` mediante llamadas simultáneas a `PUT /v1/config`.
- **Implementación:**
  - Se introdujo `_config_lock` (`asyncio.Lock`) en `RCONClient` para serializar de manera atómica las modificaciones de configuración.
  - Sincronización íntegra de todos los slots reservados activos sin importar la cantidad (136+ VIPs garantizados).
  - `add_reserved_slot` y `remove_reserved_slot` ahora combinan y respetan las membresías activas de la base de datos, en lugar de sobreescribir el archivo de configuración basándose en la memoria volátil del servidor de juego.
  - Normalización de retornos de carro (`\r\n` a `\n`) para prevenir acumulación y corrupción de formato INI en Unreal Engine.

### 🛡️ Detección Directa y Sincronización de Bans
- `get_bans()` ahora consulta directamente la ruta nativa `GET /v1/bans` del servidor Wardogs (CL-501228), garantizando la detección inmediata de los baneos aplicados dentro del juego o vía consola administrativa, con fallback automático a la inspección de `ServerSettings.ini`.

### 💳 Tebex: Manejo de Ciclo de Vida de Suscripciones
- **Fin de suscripción respetuoso (`recurring-payment.ended`):** Si un jugador cancela la renovación automática en Tebex o PayPal, su membresía **ya no se revoca de inmediato**. Se mantiene activa hasta agotar su fecha de vencimiento prepagada (`end_time > now`), desvinculando únicamente el ID de suscripción para detener cargos futuros.
- **Revocación exclusiva en reembolsos y disputas:** Las revocaciones inmediatas y la remoción de roles en Discord quedan estrictamente reservadas para eventos de contracargo o reembolso (`payment.refunded`, `payment.dispute.lost`).
- **Idempotencia total:** Manejo blindado contra entregas duplicadas de webhooks mediante control estricto de transacciones en `payment_records`.

---

## ✨ Nuevas Características

### 🎮 Vinculación de Cuentas vía Steam OpenID OAuth
- **Flujo Oficial y Seguro:** Los usuarios pueden vincular su cuenta de Discord con su cuenta de Steam haciendo clic en un botón interactivo que abre la autenticación oficial de Steam Web.
- **Comando `/player link`:** Envía un mensaje privado y efímero con el enlace directo y token de sesión único.
- **Canal Permanente `/player link_channel`:** Permite a los administradores fijar un panel persistente en un canal de bienvenida con un botón interactivo reutilizable para toda la comunidad.

### 🌐 Arquitectura Multi-RCON
- **Soporte Multiserver:** Capacidad de registrar y gestionar múltiples instancias de servidores de juego en la tabla `rcon_servers`.
- **Ruteo de Membresías por Servidor:** Las membresías pueden tener alcance global (`server_id = NULL`) o asignarse a un servidor específico (`server_id = N`).
- **Fallback Automático:** Si no hay servidores registrados en BD, el sistema opera de manera transparente usando las credenciales predeterminadas del archivo de entorno `.env`.

### 🏷️ Sistema Dinámico de Tipos de Membresía y Roles (DDD)
- **Roles y Membresías Dinámicas:** Creación y parametrización de tipos de membresías (`VIP_COMUN`, `VIP_EXPRESS`, `VIP_PERMANENTE`, etc.) directamente en BD sin necesidad de modificar el código fuente.
- **Preservación de Roles Especiales:** Los roles asignados como insignias o reconocimientos especiales (ej. VIP Fundador, Veterano) perduran en la cuenta del jugador independientemente del vencimiento del slot reservado.
- **Protección de Roles en Discord:** Los roles de vinculación y los roles de baneo están blindados contra remociones accidentales durante el barrido rutinario de roles de membresía.

### 💾 Backups Automatizados de Base de Datos
- Tarea en segundo plano en `api_rcon` que genera volcados completos SQL cada 12 horas.
- Almacenamiento rotativo en directorio `backups/sql/` con política de retención configurable y actualización de enlace simbólico / archivo `latest.sql`.

---

## 🧪 Cobertura de Pruebas Automatizadas

- **`api_rcon`:** 50 tests unitarios y de integración pasando al 100% (cobertura de webhooks Tebex, locks RCON, parsing INI, OpenID Steam, roles y sincronización).
- **`discord_bot`:** 14 tests unitarios pasando al 100% (comandos, cliente API y vistas interactivas).
