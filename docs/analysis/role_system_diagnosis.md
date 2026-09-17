# Diagnóstico y Rediseño del Sistema de Roles

## El Problema Real: La Tabla de Roles no Sabe lo que Es

Después de auditar el código y los datos, se confirma que **la tabla `roles` y `player_roles` están conceptualmente rotas**. No es un bug técnico; es un error de diseño de dominio.

### Estado Actual (la radiografía)

```
=== TABLA: roles ===
  id=1, name='1546690312762564648'    ← ¿Qué es esto? Un número. ¿Qué significa? Nadie lo sabe mirando la DB.

=== TABLA: player_roles ===
  9 jugadores apuntan al role_id=1    ← ¿Estos 9 son admins? ¿VIPs? ¿Decorativos? Imposible saberlo.

=== BotConfig ===
  ADMIN_ROLE_ID = 1433128734826692811   ← Un ID de Discord diferente al de la tabla roles
  OWNER_ROLE_ID = 1546690312762564648   ← Casualmente coincide con el role.name de la tabla
  VIP_ROLE_IDS = 1546845...,1546846...,1546690...  ← El OWNER_ROLE_ID también está en la lista VIP (!)
  ROLE_MAP_VIP_COMUN = 1546845...
```

### Los 5 Pecados Capitales

**1. La tabla `roles` no tiene semántica**
Un `Role` es solo un `name: str` que almacena un número de Discord. No dice si ese rol es administrativo, VIP, decorativo, o de castigo. La tabla es un buzón ciego.

**2. Hay DOS sistemas de roles que no se hablan**
- **Sistema A (BotConfig):** `ADMIN_ROLE_ID`, `OWNER_ROLE_ID`, `VIP_ROLE_IDS`, `ROLE_MAP_*` → Claves sueltas en una tabla key-value. Aquí está la "inteligencia" del negocio.
- **Sistema B (Role/PlayerRole):** Una tabla relacional que guarda números sin contexto. Aquí está el "estado" de los jugadores.
- **Nadie los conecta limpiamente.** La API tiene que hacer malabares para cruzarlos.

**3. `OWNER_ROLE_ID` y `ADMIN_ROLE_ID` son cosas diferentes por accidente**
El rol de "Dueño" es simultáneamente un "rol VIP". Esto viola directamente la separación de responsabilidades.

**4. Los comandos son opacos**
`/special_role add` pide seleccionar un "Rol de Discord" y guarda el ID numérico en la DB. No te dice *para qué* es ese rol.

**5. La sincronización ignora la semántica**
`sync_memberships` filtra numéricamente para decidir qué roles sincronizar a Discord, ignorando si son de admin, VIP, o castigo.

---

## Analogía de Negocio: El "Club Deportivo"

Imagina que tienes un club deportivo:
- **Membresía** = La cuota que pagaste (Mensual, Anual, Vitalicia). Te da acceso a la cancha.
- **Credencial** = Tu tarjeta física con tu foto. Identifica quién eres.
- **Rol** = Tu función en el club: Socio, Entrenador, Director Técnico, Presidente.

Hoy el sistema tiene las cuotas (Membresías) bien hechas, pero los roles son como si pegaras stickers de colores a los carnets sin escribir qué significan. Alguien tiene un sticker azul, pero ¿azul significa "entrenador"? Depende de si miras un cartel pegado en la pared (BotConfig) que dice "azul = entrenador".

**Lo correcto:** El rol dice explícitamente *qué es*. La credencial (tabla Role) tiene un campo `type` que dice "ADMINISTRATIVO" o "VIP" o "PÚBLICO". No dependes de un cartel en la pared.
