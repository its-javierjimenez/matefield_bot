# 100-Scenario Deep Audit Plan & Identified Bugs

Based on a deep analysis of the application's architecture (RCON API, Discord Bot, Database Schema, Rewards, and Memberships), here is the 100-scenario audit structured by category. This document serves as the guide for the deterministic refactoring and bug-hunting effort.

## Phase 1: Database & Schema Conflicts (Scenarios 1-15)
1. **Multiple NULL Unique Constraints**: `Player.discord_id` is unique, but many players won't have it linked initially. Do multiple NULLs crash the DB depending on the SQL engine?
2. **Foreign Key Type Mismatch**: `Role.id` is `int` (Integer), but `Membership.role_granted_id` and `special_role_id` are `BigInteger`. This causes constraint and index performance issues.
3. **Float for Currency**: `MembershipType.price_usd` uses `float`. Floating-point arithmetic inaccuracies could cause financial sync issues. Needs `Numeric(10,2)` or integer cents.
4. **Missing Unique Constraints**: `Team.name` and `code` are unique, but `MatchTeamStats` has `match_id` and `team_id` as primary keys without a unique index on the combination if it wasn't a composite PK (it is, which is good).
5. **Dangling Memberships**: Deleting a `Player` might leave orphaned `Membership` records if cascading isn't properly configured on the database engine.
6. **Timezone Naivety**: Are all `datetime.now(timezone.utc)` properly returning timezone-aware objects, and is the DB engine storing them without timezone offset stripping?
7. **UUID Defaults**: Using `str(uuid.uuid4())` in `Field(default_factory=...)` can cause deterministic issues if the system clock or PRNG is exhausted.
8. **String Lengths**: `RconServer.password` and `BotConfig.config_value` have no length limits, susceptible to text overflow in some engines.
9. **Role Deletion vs Memberships**: If a `Role` is deleted, `PlayerRole` might cascade, but what happens to `Membership.role_granted_id`? (Missing SET NULL or CASCADE).
10. **Membership Server Binding**: `Membership.server_id` is optional. If null, does it apply to all servers? The logic needs to be deterministic.
11. **Reward Item Expiration**: `RewardItem.duration_days` is optional. A missing duration on a temporary reward causes infinite grants if unhandled.
12. **Claim Code Collision**: `RewardClaim.claim_code` relies on uniqueness, but if generated concurrently without DB-level retry, it throws 500 errors.
13. **Session Overlap**: `PlayerSession` start and end times overlapping for the same `steam_id` across different servers.
14. **Seeding Seconds Negative**: If `end_time` is recorded before `start_time` due to server clock drift, `total_seconds` becomes negative.
15. **Status Typo Vulnerability**: `Membership.rcon_sync_status` uses raw strings ("PENDING", "SUCCESS"). A typo in the code will not be caught by DB enums.

## Phase 2: RCON & Network Race Conditions (Scenarios 16-35)
16. **Concurrent Command Execution**: Two Discord tasks sending `/admin add` at the same time to the same RCON server.
17. **RCON Socket Timeout**: The RCON server hangs, holding the Discord bot task open until the bot gets rate-limited by Discord.
18. **Partial Execution**: A command series `[A, B, C]` fails at `B`. Does it rollback `A`? (Non-deterministic workflow).
19. **RCON Reconnection Storm**: If RCON is down, 50 tasks trying to sync roles will spam connection attempts, causing a localized DDoS.
20. **Invalid Characters in RCON**: Player with a name containing `"` or `\n` breaking the RCON command parser.
21. **Command Injection**: Unsanitized `steam_id` or `reason` in RCON payloads allowing malicious command execution.
22. **Silent RCON Failure**: RCON returns success (e.g., 200 OK) but the payload says "Player not found". Logic reads HTTP 200 and assumes success.
23. **Simulation Mismatch**: Dev environment mock RCON always returns 200, hiding parsing errors present in Production.
24. **Stale Connection Pool**: Async HTTP clients pointing to a restarted RCON API will hang on broken pipes.
25. **Rate Limit Miscalculation**: Discord bot exceeding 50 requests/sec because RCON sync is executed in `asyncio.gather` without semaphores.
26. **Sync Status Stuck in PENDING**: If the bot crashes mid-sync, `Membership.rcon_sync_status` remains PENDING forever.
27. **Duplicate Role Syncs**: Sync task fires at 00:00, and manually at 00:00:01, applying the VIP role twice in RCON.
28. **Role Removal Race**: VIP expires, bot removes role. Admin adds VIP manually simultaneously. Bot removes it again on the next pass.
29. **Punishment Evasion**: Player disconnects right before the RCON ban command is executed.
30. **Long Response Truncation**: RCON `showadmin` returns a payload too large for the parser, truncating the JSON response.
31. **IP Binding Conflict**: Two RCON servers configured with the same IP and Port by accident.
32. **Authentication Desync**: RCON password changes, but `RconServer` DB table isn't updated. Tasks fail silently.
33. **Missing Player Target**: Command targets a SteamID that just left the server. RCON returns "Player not found", but bot treats it as a fatal error instead of skipping.
34. **Network Partition**: Database is reachable, but RCON servers are not. Memberships are created but never synced.
35. **Event Loop Blocking**: Synchronous RCON library used inside an async function, freezing the entire Discord bot.

