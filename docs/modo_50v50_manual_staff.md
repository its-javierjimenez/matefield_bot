# 🛡️ Guía del Staff: Modo 50v50 (A Prueba de Bobos)
> **Manual Ultra Simple para Administradores y Moderadores**  
> *Versión 2.2 — Compatible con Discord (Copiar y pegar directo sin que se rompa nada)*

---

## 1. El Modo 50v50 explicado como si tuvieras 5 años 👶

Normalmente el juego tiene 3 equipos: **Rojo**, **Verde** y **Azul** (33 vs 33 vs 33).  
El **Modo 50v50** elimina por completo al equipo **Azul** y convierte la partida en una guerra campal de **50 Rojos vs 50 Verdes**.

```text
[JUGADORES ENTRANDO AL SERVIDOR]
 ├── ¿Eligen Azul? ──► El bot los manda directo al equipo con menos gente.
 └── ¿Eligen Rojo o Verde?
      ├── Primeros 15 segundos ──► Entran con amigos (tope 50 y máx 6 de dif).
      └── Pasado el segundo 15:
           ├── ¿Ya estás jugando adentro? ──► NADIE te toca. Sos intocable.
           └── ¿Sos NUEVO y elegís el equipo lleno? ──► El bot te manda al otro equipo.
```

---

## 2. ¿Cómo funciona el Auto-Balance? (Explicación Tonta del Portero) 🚪🕺

Imaginate que el servidor es un **boliche (discoteca)** con dos salas: **Sala Roja (Valkyra)** y **Sala Verde (Manticore)**:

1. **La Puerta Libre (Primeros 15 segundos con tope de seguridad):**
   * Durante los primeros 15 segundos de la partida, la puerta está abierta para entrar con amigos y escuadras.
   * **Frenos de Seguridad Automáticos:**
     * **Techo Máximo de 50:** Ningún equipo puede superar los 50 jugadores jamás. Si una sala llega a 50, se cierra de inmediato.
     * **Diferencia Máxima de 6:** Si una sala le saca 6 o más jugadores de ventaja a la otra (ej: 18 vs 12), el portero se despierta y frena a los nuevos para que no rompan la partida.
   * En el chat de todo el servidor sale el aviso:  
     > 📢 `Modo 50v50: 15s antes de autobalance`  

2. **Nadie que esté adentro se mueve (Regla de Oro):**
   * Si ya entraste a una sala, **el bot NUNCA te va a sacar**.
   * ¿Compraste un tanque? **Tu tanque está a salvo.**
   * ¿Estás esperando 2 minutos en la base a que llegue tu helicóptero? **Tu helicóptero está a salvo.**
   * ¿El otro equipo se quedó sin gente porque son malos y se fueron (ragequit)? **A vos NO te pasa nadie.** El ragequit lo resuelven los admins manualmente si hace falta.

3. **El Portero en la Entrada (Del segundo 15 en adelante):**
   * Al cumplirse el segundo 15 sale el aviso definitivo:  
     > 📢 `Modo 50v50: Autobalance ACTIVO`
   * A partir de ahí, el bot se para de **patovica/portero** en la entrada:
     * Si la Sala Roja tiene 30 personas y la Verde tiene 20, y cae un **jugador nuevo** que intenta meterse a la Roja...
     * El portero lo frena en la puerta y le dice: *"No flaco, Roja está llena, vas a Verde"*.
     * El jugador entra a Verde y recibe un mensaje privado en su pantalla:  
       > 💬 *"Se te ha asignado al equipo Manticore para balancear la partida."*
   * Así de simple: los equipos se emparejan solos con la gente nueva que va entrando, **sin tocarle el pelo a los que ya están jugando**.

4. **El Candado Antitraidores (Estilo ARMA):**
   * Si un vivo aprieta Escape a mitad de partida e intenta cambiarse al equipo que va ganando...
   * El bot lo detecta en 5 segundos, lo devuelve de una patada a su equipo original y le susurra:  
     > 💬 *"Cambio de equipo no permitido durante la partida."*

---

## 3. ¿Qué pasa si mando el comando? (Preguntas Frecuentes del Staff) ❓

Aquí tenés exactamente lo que pasa en cada situación para que no tengas miedo de meter la pata:

