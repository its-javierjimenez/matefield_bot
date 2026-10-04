# wardogs-config

Paquete centralizado de configuración y variables de entorno para Matefield / Wardogs, implementado con `pydantic-settings` y administrado con UV Workspace.

## Contenido

- **`BaseAppConfig`**: Clase base con resolución dinámica de archivos `.env` (soporta `.env`, `.env.local`, `.env.dev`, `.env.prod`, o `ENV_FILE` personalizado).
- **`SecuritySettings`**: Configuración de seguridad, API Keys, tokens de Discord, secretos de sesión y webhooks (Tebex, Steam).
- **`ConnectionSettings`**: Parámetros de base de datos (`DATABASE_URL`), RCON, URLs públicas y políticas de backups.
- **`DiscordBotSettings`**: Configuración exclusiva para el bot de Discord (`DISCORD_TOKEN`, `API_BASE_URL`, emojis de interacción).
- **`EnvironmentSettings`**: Modelo contenedor para el backend API (`APP_ENV`, `SECURITY_SETTINGS`, `CONNECTIONS_SETTINGS`).
- **Instancias singleton exportadas**:
  - `ENVIRONMENT_SETTINGS`: Instancia lista para usar en la API.
  - `BOT_SETTINGS`: Instancia lista para usar en el bot de Discord.
  - `is_prod()`: Helper para comprobar si el entorno es producción.

## Uso

### En la API RCON (`apps/api_rcon`)

```python
from wardogs_config import ENVIRONMENT_SETTINGS, is_prod

# Acceso tipado
api_key = ENVIRONMENT_SETTINGS.SECURITY_SETTINGS.API_KEY
db_url = ENVIRONMENT_SETTINGS.CONNECTIONS_SETTINGS.DATABASE_URL
```

### En el Bot de Discord (`apps/discord_bot`)

```python
from wardogs_config import BOT_SETTINGS

bot = hikari.GatewayBot(BOT_SETTINGS.DISCORD_TOKEN)
```
