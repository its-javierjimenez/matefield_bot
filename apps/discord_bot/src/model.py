import hikari
import os
from src.api_client import APIClient

class Model:
    api: APIClient
    active_match_id: str
    players_cache: dict
    initial_scan_done: bool
    
    def __init__(self):
        self.api = APIClient(
            base_url=os.environ.get("API_BASE_URL", "http://127.0.0.1:8000"),
            api_key=os.environ.get("API_KEY", "default_secret_key")
        )
        self.active_match_id = ""
        self.players_cache = {}
        self.hacker_monitors = {}
        self.player_last_seen = {}
        self.initial_scan_done = False

