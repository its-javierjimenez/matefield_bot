# Configuración local de Discord

Aplicación: **Matefield Test BOT** (`1554286067442524252`).
Servidor de pruebas: **PRUEBAS MATEFIELD** (`1552776537772920963`).
Canal de staff habilitado: `🔰╽comandos` (`1552776538968166529`).
Hay otro canal `🤖╽comandos` en Comunidad: es distinto y no se modificó.

## Qué archivo se usa

| Ejecución | Archivo / origen |
| --- | --- |
| Docker Compose local, bot y API | `.env.local`, inyectado por `env_file` |
| Python directo, bot y API | `.env` más cercano al entrypoint al buscar hacia la raíz; actualmente el de la raíz del proyecto |
| Compose desarrollo | `.env.dev` |
| Compose producción | `.env.prod` |

`apps/discord_bot/src/main.py` y `apps/api_rcon/src/main.py` ejecutan `load_dotenv()` sin `override`: una variable ya exportada en el proceso tiene prioridad sobre el archivo. Pydantic lee ese entorno; los modelos de settings no seleccionan otro archivo. Docker trabaja en `/app/apps/discord_bot` o `/app/apps/api_rcon`. Los archivos `main.py` directamente bajo cada app son ejemplos que solo imprimen un saludo y no arrancan los servicios.

`.env.local` usa los nombres internos `api_rcon`, `postgres` y `mock_rcon`. `.env` usa `127.0.0.1` para ejecución directa en WSL contra los puertos publicados por Docker. Ambos guardan la identidad del mismo bot. No ejecutar dos instancias del bot simultáneamente.

## Aplicar cambios en Docker

Desde la raíz del proyecto:

```bash
docker compose -f docker-compose.local.yml up -d --no-deps --force-recreate api_rcon discord_bot
```

Un simple `docker restart` no vuelve a cargar las variables de `env_file`.
Editar `.env.local` para la ejecución actual en Docker. Si también se utiliza Python directo, mantener el token correspondiente en `.env`. No versionar ni compartir estos archivos.

## Python directo (opcional)

Requiere Python 3.13+, uv y dependencias instaladas. Este modo no quedó iniciado; la ejecución verificada es Docker.

Desde `apps/discord_bot`: `uv run python -m src.main`.
Desde `apps/api_rcon`: `uv run uvicorn src.main:app --host 0.0.0.0 --port 8000`.
Detener el servicio equivalente en Docker antes de arrancarlo directamente.

Alembic es un caso separado: si `DATABASE_URL` ya existe, la usa. Si no existe, busca según `ENV_FILE`, luego `ENV=prod/local`, luego `.env.dev` si existe y finalmente `.env`. En Docker, `DATABASE_URL` ya llega desde `.env.local`.

## Alcance verificado

Bot y API usan la aplicación de pruebas; la base local tiene `GUILD_ID` del servidor de pruebas. Los comandos se registran globalmente por Crescent. El bot tiene acceso específico al canal privado de staff, sin permiso Administrador.

## Vinculación desde Discord

El panel utiliza un botón verde persistente `btn_start_steam_link` con el logo de Steam. El evento del gateway de Discord aporta la identidad del usuario; el handler sigue registrado al reiniciar el bot. El bot consulta la API con `X-API-Key` antes de emitir el enlace. Si ya existe vínculo, responde de forma privada y no ofrece botón. `/player link` utiliza el mismo flujo.

El enlace privado a Steam dura diez minutos, lleva propósito, nonce aleatorio e identidad firmados con HMAC. La API ignora cualquier identidad de Chrome o parámetro Discord sin firma y vuelve a consultar el vínculo al abrir el enlace y al recibir el retorno de Steam. Un cookie temporal por intento protege el retorno; no guarda ni selecciona una identidad Discord y permite dos cuentas Discord en pestañas distintas. Se valida que Steam haya firmado el retorno exacto, identidad y campos requeridos, y se verifica la respuesta con Steam.

La migración `m9i0d1e2f3g4` guarda el hash de los enlaces consumidos en la misma transacción que el vínculo. Las restricciones únicas y actualizaciones condicionales evitan reemplazos concurrentes. Repetir un callback devuelve el vínculo existente sin volver a otorgar roles; un enlace consumido tampoco sirve después de desvincular. Los registros vencidos se purgan en el mantenimiento periódico.

Las rutas públicas antiguas de OAuth/cambio de cuenta ya no autentican: indican volver al botón de Discord. Se retiró la sesión de identidad de 12 horas. Los secretos OAuth que pudieran quedar en los archivos locales no se utilizan para este flujo; no hace falta configurar redirect URI de Discord. Los enlaces de la versión anterior deben solicitarse nuevamente.

Las pantallas finales no tienen botones; muestran el resultado y la indicación breve aprobada. No se requiere ni se realizó una autorización personal durante la verificación automatizada.

El enlace privado contiene solo identificadores y vigencia; nombre/avatar se resuelven fuera de la URL para respetar el máximo de 512 caracteres de los botones de Discord. La respuesta de cuenta ya vinculada muestra campos separados «Discord» y «Steam», incluso cuando ambos nombres coinciden. Panel vigente publicado por el usuario: `1554316608413892640` en el canal de staff indicado arriba.

Las rutas históricas se conservan solo como respuesta 410 para enlaces guardados: no implementan OAuth ni cambio de identidad. Las páginas comparten `/static/css/steam_link.css`; ya no requieren variables de enlaces a canales. Cancelar Steam devuelve una indicación breve para volver a Discord, y un enlace incompleto muestra la misma recuperación que uno vencido.
