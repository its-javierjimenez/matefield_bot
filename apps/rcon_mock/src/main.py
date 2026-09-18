from fastapi import FastAPI, Depends, Header, HTTPException, Request
from typing import Optional, List
import datetime
from wardogs_schemas import v1 as schemas

app = FastAPI(title="Wardogs RCON Mock")

audit_logs = []

def add_audit_log(event: str, detail: str):
    audit_logs.insert(0, {
        "timestampUtc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "peer": "127.0.0.1",
        "sessionId": "mock-session",
        "event": event,
        "detail": detail
    })

def verify_auth(authorization: Optional[str] = Header(None)):
    if authorization != "Bearer test":
        raise HTTPException(status_code=401, detail="Unauthorized")
    return authorization

from typing import Any, Dict

mock_state: Dict[str, Any] = {
    "score": 50,
    "rotation": 0,
    "maps": ["Bakurani", "Desert Strike", "Urban Combat", "Jungle Ops"],
    "match_seconds": 600,
    "lonestar_score": 100,
    "manticore_score": 150,
    "valkyre_score": 200
}

@app.get("/v1/status", response_model=schemas.Status)
async def get_status(auth: str = Depends(verify_auth)):
    # Simulate time passing/points
    mock_state["score"] += 15
    mock_state["match_seconds"] += 10
    mock_state["lonestar_score"] += random.randint(1, 5)
    mock_state["manticore_score"] += random.randint(1, 5)
    mock_state["valkyre_score"] += random.randint(1, 5)
    
    if mock_state["score"] >= 100:
        mock_state["score"] = 0
        mock_state["rotation"] = (mock_state["rotation"] + 1) % len(mock_state["maps"])
        mock_state["match_seconds"] = 0
        mock_state["lonestar_score"] = 0
        mock_state["manticore_score"] = 0
        mock_state["valkyre_score"] = 0
        
    current_map = mock_state["maps"][mock_state["rotation"]]
    
    return {
        "serverName": "Wardogs Mock Server",
        "map": current_map,
        "experiences": ["Rush", "Conquest"],
        "lighting": "Day",
        "alternator": "Random",
        "scoreTick": {"current": mock_state["score"], "min": 0, "max": 100},
        "scoreCap": 100,
        "matchSeconds": mock_state["match_seconds"],
        "players": {"current": len(mock_players), "max": 100},
        "factionScores": [
            {"name": "Lonestar", "colorHex": "#0000FF", "score": mock_state["lonestar_score"]},
            {"name": "Manticore", "colorHex": "#00FF00", "score": mock_state["manticore_score"]},
            {"name": "Valkyre", "colorHex": "#FF0000", "score": mock_state["valkyre_score"]}
        ],
        "rotation": {"nowIndex": mock_state["rotation"], "nextIndex": (mock_state["rotation"] + 1) % len(mock_state["maps"])}
    }

from typing import Any, Dict, List

mock_players: List[Dict[str, Any]] = [
    {
        "name": "PlayerOne",
        "steamId": "76561198000000001",
        "faction": "Lonestar",
        "kills": 15,
        "deaths": 2,
        "cash": 1500,
        "pingMs": 45
    },
    {
        "name": "PlayerTwo",
        "steamId": "76561198000000002",
        "faction": "Manticore",
        "kills": 3,
        "deaths": 5,
        "cash": 300,
        "pingMs": 60
    },
    {
        "name": "PlayerThree",
        "steamId": "76561198000000003",
        "faction": "Valkyre",
        "kills": 8,
        "deaths": 1,
        "cash": 800,
        "pingMs": 30
    }
]

import random

@app.get("/v1/players", response_model=schemas.Players1)
async def get_players(auth: str = Depends(verify_auth)):
    # Si acaba de cambiar el mapa (score es bajo), quizas podriamos reiniciar los stats, 
    # pero para simular basta con subirlos aleatoriamente.
    for p in mock_players:
        if random.random() > 0.5:
            p["kills"] += random.randint(1, 3)
            p["cash"] += random.randint(50, 200)
        if random.random() > 0.7:
            p["deaths"] += 1
        p["pingMs"] = random.randint(20, 100)
        
    return {
        "players": mock_players
    }

@app.get("/v1/audit", response_model=schemas.Audit)
async def get_audit(limit: int = 50, auth: str = Depends(verify_auth)):
    return {
        "entries": audit_logs[:limit]
    }

reserved_slots_state = ["76561198000000001"]

@app.get("/v1/reserved-slots", response_model=schemas.ReservedSlots)
async def get_reserved_slots(auth: str = Depends(verify_auth)):
    return {
        "reservedSlots": reserved_slots_state
    }

@app.post("/v1/reserved-slots")
async def add_reserved_slot(req: schemas.SteamIdRequest, auth: str = Depends(verify_auth)):
    add_audit_log("ReservedSlotAdded", f"Added steamId: {req.steamId}")
    if req.steamId not in reserved_slots_state:
        reserved_slots_state.append(req.steamId)
    return {"message": "Success"}

@app.delete("/v1/reserved-slots/{steam_id}")
async def remove_reserved_slot(steam_id: str, auth: str = Depends(verify_auth)):
    add_audit_log("ReservedSlotRemoved", f"Removed steamId: {steam_id}")
    if steam_id in reserved_slots_state:
        reserved_slots_state.remove(steam_id)
    return {"message": "Success"}

@app.post("/v1/broadcast")
async def broadcast(req: schemas.MessageRequest, auth: str = Depends(verify_auth)):
    add_audit_log("Broadcast", f"Message: {req.message}")
    return {"message": "Broadcast sent"}

