# Manual de Comandos de Discord

El bot de Discord utiliza Slash Commands (comandos de barra `/`) para gestionar la base de datos y controlar el servidor de juego mediante RCON. Los comandos están organizados en grupos (plugins) según su propósito.

> **Nota:** La mayoría de estos comandos están protegidos y requieren el rol de Administrador (`ADMIN_ROLE_ID`) o permisos de Administrador en Discord para ser ejecutados.

---

## 🎮 Comandos de Cuenta de Jugador (`/player`)
Comandos orientados a la experiencia del usuario regular o VIP.

- `/player steam_id`
  Vincula tu cuenta de Discord con tu `Steam ID`. Este es el primer paso indispensable para recibir membresías o roles.
- `/player profile`
  Muestra un panel completo (Embed) con tus estadísticas históricas y vigentes (Nivel VIP, Rol, Kills, Deaths).
- `/player check_vip`
  Verifica si posees una membresía VIP activa y cuándo expira.
- `/player welcome_message_set`
  *(Requiere VIP o ADMIN)* Permite establecer un mensaje personalizado que el bot anunciará en el servidor de juego cuando te conectes.

---

## 🛡️ Comandos de Administración de Servidor (`/admin`)
Comandos para moderar el servidor de juego en tiempo real. Todos requieren permisos de **Admin**.

- `/admin map`
  Cambia el mapa actual del servidor a uno nuevo de forma inmediata.
- `/admin end_match`
  Fuerza la finalización de la partida en curso, procesando estadísticas y cerrando la ronda.
- `/admin broadcast`
  Envía un mensaje global (Broadcast) que aparecerá en el centro de la pantalla de todos los jugadores en el servidor.
- `/admin monitor`
  Inicia el "Hacker Monitor" sobre un jugador específico. Monitorea sus Kills Per Minute (KPM) y actualiza un panel en Discord cada 5 segundos.
- `/admin stop_monitor`
  Detiene el monitoreo en tiempo real de un jugador.
- `/admin ban`
  Banea a un usuario del servidor de juego y del servidor de Discord (asignándole un rol de castigo).
- `/admin pardon`
  Desbanea a un usuario (Unban) y restaura sus permisos originales.

---

## 🗄️ Comandos de Base de Datos (`/db`)
Comandos para gestionar registros, membresías y datos puros. (Requieren Admin).

- `/db role add` / `/db role remove`
  Añade o remueve un rol específico de Discord a la cuenta de un jugador en la base de datos.
- `/db sync_roles`
  Fuerza una sincronización manual inmediata de todos los roles de Discord hacia todos los miembros, basándose en lo que dice la BD.
- `/db add_membership`
  Otorga una membresía VIP a un jugador (requiere especificar tipo de VIP y duración en días).
- `/db remove_membership`
  Revoca una membresía VIP activa.
- `/db query_discord` / `/db query_steam`
  Realiza consultas forenses a la base de datos para ver el estado crudo (raw) de un jugador usando su Discord o Steam ID.

---

## ⚙️ Comandos de Configuración (`/config`)
Comandos diseñados para los dueños (`OWNER`) para configurar el comportamiento del ecosistema.

- `/config admin_role`
  Establece cuál es el rol de Discord que el bot considerará como "Administrador Nivel 1" (Aquel que puede usar los comandos `/admin` y `/db`).
- `/config match_channel`
  Define el canal de texto donde el bot publicará los resultados finales y MVP de las partidas cuando terminen.
- `/config announcement_channel`
  Define el canal para anuncios globales.
- `/config vip list` / `add` / `remove`
  Configura qué roles de Discord son considerados "Roles VIP" permitidos.
- `/config vip_map add` / `remove`
  Enlaza el nombre de una membresía en la base de datos (ej: `VIP_COMUN`) con el ID de un Rol específico de Discord, indicándole al bot qué rol dar cuando alguien compre ese paquete.
- `/config ban_map add` / `unmap`
  Enlaza una duración de baneo (en días) con un Rol de Castigo en Discord (ej: 0 días = Rol Baneado Permanente).
- `/config sync_whitelist add` / `remove`
  Maneja la "Lista Blanca" de usuarios de Discord (generalmente dueños o bots) a los cuales el bot de sincronización NUNCA debe modificarles o quitarles roles automáticamente.
