# Dashboard Stats Design

## Goal

Build an Eden-style public server statistics dashboard for KDAOC. The first implementation should be useful enough for launch, not just a placeholder: live population, realm/class distribution, server performance trends, weekly realm gold inflow, weekly realm RP inflow, and a Naver Cafe banner that shows live player count.

The Naver Cafe remains the community home page. The game server provides the statistics page and image badge, and the cafe links to or embeds the badge where Naver Cafe permits image placement.

Reference direction: Eden's public stats page groups population, class, RvR, currency, and server performance into readable chart sections: https://eden-daoc.net/stats

## Scope

In scope:

- Public dashboard page served by the existing Atlas API host.
- JSON endpoints for live and historical dashboard data.
- Naver Cafe-friendly image badge for the cafe front page.
- Live totals for current players, realms, classes, uptime, and last update time.
- Historical charts for 24-hour population and CPU/RAM trends.
- Weekly realm trend charts for server-issued gold and server-issued RP.
- Privacy-safe aggregation only.

Out of scope for the first implementation:

- Account names, character names, IPs, exact zones, or guild-level details.
- Admin-only dashboard controls.
- Separate web service deployment.
- Full economy dashboards beyond server-issued gold inflow.
- Boss/item-specific analytics.

## Architecture

Use the existing `GameServer/API/ApiHost.cs` rather than a new web service. The API host already serves Swagger docs and endpoints such as `/stats`, `/stats/uptime`, and realm/player data.

Add a dashboard area with three responsibilities:

- `DashboardStatsProvider`: gathers live server state, reads historical stats, caches responses, and hides private data.
- Dashboard API endpoints: expose structured JSON for the browser UI.
- Static dashboard/badge rendering: serve the dashboard HTML/JS/CSS and generate the Naver Cafe badge image.

The implementation should keep collection, aggregation, and HTTP endpoint code separated so the dashboard can later move to a standalone service without rewriting the metrics logic.

## Endpoints

Add these public endpoints under the existing API host:

- `GET /dashboard`
  - Returns the public dashboard page.
  - Uses a lightweight static page with client-side charts.

- `GET /api/dashboard/live`
  - Returns current player totals, realm totals, class totals, uptime, current CPU/RAM, and timestamp.
  - Cached for 10-30 seconds.

- `GET /api/dashboard/history?range=24h`
  - Returns time-series data from `serverstats`.
  - Includes total clients, realm population, CPU, and memory.
  - Initially support `24h`; design the API shape so `7d` can be added later.

- `GET /api/dashboard/realm-activity?range=7d`
  - Returns weekly bucketed realm activity.
  - Includes server-issued gold and server-issued RP per realm.
  - Default bucket should be hourly for 7 days.

- `GET /status/badge.png`
  - Returns a Naver Cafe-friendly PNG badge.
  - Shows current online count and realm split.
  - Uses no-cache or short cache headers. Target cache window is 60 seconds.

## Dashboard Layout

Top summary cards:

- Current online players.
- Realm split: Albion, Midgard, Hibernia.
- Server uptime.
- Last updated time.

Charts:

- 24-hour online player trend.
- Current realm population ratio.
- Current class distribution.
- CPU/RAM trend.
- This week's server-issued gold by realm.
- This week's server-issued RP by realm.

CPU/RAM should not have duplicate top cards. It appears only in the performance trend chart.

## Naver Cafe Badge

The cafe front page should use a large banner-style image. The badge should be clickable where the cafe editor supports image links, sending users to `/dashboard`.

Badge content:

- KDAOC server status label.
- Current online count.
- Albion/Midgard/Hibernia counts.
- Optional "updated at" time if it does not make the badge noisy.

Because Naver Cafe can restrict scripts and iframes, do not depend on JavaScript running inside the cafe. The badge must work as a plain image URL.

## Data Sources

Live population:

- Use `ClientService.Instance.ClientCount`.
- Use `ClientService.Instance.GetPlayersOfRealm(eRealm.*)` for realm counts.
- Iterate currently connected clients/players for class counts.

Uptime:

- Use `GameServer.Instance.StartupTime`.

Performance:

- Current CPU should reuse the existing process CPU measurement pattern from `GameServer/gameutils/StatSave.cs`.
- Current memory can use managed memory for parity with existing `serverstats`, with room to add process working set later.

Population/performance history:

- Use existing `CoreDatabase/Tables/DbServerStat.cs` mapped to `serverstats`.
- `StatSave` already writes clients, CPU, memory, and realm counts.
- Dashboard operation should require `statsave_interval` to be enabled. The recommended production value is 1 minute.

Weekly gold/RP realm activity:

- Add a new aggregate table, tentatively `dashboard_realm_activity`.
- Store time bucket, realm, server-issued gold, and server-issued RP.
- Use hourly buckets for the first implementation.

## Gold/RP Definition

Gold earned means server-issued gold inflow only:

- Include mob drops, quest rewards, task rewards, and other system rewards where the server creates or awards money to a player.
- Include NPC merchant sell payouts because the server is issuing currency to the player.
- Exclude player-to-player trades.
- Exclude vault, house, lockbox, consignment, and character-to-character transfers.
- Exclude GM/admin manual grants.

RP earned means server-issued RP only:

- Include PvP kill RP, bonuses, events, quest/system RP rewards.
- Exclude GM/admin manual grants.

Implementation note: do not blindly hook every `GamePlayer.AddMoney` call as "gold earned". That would mix trades and transfers into the economy chart. Prefer explicit tracking calls from trusted server reward paths, or add a reward-source-aware API that callers must use when money is newly issued.

## Caching And Refresh

- Dashboard page refreshes live data every 30 seconds.
- Live API response cache: 10-30 seconds.
- History API response cache: 60 seconds.
- Badge image cache: 60 seconds or less, with cache headers chosen to avoid stale cafe display where possible.

The dashboard should keep rendering if one chart fails. Failed panels show a compact error state while the rest of the page remains usable.

## Privacy

The public endpoints must not expose:

- Account names.
- Character names.
- IP addresses.
- Exact player locations.
- Online player lists.
- GM/tester status.

All data is aggregated by realm, class, time bucket, or server process.

## Testing

Unit tests:

- Live stats provider returns correct totals from fake/sampled players.
- Class and realm aggregation exclude invalid/null players safely.
- Gold/RP tracker excludes GM/admin grants.
- Gold tracker does not count player trade/transfer paths.
- History query returns buckets in chronological order.

Integration/lightweight tests:

- `/api/dashboard/live` returns JSON without private fields.
- `/api/dashboard/history?range=24h` handles an empty `serverstats` table.
- `/api/dashboard/realm-activity?range=7d` handles no activity rows.
- `/status/badge.png` returns PNG content type and non-empty bytes.

Manual checks:

- Dashboard renders at desktop and mobile widths.
- Charts update without full page reload.
- Naver Cafe badge image URL can be placed in cafe front page content.

## Rollout

1. Add data contracts and provider skeleton.
2. Add live JSON endpoint.
3. Add static dashboard page with charts against sample/live JSON.
4. Enable/read `serverstats` history for population and CPU/RAM.
5. Add realm activity aggregate table and tracker.
6. Wire server-issued RP tracking.
7. Wire server-issued gold tracking only in trusted reward paths.
8. Add PNG badge endpoint.
9. Update deployment notes for enabling `atlas_api` and `statsave_interval`.

The first deploy can show empty weekly gold/RP charts until activity accumulates. Empty states should say there is not enough data yet rather than appearing broken.
