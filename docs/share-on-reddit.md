# Reddit post draft

## Title

Deadlock build tracker with clear before-and-after changes

## Body

I made a small tracker for anyone who wants to see what changed between Deadlock builds without reading a file diff. It shows the five latest readable changes as cards, with the previous value, the new value, and when that build was recorded.

For example, one saved Street Brawl value went from **65 to 50**. A later build added a **15.0** minimum stroke-distance value for Violet's Living Ink; the tracker says **"Not listed to 15.0"** because the earlier build had no value for that field. It doesn't turn that into a made-up increase.

Each build has a fuller report and a link back to the exact SteamTracking source. If you want to check a complex change, you can download its complete before-and-after data. Ability cards use matching Deadlock artwork when there is a verified icon; otherwise they stay text-only.

This follows selected extracted game data, so it isn't a full set of patch notes and it can't tell us how a change played in a match.

Tracker: https://github.com/jordanbenjaminmitchell/deadlock-tracker

I'd welcome feedback on which changes are most useful to surface first.
