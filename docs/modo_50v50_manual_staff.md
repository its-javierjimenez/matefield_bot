# 🛡️ Manual de Operación: Modo 50v50 & Team Balancing
> **Documento Oficial de Referencia para el Equipo de Staff y Moderación**  
> *Versión 2.1 — Modelo Global de Portero (Gatekeeper), Calentamiento de 1 Minuto, Whispers y Sellado ARMA*

---

## 1. ¿Qué es el Modo 50v50?

El juego *Wardogs* está diseñado nativamente con una estructura tripartita de **33 vs 33 vs 33** entre tres facciones:
* 🔴 **Valkyra (Rojo)**
* 🟢 **Manticore (Verde)**
* 🔵 **Lonestar (Azul)**

El **Modo 50v50** transforma la partida en una guerra campal de **50 vs 50 (Valkyra vs Manticore)**, neutralizando por completo la facción **Lonestar (Azul)** y garantizando un equilibrio justo sin alterar la partida de los veteranos, sin separar a grupos de amigos y sin arriesgar el dinero o vehículos comprados en base.

```text
[Jugadores conectando al servidor]
 ├── Entran a Lonestar (Azul)
 │    └──► Drenado Inmediato ──► Asignación al equipo menor (Rojo/Verde) + Whisper
 └── Entran a Valkyra (Rojo) o Manticore (Verde)
      ├── ¿Intentan cambiarse manualmente de equipo en el menú?
      │    └──► SÍ ──► Sellado ARMA: Reversión inmediata a su equipo + Whisper
      │
      ├── ¿La partida lleva menos de 1 minuto (< 60s)?
      │    └──► SÍ ──► Calentamiento: Selección libre con amigos + Anuncio global
      │
      └──► ¿La partida lleva 1 minuto o más (>= 60s)?
           ├── ¿Ya estaban jugando en su equipo?
           │    └──► INMUNIDAD TOTAL: Jamás son movidos (helicópteros y tanques 100% a salvo)
           └── ¿Es un jugador nuevo entrando al equipo LLENO / MAYOR?
                └──► PORTERO ACTIVO: Redirección inmediata al equipo menor + Whisper + Bloqueo
```

---

## 2. Fundamentos Técnicos: ¿Por qué el Bot y no el Servidor Nativo?

El archivo `ServerSettings.ini` del servidor de juego cuenta con una opción interna:
```ini
[/Script/WDGame.WDGameStateSession]
bLockOverpopulatedTeamsConfig=true
OverpopulatedTeamThresholdConfig=1
```

### ¿Por qué NO usamos el balanceador nativo del juego para 50v50?
1. **Conflicto de 3 facciones**: El servidor de juego evalúa constantemente las **3 facciones**.
2. **Bloqueo involuntario**: Como mantenemos a Lonestar (Azul) en 0 jugadores, en cuanto Valkyra y Manticore tienen 3 o 4 jugadores, el motor del juego detecta que ambos superan a Azul por más de 1 jugador.
3. **El bug de selección**: El servidor nativo **bloquea a Valkyra y Manticore** en la pantalla de carga y **fuerza a todos los jugadores nuevos a meterse a Lonestar (Azul)**.
4. **La Solución**: Al activar 50v50, el bot apaga remotamente `bLockOverpopulatedTeamsConfig=false` en el RCON del servidor, tomando el **control inteligente absoluto** del balanceo mediante su propio motor cada 6 segundos.

---

## 3. Ciclo de Vida del Modo: Activación Limpia ([NEXT MATCH])

Los cambios en la configuración del servidor de juego (`ServerSettings.ini`) solo surten efecto cuando una nueva partida comienza o se reinicia el mapa. Por ello, el bot implementa un ciclo de vida diferido de 4 estados para no romper partidas en curso:

* 🟡 **`pending_enable`** *(Pendiente de activación)*
  > El staff ejecutó `/mode50v50 enable`. El RCON ya queda configurado con el candado nativo en `false`. La automatización espera pacientemente a que termine la partida actual para no romperla.
* 🟢 **`active`** *(Modo 50v50 100% activo)*
  > La nueva partida inició tras la rotación. Se resetea el conteo y arranca el ciclo de 50v50 con los anuncios globales.
* 🟠 **`pending_disable`** *(Pendiente de apagado)*
  > El staff ejecutó `/mode50v50 disable`. El RCON se restaura a `true`. Para no estropear la partida en juego, el bot sigue operando en 50v50 hasta que concluya el mapa.
* ⚪ **`inactive`** *(Modo apagado)*
  > Estado por defecto (partida estándar 33v33v33).

