# Guía de Comandos de Matefield Bot

Aquí encontrarás el listado completo de todos los comandos de Discord disponibles, divididos por el nivel de acceso requerido para ejecutarlos. La arquitectura actual está orientada al manejo de RCON, membresías VIP y roles especiales sin depender de servicios externos.

---

## 🌎 Comandos Públicos
Estos comandos pueden ser utilizados por cualquier usuario del servidor, ya sea que tengan o no su cuenta de Steam vinculada al bot.

* **`/player link`**
  Genera un enlace único, privado y seguro para vincular la cuenta de Discord con la de Steam. Si ya estás vinculado, el bot te lo confirmará.
  *(Nota: Al vincularte, recibirás inmediatamente el rol de Discord de verificación ("LINK_ROLE_ID"). Si tu cuenta de Steam ya poseía membresías VIP o roles especiales en la BD, estos se aplicarán en el siguiente ciclo periódico de sincronización o de inmediato si un admin corre `/roles sync`).*

* **`/player link_channel`** *(Solo Admin para configurar)*
  Genera un panel público (embed con botón verde) en el canal donde se ejecuta. Cualquier jugador puede clickear el botón para recibir el enlace de vinculación por mensaje directo.

---

## 🔗 Comandos para Usuarios Vinculados
Exclusivos para aquellos jugadores que ya completaron el proceso de vinculación de Steam a través del bot.

* **`/player info`** *(Generalmente público, pero centrado en stats)*
  Muestra la información de un jugador (Puntos de seeding, kills, deaths).

* **`/player memberships`**
  Muestra el historial completo de membresías VIP asociadas a tu cuenta (activas, inactivas y expiradas).

---

## 🛡️ Comandos de Administrador
Comandos exclusivos para el Staff del servidor. Permiten gestionar la base de datos, configurar el bot, asignar membresías VIP y administrar roles en tiempo real de forma manual e interna.

### 🔗 Gestión de Cuentas de Jugadores
* **`/player unlink [usuario]`** *(Solo Admin)*
  Desvincula la cuenta de Discord especificada de su cuenta de Steam (o la del propio admin si no se pasa usuario), liberando el `discord_id` en la BD y retirando únicamente el rol de verificación (`LINK_ROLE_ID`) en Discord.
  *(Nota: Las membresías VIP, estadísticas y roles en la Base de Datos permanecen intactas asociadas al `steam_id`. Si se desea limpiar los roles de Discord de una cuenta antigua antes de desvincularla, el Staff debe usar `/roles remove_all @usuario`).*

### 🎭 Gestión de Roles Especiales (Base de Datos)
Estos comandos interactúan con la tabla de roles registrados en la Base de Datos.
* **`/roles give @usuario rol`**
  Le asigna un rol especial registrado en la BD a un jugador vinculado. El rol se impacta en tiempo real tanto en la Base de Datos como asignando el rol de Discord correspondiente.
* **`/roles remove @usuario rol`**
  Le quita un rol especial registrado a un jugador vinculado en tiempo real.
* **`/roles remove_all @usuario`**
  Limpieza de roles de Discord. Le retira al usuario en tiempo real absolutamente todos los roles administrados por el bot (roles vinculados, VIP y especiales).
  *(Aviso de arquitectura: Si el usuario continúa vinculado a su SteamID y tiene membresías vigentes en la BD, la tarea de sincronización periódica del bot le volverá a entregar los roles correspondientes al cabo de su ciclo. Por ello, este comando está diseñado para usarse justo antes de `/player unlink` cuando se atiende un cambio o traspaso de cuenta).*
* **`/roles register`**
  Registra un nuevo rol (Código, Nombre, Tipo y Rol de Discord asociado) en la base de datos para poder usarlo después.
* **`/roles list`**
  Muestra todos los roles registrados actualmente en la base de datos.
* **`/roles player_list rol`**
  Lista a todos los jugadores vinculados que poseen el rol especificado.
* **`/roles set_link`**
  Configura cuál es el Rol de Discord que se otorga automáticamente cuando un jugador se vincula exitosamente a través de `/player link`.
