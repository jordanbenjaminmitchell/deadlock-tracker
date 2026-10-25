# Deadlock build tracker

See what changed in Deadlock, one update at a time. Each build has a short explanation, a change card, and exact before-and-after values when both are known. [Find a character or mode in the build history](reports/index.md).

These are changes in extracted files. A value changing in a file does not, on its own, tell us how it felt or worked in a match.

**[Recent updates](reports/recent-changes.md) · [Browse by character or mode](reports/index.md) · [Latest report](reports/latest.md) · [Street Brawl](reports/street-brawl.md)**

<!-- RECENT_CHANGES_START -->
## What changed in Deadlock?

**Latest build recorded:** [6819](reports/builds/6819.md) on Oct 22, 2026 at 23:53 UTC.

**Tracker check:** Scheduled every five minutes. [See the most recent check and its time](https://github.com/jordanbenjaminmitchell/deadlock-tracker/actions/workflows/track.yml). GitHub may start a check late.

### Latest update

Violet · Living Ink — Minimum stroke distance is now listed as **15.0**. There is no confirmed earlier value.

<a href="reports/infographics/latest.svg"><img src="reports/infographics/latest.svg" width="320" alt="Violet · Living Ink — Minimum stroke distance is now listed as 15.0. There is no confirmed earlier value. Build 6819."></a>

[See everything found in build 6819](reports/builds/6819.md).

### Earlier updates with changes in the files we follow

Each build gets one card. The key numbers sit below it, with the previous and new value shown when both are known.

#### Build 6813 · Oct 22, 2026 04:14 UTC

Warden · Last Stand — Fear immunity changed from **Off** to **On**.

<a href="reports/infographics/6813.svg"><img src="reports/infographics/6813.svg" width="280" alt="Warden · Last Stand — Fear immunity changed from Off to On. Build 6813."></a>

Key values in this update:

- **Warden · Last Stand — Fear immunity**: Off → **On** (Fear immunity added)
- **Warden · Last Stand — Fear immunity during auto-cast delay**: new setting **On**

[See all changes in build 6813](reports/builds/6813.md).

#### Build 6801 · Oct 20, 2026 21:02 UTC

Nurse Harrow changed from **Pre-release** to **Released** in the game data.

<a href="reports/infographics/6801.svg"><img src="reports/infographics/6801.svg" width="280" alt="Nurse Harrow changed from Pre-release to Released in the game data. Build 6801."></a>

Key values in this update:

- **Nurse Harrow — Release status**: Pre-release → **Released**
- **Nurse Harrow — Maximum health**: 780.0 → **730** (Down 50 · 6.41%)
- **Nurse Harrow — Sprint speed**: 1.6 → **2.5** (Up 0.9 · 56.25%)
- **Nurse Harrow — Maximum move speed**: 7.2 → **6.8** (Down 0.4 · 5.56%)
- **Nurse Harrow — Base health regen**: 2.0 → **0** (Down 2 · 100.00%)

[See all changes in build 6801](reports/builds/6801.md).

#### Build 6794 · Oct 17, 2026 21:32 UTC

Street Brawl — Buy time, fifth value changed from **65** to **50**.

<a href="reports/infographics/6794.svg"><img src="reports/infographics/6794.svg" width="280" alt="Street Brawl — Buy time, fifth value changed from 65 to 50. Build 6794."></a>

- **Street Brawl — Buy time, fifth value**: 65 → **50** (Down 15 · 23.08%)

[See all changes in build 6794](reports/builds/6794.md).

<details>
<summary>Last five changes with a verified before and after</summary>

These are individual values, so several can come from one build.

- **Warden · Last Stand — Fear immunity**: Off → **On** (Fear immunity added) · Build 6813 ([card](reports/infographics/recent/6813-1cd069c8b4a2.svg); [full update](reports/builds/6813.md))
- **Nurse Harrow — Release status**: Pre-release → **Released** · Build 6801 ([card](reports/infographics/recent/6801-2de523031bd0.svg); [full update](reports/builds/6801.md))
- **Nurse Harrow — Maximum health**: 780.0 → **730** (Down 50 · 6.41%) · Build 6801 ([card](reports/infographics/recent/6801-a4483b1c959f.svg); [full update](reports/builds/6801.md))
- **Nurse Harrow — Sprint speed**: 1.6 → **2.5** (Up 0.9 · 56.25%) · Build 6801 ([card](reports/infographics/recent/6801-d6f27d6154ce.svg); [full update](reports/builds/6801.md))
- **Nurse Harrow — Maximum move speed**: 7.2 → **6.8** (Down 0.4 · 5.56%) · Build 6801 ([card](reports/infographics/recent/6801-8039798a3b0c.svg); [full update](reports/builds/6801.md))

</details>
<!-- RECENT_CHANGES_END -->

## How to read the changes

The tracker is scheduled to look for a new Deadlock build every five minutes. GitHub may start a scheduled check late. The page changes when [SteamTracking](https://github.com/SteamTracking/GameTracking-Deadlock) records a newer build. [See the latest check](https://github.com/jordanbenjaminmitchell/deadlock-tracker/actions/workflows/track.yml). A new setting is shown without a guessed old number. Every build report links to its source data.

Names come from the game data; some may be development labels. Each report links to the SteamTracking commit it came from. Open **Check the exact source values** in a report if you want the original data behind the plain-language text. The tracker covers selected game data, so a build can still contain changes outside these reports.

The icons on hero and ability cards are [actual Deadlock artwork](assets/icons/SOURCES.md). If matching art is unavailable, the card shows the change without an image.

## Examples from the archive

- [Street Brawl, build 6794](reports/builds/6794.md): the fifth buy-time value changed **65 → 50**, a decrease of 15.
- [Violet's Living Ink, build 6819](reports/builds/6819.md): **15.0** first appeared as a minimum stroke-distance setting. [The source investigation](docs/source-investigation-6819.md) explains why no earlier number can be verified.

[How the tracker works and how to run it](docs/technical.md)
