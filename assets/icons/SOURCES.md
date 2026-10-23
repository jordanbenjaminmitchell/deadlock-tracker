# Deadlock ability icons

These are extracted Deadlock ability icons, used only when a card's changed field belongs to the matching ability. The icons are game artwork owned by Valve; this repository's MIT license does not cover them.

| Local file | Ability | Source |
|---|---|---|
| `living-ink.webp` | Violet · Living Ink (including its Draw field) | [Ability page](https://deadlock.gs/abilities/living-ink/) · [image](https://cdn.source.gs/deadlock/img/ability-ability-artist-homingbrush-d78aee-192.webp) |
| `abstract-landscape.webp` | Violet · Abstract Landscape | [Ability page](https://deadlock.gs/abilities/abstract-landscape/) · [image](https://cdn.source.gs/deadlock/img/ability-ability-artist-bamboogrove-5007f7-192.webp) |
| `last-stand.webp` | Warden · Last Stand | [Ability page](https://deadlock.gs/abilities/last-stand/) · [image](https://cdn.source.gs/deadlock/img/ability-ability-warden-riot-protocol-8de524-192.webp) |

For new abilities, the tracker reads `m_strAbilityImage` in the archived `abilities.vdata` snapshot and downloads only the matching WebP from the [Deadlock API asset CDN](https://assets-bucket.deadlock-api.com/assets-api-res/images/abilities/). It records each downloaded file's game path, URL, hash, and first build in `auto-sources.json`. The tracker rejects image paths outside the game's ability icon folder. If the image is missing or the CDN is unavailable, the card stays text-only; the build report still publishes.

Cards embed the small local icon files, so archived graphics do not rely on an external image server when viewed.