> ℹ️ **Nota para el Staff:** Si activas `enable` por error y luego ejecutas `disable` antes de que cambie el mapa, el bot cancela la activación de inmediato sin esperar al cambio de ronda.

---

## 4. Sellado de Equipos Estilo ARMA (Prohibición de Cambio Voluntario)

Inspirado en los servidores tácticos de **ARMA King of the Hill**, los equipos quedan **sellados durante toda la partida**:

1. **Sin Cambios de Conveniencia**: Los jugadores **no pueden** cambiarse voluntariamente de equipo a mitad de partida (por ejemplo, pasarse al bando que va ganando).
2. **Detección Instantánea**: Cada 6 segundos, el bot compara la facción en vivo del jugador con su facción oficialmente asignada (`assigned_faction`).
3. **Reversión Inmediata**: Si detecta que un jugador se cambió de equipo por su cuenta:
   * Ejecuta inmediatamente `switch_faction` regresándolo a su bando asignado.
   * Le aplica un cooldown de 15 segundos para evitar bucles.
   * Le envía un **whisper privado**:
     > 💬 *"Cambio de equipo no permitido durante la partida."*

---

## 5. Anuncios Globales (Broadcast) y Whispers Privados

El bot informa tanto a todo el servidor como de forma privada a cada jugador:

### 📢 Anuncios Globales por Chat (Broadcast):
* Al inicio de la partida (durante el primer minuto):
  > 📢 `Modo 50v50: 1m antes de autobalance`
* Al cumplirse el primer minuto de juego (minuto 1:00):
  > 📢 `Modo 50v50: Autobalance ACTIVO`

### 💬 Whispers Privados por RCON:
* 💬 **Intento de cambio manual no permitido:**
  > `"Cambio de equipo no permitido durante la partida."`  
  *Explicación:* Informa al jugador que el cambio manual está prohibido y que fue devuelto a su facción.

* 💬 **Asignación automática desde Lonestar (Azul):**
  > `"Se te ha asignado al equipo {Valkyra/Manticore}."`  
  *Explicación:* Explica al jugador recién conectado a qué equipo oficial fue destinado.

* 💬 **Nuevo jugador redirigido por sobrepoblación:**
  > `"Se te ha asignado al equipo {Valkyra/Manticore} para balancear la partida."`  
  *Explicación:* Notifica al nuevo jugador que intentó entrar al equipo mayor que fue reubicado en el equipo con menos jugadores para mantener la partida equilibrada.

* 🛡️ **Espectadores y Árbitros (`White` / `None`):**
  > *Silencio absoluto.* Nunca reciben mensajes ni son transferidos.

---

## 6. Algoritmo de Team Balancing: "Portero Global" (Simple y Seguro)

El bot ejecuta un ciclo cada 6 segundos (`mode_50v50_loop`). El sistema funciona bajo un principio simple: **nadie que ya esté jugando es movido jamás, el balance se gestiona en la puerta de entrada**:

### Paso 1: Drenado Continuo de Lonestar (Azul)
* Cualquier jugador que aparezca en Lonestar (Azul) es transferido al equipo con menor población entre Valkyra y Manticore (o a su equipo original si ya tenía uno asignado).
* Recibe el whisper: *"Se te ha asignado al equipo {target}."*

### Paso 2: Fase 1 — Calentamiento Inicial (Primeros 60 Segundos)
* Durante el primer minuto (`matchSeconds < 60`), se emite el anuncio `Modo 50v50: 1m antes de autobalance`.
* Los jugadores pueden conectarse y elegir Valkyra o Manticore con total libertad.
* **Propósito:** Permite que grupos de amigos, clanes o escuadras carguen el mapa (sin importar si uno tiene SSD y otro HDD) y elijan el mismo equipo sin que el bot los separe en el arranque.

### Paso 3: Fase 2 — Portero Activo (A partir del Minuto 1 / matchSeconds >= 60)
* Al minuto 1:00, se emite el anuncio `Modo 50v50: Autobalance ACTIVO`.
* **Inmunidad Total para Jugadores Existentes:** Todo jugador que ya esté en Valkyra o Manticore queda **100% protegido para siempre**.
  * ¿Compró un tanque en base? **Protegido.**
  * ¿Está esperando 2 minutos a que llegue un helicóptero? **Protegido.**
  * ¿Gastó su billetera en equipamiento? **Protegido.**
  * Jamás se le moverá de equipo por abandonos ajenos.
* **El Portero en la Entrada:** Cuando un **NUEVO jugador** conecta al servidor:
  * Si elige el equipo con **MÁS jugadores** que el rival (sobrepopulador): El bot lo intercepta de inmediato en la pantalla de bienvenida, lo transfiere al equipo con menos jugadores, lo bloquea allí y le envía el whisper: *"Se te ha asignado al equipo {target} para balancear la partida."*
  * Si elige el equipo con **MENOS o IGUAL número de jugadores**: Es aceptado de forma inmediata en su equipo elegido.

