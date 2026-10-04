# Guía de Comandos de Matefield Bot

Aquí encontrarás el listado completo de todos los comandos de Discord disponibles, extraído directamente del código fuente y divididos por el nivel de acceso requerido para ejecutarlos.

---

## 🌎 Comandos Públicos
Estos comandos pueden ser utilizados por cualquier usuario del servidor, ya sea que tengan o no su cuenta de Steam vinculada al bot.

* **`/player link`**
  Genera un enlace único, privado y seguro para vincular la cuenta de Discord con la de Steam.
* **`/match status`**
  Muestra el estado de la partida actual en vivo en el servidor.
* **`/match players`**
  Muestra todos los jugadores actualmente conectados en la partida.
* **`/match leaderboard`**
  Muestra el top 10 de jugadores con mejor puntaje en la partida actual.
* **`/leaderboard list`**
  Muestra el Top 15 de los mejores jugadores históricos del servidor (Kills, Deaths o Dinero Generado).
* **`/server status`**
  Muestra el estado actual del servidor RCON y la rotación.

---

## 🔗 Comandos para Usuarios Vinculados
Exclusivos para aquellos jugadores que ya completaron el proceso de vinculación de Steam a través del bot.

* **`/player profile`**
  Muestra el perfil histórico de tu cuenta de Steam o el de otro jugador (Puntos, Kills, etc).
* **`/player memberships`**
  Muestra tu historial completo de membresías VIP (activas, inactivas y expiradas).
* **`/rewards balance`**
  Consulta tus puntos acumulados por tiempo de seeding en el servidor.
* **`/rewards catalog`**
  Explora el catálogo de recompensas disponibles para canjear con puntos.
* **`/rewards claim`**
  Canjea tus puntos por una recompensa del catálogo.

---

## 💎 Comandos Exclusivos (Solo VIP / Admin)
Comandos que requieren poseer una membresía VIP activa o privilegios de administración.

* **`/player welcome_message_set`**
  Establece un mensaje de bienvenida personalizado que el bot anunciará globalmente en el juego cada vez que entres al servidor.

---

## 🛡️ Comandos de Administrador
Exclusivos para el Staff. Permiten administrar cuentas, membresías, roles, RCON y configuración.

### 🔗 Gestión de Cuentas y Jugadores
* **`/player unlink [usuario]`**
  Desvincula la cuenta de Discord de Steam (retira el rol de link en Discord, no limpia roles VIP).
* **`/player list`**
  Lista a todos los jugadores registrados en la base de datos (Paginado).
* **`/player edit`**
  Edita la información interna de un jugador vinculado.

### 🎭 Gestión de Roles y Vinculación
* **`/roles give`** / **`/roles remove`** / **`/roles remove_all`**
  Añade o retira roles registrados en la BD, o realiza una limpieza total de roles a un usuario (útil antes de un unlink).
* **`/roles sync`**
  Fuerza la sincronización en Discord de los roles exactos que debería tener el usuario según la BD.
* **`/roles register`** / **`/roles list`** / **`/roles player_list`** / **`/roles set_link`**
  Gestión del catálogo interno de roles.
* **`/special_role add`** / **`/special_role remove`**
  Añade o retira un rol etiquetado como "SPECIAL" en la base de datos a un jugador.
* **`/player set_role`** / **`/player remove_role`**
  Asignación y remoción de roles directamente desde el comando del jugador.

### 💎 Gestión de Membresías VIP y Cupos
* **`/membership add`** / **`/membership edit`** / **`/membership remove`** / **`/membership extend`**
  Administración directa de membresías de jugadores.
* **`/membership compensate_all`**
  Extiende todas las membresías activas globalmente por "X" días.
* **`/membership list`** / **`/membership export`**
  Lista (paginado) o exporta a CSV el registro de membresías.
* **`/membership sync`**
  Sincronización global y masiva de membresías en BD con Discord y RCON.
* **`/membership_type create`** / **`/membership_type edit`** / **`/membership_type list`**
  Gestión del catálogo de paquetes VIP (ej. VIP_GOLD).
* **`/quota list`** / **`/quota set`**
  Configuración y revisión del límite de ocupación (cupos) de cada tipo de membresía.

### 🎁 Gestión de Recompensas (Rewards)
Todos bajo el grupo `/rewards admin`:
* **`set_threshold`** / **`set_rate`**: Configuran los requisitos para farmear puntos.
* **`add_item`**: Añade un ítem al catálogo.
* **`verify`** / **`deliver`** / **`refund`**: Gestión de tickets, códigos y devoluciones.
* **`give_points`**: Otorga o descuenta puntos manualmente.

### 🖥️ Gestión de RCON, Servidores y Partida
* **`/rcon add`** / **`/rcon list`** / **`/rcon edit`** / **`/rcon remove`** / **`/rcon test`** / **`/rcon sync_all`**
  Gestión del pool de servidores de juego.
* **`/server announce`**
  Envía un anuncio al servidor de juego mediante RCON.
* **`/server set_max_reserved`**
  Modifica en vivo el límite máximo de slots reservados del juego.
* **`/reserved_slots list`** / **`/reserved_slots add`** / **`/reserved_slots remove`** / **`/reserved_slots sync_status`**
  Gestión manual de la lista blanca de slots reservados en el servidor RCON.
* **`/hacker monitor`**
  Activa el monitoreo especial de KPM sobre un jugador para detectar posibles hacks.
* **`/match player_info`** / **`/match logs`**
  Información en vivo de los jugadores y auditoría de la partida.

### ⚙️ Configuración General y Utilidades
* **`/player link_channel`**
  Genera el panel visual en Discord con el botón "Vincular Steam".
* **`/config list`** / **`/config announcement_channel`** / **`/config match_channel`**
  Configuración de canales internos del bot.
* **`/whitelist add`** / **`/whitelist remove`**
  Protege a un usuario para que el bot NUNCA modifique sus roles en las sincronizaciones automáticas.
