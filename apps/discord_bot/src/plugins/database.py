import asyncio
import crescent
import hikari
from src.model import Model
from src.hooks import admin_only

plugin = crescent.Plugin[hikari.GatewayBot, Model]()

async def autocomplete_tipo(
    ctx: crescent.AutocompleteContext, option: hikari.AutocompleteInteractionOption
) -> list[tuple[str, str]]:
    tipos = ["VIP_COMUN", "VIP_EXPRESS", "VIP_PERMANENTE"]
    try:
        val = str(option.value).lower()
        return [(t, t) for t in tipos if val in t.lower()]
    except Exception:
        return [(t, t) for t in tipos]



db_group = crescent.Group("db", "Comandos de consultas de Base de Datos", hooks=[admin_only])

@plugin.include
@db_group.child
@crescent.command(name="leaderboard", description="Muestra el Top 15 de jugadores")
class DbLeaderboard:
    metric = crescent.option(
        str, 
        "Métrica a usar para el ranking", 
        choices=(
            ("Kills", "kills"),
            ("Muertes", "deaths"),
            ("Dinero Generado", "cash_earned")
        ),
        default="kills"
    )

    async def callback(self, ctx: crescent.Context) -> None:
        await ctx.defer()
        
        try:            res = await plugin.model.api.get_leaderboard(metric=str(self.metric), limit=15)
        except Exception as e:
            await ctx.respond(f"❌ Error al consultar la base de datos: {e}")
            return
            
        leaderboard = res.get("leaderboard", [])
        
        if not leaderboard:
            await ctx.respond("⚠️ No hay datos suficientes para mostrar el leaderboard.")
            return

        embed = hikari.Embed(
            title=f"🏆 Top 15 Jugadores - {str(self.metric).replace('_', ' ').title()}",
            color=0xFFD700
        )
        
        steam_ids = [entry['steam_id'] for entry in leaderboard if 'steam_id' in entry]
        steam_names = {}
        if steam_ids:
            steam_names = await plugin.model.api.get_steam_players_batch(steam_ids)
            
        description = ""
        for i, entry in enumerate(leaderboard, 1):
            steam_id = entry['steam_id']
            discord_id = entry.get("discord_id")
            steam_name = steam_names.get(steam_id, {}).get("name", f"SteamID: {steam_id}")
            
            player_mention = f"<@{discord_id}>" if discord_id else steam_name
            description += f"**{i}.** {player_mention} - **{entry['total']}**\n"
            
        embed.description = description
        await ctx.respond(embed=embed)


@plugin.include
@db_group.child
@crescent.command(name="add_membership", description="Añade una membresía VIP a un jugador vinculado")
class DbAddMembership:
    usuario = crescent.option(hikari.User, "Usuario de Discord a añadir membresía")
    tipo = crescent.option(
        str,
        "Tipo de membresía a otorgar (autocompletado o escribe uno)",
        autocomplete=autocomplete_tipo
    )
    dias = crescent.option(int, "Duración en días (opcional, sobreescribe default, 0 = permanente)", default=None)
    rol_especial = crescent.option(
        hikari.Role,
        "Rol especial adicional a asignar (opcional)",
        default=None
    )

    async def callback(self, ctx: crescent.Context) -> None:
        await ctx.defer()
        try:
            player_info = await plugin.model.api.get_player_by_discord(str(self.usuario.id))
            if not player_info:
                await ctx.respond("❌ Este usuario no tiene una cuenta de Steam enlazada en la base de datos.")
                return
                
            steam_id = player_info.get("steam_id")
            if not steam_id:
                await ctx.respond("❌ La cuenta no tiene Steam ID asociado.")
                return
                
            special_role = str(self.rol_especial.id) if self.rol_especial else None
            await plugin.model.api.add_membership(str(steam_id), str(self.tipo), self.dias, special_role)
            
            if self.dias is None:
                dias_str = "Predeterminado (config)"
            elif self.dias == 0:
                dias_str = "Permanente"
            else:
                dias_str = f"{self.dias} días"
            msg = f"✅ Membresía {self.tipo} añadida a <@{self.usuario.id}> ({steam_id}) por {dias_str}."
            if special_role:
                msg += f"\n(Rol especial <@&{special_role}> asignado en base de datos)"
            await ctx.respond(msg)
        except Exception as e:
            await ctx.respond(f"❌ Error: {e}")