## Phase 3: Discord Bot Permissions & Exploits (Scenarios 36-50)
36. **Unauthorized Sync Trigger**: Regular user guessing the `/roles sync` command if it isn't properly gated by Discord permissions.
37. **Cross-Tenant Unlinking**: User A unlinking User B's SteamID via the `/player unlink` command.
38. **Admin Privilege Escalation**: Moderator with "manage messages" using `/admin reserved add` on themselves.
39. **Command Replay**: Double-clicking a Discord UI button to claim a reward twice before the DB locks the transaction.
40. **Bot Hierarchy Abuse**: Bot trying to assign a Discord role higher than its own role, causing a 403 Forbidden loop.
41. **Cache Poisoning**: Discord member cache is stale, bot thinks a user left the server and revokes their RCON VIP.
42. **Interaction Timeout**: `edit_initial_response` takes longer than 15 minutes due to DB locks, failing with Discord API error.
43. **Ghost Roles**: Discord role is deleted in the server, but `Role.discord_role_id` still exists in the DB.
44. **Unregistered Slash Commands**: Dev environment commands leaking into Production because of global sync.
45. **DM Exploitation**: Executing sensitive slash commands in DMs where server roles cannot be validated.
46. **Embed Limit Exceeded**: Sync report with 100+ members exceeds Discord's 4096 character limit for embed descriptions.
47. **Ephemeral Leaks**: Error traces containing DB passwords shown to users in ephemeral messages during Dev mode.
48. **Missing Intent Fallback**: Bot starts without Server Members Intent, causing all syncs to assume users have 0 roles.
49. **Bot Re-invitation**: Bot is kicked and re-invited, losing memory of previous interactions if relying on local state.
50. **Rate Limit Lockout**: Heavy automated syncing hits Discord's global 10,000 requests/10min limit.

## Phase 4: Memberships, Seeding & Rewards (Scenarios 51-75)
51. **Infinite Membership Glitch**: `end_time` logic calculates `now() + 30 days` on every renewal instead of extending the existing `end_time`.
52. **Negative Points Claim**: User claims a reward costing 500 points when they have 400. DB doesn't have a `CHECK (reward_points >= 0)` constraint.
53. **Concurrent Point Spending**: User spams `/reward claim` from two devices. Transaction isolation level allows double spending.
54. **Seeding Farm**: User joins empty server, stays 24/7. System grants infinite points. No daily cap on seeding rewards.
55. **Zero-Point Rewards**: Reward item cost is set to 0 by mistake. Users script the claim command to generate 10,000 claims.
56. **Membership Downgrade Issue**: User has VIP (Role A), buys SYSTEM (Role B). Bot fails to remove Role A or calculate priorities.
57. **Expired VIP Still Active**: Cron job fails to run, so VIPs whose `end_time` passed remain active in RCON.
58. **Booster Status Loss**: User boosts Discord, gets VIP. User unboosts, but the bot misses the `member_update` event, keeping the VIP.
59. **Refund Exploitation**: User buys VIP, gets points, refunds VIP. Points are not rolled back.
60. **Reward Delivery Crash**: Reward type `CUSTOM` delivery crashes, leaving `RewardClaim.status` as "PENDING" but deducting points.
61. **Manual Ticket Desync**: Reward requires manual ticket. Admin fulfills it but forgets to update `RewardClaim`, keeping it pending.
62. **Seeding Session Orphan**: Server restarts, `PlayerSession` never gets an `end_time`.
63. **Multi-Server Seeding**: Player connects to Server 1 and Server 2 simultaneously (via exploit), double-dipping points.
64. **Role Exclusivity**: A player is assigned `PUNISHMENT` (banned) but also has `VIP`. The VIP sync overrides the punishment in RCON.
65. **Membership Type Deletion**: Admin deletes a `MembershipType` that is currently tied to active `Membership` records.
66. **Price Change Retrospection**: Admin changes `MembershipType.price_usd`. Old memberships recalculate based on new price in reports.
67. **Redemption Token Expiry**: Steam link token expires during the linking process, failing the callback silently.
68. **Token Brute Force**: 6-character Steam link token is brute-forced by an attacker to link someone else's account.
69. **Reward Claim Code Collision**: Two users claim different rewards at the same millisecond and get the same `claim_code`.
70. **Inactive Server Sync**: Sync attempts to apply memberships to an `RconServer` where `is_active=False`.
71. **Default Server Assumption**: Membership has no `server_id`. Code assumes it applies to `is_default=True`, but there are 0 or 2 default servers.
72. **Points Reset Bug**: A logic error sets player points to `0` instead of `-= cost`.
73. **Booster Double Credit**: Server boost triggers multiple events, granting the user multiple active memberships.
74. **Permanent Membership Override**: User with permanent VIP buys 30-day VIP. The system overwrites `end_time=None` with `end_time=30 days`.
75. **Missing Reward Action**: Reward type `ROLE` tries to assign a role ID that no longer exists in the DB.