---

## 7. Matriz Rápida de Decisiones del Bot

```text
PERFIL DEL JUGADOR       ESTADO EN EL JUEGO    TIEMPO / ACTIVIDAD    ACCIÓN DEL BOT
─────────────────────────────────────────────────────────────────────────────────────────────
Jugador existente        Ya en Valkyra/Manticore Cualquiera (0 a 100m) ❌ INMUNE (Jamás se mueve)
Comprando en base        Esperando heli/tanque  $0 cash ganado        ❌ PROTEGIDO (100% seguro)
Amigos en calentamiento  Minuto 0:00 a 1:00     matchSeconds < 60s    ✅ LIBRE (Eligen juntos)
Nuevo sobrepopulador     Entra tras minuto 1:00 Intenta bando mayor   ⛔ REDIRIGIDO al menor + whisper
Nuevo balanceador        Entra tras minuto 1:00 Elige bando menor     ✅ ACEPTADO en su equipo
Espectador / Árbitro     Facción White / None   Cualquiera            ❌ INTOCABLE (Ignorado)
Cambio voluntario menú   Intento en el menú     Cualquiera            ⛔ REVERTIDO al suyo + whisper
```

---

## 8. Guía de Casos de Uso Reales para el Staff (FAQ)

### ❓ Caso 1: *"Entré con 4 amigos a Valkyra y Manticore está vacío (5v0) al empezar la ronda. ¿Nos va a separar el bot?"*
> **Respuesta:** **No.** Durante el primer minuto de partida (`matchSeconds < 60`), el auto-balanceo está pausado. Los 5 amigos pueden elegir Valkyra sin problema mientras ven en pantalla el anuncio `Modo 50v50: 1m antes de autobalance`.

### ❓ Caso 2: *"Compré un helicóptero o un tanque y estoy esperando 2 minutos en base a que llegue. ¿El bot me puede cambiar de equipo y hacerme perder la plata?"*
> **Respuesta:** **No.** Los jugadores que ya están dentro del equipo tienen inmunidad total. El bot **nunca** mueve a nadie que ya esté en el roster de un equipo. Tu dinero, tus vehículos y tu escuadra están 100% a salvo.

### ❓ Caso 3: *"Manticore va perdiendo y 7 jugadores se desconectaron por frustración (quedó 50 vs 43). ¿El bot va a pasar a los veteranos de Valkyra?"*
> **Respuesta:** **No.** El bot jamás castiga ni frustra a los jugadores que ya están jugando en Valkyra. La partida se equilibra naturalmente a través del **portero**: cada jugador nuevo que ingrese al servidor intentando meterse a Valkyra será automáticamente transferido a Manticore hasta que los equipos vuelvan a estar 50 vs 50.

### ❓ Caso 4: *"Un jugador nuevo conecta al servidor y el juego lo asigna a Lonestar (Azul). ¿Qué sucede?"*
> **Respuesta:** En menos de 6 segundos, el bot lo transfiere automáticamente al equipo con menor cantidad de jugadores (Rojo o Verde) y le manda el whisper privado: *"Se te ha asignado al equipo Valkyra/Manticore"*. A partir de ahí, queda sellado en ese bando.

### ❓ Caso 5: *"Un jugador intenta cambiarse desde el menú in-game al equipo que va ganando."*
> **Respuesta:** El bot detecta que su facción cambió sin orden del sistema, lo regresa inmediatamente a su facción original y le envía un whisper: *"Cambio de equipo no permitido durante la partida."*

### ❓ Caso 6: *"Hay moderadores o árbitros en modo espectador (facción White)."*
> **Respuesta:** El bot los filtra inmediatamente antes de procesar cualquier lógica. Nunca se les mueve de facción, nunca se les envían whispers y nunca interfieren en el conteo de 50v50.

---

## 9. Comandos de Administración del Modo

Los administradores pueden gestionar el modo mediante los comandos de Discord o la API RCON:

* **`/mode50v50 status`**: Muestra el estado actual (`inactive`, `pending_enable`, `active`, `pending_disable`), conteo de jugadores por equipo y configuración de RCON.
* **`/mode50v50 enable`**: Programa el modo 50v50 para activarse en el siguiente mapa (`pending_enable`).
* **`/mode50v50 disable`**: Programa el apagado ordenado del modo al terminar la partida actual (`pending_disable`).

---
*Manual verificado y probado al 100% contra el Mock RCON oficial con 21 pruebas unitarias y de integración.*