@plugin.include
@db_group.child
@crescent.command(name="reserved_slots", description="Muestra la lista de SteamIDs con slots reservados en el RCON")
class DbReservedSlots:
    async def callback(self, ctx: crescent.Context) -> None:
        await ctx.defer()
        try:
            res = await plugin.model.api.get_reserved_slots()
            slots = res.reservedSlots if res else []
            if not slots:
                await ctx.respond("?? No hay slots reservados actualmente en el RCON.")
                return
                
            steam_profiles = await plugin.model.api.get_steam_players_batch(slots)
            
            lines = []
            for s in slots:
                db_player = await plugin.model.api.get_player_by_steam(s)
                discord_username = "Desconocido"
                if db_player and db_player.get("discord_id"):
                    discord_id = db_player.get("discord_id")
                    try:
                        user = await ctx.app.rest.fetch_user(int(discord_id))
                        discord_username = user.username
                    except:
                        discord_username = f"ID: {discord_id}"
                        
                steam_name = steam_profiles.get(s, {}).get("personaname", "Desconocido")
                lines.append(f"- `{s}` | Steam: **{steam_name}** | Discord: **{discord_username}**")
                
            # Cut into chunks if necessary
            desc = "\n".join(lines)
            if len(desc) <= 4096:
                embed = hikari.Embed(
                    title=f"?? Slots Reservados en RCON ({len(slots)})",
                    description=desc,
                    color=0x4169E1
                )
                await ctx.respond(embed=embed)
            else:
                await ctx.respond(f"Hay demasiados jugadores ({len(slots)}) para mostrar en un embed. Usa `/reserved_slots list` en vez.")
        except Exception as e:
            await ctx.respond(f"? Error obteniendo slots reservados: {e}")



@plugin.include
@db_group.child
@crescent.command(name="players", description="Lista todos los jugadores registrados (Paginado)")
class DbPlayers:
    vinculacion: str = crescent.option(str, "Filtrar por vinculación a Discord", choices=(("Todos", "all"), ("Vinculados", "linked"), ("No Vinculados", "unlinked")), default="all")  # type: ignore
    
    async def callback(self, ctx: crescent.Context) -> None:
        await ctx.defer()
        page = 1
        try:
            res = await plugin.model.api.get_paginated_players(page=page, limit=10, linked=self.vinculacion)
            players = res.get("players", [])
            total = res.get("total", 0)
            
            if not players:
                await ctx.respond("No hay jugadores que coincidan con los filtros.")
                return
                
            embed = hikari.Embed(
                title=f"👥 Lista de Jugadores (Pág {page})",
                description=f"Total resultados: {total} | Filtros: Link={self.vinculacion}",
                color=0x00BFFF
            )
            
            for p in players:
                name = p.get('name', 'Sin Nickname')
                link_emoji = "🔗" if p.get('is_linked') else "❓"
                discord_str = f"<@{p['discord_id']}>" if p.get('is_linked') else "No enlazado"
                vip_str = f" | **VIP:** {p.get('vip_type')}" if p.get('vip_type') else ""
                sp_str = f" | **Especial:** {p.get('special_role')}" if p.get('special_role') else ""
                
                embed.add_field(
                    name=f"{link_emoji} {name} (SteamID: {p['steam_id']})", 
                    value=f"Discord: {discord_str}{vip_str}{sp_str}", 
                    inline=False
                )
                
            l_char = self.vinculacion[0:2]
            
            # Create a SelectMenu with players
            select_menu = ctx.app.rest.build_message_action_row().add_text_menu("db_players_select")
            select_menu.set_placeholder("Selecciona un jugador para ver su histórico")
            for p in players:
                name = p.get('name', 'Unknown')
                if not name: name = 'Unknown'
                # Discord limits options to 100 chars, so truncate
                label = f"{name} ({p['steam_id']})"[:100]
                select_menu.add_option(label, p['steam_id'], description=f"Ver perfil histórico de {name}"[:100])
            select_menu = select_menu.parent
            
            # Create navigation buttons
            button_row = ctx.app.rest.build_message_action_row()
            button_row.add_interactive_button(hikari.ButtonStyle.PRIMARY, f"prev_players_{page}_{l_char}", label="⬅️ Anterior")
            button_row.add_interactive_button(hikari.ButtonStyle.PRIMARY, f"next_players_{page}_{l_char}", label="Siguiente ➡️")
            
            components = [select_menu, button_row]
            await ctx.respond(embed=embed, components=components)
        except Exception as e:
            await ctx.respond(f"❌ Error: {e}")

