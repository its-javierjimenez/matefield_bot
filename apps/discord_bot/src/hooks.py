import crescent
import hikari
import os

async def admin_only(ctx: crescent.Context) -> crescent.HookResult:
    if not ctx.member:
        await ctx.respond("Este comando solo puede usarse en un servidor.", flags=hikari.MessageFlag.EPHEMERAL)
        return crescent.HookResult(exit=True)
        
    # El creador del servidor o alguien con el permiso nativo de Administrador de Discord tiene acceso total
    if isinstance(ctx.member, hikari.InteractionMember) and (ctx.member.permissions & hikari.Permissions.ADMINISTRATOR) == hikari.Permissions.ADMINISTRATOR:
        return crescent.HookResult()
        
    roles = await ctx.client.model.api.get_all_roles()
    admin_role_ids = [int(r["discord_role_id"]) for r in roles if r.get("role_type") == "SYSTEM" and r.get("discord_role_id") and str(r["discord_role_id"]).isdigit()]
    
    if any(r in ctx.member.role_ids for r in admin_role_ids):
        return crescent.HookResult()
        
    await ctx.respond("No tienes permisos de Administrador para usar este comando.", flags=hikari.MessageFlag.EPHEMERAL)
    return crescent.HookResult(exit=True)

async def vip_or_admin(ctx: crescent.Context) -> crescent.HookResult:
    if not ctx.member:
        await ctx.respond("Este comando solo puede usarse en un servidor.", flags=hikari.MessageFlag.EPHEMERAL)
        return crescent.HookResult(exit=True)
        
    # Los Administradores nativos de Discord tambin tienen acceso a comandos VIP
    if isinstance(ctx.member, hikari.InteractionMember) and (ctx.member.permissions & hikari.Permissions.ADMINISTRATOR) == hikari.Permissions.ADMINISTRATOR:
        return crescent.HookResult()
        
    roles = await ctx.client.model.api.get_all_roles()
    admin_role_ids = [int(r["discord_role_id"]) for r in roles if r.get("role_type") == "SYSTEM" and r.get("discord_role_id") and str(r["discord_role_id"]).isdigit()]
    vip_role_ids = [int(r["discord_role_id"]) for r in roles if r.get("role_type") == "VIP" and r.get("discord_role_id") and str(r["discord_role_id"]).isdigit()]
    
    if any(r in ctx.member.role_ids for r in admin_role_ids) or any(r in ctx.member.role_ids for r in vip_role_ids):
        return crescent.HookResult()
        
    await ctx.respond("No tienes permisos VIP/Admin para usar este comando.", flags=hikari.MessageFlag.EPHEMERAL)
    return crescent.HookResult(exit=True)

async def check_is_admin(ctx: crescent.Context) -> bool:
    if not ctx.member:
        return False
        
    if isinstance(ctx.member, hikari.InteractionMember) and (ctx.member.permissions & hikari.Permissions.ADMINISTRATOR) == hikari.Permissions.ADMINISTRATOR:
        return True
        
    roles = await ctx.client.model.api.get_all_roles()
    admin_role_ids = [int(r["discord_role_id"]) for r in roles if r.get("role_type") == "SYSTEM" and r.get("discord_role_id") and str(r["discord_role_id"]).isdigit()]
    return any(r in ctx.member.role_ids for r in admin_role_ids)
