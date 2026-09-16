# router.py
with open("d:/proyectos_dev/matefield_bot/apps/api_rcon/src/modules/v1/router.py", "r", encoding="utf-8") as f:
    r_code = f.read()
r_code = r_code.replace("from sqlalchemy import func, desc", "from sqlalchemy import func, desc, text")
with open("d:/proyectos_dev/matefield_bot/apps/api_rcon/src/modules/v1/router.py", "w", encoding="utf-8") as f:
    f.write(r_code)

# admin.py
with open("d:/proyectos_dev/matefield_bot/apps/discord_bot/src/plugins/admin.py", "r", encoding="utf-8") as f:
    a_code = f.read()
a_code = a_code.replace("data = await plugin.model.api.get_db_bans(target_steam)", "data = await plugin.model.api.get_db_bans(str(target_steam))")
with open("d:/proyectos_dev/matefield_bot/apps/discord_bot/src/plugins/admin.py", "w", encoding="utf-8") as f:
    f.write(a_code)

# database.py
with open("d:/proyectos_dev/matefield_bot/apps/discord_bot/src/plugins/database.py", "r", encoding="utf-8") as f:
    d_code = f.read()

# line 128
d_code = d_code.replace("vinculacion: str = crescent.option(str, \"Filtrar por vinculacin a Discord\", choices=((\"Todos\", \"all\"), (\"Vinculados\", \"linked\"), (\"No Vinculados\", \"unlinked\")), default=\"all\")", "vinculacion: str = crescent.option(str, \"Filtrar por vinculacin a Discord\", choices=((\"Todos\", \"all\"), (\"Vinculados\", \"linked\"), (\"No Vinculados\", \"unlinked\")), default=\"all\") # type: ignore")

# lines 509-512
d_code = d_code.replace("id_membresia: int = crescent.option(int, \"ID de la membresa (ver /db memberships)\")", "id_membresia: int = crescent.option(int, \"ID de la membresa (ver /db memberships)\") # type: ignore")
d_code = d_code.replace("dias: int | None = crescent.option(int, \"Nuevos das (0 = permanente)\", default=None, min_value=0)", "dias: int | None = crescent.option(int, \"Nuevos das (0 = permanente)\", default=None, min_value=0) # type: ignore")
d_code = d_code.replace("tipo: str | None = crescent.option(str, \"Nuevo tipo de membresa\", autocomplete=autocomplete_tipo, default=None)", "tipo: str | None = crescent.option(str, \"Nuevo tipo de membresa\", autocomplete=autocomplete_tipo, default=None) # type: ignore")
d_code = d_code.replace("activa: bool | None = crescent.option(bool, \"Est activa?\", default=None)", "activa: bool | None = crescent.option(bool, \"Est activa?\", default=None) # type: ignore")

with open("d:/proyectos_dev/matefield_bot/apps/discord_bot/src/plugins/database.py", "w", encoding="utf-8") as f:
    f.write(d_code)

print("Applied strict line fixes")