* **`/roles sync @usuario`**
  Fuerza una sincronización en tiempo real estilo manual ("commit/pull"). Revisa la base de datos y le asigna (o remueve) en Discord **exactamente** los roles que le corresponden por su estado de vinculación y membresías VIP o roles especiales. Ideal para aplicar roles de inmediato cuando se asiste a un usuario tras un cambio de cuenta.

### 💎 Gestión de Membresías (VIP)
Administración de VIPs, duración y privilegios de slots en el servidor. Todas las asignaciones, ediciones y remociones aplican los cambios de roles en Discord en tiempo real y son tenidas en cuenta por el motor de sincronización de RCON en segundo plano (poll RCON).
* **`/membership add @usuario tipo`**
  Le añade una membresía VIP a un jugador vinculado. Puedes especificar los días y si tiene rol especial o pertenece a un servidor específico. (Impacto en tiempo real de roles y base de datos).
* **`/membership edit id_membresia`**
  Edita los parámetros (días, tipo, estado activo/inactivo) de una membresía existente. (Impacto en tiempo real en roles).
* **`/membership remove id_membresia`**
  Elimina una membresía VIP de la base de datos permanentemente. Revoca los permisos en Discord si no tiene más membresías activas.
* **`/membership extend id_membresia dias`**
  Añade `X` cantidad de días a la membresía especificada.
* **`/membership compensate_all dias`**
  Extiende absolutamente todas las membresías activas por la cantidad de días especificados (útil para caídas del servidor generalizadas).
* **`/membership list`**
  Muestra una lista paginada de todas las membresías VIP actuales de la base de datos.
* **`/membership export`**
  Genera y descarga un archivo CSV con el reporte completo de todas las membresías.
* **`/membership sync`**
  Fuerza la ejecución global de sincronización. Recorre toda la base de datos y alinea los slots de RCON y los roles de Discord para todos los usuarios.

### 📦 Gestión de Paquetes VIP (Tipos)
Configuración del catálogo de VIPs que se pueden asignar manualmente.
* **`/membership_type create`**
  Crea un nuevo paquete VIP (ej. VIP_GOLD) definiendo duración predeterminada, cupos máximos, rol de Discord automático y alcance global o por servidor RCON. (Las dependencias de precios para ecommerce fueron eliminadas).
* **`/membership_type edit`**
  Modifica los detalles de un paquete VIP existente.
* **`/membership_type list`**
  Muestra todos los paquetes configurados actualmente en el catálogo.

### 🖥️ Gestión de Servidores RCON
Gestión de servidores de juego para el bot (para el poll en segundo plano).
* **`/rcon add ip puerto contraseña [nombre] [esquema] [activo] [default]`**
  Añade un nuevo servidor RCON a la base de datos.
* **`/rcon list`**
  Lista todos los servidores RCON registrados y muestra su estado de conexión.
* **`/rcon test id_servidor`**
  Realiza una prueba de conexión directa al servidor y muestra latencia y datos en vivo de jugadores conectados y colas.
* **`/rcon update id_servidor`**
  Actualiza datos del servidor (ip, puerto, password, etc).
* **`/rcon delete id_servidor`**
  Elimina un servidor RCON de la base de datos.
* **`/rcon sync`**
  Fuerza la inyección manual de comandos reservados (Slots VIP) al servidor seleccionado.

### ⚙️ Configuración General y Whitelist
* **`/config list`**
  Muestra la configuración interna del bot (rol linkeado, canales de match).
* **`/config announcement_channel`**
  Define el canal de Discord donde el bot enviará anuncios automáticos del servidor de juego.
* **`/config match_channel`**
  Define el canal donde se enviarán las estadísticas y resultados al terminar cada partida.
* **`/whitelist add @usuario` / `/whitelist remove @usuario`**
  Añade o remueve a un usuario de la "Lista Blanca". El bot **nunca** le quitará roles a los usuarios que estén en esta lista durante las sincronizaciones automáticas, incluso si no tienen VIP o se desvinculan (útil para fundadores o dueños).