class DbMatches:
    async def callback(self, ctx: crescent.Context) -> None:
        await ctx.defer()
        page = 1
        try:
            res = await plugin.model.api.get_paginated_matches(page=page, limit=10)
            matches = res.get("matches", [])
            total = res.get("total", 0)
            
            if not matches:
                await ctx.respond("No hay partidas registradas.")
                return
                
            embed = hikari.Embed(
                title=f"⚔️ Historial de Partidas (Pág {page})",
                description=f"Total jugadas: {total}",
                color=0xFF4500
            )
            
            for m in matches:
                start = m['start_time'][:16].replace("T", " ")
                end = m['end_time'][:16].replace("T", " ") if m['end_time'] else "En progreso"
                embed.add_field(name=f"Match ID: {m['id']}", value=f"**Mapa:** {m['map']}\n**Inicio:** {start}\n**Fin:** {end}", inline=False)
                
            components = [
                ctx.app.rest.build_message_action_row()
                .add_interactive_button(hikari.ButtonStyle.PRIMARY, f"prev_matches_{page}", label="◀ Anterior")
                .add_interactive_button(hikari.ButtonStyle.PRIMARY, f"next_matches_{page}", label="Siguiente ▶")
            ]
            await ctx.respond(embed=embed, components=components)
        except Exception as e:
            await ctx.respond(f"❌ Error: {e}")

@plugin.include
@crescent.event
async def on_interaction(event: hikari.InteractionCreateEvent) -> None:
    if not isinstance(event.interaction, hikari.ComponentInteraction):
        return
        
    custom_id = event.interaction.custom_id
    if custom_id.startswith("prev_players_") or custom_id.startswith("next_players_"):
        parts = custom_id.split("_")
        action = parts[0]
        current_page = int(parts[2])
        
        l_char = parts[3] if len(parts) > 3 else "al"
        
        linked = {"al": "all", "li": "linked", "un": "unlinked"}.get(l_char, "all")
        
        new_page = current_page - 1 if action == "prev" else current_page + 1
        if new_page < 1:
            new_page = 1
            
        try:
            res = await plugin.model.api.get_paginated_players(page=new_page, limit=10, linked=linked)
            players = res.get("players", [])
            total = res.get("total", 0)
            
            if not players and action == "next":
                await event.interaction.create_initial_response(
                    hikari.ResponseType.MESSAGE_UPDATE
                )
                return
                
            embed = hikari.Embed(
                title=f"👥 Lista de Jugadores (Pág {new_page})",
                description=f"Total resultados: {total} | Filtros: Link={linked}",
                color=0x00BFFF
            )
            
            for p in players:
                name = p.get('name', 'Sin Nickname')
                link_emoji = "🔗" if p.get('is_linked') else "❓"
                discord_str = f"<@{p['discord_id']}>" if p.get('is_linked') else "No enlazado"
                vip_str = f" | **VIP:** {p.get('vip_type')}" if p.get('vip_type') else ""
                sp_str = f" | **Especial:** {p.get('special_role')}" if p.get('special_role') else ""
                
                embed.add_field(
                    name=f"{link_emoji} {name} (SteamID: {p['steam_id']})", 
                    value=f"Discord: {discord_str}{vip_str}{sp_str}", 
                    inline=False
                )
                
            # Create a SelectMenu with players
            select_menu = plugin.app.rest.build_message_action_row().add_text_menu("db_players_select")
            select_menu.set_placeholder("Selecciona un jugador para ver su histórico")
            for p in players:
                name = p.get('name', 'Unknown')
                if not name: name = 'Unknown'
                label = f"{name} ({p['steam_id']})"[:100]
                select_menu.add_option(label, p['steam_id'], description=f"Ver perfil histórico de {name}"[:100])
            select_menu = select_menu.parent
            
            button_row = plugin.app.rest.build_message_action_row()
            button_row.add_interactive_button(hikari.ButtonStyle.PRIMARY, f"prev_players_{new_page}_{l_char}", label="⬅️ Anterior")
            button_row.add_interactive_button(hikari.ButtonStyle.PRIMARY, f"next_players_{new_page}_{l_char}", label="Siguiente ➡️")
            
            components = [select_menu, button_row]
            
            await event.interaction.create_initial_response(
                hikari.ResponseType.MESSAGE_UPDATE,
                embed=embed,
                components=components
            )
        except Exception as e:
            pass

    elif custom_id == "db_players_select":
        steam_id = event.interaction.values[0]
        try:
            steam_info = await plugin.model.api.get_steam_player(steam_id)
            player_name = steam_info.get("personaname") if steam_info else "Desconocido"
            
            hist_stats = await plugin.model.api.get_player_historical_stats(steam_id)
            if not hist_stats:
                hist_stats = {"total_kills": 0, "total_deaths": 0, "total_cash_earned": 0}
                
            embed = hikari.Embed(title=f"📊 Perfil Histórico: {player_name}", color=0x3498DB)
            if steam_info and steam_info.get("avatarfull"):
                embed.set_thumbnail(steam_info["avatarfull"])
                
            embed.add_field(
                name="📚 Histórico Total",
                value=(
                    f"💀 **Kills:** `{hist_stats.get('total_kills', 0)}`\n"
                    f"⚰️ **Deaths:** `{hist_stats.get('total_deaths', 0)}`\n"
                    f"💰 **Cash Earned:** `${hist_stats.get('total_cash_earned', 0)}`"
                ),
                inline=False
            )
            embed.set_footer(text=f"Steam ID: {steam_id}")
            
            await event.interaction.create_initial_response(
                hikari.ResponseType.MESSAGE_CREATE,
                embed=embed,
                flags=hikari.MessageFlag.EPHEMERAL # Show ephemeral to not clutter chat
            )
        except Exception as e:
            pass

    elif custom_id.startswith("prev_matches_") or custom_id.startswith("next_matches_"):
        parts = custom_id.split("_")
        action = parts[0]
        current_page = int(parts[2])
        
        new_page = current_page - 1 if action == "prev" else current_page + 1
        if new_page < 1:
            new_page = 1
            
        try:
            res = await plugin.model.api.get_paginated_matches(page=new_page, limit=10)
            matches = res.get("matches", [])
            total = res.get("total", 0)
            
            if not matches and action == "next":
                await event.interaction.create_initial_response(
                    hikari.ResponseType.MESSAGE_UPDATE
                )
                return
                
            embed = hikari.Embed(
                title=f"⚔️ Historial de Partidas (Pág {new_page})",
                description=f"Total jugadas: {total}",
                color=0xFF4500
            )
            
            for m in matches:
                start = m['start_time'][:16].replace("T", " ")
                end = m['end_time'][:16].replace("T", " ") if m['end_time'] else "En progreso"
                embed.add_field(name=f"Match ID: {m['id']}", value=f"**Mapa:** {m['map']}\n**Inicio:** {start}\n**Fin:** {end}", inline=False)
                
            components = [
                plugin.app.rest.build_message_action_row()
                .add_interactive_button(hikari.ButtonStyle.PRIMARY, f"prev_matches_{new_page}", label="◀ Anterior")
                .add_interactive_button(hikari.ButtonStyle.PRIMARY, f"next_matches_{new_page}", label="Siguiente ▶")
            ]
            
            await event.interaction.create_initial_response(
                hikari.ResponseType.MESSAGE_UPDATE,
                embed=embed,
                components=components
            )
        except Exception as e:
            pass

