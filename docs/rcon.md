# Wardogs server RCON API — UNOFFICIAL community reference (v1)
Use this as context when helping me build tools (status bots, dashboards, moderation helpers) against it.
Note: unofficial and may be incomplete or change. Confirm what a server supports via GET /v1/capabilities.

## Connection
Base URL: http://<host>:<port>/v1/...
Default RCON port is 7776 (settable in config or with -RCONPort=).
Transport is PLAIN HTTP. There is no TLS on the RCON listener — do not "fix" the
scheme to https, it will refuse the connection. The password therefore crosses
the wire in the clear: bind the listener to loopback and tunnel in, or put a
TLS-terminating proxy in front. Bodies/responses are JSON, except the two
config-document endpoints which use text/plain.
Auth: every request sends the header
  Authorization: Bearer <rcon-password>
There is no separate login. The one token authorizes every endpoint (read AND
write) — it is the full-access RCON password, so keep it server-side, never in a
browser. An https page cannot call a plain-http server at all (mixed content is
blocked), so make the call from a server, not from the page.
Connection check: GET /v1/status — a success means the token is valid.
Errors: non-2xx status with body { "error": { "code": string, "message": string } }.
Feature detection: GET /v1/capabilities ->
  { apiVersion, build, auth: { scheme, header },
    limits: { maxBodyBytes, maxRequestsPerMinutePerIp },
    config: { writable: boolean, document: "/v1/config" },
    routes: string[] }   // "METHOD /path", {param} placeholders
Not every server runs the same build; branch on routes rather than catching 404s.

## IMPORTANT: eight write endpoints were removed on 2026-09-14
Build ++Wardogs+Live-CL-501228 dropped PATCH /v1/settings, POST and DELETE
/v1/reserved-slots, POST and DELETE /v1/rotation/entries,
POST /v1/rotation/entries/{i}/move, POST /v1/rotation/save and PUT /v1/sponsor.
A current server answers 404 and omits them from /v1/capabilities. Older servers
still serve them, so check capabilities and support both paths.
What they did now happens by editing the config document:
  reserved slots -> DefaultReservedPlayerIds in [/Script/WDGame.WDGameSession]
  rotation       -> RotationEntries in [/Script/WDGame.WDServerMapRotationSettings]
  rotation on/off, ordered/random -> bEnabled, RotationMode in that same section
  score period   -> ScorePeriod in [MatchState.Playing.KOTH]
  sponsor banner -> ServerImageURL in [/Script/WDGame.WDGameSession]
  rotation save  -> nothing to do; the document IS the file

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
GET /v1/server-id                           { serverId } — stable across restarts
GET /v1/health                              { status, uptimeSeconds, connections: { active },
                                              gameThreadQueue: { inFlight, depth, rejectedTotal } }

## Write endpoints (request body shown)
POST   /v1/players/{steamId}/kick           { reason }
POST   /v1/players/{steamId}/kill           (no body)
POST   /v1/players/{steamId}/message        { message }
PATCH  /v1/players/{steamId}                 { faction }           (capability-gated)
POST   /v1/broadcast                        { message }
POST   /v1/bans                             { steamId, reason? }
DELETE /v1/bans/{steamId}                    (no body)
POST   /v1/reserved-slots                   { steamId }              REMOVED 2026-09-14
DELETE /v1/reserved-slots/{steamId}          (no body)                REMOVED 2026-09-14
POST   /v1/match/map                        { map, experiences?, lighting?, zoneAlternator? }
POST   /v1/match/end                        (no body)
POST   /v1/match/restart                    (no body)
PUT    /v1/world/lighting                   { lighting }
POST   /v1/rotation/entries                 { map, ... }             REMOVED 2026-09-14
DELETE /v1/rotation/entries/{i}              (no body)                REMOVED 2026-09-14
POST   /v1/rotation/entries/{i}/move        { direction: "up"|"down" } REMOVED 2026-09-14
POST   /v1/rotation/save                     (no body)                REMOVED 2026-09-14
PATCH  /v1/settings                          { scoreTick?, ... }      REMOVED 2026-09-14
POST   /v1/config/validate                   config text (text/plain)
PUT    /v1/config                            config text (text/plain); header If-Match: "<revision>"; query force=true, fullApply=true
PUT    /v1/sponsor                           { imageUrl }            REMOVED 2026-09-14

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
  errors:  [ { section, key, code, message } ],  // non-empty => NOTHING applied
  changed: [ { section, added, removed, keys: [] } ],
  outcomes: [], shadowed: [], stripped: [], warnings: [], timingsMs }
HTTP 200 applied, 412 stale revision, 422 a value was rejected.

PUT /v1/config REPLACES THE WHOLE DOCUMENT. Sections you omit are removed. Always
GET it, edit that exact text, PUT it back, and send If-Match: "<revision>".
Every value is revalidated on every apply, including ones you did not touch, so a
pre-existing bad value blocks unrelated edits until it is corrected — read
errors[] and name the offending key to the user.
Array keys use Unreal operators: !Key=ClearArray empties the array and .Key=value
appends. The !Key line is a directive, NOT a member — skip it when indexing.

## Player names
The API returns steamId only, not display names or avatars. Resolve them with the
Steam Web API (ISteamUser/GetPlayerSummaries) using your own key; batch and cache.

## ServerSettings.ini (server config, read at startup)
Only whitelisted sections/keys are honored; omitted keys keep defaults. RCON
ban/reserve/rotation commands edit this file and persist back to it.

[/Script/WDRCON.WDRCONSettings]   ; the RCON listener
bEnabled=true            ; OFF by default
BindAddress=127.0.0.1    ; loopback; 0.0.0.0 = every interface, still plain HTTP
Port=7776                ; default
Password=                ; plaintext; if empty, auto-written to Saved/RCON/ADMIN-PASSWORD.txt
PasswordHash=""          ; from `WardogsServer -GenerateRCONHash=<pw>`; wins over Password

[/Script/WDGame.WDGameSession]
ServerName= ; ServerPassword= (empty=open) ; ServerImageURL= (1024x256)
ServerMinPlayerCash=0 ; ServerMaxPlayerCash=0 ; ServerMinPlayerLevel=0 ; ServerMaxPlayerLevel=0
MaxReservedSlots=20
!DefaultReservedPlayerIds=ClearArray      ; directive: empty the array first
.DefaultReservedPlayerIds="<steamId64>"   ; one per line
.DefaultBannedPlayerIds="<steamId64>"     ; one per line

[/Script/Engine.GameSession]
MaxPlayers=128           ; clamped by a dev-set min/max

[MatchState.PreMatch.WaitingForPlayers.PlayerCount]
MinimumRequiredPlayers=60

[MatchState.Playing.KOTH]
ScorePeriod=24           ; score tick seconds, 18-30

[/Script/WDGame.WDGameStateSession]
bLockOverpopulatedTeamsConfig=true
OverpopulatedTeamThresholdConfig=2

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