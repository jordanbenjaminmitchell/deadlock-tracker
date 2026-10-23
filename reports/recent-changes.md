## The latest five changes

Here are the five most recent individual values we found changing in the game data we track. The time on each card is when SteamTracking recorded the build (UTC). Values use the source's units; we do not guess at missing units. Open a build report to see every change in that build.

<table>
<tr>
<td width="20%">
<a href="infographics/recent/6819-7c3bc775ffd6.svg"><img src="infographics/recent/6819-7c3bc775ffd6.svg" width="185" alt="Build 6819: Violet · Living Ink, Minimum stroke distance, Added 15.0"></a>
</td>
<td width="20%">
<a href="infographics/recent/6813-4ac8e64d4b98.svg"><img src="infographics/recent/6813-4ac8e64d4b98.svg" width="185" alt="Build 6813: Warden · Last Stand, Auto-cast delay state flags, Fear-immunity flag added"></a>
</td>
<td width="20%">
<a href="infographics/recent/6813-31c66ad54ffe.svg"><img src="infographics/recent/6813-31c66ad54ffe.svg" width="185" alt="Build 6813: Warden · Last Stand, Warden buff state flags, Fear-immunity flag added"></a>
</td>
<td width="20%">
<a href="infographics/recent/6801-3875ea06f36b.svg"><img src="infographics/recent/6801-3875ea06f36b.svg" width="185" alt="Build 6801: Violet · Abstract Landscape, Duration reduction allowed, Now off"></a>
</td>
<td width="20%">
<a href="infographics/recent/6801-645c36996f46.svg"><img src="infographics/recent/6801-645c36996f46.svg" width="185" alt="Build 6801: Violet · Living Ink, Duration extension allowed, Now on"></a>
</td>
</tr>
</table>

### What changed, and when

<ol>
<li><strong>Violet · Living Ink — Minimum stroke distance: Added 15.0</strong><br>Build 6819 · Oct 22, 2026 23:53 UTC (<a href="infographics/recent/6819-7c3bc775ffd6.svg">view card</a>; <a href="builds/6819.md">all changes</a>; <a href="https://github.com/SteamTracking/GameTracking-Deadlock/commit/17462b250a0ca80e7f80102f2c83cc3eecff5f12">source commit</a>)<br><code>unset</code> → <code>15.0</code> · Source field: <code>abilities.ability_artist_pullbrush.m_flMinStrokeDistance</code></li>
<li><strong>Warden · Last Stand — Auto-cast delay state flags: Fear-immunity flag added</strong><br>Build 6813 · Oct 22, 2026 04:14 UTC (<a href="infographics/recent/6813-4ac8e64d4b98.svg">view card</a>; <a href="builds/6813.md">all changes</a>; <a href="https://github.com/SteamTracking/GameTracking-Deadlock/commit/a94d8b455203f12b176de75a5598dd8e6e8a94d4">source commit</a>)<br><code>unset</code> → <code>&quot;MODIFIER_STATE_FEAR_IMMUNE&quot;</code> · Source field: <code>abilities.ability_warden_riot_protocol.m_AutoCastDelayModifier.m_nEnabledStateMask</code></li>
<li><strong>Warden · Last Stand — Warden buff state flags: Fear-immunity flag added</strong><br>Build 6813 · Oct 22, 2026 04:14 UTC (<a href="infographics/recent/6813-31c66ad54ffe.svg">view card</a>; <a href="builds/6813.md">all changes</a>; <a href="https://github.com/SteamTracking/GameTracking-Deadlock/commit/a94d8b455203f12b176de75a5598dd8e6e8a94d4">source commit</a>)<br><code>&quot;MODIFIER_STATE_SINCLAIR_TAX_ULT_ACTIVE | MODIFIER_STATE_SINCLAIR_TAX_KEEP_MODEL_SWAP&quot;</code> → <code>&quot;MODIFIER_STATE_SINCLAIR_TAX_ULT_ACTIVE | MODIFIER_STATE_SINCLAIR_TAX_KEEP_MODEL_SWAP | MODIFIER_STATE_FEAR_IMMUNE&quot;</code> · Source field: <code>abilities.ability_warden_riot_protocol.m_WardenBuffModifier.m_nEnabledStateMask</code></li>
<li><strong>Violet · Abstract Landscape — Duration reduction allowed: Now off</strong><br>Build 6801 · Oct 20, 2026 21:02 UTC (<a href="infographics/recent/6801-3875ea06f36b.svg">view card</a>; <a href="builds/6801.md">all changes</a>; <a href="https://github.com/SteamTracking/GameTracking-Deadlock/commit/37f9aebdc62766aa13748f73309b9b8120549833">source commit</a>)<br><code>unset</code> → <code>false</code> · Source field: <code>abilities.ability_artist_bamboogrove.m_BambooModifier.m_ImmuneModifier.m_bDurationReducible</code></li>
<li><strong>Violet · Living Ink — Duration extension allowed: Now on</strong><br>Build 6801 · Oct 20, 2026 21:02 UTC (<a href="infographics/recent/6801-645c36996f46.svg">view card</a>; <a href="builds/6801.md">all changes</a>; <a href="https://github.com/SteamTracking/GameTracking-Deadlock/commit/37f9aebdc62766aa13748f73309b9b8120549833">source commit</a>)<br><code>unset</code> → <code>true</code> · Source field: <code>abilities.ability_artist_homingbrush.m_StackModifier.m_bDurationExtendible</code></li>
</ol>