### 🔹 "¿Qué pasa si tiro `/mode50v50 enable` en mitad de una partida?"
> **Respuesta:** **NO PASA NADA MALO. No se corta la partida.**  
> El bot es inteligente: deja la configuración lista en el servidor y espera pacientemente a que termine la partida actual. En cuanto termine la ronda y cambie el mapa... **¡PUM!** La nueva partida arranca automáticamente en 50v50.

### 🔹 "¿Qué pasa si me equivoqué y tiré `/mode50v50 enable` por error?"
> **Respuesta:** No te preocupes. Antes de que termine el mapa tirás `/mode50v50 disable`.  
> El bot cancela la orden de inmediato y la próxima partida arrancará normal en 33v33v33.

### 🔹 "¿Qué pasa si ya estamos jugando en 50v50 y tiro `/mode50v50 disable`?"
> **Respuesta:** **Tampoco rompe nada.**  
> El bot deja que la partida en curso termine en paz en 50v50 hasta el final. Cuando termine el mapa y cambie de ronda, el servidor vuelve solo al modo normal de 3 facciones.

### 🔹 "¿Cómo sé en qué estado está el servidor ahora mismo?"
> **Respuesta:** Tirás el comando:
> ```text
> /mode50v50 status
> ```
> El bot te va a responder clarito:
> * ⚪ `inactive`: El modo está apagado (partida normal 33v33v33).
> * 🟡 `pending_enable`: Esperando a que termine el mapa actual para activar 50v50.
> * 🟢 `active`: ¡El modo 50v50 está jugando y balanceando ahora mismo!
> * 🟠 `pending_disable`: El 50v50 actual terminará y el próximo mapa será normal.

---

## 4. Resumen de Mensajes que ven los Jugadores 💬

### A. Avisos de Estado (cuando el Staff usa los comandos):
* 📢 **Al programar activación:**  
  `Modo 50v50: En la siguiente partida se activara el modo 50v50`
* 📢 **Al cancelar activación:**  
  `Modo 50v50: Se ha cancelado la activacion, seguiremos normal`
* 📢 **Al programar desactivación en plena partida:**  
  `Modo 50v50: En la siguiente partida se desactivara el modo 50v50`
* 📢 **Al cancelar desactivación (seguir en 50v50):**  
  `Modo 50v50: Se ha cancelado la desactivacion, seguiremos en modo 50v50`
* 📢 **Al iniciar la partida 50v50:**  
  `Modo 50v50 ACTIVADO para esta partida (Rojo vs Verde)!`
* 📢 **Al finalizar la partida 50v50:**  
  `Modo 50v50 FINALIZADO. Volviendo a 33v33v33.`

### B. Avisos de Calentamiento / Autobalance:
* 📢 **Segundo 0 (Inicio de partida):**  
  `Modo 50v50: 15s antes de autobalance`
* 📢 **Segundo 15 (Autobalance Activo):**  
  `Modo 50v50: Autobalance ACTIVO`

### C. Mensajes Privados (Susurros):
* 💬 **Al que intentó cambiarse de equipo de vivo:**  
  `Cambio de equipo no permitido durante la partida.`
* 💬 **Al que entró en Azul:**  
  `Se te ha asignado al equipo Valkyra/Manticore.`
* 💬 **Al nuevo que intentó entrar al equipo lleno:**  
  `Se te ha asignado al equipo Valkyra/Manticore para balancear la partida.`
* 🛡️ **A los Moderadores / Espectadores (White):**  
  *Silencio total.* El bot no los toca, no los mueve y no les manda mensajes.

---

## 5. Tabla Rápida: ¿A quién puede mover el Bot? 📋

```text
SITUACIÓN DEL JUGADOR                          ¿EL BOT PUEDE MOVERLO?
─────────────────────────────────────────────────────────────────────────────
Jugador que ya está jugando (cualquier tiempo) ❌ NUNCA (100% Inmune)
Comprando en base o esperando helicóptero      ❌ NUNCA (Vehículos a salvo)
Amigos entrando al inicio (< 15s)              ✅ LIBRES (Tope 50 y máx 6 dif)
Nuevo jugador entrando al equipo lleno         ⛔ REDIRIGIDO al equipo menor
Nuevo jugador entrando al equipo con menos     ✅ ENTRA directo a su equipo
Jugador que intenta cambiarse en el menú       ⛔ REVERTIDO a su equipo
Moderador / Admin en Espectador (White)        ❌ INTOCABLE (Ignorado)
```

---
*Manual redactado para todo el staff. Diseñado para ser infalible y no requerir conocimientos técnicos.*
