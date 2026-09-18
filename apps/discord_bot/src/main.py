import hikari
import crescent
from dotenv import load_dotenv
import os
import logging
import colorlog
from src.model import Model

# Configurar logs coloridos
handler = colorlog.StreamHandler()
handler.setFormatter(colorlog.ColoredFormatter(
    '%(log_color)s[%(asctime)s] [%(levelname)s] %(name)s: %(message)s',
    datefmt='%H:%M:%S',
    log_colors={
        'DEBUG': 'cyan',
        'INFO': 'green',
        'WARNING': 'yellow',
        'ERROR': 'red',
        'CRITICAL': 'bold_red',
    }
))

logger = colorlog.getLogger("wardogs")
logger.addHandler(handler)
logger.setLevel(logging.INFO)
# Hikari ya tiene sus propios logs, los dejamos en INFO o WARNING si queremos menos ruido
logging.getLogger("hikari").setLevel(logging.WARNING)

load_dotenv()

bot = hikari.GatewayBot(
    os.environ["DISCORD_TOKEN"],
    intents=hikari.Intents.ALL_UNPRIVILEGED
)
model = Model()
client = crescent.Client(bot, model)

# Cargar plugins (aqui cargaremos los comandos)
client.plugins.load_folder("src.plugins")

if __name__ == "__main__":
    if os.environ.get("DISCORD_TOKEN") == "tu_token_aqui":
        print("Error: Por favor configura el DISCORD_TOKEN en el archivo .env")
    else:
        bot.run()