@plugin.include
@db_group.child
@crescent.command(name="status", description="Muestra el estado actual del servidor RCON y rotación")
class DbStatus:
    async def callback(self, ctx: crescent.Context) -> None:
        await ctx.defer()
        try:
            status = await plugin.model.api.get_status()
            
            embed = hikari.Embed(
                title=f"🎮 {status.serverName or 'Servidor Wardogs'}",
                color=0x32CD32
            )
            
            score_curr = status.scoreTick.current if status.scoreTick else 0
            score_max = status.scoreCap or 100
            
            embed.add_field(name="Mapa Actual", value=f"**{status.map}**", inline=True)
            embed.add_field(name="Modos", value=", ".join(status.experiences or []), inline=True)
            embed.add_field(name="Score", value=f"{score_curr} / {score_max}", inline=True)
            
            players_curr = status.players.current if status.players else 0
            players_max = status.players.max if status.players else 64
            embed.add_field(name="Jugadores", value=f"{players_curr} / {players_max}", inline=False)
            
            await ctx.respond(embed=embed)
        except Exception as e:
            await ctx.respond(f"❌ Error al conectar con el servidor: {e}")

@plugin.include
@crescent.hook(admin_only)
@db_group.child
@crescent.command(name="memberships", description="Listado de membresías (Paginado)")
class DbMemberships:
    async def callback(self, ctx: crescent.Context) -> None:
        await ctx.defer(ephemeral=True)
        page = 1
        try:
            res = await plugin.model.api.get_paginated_memberships(page=page, limit=10)
            memberships = res.get("memberships", [])
            total = res.get("total", 0)
            
            if not memberships:
                await ctx.respond("No hay membresías registradas.")
                return
                
            embed = hikari.Embed(
                title=f"📋 Listado de Membresías (Pág {page})",
                description=f"Total registradas: {total}",
                color=0x00FF00
            )
            
            for m in memberships:
                status = "🟢 Activa" if m['is_active'] else "🔴 Inactiva"
                end_str = m['end_date'][:10] if m['end_date'] else "Permanente"
                sp_str = f" | **Especial:** <@&{m.get('special_role')}>" if m.get('special_role') else ""
                embed.add_field(
                    name=f"[ID: {m.get('id', '?')}] SteamID: {m['steam_id']}", 
                    value=f"**Tipo:** {m['type']} | **Estado:** {status}\n**Vence:** {end_str}{sp_str}", 
                    inline=False
                )
                
            components = [
                ctx.app.rest.build_message_action_row()
                .add_interactive_button(hikari.ButtonStyle.PRIMARY, f"mem_prev_{page}", label="Anterior")
                .add_interactive_button(hikari.ButtonStyle.PRIMARY, f"mem_next_{page}", label="Siguiente")
            ]
            
            await ctx.respond(embed=embed, components=components)
        except Exception as e:
            await ctx.respond(f"❌ Error: {e}")

