# Wardogs server RCON API — UNOFFICIAL community reference (v1)
Use this as context when helping me build tools (status bots, dashboards, moderation helpers) against it.
Note: unofficial and may be incomplete or change. Confirm what a server supports via GET /v1/capabilities.

## Connection
Base URL: <scheme>://<host>:<port>/v1/...
Default RCON port is 7776 (settable in config or with -RCONPort=).
Transport depends on the listener bind: a loopback listener (127.0.0.1) allows
plaintext over http://; a network listener (0.0.0.0) REQUIRES TLS, so any server
you reach remotely is https://. Bodies/responses are JSON, except the two
config-document endpoints which use text/plain.
Auth: every request sends the header
  Authorization: Bearer <rcon-password>
There is no separate login. The one token authorizes every endpoint (read AND
write) — it is the full-access RCON password, so keep it server-side, never in a
browser. A browser page can call a TLS (https) server; it cannot call a
plaintext loopback listener from an https page (mixed content).
Connection check: GET /v1/status — a success means the token is valid.
Errors: non-2xx status with body { "error": { "code": string, "message": string } }.
Feature detection: GET /v1/capabilities -> { routes: string[], config: { writable: boolean } }.
Not every server enables every route; check here before assuming one exists.

## Read endpoints
GET /v1/status                              live match state (shape below)
GET /v1/players                             connected players (shape below)
GET /v1/capabilities                        supported routes + config flags
GET /v1/bans                                ban list
GET /v1/reserved-slots                      reserved steamIds
GET /v1/audit?limit=N                       admin action log (N 1-500, default 50)
GET /v1/config                              config document + revision
GET /v1/rotation                            map rotation
GET /v1/catalog/maps
GET /v1/catalog/lightings
GET /v1/catalog/experiences
GET /v1/catalog/maps/{id}/experiences
GET /v1/catalog/maps/{id}/alternators
GET /v1/sponsor

## Write endpoints (request body shown)
POST   /v1/players/{steamId}/kick           { reason }
POST   /v1/players/{steamId}/kill           (no body)
POST   /v1/players/{steamId}/message        { message }
PATCH  /v1/players/{steamId}                 { faction }           (capability-gated)
POST   /v1/broadcast                        { message }
POST   /v1/bans                             { steamId, reason? }
DELETE /v1/bans/{steamId}                    (no body)
POST   /v1/reserved-slots                   { steamId }
DELETE /v1/reserved-slots/{steamId}          (no body)
POST   /v1/match/map                        { map, experiences?, lighting?, zoneAlternator? }
POST   /v1/match/end                        (no body)
POST   /v1/match/restart                    (no body)
PUT    /v1/world/lighting                   { lighting }
POST   /v1/rotation/entries                 { map, experiences?, lighting?, zoneAlternator? }
DELETE /v1/rotation/entries/{i}              (no body)
POST   /v1/rotation/entries/{i}/move        { direction: "up" | "down" }
POST   /v1/rotation/save                     (no body)
PATCH  /v1/settings                          { scoreTick?, rotationEnabled?, rotationMode? }
POST   /v1/config/validate                   config text (text/plain)
PUT    /v1/config                            config text (text/plain); header If-Match: "<revision>"; query force=true, fullApply=true
PUT    /v1/sponsor                           { imageUrl }

## Response shapes
GET /v1/status:
{ serverName, map, experiences: string[], lighting, alternator,
  scoreTick: { current, min, max }, scoreCap, matchSeconds,
  players: { current, max },
  factionScores: [ { name, colorHex, ... } ],   // one row per faction
  rotation: { nowIndex, nextIndex } }           // integers, or null

GET /v1/players:
{ players: [ { name, steamId, faction, kills, deaths, cash, pingMs } ] }
  faction is a server-defined name; match it to a factionScores row by colorHex.

GET /v1/rotation:
{ enabled, mode: "ordered" | "random",
  entries: [ { map, experiences: string[], lighting, zoneAlternator,
               status: "now" | "next" | ..., denied: boolean } ] }

GET /v1/bans:            { bans: [ { steamId, bannedAtUtc, bannedBy, reason } ] }
GET /v1/reserved-slots:  { reservedSlots: string[] }
GET /v1/audit:           { entries: [ { timestampUtc, peer, sessionId, event, detail } ] }
GET /v1/config:          { revision, writable, text, sections: [], warnings: [] }

PUT /v1/config & POST /v1/config/validate result:
{ ok, revision, error: { code, message },
  outcomes: [], shadowed: [], stripped: [], errors: [], changed: [],
  conflict: [],        // present on HTTP 412 (stale revision)
  warnings: [], timingsMs }

## Player names
The API returns steamId only, not display names or avatars. Resolve them with the
Steam Web API (ISteamUser/GetPlayerSummaries) using your own key; batch and cache.

## ServerSettings.ini (server config, read at startup)
Only whitelisted sections/keys are honored; omitted keys keep defaults. RCON
ban/reserve/rotation commands edit this file and persist back to it.

[/Script/WDRCON.WDRCONSettings]   ; the RCON listener
bEnabled=true            ; OFF by default
BindAddress=127.0.0.1    ; loopback = plaintext ok; 0.0.0.0 = needs TLS
Port=7776                ; default
Password=                ; plaintext; if empty, auto-written to Saved/RCON/ADMIN-PASSWORD.txt
PasswordHash=""          ; from `WardogsServer -GenerateRCONHash=<pw>`; wins over Password

[/Script/WDGame.WDGameSession]
ServerName= ; ServerPassword= (empty=open) ; ServerImageURL= (1024x256)
ServerMinPlayerCash=0 ; ServerMaxPlayerCash=0 ; ServerMinPlayerLevel=0 ; ServerMaxPlayerLevel=0
MaxReservedSlots=20
+DefaultReservedPlayerIds="<steamId64>"   ; one per line
+DefaultBannedPlayerIds="<steamId64>"     ; one per line

[/Script/Engine.GameSession]
MaxPlayers=128           ; clamped by a dev-set min/max

[MatchState.PreMatch.WaitingForPlayers.PlayerCount]
MinimumRequiredPlayers=60

[MatchState.Playing.KOTH]
ScorePeriod=24           ; score tick seconds, 18-30

[/Script/WDGame.WDGameStateSession]
bLockOverpopulatedTeamsConfig=true  ; When true, blocks joining teams with population advantage (NEXT MATCH)
OverpopulatedTeamThresholdConfig=1  ; Max player difference allowed before locking (NEXT MATCH)
; Controlled via PUT /v1/config with header If-Match: "<revision>"


[/Script/WDGame.WDServerMapRotationSettings]
bEnabled=true ; RotationMode=Ordered|Random
+RotationEntries=(Map="Kavkazi",Experience="Bakurani_KOTH_01",Lighting="DayClear",ZoneAlternator="ZoneAlternator.Factory.Circle")
+RotationEntries=(Map="Europe",Experiences="Madrid_KOTH_01+KOTH_InfantryOnly",Lighting="DayLateGray")
; Experience=one; Experiences=several joined with +; ZoneAlternator optional.

## Notes
- Check GET /v1/capabilities per server; not all routes are always enabled.
- No published rate limit. Poll gently — every few seconds at most (the official panel refreshes on a 3-5s cadence).
- The bearer token is the full-access RCON password; never ship it to a browser.
- Unofficial. Verify against your own server.