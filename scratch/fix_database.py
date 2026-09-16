import re

with open("d:/proyectos_dev/matefield_bot/apps/discord_bot/src/plugins/database.py", "r", encoding="utf-8") as f:
    content = f.read()

# Fix logger
if "import logging" not in content:
    content = content.replace("import hikari", "import hikari\nimport logging\n\nlogger = logging.getLogger(__name__)")

# Remove type ignores that are unused
content = content.replace("# type: ignore", "")

# Cast steam_id to str for add_special_role, remove_special_role, edit_player
content = content.replace("add_special_role(steam_id,", "add_special_role(str(steam_id),")
content = content.replace("remove_special_role(steam_id,", "remove_special_role(str(steam_id),")
content = content.replace("edit_player(\n                steam_id,", "edit_player(\n                str(steam_id),")
# Also cast kwargs to str if they are not None
# The error was: "element `int` of union `int | None` is not assignable to `str | None`"
# Pylance thinks self.mensaje_bienvenida is int | None ? Maybe because crescent.option returns an unexpected type if not specified right?
content = content.replace("custom_welcome_message=self.mensaje_bienvenida,", "custom_welcome_message=str(self.mensaje_bienvenida) if self.mensaje_bienvenida else None,")
content = content.replace("observations=self.observacion", "observations=str(self.observacion) if self.observacion else None")

with open("d:/proyectos_dev/matefield_bot/apps/discord_bot/src/plugins/database.py", "w", encoding="utf-8") as f:
    f.write(content)
print("Fixed database.py type errors")
