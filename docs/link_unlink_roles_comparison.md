# Comparativa: Gestion Automatica vs Manual de Roles en Link y Unlink

Este documento detalla las implicaciones tecnicas, operativas y de experiencia de usuario entre dos modelos de gestion de roles para el bot de Matefield: automatizar la entrega y retiro de roles VIP directamente en `link` y `unlink`, o mantener dichas operaciones desacopladas mediante comandos explicitos de administracion (`/roles sync` y `/roles remove_all`).

---

## 1. Modelo de Datos y Fuentes de Verdad

Para comprender el flujo, es fundamental distinguir como se almacenan los datos:

* **Base de Datos (PostgreSQL)**: La entidad principal propietaria de los beneficios (membresias VIP, roles especiales, slots reservados de Squad, puntos de seeding y estadisticas) es el `steam_id`. El `discord_id` es un atributo secundario que vincula una cuenta de Discord con ese `steam_id`.
* **Servidor de Discord**: Los roles de Discord son etiquetas cosmeticas y de permisos de canal asignadas a un miembro dentro de la plataforma Discord.

---

## 2. Definicion de los Paradigmas

### Opcion A: Automatizacion Total en Link y Unlink (Event-Driven)

En este modelo, las acciones de vinculacion y desvinculacion sincronizan activamente el estado de los roles de Discord del usuario:

1. **Al vincular (`/player link`)**:
   * Se asigna el rol de Verificado (`LINK_ROLE_ID`).
   * Si el `steam_id` autenticado ya posee membresias VIP activas o roles especiales registrados en la base de datos, el sistema le otorga inmediatamente los roles de Discord correspondientes.
2. **Al desvincular (`/player unlink`)**:
   * Se elimina la asociacion en base de datos (`player.discord_id = NULL`).
   * Se retira el rol de Verificado (`LINK_ROLE_ID`) del usuario de Discord.
   * Se retiran de inmediato los roles VIP y especiales de esa cuenta en Discord.
   * **Importante**: Las membresias activas, dias restantes y roles en la base de datos **se conservan intactos** en el `steam_id`.

### Opcion B: Desacoplamiento y Comandos Explicitos (`/roles sync` y `/roles remove_all`)

En este modelo, `link` y `unlink` se limitan unicamente a la verificacion de identidad, requiriendo acciones secundarias para los roles VIP:

1. **Al vincular (`/player link`)**:
   * Se asigna unicamente el rol de Verificado (`LINK_ROLE_ID`).
   * La entrega de roles VIP queda a la espera de la tarea automatica en segundo plano o requiere que el Staff ejecute manualmente `/roles sync @usuario`.
2. **Al desvincular (`/player unlink`)**:
   * Se elimina la asociacion en base de datos (`player.discord_id = NULL`).
   * Se retira unicamente el rol de Verificado (`LINK_ROLE_ID`).
   * Los roles VIP permanecen en la cuenta de Discord a menos que un administrador ejecute de forma explicita `/roles remove_all @usuario`.

---

## 3. Matriz Comparativa

| Criterio | Opcion A: Automatica en Link/Unlink | Opcion B: Con `/roles sync` y `/roles remove_all` |
| :--- | :--- | :--- |
| **Experiencia del Jugador** | **Inmediata**: Al vincular, accede a canales VIP y beneficios al instante sin abrir tickets. | **Asistida o diferida**: Debe esperar el intervalo de sincronizacion del bot o pedir soporte al Staff. |
| **Carga de Trabajo del Staff** | **Baja**: No requiere supervision constante en operaciones diarias de vinculacion y desvinculacion. | **Alta**: El Staff debe recordar ejecutar comandos adicionales tras cada desvinculacion. |
| **Prevencion de Fuga de Roles** | **Maxima**: La cuenta desvinculada pierde de inmediato el acceso a salas VIP en Discord. | **Vulnerable**: Si el administrador olvida correr `remove_all`, la cuenta conserva roles VIP sin estar vinculada. |
| **Migracion de Cuenta (Discord perdido/robado)** | **Optima**: La cuenta vieja pierde roles en Discord, pero al vincular la cuenta nueva, el jugador recupera sus dias de VIP vigentes automaticamente. | **Correcta pero manual**: Requiere una secuencia estricta: `remove_all` en cuenta vieja, `unlink`, y luego `sync` en cuenta nueva. |
| **Sanciones y Expulsiones** | Requiere el uso de `/roles remove_all` o comandos de membresias para cancelar beneficios en la BD y slots de RCON. | El Staff utiliza `remove_all` de forma habitual para purgar usuarios. |
| **Riesgo de Error Humano** | Minimo en el dia a dia; solo requiere atencion en casos disciplinarios. | Elevado por olvido de comandos complementarios. |

---

## 4. Analisis Tecnico y Operativo

### Evaluacion de la Opcion A

#### Ventajas
* **Atencion a donadores sin friccion**: Si un usuario adquiere un paquete VIP previo a vincularse o mientras esta en el servidor, su estado se actualiza en el momento exacto en que completa la autenticacion de Steam.
* **Higiene del servidor de Discord**: Evita la acumulacion de usuarios que ya no forman parte de la comunidad o que cambiaron de cuenta pero siguen conservando canales y estatus VIP.
* **Preservacion de la inversion del jugador**: Desvincular no destruye las compras de la base de datos; solo remueve el acceso visual en Discord.

#### Consideraciones
* El Staff debe tener presente que `/player unlink` **no anula una membresia en los servidores de juego**. Si un jugador fue expulsado por comportamiento toxico, desvincularlo le quitara los roles de Discord, pero su slot reservado de Squad seguira activo hasta que se utilice `/roles remove_all` o expire su periodo.

### Evaluacion de la Opcion B

#### Ventajas
* **Separacion estricta de dominios**: `unlink` solo altera la tabla de jugadores y el rol base, delegando la logica de roles a los comandos especificos del modulo de membresias.
* **Control manual visible**: Cada cambio de rol requiere una accion deliberada por parte de un administrador con confirmacion visual en el canal.

#### Consideraciones
* **Fuga constante de roles (Role Leak)**: En la practica operativa de administracion de servidores, los administradores suelen ejecutar unicamente el comando intuitivo (`/player unlink`), omitiendo `/roles remove_all`. Como resultado, cuentas abandonadas o desvinculadas permanecen con roles VIP.
* **Tickets repetitivos**: Incremento de consultas en canales de soporte del tipo "Ya me vincule pero no tengo el rol VIP".

---

## 5. Protocolo Recomendado para el Staff

La implementacion optima combina la **automatizacion defensiva de la Opcion A** con el **uso deliberado de comandos administrativos**:

1. **Flujo de Cambio de Cuenta Legítimo (Jugador perdio acceso a su Discord)**:
   * El Administrador ejecuta: `/player unlink usuario:@CuentaVieja`
   * Resultado: La cuenta vieja pierde el rol Verificado y roles VIP en Discord. El `steam_id` conserva sus dias restantes.
   * El jugador procede a ejecutar `/player link` desde su `@CuentaNueva`.
   * Resultado: La cuenta nueva recibe el rol Verificado y sus roles VIP de manera automatica.

2. **Flujo de Sancion / Expulsion (Revocacion total de beneficios)**:
   * El Administrador ejecuta primero: `/roles remove_all usuario:@Infractor`
   * Resultado: Se desactivan las membresias en la base de datos, se retiran los slots en los servidores de juego (RCON) y se eliminan todos los roles de Discord.
   * El Administrador ejecuta luego: `/player unlink usuario:@Infractor`
   * Resultado: Se libera el enlace entre Steam y Discord.
