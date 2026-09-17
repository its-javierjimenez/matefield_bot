import re

with open("d:/proyectos_dev/matefield_bot/apps/discord_bot/src/plugins/account.py", "r", encoding="utf-8") as f:
    content = f.read()

pattern = re.compile(r'await ctx\.respond\(f"✅ Mensaje de bienvenida establecido\."\)')
replacement = r'preview_msg = f"El {active_role} [Nombre en Juego] se conectó: \"{self.message}\""\n        await ctx.respond(f"✅ **Mensaje de bienvenida establecido.**\\n👀 **Vista Previa:**\\n> {preview_msg}")'

if pattern.search(content):
    content = pattern.sub(replacement, content)
    with open("d:/proyectos_dev/matefield_bot/apps/discord_bot/src/plugins/account.py", "w", encoding="utf-8") as f:
        f.write(content)
    print("Success replacing!")
else:
    print("Failed to find exact block")