## Phase 5: Determinism, Quality & Edge Cases (Scenarios 76-100)
76. **Floating Point IDs**: JavaScript parsing a 64-bit Steam ID as a float and rounding it (e.g., 76561197960287930 -> 76561197960287940).
77. **Case Sensitivity**: Steam ID stored as uppercase in DB but queried as lowercase from Discord.
78. **Empty String vs NULL**: In-game name is `""` instead of `NULL`, breaking `if not player.in_game_name` logic if not careful.
79. **Database Connection Leak**: Sessions are not properly closed in exception blocks.
80. **Memory Leak in Tracer**: `DevActionTracer` keeps adding to `self.logs` without bound, crashing the bot after 100,000 commands.
81. **Uncaught Exceptions in Tasks**: Background task throws exception and dies silently, halting all future scheduled syncs.
82. **Timezone Shifts**: Daylight savings time causes a 1-hour gap or overlap in seeding session calculations.
83. **Dirty Reads**: Transaction A reads player points, Transaction B reads player points. Both subtract and write back. (Need `select_for_update()`).
84. **Config Value Caching**: `BotConfig` values are cached forever. Admin changes a config, but bot requires a restart to see it.
85. **Database Migration Failures**: Alembic migration adds a non-nullable column without a default value, crashing deployment.
86. **Dependency Version Skew**: Pydantic v1 vs v2 incompatibilities in `wardogs-config` when deployed to production.
87. **Circular Imports**: Adding cross-references between `roles.py` and `tasks.py` causing runtime import errors.
88. **Log File Rotation**: Logs grow infinitely until the disk is 100% full.
89. **Environment Variable Fallback**: Production falls back to `development` settings if `APP_ENV` is misspelled.
90. **Test Flakiness**: Unit tests fail randomly because they depend on external RCON server timing.
91. **Fixture State Leakage**: Test A modifies the DB, Test B reads it and fails.
92. **Unmocked External Calls**: Tests actually try to hit the Steam API, getting rate-limited on CI/CD.
93. **Simultaneous Crons**: Two instances of the bot are running, both executing the cron jobs and duplicating work.
94. **Data Truncation Error**: Name is 256 characters long, DB column is `VARCHAR(255)`.
95. **Bot Token Rotation**: Bot token is rotated, but running instances aren't restarted, leading to persistent 401s.
96. **Orphaned Async Tasks**: Using `asyncio.create_task` without keeping a strong reference, causing Python's garbage collector to cancel the task midway.
97. **Null Object Anti-Pattern**: `NullTracer` accidentally returns `None` where a real return value is expected, causing `AttributeError` downstream.
98. **Missing Transaction Rollback**: An error happens halfway through `sync_single_user_roles`, but the DB session is committed anyway.
99. **Slow Query Buildup**: Querying `RewardClaim` without indexes on `status` and `steam_id` causes table scans, slowing down the bot over time.
100. **Hardcoded IDs**: Logic relies on `Role.id == 1` instead of `Role.code == 'SYSTEM'`, breaking across environments.
