with open("C:\\Users\\itsja\\.gemini\\antigravity-ide\\brain\\ca324d82-d5f3-4a77-b8f9-66b54c7148af\\walkthrough.md", "r", encoding="utf-8") as f:
    content = f.read()

new_content = """## 4. Baneos Temporales y Roles (Entidad Acción)
Se ha implementado el sistema de baneos temporales gestionados íntegramente por el bot y su reflejo automático en roles de Discord.

**Características principales:**
- **Mapeo de Roles:** El comando `/ban_role map <rol> <días>` permite configurar qué rol de Discord asignar según la duración del ban. (0 días = permanente).
- **Ban con Duración:** Se actualizó `/ban add <steam_id> <razón> [días]` para aceptar un tiempo.
- **Sincronización Bot -> Discord:** Cuando aplicas un ban (o el bot absorbe uno manual desde RCON), el bot busca al usuario de Discord vinculado y le asigna el rol correspondiente a esa duración.
- **Auto-Desbaneo:** Una nueva tarea en segundo plano revisa cada minuto si los baneos temporales expiraron (`expires_at < now()`). Si es así, los quita de la base de datos, desbanea del servidor RCON, y le quita el rol al usuario en Discord.
- **Migración DB:** Se ejecutó `ALTER TABLE bans ADD COLUMN expires_at TIMESTAMP WITH TIME ZONE;` en producción exitosamente.
"""

with open("C:\\Users\\itsja\\.gemini\\antigravity-ide\\brain\\ca324d82-d5f3-4a77-b8f9-66b54c7148af\\walkthrough.md", "a", encoding="utf-8") as f:
    f.write("\n\n" + new_content)
print("Updated walkthrough")
