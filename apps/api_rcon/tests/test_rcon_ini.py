import pytest
from src.connections.apis.rcon import _update_ini_array

def test_update_ini_array_creates_section_when_missing():
    initial_text = ""
    section = "[/Script/Squad.SquadGameMode]"
    key_prefix = "ReservedSlots"
    items = ["76561198000000001", "76561198000000002"]

    result = _update_ini_array(initial_text, section, key_prefix, items)

    assert section in result
    assert "!ReservedSlots=ClearArray" in result
    assert ".ReservedSlots=76561198000000001" in result
    assert ".ReservedSlots=76561198000000002" in result

def test_update_ini_array_preserves_other_keys_and_sections():
    initial_text = (
        "[General]\n"
        "ServerName=Matefield Server\n"
        "\n"
        "[/Script/Squad.SquadGameMode]\n"
        "MaxPlayers=64\n"
        "!ReservedSlots=ClearArray\n"
        ".ReservedSlots=OLD_STEAM_ID\n"
        "TickRate=30\n"
        "\n"
        "[Admin]\n"
        "Password=secret\n"
    )
    section = "[/Script/Squad.SquadGameMode]"
    key_prefix = "ReservedSlots"
    items = ["NEW_STEAM_ID_1", "NEW_STEAM_ID_2"]

    result = _update_ini_array(initial_text, section, key_prefix, items)

    # Old steam ID should be replaced
    assert "OLD_STEAM_ID" not in result
    assert "!ReservedSlots=ClearArray" in result
    assert ".ReservedSlots=NEW_STEAM_ID_1" in result
    assert ".ReservedSlots=NEW_STEAM_ID_2" in result

    # Other settings must remain intact
    assert "ServerName=Matefield Server" in result
    assert "MaxPlayers=64" in result
    assert "TickRate=30" in result
    assert "Password=secret" in result

def test_update_ini_array_empty_items():
    initial_text = (
        "[/Script/Squad.SquadGameMode]\n"
        "!BannedSlots=ClearArray\n"
        ".BannedSlots=BANNED_ID\n"
    )
    section = "[/Script/Squad.SquadGameMode]"
    key_prefix = "BannedSlots"
    items = []

    result = _update_ini_array(initial_text, section, key_prefix, items)

    assert "!BannedSlots=ClearArray" in result
    assert ".BannedSlots=" not in result
    assert "BANNED_ID" not in result

def test_update_ini_array_consecutive_updates_idempotent():
    initial_text = "[Config]\nKey=Value"
    section = "[Config]"
    key_prefix = "Slots"
    items = ["ID_1", "ID_2"]

    first_update = _update_ini_array(initial_text, section, key_prefix, items)
    second_update = _update_ini_array(first_update, section, key_prefix, items)

    assert first_update == second_update
    assert second_update.count("!Slots=ClearArray") == 1
    assert second_update.count(".Slots=ID_1") == 1
    assert second_update.count(".Slots=ID_2") == 1
