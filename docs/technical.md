# How this tracker works

About once an hour, the [GitHub Actions workflow](../.github/workflows/track.yml) checks SteamTracking for new Deadlock client builds. It confirms the build number in `steam.inf`, compares six extracted game data files with the previous archived build, and writes a report and a single-change card. If a build has more than one change, its card shows one example and links to the complete report. You can also run it manually. If there is no new build, it leaves the archive alone.

The reports show before and after values, including the numerical difference and percentage where those make sense. Each one links back to the source commit and files. Cards use [Deadlock ability icons](../assets/icons/SOURCES.md) matched to the image path in the archived game data. The workflow saves newly needed icons automatically; if an icon is unavailable, the card stays text-only. Snapshots live in `data/builds/`, and identical file content is stored once in `data/blobs/`. A game data download or parsing failure stops the run before it saves a partial build.

### Local commands

Python 3.12+ and the standard library are sufficient.

```sh
python -m unittest discover -s tests -v
python src/tracker.py
python src/tracker.py --validate
python src/compare_builds.py 6793 6794
python src/compare_builds.py 6793 6819 --json
```

The comparison and validation commands use saved snapshots, so they also work offline. Every build report links to a complete JSON comparison with the original before and after values. To rebuild the public reports and graphics from the archive after a copy change, run `python src/tracker.py --refresh-presentation`. This archive starts at build 6793. To collect earlier history, lower `FIRST_BUILD` in `src/tracker.py` and run the tracker in a fresh archive.

## Where the information comes from

| Source | How we use it |
|---|---|
| [SteamTracking GameTracking-Deadlock](https://github.com/SteamTracking/GameTracking-Deadlock) | The source for every report. We read its extracted VData and confirm the client build in `steam.inf`. This is public extracted data, not an official Valve API. |
| [SteamDB Deadlock history](https://steamdb.info/app/1422450/history/) | A reference for Steam app and depot history. The tracker does not pull data from it. |
| [Frogtech changelog](https://changelog.frogtech.dev/) | Useful context for file and map changes. Its interpretations are not substituted for source values. |
| [Deadlock Data API](https://deadlock-data-api.iainfox.dev/docs) | A separate, nightly hero and item reference. Its version IDs and timing differ from client builds, so we do not merge its data into reports. |
| [unDeadlock](https://undeadlock.com/), [deadlock.io](https://deadlock.io/api/v1/index.json), and [Deadlock Almanac](https://deadlock.ing/) | Extra references for research. The tracker does not import their interpretations. |
| [r/DeadlockTheGame](https://www.reddit.com/r/DeadlockTheGame/) | Sometimes provides a discussion for an exact build. Any such link is optional context, not proof of a data change. |

The tracker reads `abilities.vdata`, `generic_data.vdata`, `heroes.vdata`, `misc.vdata`, `modifiers.vdata`, and `npc_units.vdata`. Those files contain Street Brawl settings, heroes, abilities, items, NPCs, and other values. The tracker does not archive map geometry, executable code, assets, localization, or VData files outside that group. A report with zero tracked changes does not mean the whole game stayed the same.

The code in this repository is offered under the MIT license. Game data and game artwork remain the property of their respective owners; this repository does not grant rights to those materials. Reports cite the source commit and each extracted file.

## A couple of changes in the archive

- [Street Brawl, build 6794](../reports/builds/6794.md): the fifth buy-time value changed **65 → 50** (−15, or −23.08%). [Check the source commit](https://github.com/SteamTracking/GameTracking-Deadlock/commit/df1192043fd269aee7edf4dffdfb4cfc03d05f64).
- [Violet's Living Ink, build 6819](../reports/builds/6819.md): a minimum stroke distance value of **15.0** appeared in the file. There was no earlier value in the tracked field, so this is an addition, not a measured increase.

## If updates stop

Check the workflow's **Read and write permissions** if GitHub does not let it save new reports. A GitHub rate limit, a missing upstream file, or a parsing error can also pause updates. If an upstream commit for an archived build changes, the tracker stops and asks for investigation instead of quietly replacing the old snapshot.
