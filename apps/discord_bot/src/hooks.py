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
        
    admin_role_str = await ctx.client.model.api.get_bot_config("ADMIN_ROLE_ID")
    admin_role_id = int(admin_role_str) if admin_role_str else 0
    
    if admin_role_id in ctx.member.role_ids:
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
        
    admin_role_str = await ctx.client.model.api.get_bot_config("ADMIN_ROLE_ID")
    vip_roles_str = await ctx.client.model.api.get_bot_config("VIP_ROLE_IDS")
    
    admin_role_id = int(admin_role_str) if admin_role_str else 0
    vip_role_ids = [int(r) for r in vip_roles_str.split(",")] if vip_roles_str else []
    
    if admin_role_id in ctx.member.role_ids or any(r in ctx.member.role_ids for r in vip_role_ids):
        return crescent.HookResult()
        
    await ctx.respond("No tienes permisos VIP/Admin para usar este comando.", flags=hikari.MessageFlag.EPHEMERAL)
    return crescent.HookResult(exit=True)

async def check_is_admin(ctx: crescent.Context) -> bool:
    if not ctx.member:
        return False
        
    if isinstance(ctx.member, hikari.InteractionMember) and (ctx.member.permissions & hikari.Permissions.ADMINISTRATOR) == hikari.Permissions.ADMINISTRATOR:
        return True
        
    admin_role_str = await ctx.client.model.api.get_bot_config("ADMIN_ROLE_ID")
    admin_role_id = int(admin_role_str) if admin_role_str else 0
    return admin_role_id in ctx.member.role_ids
