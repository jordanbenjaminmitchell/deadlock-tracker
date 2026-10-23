# Deadlock build tracker

Automated, build-by-build comparisons of public, extracted Deadlock game data. Every archived snapshot points to an immutable [SteamTracking/GameTracking-Deadlock](https://github.com/SteamTracking/GameTracking-Deadlock) commit, the client build recorded in `steam.inf`, and content-addressed normalized VData. The tracker never uses illustrative values as historical facts.

![Latest build infographic](reports/infographics/latest.svg)

**[Latest report](reports/latest.md) · [Recent changes](reports/recent-changes.md) · [Street Brawl](reports/street-brawl.md) · [Build history](reports/index.md)**

<!-- RECENT_CHANGES_START -->
## Latest verified field changes

Five most recent scalar changes in tracked VData. Times are upstream commit timestamps in UTC; changes within one build share a timestamp and are ordered by field path. Values keep their source units; no unit conversion is inferred. Each build report contains its full set of changes.

<table>
<tr>
<td width="20%">
<a href="reports/builds/6819.md"><img src="reports/infographics/recent/6819-0d2b1fa53934.svg" width="185" alt="Build 6819: abilities.ability_artist_pullbrush.m_flMinStrokeDistance, null to 15.0"></a>
</td>
<td width="20%">
<a href="reports/builds/6813.md"><img src="reports/infographics/recent/6813-d577a716ff9e.svg" width="185" alt="Build 6813: abilities.ability_warden_riot_protocol.m_AutoCastDelayModifier.m_nEnabledStateMask, null to &quot;MODIFIER_STATE_FEAR_IMMUNE&quot;"></a>
</td>
<td width="20%">
<a href="reports/builds/6813.md"><img src="reports/infographics/recent/6813-9ad5f3cf223c.svg" width="185" alt="Build 6813: abilities.ability_warden_riot_protocol.m_WardenBuffModifier.m_nEnabledStateMask, &quot;MODIFIER_STATE_SINCLAIR_TAX_ULT_ACTIVE | MODIFIER_STATE_SINCLAIR_TAX_KEEP_MODEL_SWAP&quot; to &quot;MODIFIER_STATE_SINCLAIR_TAX_ULT_ACTIVE | MODIFIER_STATE_SINCLAIR_TAX_KEEP_MODEL_SWAP | MODIFIER_STATE_FEAR_IMMUNE&quot;"></a>
</td>
<td width="20%">
<a href="reports/builds/6801.md"><img src="reports/infographics/recent/6801-3ff9683b2b56.svg" width="185" alt="Build 6801: abilities.ability_artist_bamboogrove.m_BambooModifier.m_ImmuneModifier.m_bDurationReducible, null to false"></a>
</td>
<td width="20%">
<a href="reports/builds/6801.md"><img src="reports/infographics/recent/6801-41dfd9fe9e10.svg" width="185" alt="Build 6801: abilities.ability_artist_homingbrush.m_StackModifier.m_bDurationExtendible, null to true"></a>
</td>
</tr>
</table>

### Exact changes and times

<ol>
<li><strong>Violet · Living Ink — Minimum stroke distance: Added 15.0</strong><br>Build 6819 · Oct 22, 2026 23:53 UTC (<a href="reports/builds/6819.md">full report</a>; <a href="https://github.com/SteamTracking/GameTracking-Deadlock/commit/17462b250a0ca80e7f80102f2c83cc3eecff5f12">upstream commit</a>)<br><code>unset</code> → <code>15.0</code> · Source field: <code>abilities.ability_artist_pullbrush.m_flMinStrokeDistance</code></li>
<li><strong>Warden · Riot Protocol — Auto-cast delay state flags: Fear-immunity flag added</strong><br>Build 6813 · Oct 22, 2026 04:14 UTC (<a href="reports/builds/6813.md">full report</a>; <a href="https://github.com/SteamTracking/GameTracking-Deadlock/commit/a94d8b455203f12b176de75a5598dd8e6e8a94d4">upstream commit</a>)<br><code>unset</code> → <code>&quot;MODIFIER_STATE_FEAR_IMMUNE&quot;</code> · Source field: <code>abilities.ability_warden_riot_protocol.m_AutoCastDelayModifier.m_nEnabledStateMask</code></li>
<li><strong>Warden · Riot Protocol — Warden buff state flags: Fear-immunity flag added</strong><br>Build 6813 · Oct 22, 2026 04:14 UTC (<a href="reports/builds/6813.md">full report</a>; <a href="https://github.com/SteamTracking/GameTracking-Deadlock/commit/a94d8b455203f12b176de75a5598dd8e6e8a94d4">upstream commit</a>)<br><code>&quot;MODIFIER_STATE_SINCLAIR_TAX_ULT_ACTIVE | MODIFIER_STATE_SINCLAIR_TAX_KEEP_MODEL_SWAP&quot;</code> → <code>&quot;MODIFIER_STATE_SINCLAIR_TAX_ULT_ACTIVE | MODIFIER_STATE_SINCLAIR_TAX_KEEP_MODEL_SWAP | MODIFIER_STATE_FEAR_IMMUNE&quot;</code> · Source field: <code>abilities.ability_warden_riot_protocol.m_WardenBuffModifier.m_nEnabledStateMask</code></li>
<li><strong>Violet · Bamboo Grove — Duration reduction allowed: Set to off</strong><br>Build 6801 · Oct 20, 2026 21:02 UTC (<a href="reports/builds/6801.md">full report</a>; <a href="https://github.com/SteamTracking/GameTracking-Deadlock/commit/37f9aebdc62766aa13748f73309b9b8120549833">upstream commit</a>)<br><code>unset</code> → <code>false</code> · Source field: <code>abilities.ability_artist_bamboogrove.m_BambooModifier.m_ImmuneModifier.m_bDurationReducible</code></li>
<li><strong>Violet · Homing Brush — Duration extension allowed: Set to on</strong><br>Build 6801 · Oct 20, 2026 21:02 UTC (<a href="reports/builds/6801.md">full report</a>; <a href="https://github.com/SteamTracking/GameTracking-Deadlock/commit/37f9aebdc62766aa13748f73309b9b8120549833">upstream commit</a>)<br><code>unset</code> → <code>true</code> · Source field: <code>abilities.ability_artist_homingbrush.m_StackModifier.m_bDurationExtendible</code></li>
</ol>
<!-- RECENT_CHANGES_END -->

## How it runs

The [GitHub Actions workflow](.github/workflows/track.yml) runs every three hours and can also be started manually. It reads commits that changed `steam.inf`, verifies each client build against that file, and processes every unarchived build in order. Six decompiled VData files are parsed and compared recursively. Identical content is stored once in `data/blobs/`; `data/builds/<number>/snapshot.json` preserves each build's source URL, commit, source revision, timestamp and blob hashes. A failed download or parse aborts before publishing a snapshot. Repeated runs with no new build make no commit.

Each build receives a Markdown report and a data-only SVG infographic. The infographic uses counts from that comparison; no stock art or generated game imagery is used. Numeric changes include old and new values, the absolute delta, and a percentage when the old value is nonzero. Reports distinguish verified extracted data from gameplay interpretation. They do not imply executable code or map geometry stayed unchanged when tracked VData is unchanged.

### Local commands

Python 3.12+ and the standard library are sufficient.

```sh
python -m unittest discover -s tests -v
python src/tracker.py
python src/compare_builds.py 6793 6794
python src/compare_builds.py 6793 6819 --json
```

The comparison command reads only archived snapshots, so it works months later without contacting the source. The default backfill starts at build 6793; earlier history can be added by lowering `FIRST_BUILD` in `src/tracker.py` and running the tracker in a fresh archive.

## Sources and coverage

| Source | What it provides | Update cadence and role |
|---|---|---|
| [SteamTracking GameTracking-Deadlock](https://github.com/SteamTracking/GameTracking-Deadlock) | Public decompiled VData, `steam.inf`, manifest and commit history. It is extracted game data, not an official Valve API. | Primary, as new commits appear. Build identity is verified from `steam.inf`. |
| [SteamDB Deadlock history](https://steamdb.info/app/1422450/history/) | Steam app/depot history and manifests, generally file-level rather than extracted parameter values. | Reference for Steam publication; not scraped by the runner. |
| [Frogtech changelog](https://changelog.frogtech.dev/) | Build-indexed file, map and patch-note interpretations from game files. It states that some results may be incomplete. | Cross-check and map-change research; not treated as the authoritative data snapshot. |
| [Deadlock Data API](https://deadlock-data-api.iainfox.dev/docs) | Nightly, versioned hero and item JSON sourced from game VPKs; versions use depot manifest IDs rather than client build numbers. | Secondary corroboration; not merged into client-build snapshots because the version schemes and capture times differ. |
| [unDeadlock](https://undeadlock.com/) | Human-readable, third-party patch interpretations. | Research only; no unattended ingestion. |
| [deadlock.io API](https://deadlock.io/api/v1/index.json) | Public structured heroes, items, abilities and game globals. | Research only; its published client build may lag Steam. |
| [Deadlock Almanac](https://deadlock.ing/) | Community reference site. | Research only; no verified historical file API found. |
| [r/DeadlockTheGame](https://www.reddit.com/r/DeadlockTheGame/) | Public exact-build discussions when the Reddit search endpoint responds. | Optional context, labeled unverified; failures never stop primary collection. |

The six tracked files are `abilities.vdata`, `generic_data.vdata`, `heroes.vdata`, `misc.vdata`, `modifiers.vdata`, and `npc_units.vdata`. These cover Street Brawl configuration, hero and item abilities, hero definitions, NPCs and other gameplay values found in those files. Map geometry, executable behavior, asset files, localization and included VData files outside this set are not archived. A commit that changes only those untracked surfaces may have a report with zero tracked changes. The source repository and its historical commits remain separately linked in every snapshot.

The code in this repository is offered under the MIT license. Game data and game artwork remain the property of their respective owners; this repository does not grant rights to those materials. Reports cite the source commit and each extracted file.

## Historical findings

- [6793 → 6794](reports/builds/6794.md): `generic_data.m_StreetBrawl.m_vecBuyTime[4]` changed **65 → 50** (−15, −23.08%), confirmed by the [SteamTracking commit](https://github.com/SteamTracking/GameTracking-Deadlock/commit/df1192043fd269aee7edf4dffdfb4cfc03d05f64).
- [6817 → 6819](reports/builds/6819.md): see the archived ability comparison for Violet's Living Ink. This report is generated from source data, including whether a field was added or changed.

## Operating limits

GitHub Actions needs repository **Workflow permissions → Read and write permissions** if an organization or repository setting overrides the workflow's `contents: write`. The tracker stops on source/parse failures; it does not publish a partial build. Public GitHub API rate limits or upstream removal of historical files can pause collection. A source history rewrite for an already archived client build is reported as an error for manual investigation rather than silently replacing data.
