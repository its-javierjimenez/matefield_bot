import sys
from pathlib import Path

discord_bot_src = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    import src
    if hasattr(src, "__path__") and str(discord_bot_src) not in src.__path__:
        src.__path__.append(str(discord_bot_src))
except ImportError:
    pass
