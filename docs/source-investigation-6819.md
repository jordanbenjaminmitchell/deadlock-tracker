# Why build 6819 has no earlier stroke-distance number

Checked October 24, 2026 at 09:20 Eastern time.

Build 6819 added `m_flMinStrokeDistance = 15.0` to Violet's Living Ink ability. The [previous saved ability file](https://github.com/SteamTracking/GameTracking-Deadlock/blob/04d261bfd6fddf07647416ab0382f9468c102830/game/citadel/pak01_dir/scripts/abilities.vdata) for build 6817 has no `m_flMinStrokeDistance` entry for `ability_artist_pullbrush`. The [build 6819 ability file](https://github.com/SteamTracking/GameTracking-Deadlock/blob/17462b250a0ca80e7f80102f2c83cc3eecff5f12/game/citadel/pak01_dir/scripts/abilities.vdata) supplies 15.0.

I also checked the extracted class definitions. The [build 6817 schema](https://github.com/SteamTracking/GameTracking-Deadlock/blob/04d261bfd6fddf07647416ab0382f9468c102830/DumpSource2/schemas/client/CCitadel_Ability_Artist_PullBrushVData.h) does not define this field. The [build 6819 schema](https://github.com/SteamTracking/GameTracking-Deadlock/blob/17462b250a0ca80e7f80102f2c83cc3eecff5f12/DumpSource2/schemas/client/CCitadel_Ability_Artist_PullBrushVData.h) introduces it with a schema default of 40. That 40 is a default in the *new* schema, while 15.0 is the build's explicit ability setting. Neither establishes a numeric value for the older build.

The previous in-game behavior may have depended on code or another setting outside this tracker. The available extracted files do not verify a previous stroke-distance number. The accurate comparison is therefore **new setting: 15.0**, with earlier behavior unverified. See the [complete saved build comparison](../reports/data/6819.json) for the exact tracked field change.

## Why the tracker still shows build 6819

As checked above, [SteamTracking's newest recorded client build](https://github.com/SteamTracking/GameTracking-Deadlock/commits/master/) is 6819, recorded October 22, 2026 at 23:53 UTC. [SteamDB's corresponding Steam build](https://steamdb.info/patchnotes/26147187/) is 26147187; SteamDB and the game use different numbering. The [tracker's scheduled checks](https://github.com/jordanbenjaminmitchell/deadlock-tracker/actions/workflows/track.yml) can succeed without changing the page when SteamTracking has no newer client build. The October 24, 2026 [scheduled run at 08:54 Eastern](https://github.com/jordanbenjaminmitchell/deadlock-tracker/actions/runs/40095861483/job/120877869880) reported no new client build.
