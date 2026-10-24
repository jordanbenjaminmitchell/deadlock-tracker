# Reddit post draft

## Title

Deadlock build tracker with clear before-and-after changes

## Body

I made a small tracker for anyone who wants to see what changed between Deadlock builds without reading a file diff. It shows the newest build on a card, then five recent changes with verified before-and-after values. Each card says when the build was recorded.

For example, one saved Street Brawl value went from **65 to 50**. A later build introduced a **15.0** minimum stroke-distance setting for Violet's Living Ink. The earlier build and its schema had no such field, so the tracker marks it as a new setting rather than claiming a previous number.

Each build has a fuller report and a link back to the exact SteamTracking source. If you want to check a complex change, you can download its complete before-and-after data. Ability cards use matching Deadlock artwork when there is a verified icon; otherwise they stay text-only.

This follows selected extracted game data, so it isn't a full set of patch notes and it can't tell us how a change played in a match.

Tracker: https://github.com/jordanbenjaminmitchell/deadlock-tracker

I'd welcome feedback on which changes are most useful to surface first.
