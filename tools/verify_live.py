import httpx

base = "http://localhost:8000"
headers = {"x-api-key": "local-api-key"}

with httpx.Client(base_url=base, headers=headers, timeout=10) as client:
    # 1. Status
    r_status = client.get("/api/v1/status")
    assert r_status.status_code == 200
    print("1. Status OK:", r_status.json().get("server_name"))
    
    # 2. Sync Memberships
    r_sync = client.post("/api/v1/db/sync_memberships")
    assert r_sync.status_code == 200
    sync_data = r_sync.json()
    print("2. Sync OK: role_maps count =", len(sync_data["role_maps"]), "managed_special_roles =", sync_data["managed_special_roles"])
    
    # 3. Admins verification
    for sid, name in [("76561199157256458", "ARTEC"), ("76561198151376508", "BlackSoulRazor")]:
        r_prof = client.get(f"/api/v1/db/players/steam/{sid}")
        assert r_prof.status_code == 200
        p = r_prof.json()
        role = p.get("active_role")
        assert role == "ADMIN", f"{name} active_role is not ADMIN: {role}"
        print(f"3. Admin {name} OK: active_role={role}, memberships={len(p.get('memberships', []))}")
        
    # 4. Membership types
    r_types = client.get("/api/v1/membership-types")
    assert r_types.status_code == 200
    types = r_types.json()
    print("4. Membership Types OK:", [(t["code"], t["price_usd"], t.get("base_price_usd"), t.get("role_id")) for t in types])

    # 5. Memberships pagination
    r_mems = client.get("/api/v1/db/memberships?page=1&limit=5")
    assert r_mems.status_code == 200
    mems = r_mems.json()
    print("5. Memberships Paginated OK: total =", mems["total"], "sample role_granted_id =", mems["memberships"][0].get("role_granted_id"))

print("\nALL LIVE INTEGRATION CHECKS PASSED!")