@plugin.include
@crescent.event
async def on_membership_button_click(event: hikari.InteractionCreateEvent) -> None:
    if not isinstance(event.interaction, hikari.ComponentInteraction):
        return
        
    custom_id = event.interaction.custom_id
    if not custom_id.startswith("mem_prev_") and not custom_id.startswith("mem_next_"):
        return
        
    current_page = int(custom_id.split("_")[-1])
    is_next = custom_id.startswith("mem_next_")
    new_page = current_page + 1 if is_next else current_page - 1
    
    if new_page < 1:
        new_page = 1
        
    try:
        res = await plugin.model.api.get_paginated_memberships(page=new_page, limit=10)
        memberships = res.get("memberships", [])
        total = res.get("total", 0)
        
        if not memberships and new_page > 1:
            await event.interaction.create_initial_response(
                hikari.ResponseType.MESSAGE_CREATE,
                "No hay más páginas.",
                flags=hikari.MessageFlag.EPHEMERAL
            )
            return
            
        embed = hikari.Embed(
            title=f"📋 Listado de Membresías (Pág {new_page})",
            description=f"Total registradas: {total}",
            color=0x00FF00
        )
        
        for m in memberships:
            status = "🟢 Activa" if m['is_active'] else "🔴 Inactiva"
            end_str = m['end_date'][:10] if m['end_date'] else "Permanente"
            sp_str = f" | **Especial:** <@&{m.get('special_role')}>" if m.get('special_role') else ""
            embed.add_field(
                name=f"[ID: {m.get('id', '?')}] SteamID: {m['steam_id']}", 
                value=f"**Tipo:** {m['type']} | **Estado:** {status}\n**Vence:** {end_str}{sp_str}", 
                inline=False
            )
            
        components = [
            plugin.app.rest.build_message_action_row()
            .add_interactive_button(hikari.ButtonStyle.PRIMARY, f"mem_prev_{new_page}", label="Anterior")
            .add_interactive_button(hikari.ButtonStyle.PRIMARY, f"mem_next_{new_page}", label="Siguiente")
        ]
        
        await event.interaction.create_initial_response(
            hikari.ResponseType.MESSAGE_UPDATE,
            embed=embed,
            components=components
        )
    except Exception as e:
        await event.interaction.create_initial_response(
            hikari.ResponseType.MESSAGE_CREATE,
            f"❌ Error: {e}",
            flags=hikari.MessageFlag.EPHEMERAL
        )
@plugin.include
@crescent.hook(admin_only)
@db_group.child
@crescent.command(name="edit_membership", description="Edita una membresía existente")
class DbEditMembership:
    id_membresia: int = crescent.option(int, "ID de la membresía (ver /db memberships)")  # type: ignore
    dias: int | None = crescent.option(int, "Nuevos días (0 = permanente)", default=None, min_value=0)  # type: ignore
    tipo: str | None = crescent.option(str, "Nuevo tipo de membresía", autocomplete=autocomplete_tipo, default=None)  # type: ignore
    activa: bool | None = crescent.option(bool, "¿Está activa?", default=None)  # type: ignore

    async def callback(self, ctx: crescent.Context) -> None:
        await ctx.defer()
        try:
            await plugin.model.api.edit_membership(self.id_membresia, days=self.dias, membership_type=self.tipo, is_active=self.activa)
            await ctx.respond(f"✅ Membresía ID {self.id_membresia} actualizada exitosamente.")
        except Exception as e:
            await ctx.respond(f"❌ Error: {e}")