@app.post("/v1/players/{steam_id}/message")
async def send_player_message(steam_id: str, req: schemas.MessageRequest, auth: str = Depends(verify_auth)):
    add_audit_log("PlayerMessage", f"Message to {steam_id}: {req.message}")
    return {"ok": True}

@app.post("/v1/players/{steam_id}/kick")
async def kick_player(steam_id: str, req: schemas.ReasonRequest, auth: str = Depends(verify_auth)):
    add_audit_log("Kick", f"Kicked {steam_id}. Reason: {req.reason}")
    global mock_players
    mock_players = [p for p in mock_players if p["steamId"] != steam_id]
    return {"ok": True}

@app.post("/v1/bans")
async def ban_player(req: schemas.BanRequest, auth: str = Depends(verify_auth)):
    add_audit_log("Ban", f"Banned {req.steamId}. Reason: {req.reason}")
    global mock_players
    mock_players = [p for p in mock_players if p["steamId"] != req.steamId]
    return {"ok": True}

@app.patch("/v1/players/{steam_id}")
async def switch_faction_patch(steam_id: str, req: schemas.FactionRequest, auth: str = Depends(verify_auth)):
    add_audit_log("SwitchFaction", f"Switched {steam_id} to faction {req.faction}")
    for p in mock_players:
        if p["steamId"] == steam_id:
            p["faction"] = req.faction
    return {"ok": True}

@app.post("/v1/players/{steam_id}/faction")
async def switch_faction_post(steam_id: str, req: schemas.FactionRequest, auth: str = Depends(verify_auth)):
    return await switch_faction_patch(steam_id, req, auth)

mock_config_state = {
    "revision": "rev100",
    "text": (
        "[/Script/WDGame.WDGameSession]\n"
        "ServerName=Wardogs Mock Server\n"
        "MaxReservedSlots=20\n\n"
        "[/Script/WDGame.WDGameStateSession]\n"
        "bLockOverpopulatedTeamsConfig=true\n"
        "OverpopulatedTeamThresholdConfig=1\n"
    )
}

@app.get("/v1/config", response_model=schemas.Config1)
async def get_config(auth: str = Depends(verify_auth)):
    return {
        "text": mock_config_state["text"],
        "revision": mock_config_state["revision"]
    }

@app.put("/v1/config", response_model=schemas.ConfigResult)
async def update_config(req: Request, auth: str = Depends(verify_auth)):
    body = await req.body()
    new_text = body.decode("utf-8")
    mock_config_state["text"] = new_text
    rev_num = 100
    try:
        rev_num = int(mock_config_state["revision"].replace("rev", "")) + 1
    except Exception:
        rev_num += 1
    new_rev = f"rev{rev_num}"
    mock_config_state["revision"] = new_rev
    add_audit_log("ConfigUpdate", f"Configuration was updated: {len(body)} bytes")
    return {
        "success": True,
        "newRevision": new_rev
    }

@app.post("/mock/next_match")
async def force_next_match():
    mock_state["score"] = 0
    mock_state["rotation"] = (mock_state["rotation"] + 1) % len(mock_state["maps"])
    mock_state["match_seconds"] = 0
    mock_state["lonestar_score"] = 0
    mock_state["manticore_score"] = 0
    mock_state["valkyre_score"] = 0
    add_audit_log("MatchTransition", f"Forced next match: {mock_state['maps'][mock_state['rotation']]}")
    return {
        "ok": True,
        "new_rotation": mock_state["rotation"],
        "map": mock_state["maps"][mock_state["rotation"]]
    }


@app.post("/mock/seed_full_server")
async def seed_full_server(total: int = 100):
    global mock_players
    new_players = []
    # Generate 100 players: 34 Lonestar, 33 Valkyre, 33 Manticore
    for i in range(1, total + 1):
        if i <= 34:
            faction = "Lonestar"
        elif i <= 67:
            faction = "Valkyre"
        else:
            faction = "Manticore"
            
        new_players.append({
            "name": f"MockPlayer_{i}",
            "steamId": f"7656119800000{i:04d}",
            "faction": faction,
            "kills": random.randint(0, 20),
            "deaths": random.randint(0, 15),
            "cash": random.randint(100, 2000),
            "pingMs": random.randint(20, 80)
        })
    mock_players = new_players
    return {
        "ok": True, 
        "total": len(mock_players), 
        "lonestar": sum(1 for p in mock_players if p["faction"] == "Lonestar"),
        "valkyre": sum(1 for p in mock_players if p["faction"] == "Valkyre"),
        "manticore": sum(1 for p in mock_players if p["faction"] == "Manticore")
    }

@app.post("/mock/reset_players")
async def reset_players():
    global mock_players
    mock_players = [
        {
            "name": "PlayerOne",
            "steamId": "76561198000000001",
            "faction": "Lonestar",
            "kills": 15,
            "deaths": 2,
            "cash": 1500,
            "pingMs": 45
        },
        {
            "name": "PlayerTwo",
            "steamId": "76561198000000002",
            "faction": "Manticore",
            "kills": 3,
            "deaths": 5,
            "cash": 300,
            "pingMs": 60
        },
        {
            "name": "PlayerThree",
            "steamId": "76561198000000003",
            "faction": "Valkyre",
            "kills": 8,
            "deaths": 1,
            "cash": 800,
            "pingMs": 30
        }
    ]
    return {"ok": True, "total": len(mock_players)}

