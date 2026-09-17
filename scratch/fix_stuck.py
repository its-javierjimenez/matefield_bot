import re

with open("d:/proyectos_dev/matefield_bot/apps/discord_bot/src/plugins/account.py", "r", encoding="utf-8") as f:
    content = f.read()

pattern = re.compile(r'(await plugin\.model\.api\.set_welcome_message\(target_steam, self\.message\))\s+@plugin\.include')
replacement = r'\1\n        await ctx.respond(f"✅ Mensaje de bienvenida establecido.")\n\n@plugin.include'

if pattern.search(content):
    content = pattern.sub(replacement, content)
    with open("d:/proyectos_dev/matefield_bot/apps/discord_bot/src/plugins/account.py", "w", encoding="utf-8") as f:
        f.write(content)
    print("Success replacing with regex!")
else:
    print("Failed to find exact block")