@plugin.include
@crescent.hook(admin_only)
@db_group.child
@crescent.command(name="remove_membership", description="Elimina una membresía existente permanentemente")
class DbRemoveMembership:
    id_membresia = crescent.option(int, "ID de la membresía (ver /db memberships)")

    async def callback(self, ctx: crescent.Context) -> None:
        await ctx.defer()
        try:
            await plugin.model.api.delete_membership(self.id_membresia)
            await ctx.respond(f"✅ Membresía ID {self.id_membresia} eliminada exitosamente.")
        except Exception as e:
            await ctx.respond(f"❌ Error: {e}")


@plugin.include
@crescent.hook(admin_only)
@db_group.child
@crescent.command(name="add_special_role", description="Añade un rol especial permanente a un jugador")
class DbAddSpecialRole:
    usuario = crescent.option(hikari.User, "Usuario de Discord") # type: ignore
    rol_especial = crescent.option(hikari.Role, "Rol especial a asignar") # type: ignore

    async def callback(self, ctx: crescent.Context) -> None:
        await ctx.defer()
        try:
            player_info = await plugin.model.api.get_player_by_discord(str(self.usuario.id))
            if not player_info:
                await ctx.respond(f"❌ El usuario {self.usuario.mention} no está vinculado.")
                return
            steam_id = player_info.get("steam_id")
            await plugin.model.api.add_special_role(steam_id, str(self.rol_especial.id))
            await ctx.respond(f"✅ Rol especial <@&{self.rol_especial.id}> añadido al jugador {self.usuario.mention} (`{steam_id}`).")
        except Exception as e:
            await ctx.respond(f"❌ Error: {e}")

@plugin.include
@crescent.hook(admin_only)
@db_group.child
@crescent.command(name="remove_special_role", description="Remueve un rol especial permanente de un jugador")
class DbRemoveSpecialRole:
    usuario = crescent.option(hikari.User, "Usuario de Discord") # type: ignore
    rol_especial = crescent.option(hikari.Role, "Rol especial a remover") # type: ignore

    async def callback(self, ctx: crescent.Context) -> None:
        await ctx.defer()
        try:
            player_info = await plugin.model.api.get_player_by_discord(str(self.usuario.id))
            if not player_info:
                await ctx.respond(f"❌ El usuario {self.usuario.mention} no está vinculado.")
                return
            steam_id = player_info.get("steam_id")
            await plugin.model.api.remove_special_role(steam_id, str(self.rol_especial.id))
            await ctx.respond(f"✅ Rol especial <@&{self.rol_especial.id}> removido del jugador {self.usuario.mention} (`{steam_id}`).")
        except Exception as e:
            await ctx.respond(f"❌ Error: {e}")

@plugin.include
@crescent.hook(admin_only)
@db_group.child
@crescent.command(name="edit_player", description="Edita información de un jugador (debe estar vinculado)")
class DbEditPlayer:
    usuario_discord = crescent.option(hikari.User, "Usuario de Discord (jugador vinculado)") # type: ignore
    mensaje_bienvenida = crescent.option(str, "Nuevo mensaje de bienvenida personalizado", default=None) # type: ignore
    observacion = crescent.option(str, "Añadir/editar nota interna sobre pagos, conducta, etc.", default=None) # type: ignore

    async def callback(self, ctx: crescent.Context) -> None:
        await ctx.defer()
        try:
            player_info = await plugin.model.api.get_player_by_discord(str(self.usuario_discord.id))
            if not player_info:
                await ctx.respond(f"❌ El usuario {self.usuario_discord.mention} no está vinculado a ningún Steam ID. Usa `/db link_player` primero.")
                return
                
            steam_id = player_info.get("steam_id")
            
            await plugin.model.api.edit_player(
                steam_id, 
                custom_welcome_message=self.mensaje_bienvenida, 
                observations=self.observacion
            )
            await ctx.respond(f"✅ Jugador `{steam_id}` ({self.usuario_discord.mention}) actualizado exitosamente.")
        except Exception as e:
            await ctx.respond(f"❌ Error: {e}")

