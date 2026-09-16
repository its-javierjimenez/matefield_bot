# 📋 Server RCON Automation - Project Tracking

Este documento mantiene un registro del progreso, las tareas completadas y las características pendientes del proyecto para mantener un tracking claro de lo que se va haciendo.

## ✅ Tareas y Características Completadas

- **Base de Datos:** Migración de estructura completada (`cash_earned` y correcciones menores).
- **Match Players:** El comando `/match players` fue refactorizado. Ahora exporta la lista de los +100 jugadores en un archivo `.md` adjunto para evadir el límite de 4096 caracteres de Discord, sin cortar las IDs.
- **Leaderboard:** Se arregló el comando `/db leaderboard`. Ahora verifica dinámicamente si el usuario está vinculado a Discord (muestra la mención) o va a buscar su nombre de Steam directamente a la API si no está vinculado.
- **Sincronización de Roles a Membresías:** Corrección del endpoint y la lógica del comando `/force_sync_roles_to_memberships`. Funciona correctamente mapeando roles de Discord hacia la base de datos (exclusivo para usuarios que ya vincularon sus cuentas).
- **Mensajes de Bienvenida (VIP/ADMIN):** Se perfeccionó el sistema de saludos in-game. Ahora el bot formatea el mensaje de forma dinámica ("El ADMIN/VIP [Nombre] se conectó: ..."), tiene un límite de 60 caracteres y cuenta con una **vista previa interactiva** con botones en Discord. Además, se arregló el bug del "VIP Infinito" validando siempre que la membresía no esté vencida en la Base de Datos.
- **Sistema Anti-Hacks (KPM):** Implementación del comando `/monitor_hacker [SteamID]` que levanta una tarea de actualización cada 5 segundos y calcula matemáticamente las *Kills per Minute* (KPM) con su propia alerta si sobrepasa el límite sugerido. Incluye botón interactivo de frenado.

## ⏳ Tareas Pendientes / Por Hacer

- **Mensaje Persistente "Live Status":** Reemplazar el reporte tradicional del servidor por un sistema donde el bot mantenga **un único mensaje fijado** en un canal y lo vaya editando cada 10 segundos con el estado de la partida, evitando hacer spam.
- **Economía - Registro de Gastos:** En `tasks.py` hay un TODO pendiente para registrar en una tabla el historial de compras (`stats_history`) cuando se detecta que a un jugador se le descontó cash.
- **Campaña de Vinculación de Cuentas:** (Tarea de comunidad) Avisarle a todos los jugadores del servidor que utilicen el comando `/link_account` con su SteamID. Sin esto, el bot no puede dar las membresías automáticas por roles.

---
*Este archivo se puede ir actualizando a medida que se agreguen o completen nuevos requerimientos.*
