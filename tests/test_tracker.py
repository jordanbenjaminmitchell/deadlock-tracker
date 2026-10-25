import io
import gzip
import hashlib
import os
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import URLError
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import tracker
from diff import category, compare
from kv3 import KV3Error, loads


class ParserTests(unittest.TestCase):
    def test_nested_values_and_typed_resource(self):
        source = '''<!-- header --> { m_StreetBrawl = { m_vecBuyTime = [50,65,] }
        x = true y = false z = resource_name:"scripts/test.vdata" // comment
        nested = { value = 2.5 } }'''
        result = loads(source)
        self.assertEqual(result["m_StreetBrawl"]["m_vecBuyTime"], [50, 65])
        self.assertEqual(result["z"], "scripts/test.vdata")
        self.assertEqual(result["nested"]["value"], 2.5)

    def test_invalid_or_empty_rejected(self):
        for source in ("", "{}", "{ a = 1 a = 2 }", "{ a = [1,2 }"):
            with self.subTest(source=source), self.assertRaises(KV3Error):
                loads(source)


class ComparisonTests(unittest.TestCase):
    def test_street_brawl_exact_change(self):
        old = {"m_StreetBrawl": {"m_vecBuyTime": [50, 50, 50, 50, 65]}}
        new = {"m_StreetBrawl": {"m_vecBuyTime": [50, 50, 50, 50, 50]}}
        changes = compare(old, new, "generic_data")
        self.assertEqual(len(changes), 1)
        self.assertEqual(changes[0]["path"], "generic_data.m_StreetBrawl.m_vecBuyTime[4]")
        self.assertEqual(changes[0]["delta"], -15)
        self.assertAlmostEqual(changes[0]["percent"], -23.076923, places=5)
        self.assertEqual(category(changes[0]["path"]), "street-brawl")

    def test_negative_baseline_does_not_claim_a_percentage(self):
        change = compare({"x": -10}, {"x": -5})[0]
        self.assertEqual(change["delta"], 5)
        self.assertNotIn("percent", change)

    def test_add_remove_type_and_bool(self):
        changes = compare({"a": 1, "b": False, "c": [1, 2]},
                          {"a": 2, "b": True, "c": [1], "d": 3})
        self.assertEqual({c["path"]: c["kind"] for c in changes},
                         {"a": "changed", "b": "changed", "c[1]": "removed", "d": "added"})
        self.assertNotIn("delta", next(c for c in changes if c["path"] == "b"))

    def test_readable_change_preserves_direction_and_does_not_invent_units(self):
        added = {"path": "abilities.ability_artist_pullbrush.m_flMinStrokeDistance",
                 "kind": "added", "old": None, "new": 15.0}
        self.assertEqual(tracker.readable_change(added),
                         ("Violet · Living Ink", "Minimum stroke distance", "Added 15.0"))
        changed = {"path": "generic_data.m_StreetBrawl.m_vecBuyTime[4]",
                   "kind": "changed", "old": 65, "new": 50, "delta": -15}
        self.assertIn("65 → 50 (-15)", tracker.readable_change(changed)[2])
        future = {"path": "abilities.ability_unknown_dash.m_flTravelSpeed",
                  "kind": "changed", "old": 50, "new": 65, "delta": 15}
        self.assertEqual(tracker.readable_change(future),
                         ("Unknown dash", "Travel speed", "50 → 65 (+15)"))
        self.assertEqual(tracker.readable_change({"path": "abilities.ability_artist_bamboogrove.m_bDurationReducible",
                                                  "kind": "added", "old": None, "new": False})[0],
                         "Violet · Abstract Landscape")
        self.assertEqual(tracker.readable_change({"path": "abilities.ability_warden_riot_protocol.m_nEnabledStateMask",
                                                  "kind": "added", "old": None, "new": "MODIFIER_STATE_FEAR_IMMUNE"})[0],
                         "Warden · Last Stand")


class PublicPresentationTests(unittest.TestCase):
    def test_latest_update_explains_a_new_setting_without_guessing(self):
        change = {"path": "abilities.ability_artist_pullbrush.m_flMinStrokeDistance",
                  "category": "abilities", "kind": "added", "old": None, "new": 15.0}
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder:
            data = Path(folder) / "data"
            data.mkdir()
            (data / "6819.json").write_text(json.dumps({"changes": [change]}), encoding="utf-8")
            with patch.object(tracker, "REPORTS", Path(folder)):
                sentence = tracker.latest_change_sentence({"build": 6819})
        self.assertIn("Violet · Living Ink", sentence)
        self.assertIn("15.0", sentence)
        self.assertIn("no confirmed earlier value", sentence)

    def test_added_value_is_not_misreported_as_increase(self):
        change = {"path": "abilities.ability_artist_pullbrush.m_flMinStrokeDistance",
                  "kind": "added", "old": None, "new": 15.0}
        self.assertEqual(tracker.public_change(change),
                         ("Violet · Living Ink", "Minimum stroke distance", "No earlier value", "15.0", ""))

    def test_markdown_source_text_is_escaped(self):
        self.assertEqual(tracker.markdown_text("<script>*change*"), "&lt;script&gt;\\*change\\*")

    def test_other_flag_changes_are_not_hidden_by_fear_summary(self):
        change = {"path": "abilities.ability_warden_riot_protocol.m_nEnabledStateMask",
                  "kind": "changed", "old": "MODIFIER_STATE_OTHER",
                  "new": "MODIFIER_STATE_FEAR_IMMUNE | MODIFIER_STATE_NEW"}
        self.assertFalse(tracker.is_public_change(change))

    def test_fear_flag_is_plain_language_and_keeps_prior_state(self):
        change = {"path": "abilities.ability_warden_riot_protocol.m_WardenBuffModifier.m_nEnabledStateMask",
                  "kind": "changed", "old": "MODIFIER_STATE_OTHER",
                  "new": "MODIFIER_STATE_OTHER | MODIFIER_STATE_FEAR_IMMUNE"}
        self.assertEqual(tracker.public_change(change),
                         ("Warden · Last Stand", "Fear immunity", "Off", "On", "Fear immunity added"))

    def test_hero_code_name_uses_public_name(self):
        change = {"path": "heroes.hero_nurse.m_mapStartingStats.EMaxHealth",
                  "kind": "changed", "old": 780.0, "new": 730, "delta": -50.0}
        self.assertEqual(tracker.public_change(change)[0], "Nurse Harrow")


class ReliabilityTests(unittest.TestCase):
    def test_latest_build_card_remains_visible_without_a_verified_pair(self):
        latest = {"build": 7000, "upstream_time": "2026-10-24T12:00:00Z"}
        with patch.object(tracker, "latest_manifest", return_value=latest):
            page = tracker.gallery_markup([], "")
        self.assertIn('src="infographics/latest.svg"', page)
        self.assertIn("[See everything found in build 7000](builds/7000.md)", page)
        self.assertIn("No comparable changes are saved yet.", page)

    def test_discovery_pages_until_the_saved_build(self):
        def row(number):
            return {"sha": str(number), "commit": {"message": f"{number} | files",
                     "committer": {"date": "2026-10-24T00:00:00Z"}}}
        filler = [{"sha": f"f{i}", "commit": {"message": "unrelated"}}
                  for i in range(99)]
        with patch.object(tracker, "fetch_json", side_effect=[[row(7001), *filler], [row(7000)]]) as fetch:
            found = tracker.discover(limit_pages=2, stop_at_build=7000)
        self.assertEqual([entry["build"] for entry in found], [7000, 7001])
        self.assertEqual(fetch.call_count, 2)

    def test_discovery_reads_steam_inf_when_commit_title_changes(self):
        sha = "a" * 40
        payload = [{"sha": sha, "commit": {"message": "Client update",
                    "committer": {"date": "2026-10-24T12:00:00Z"}}}]
        with patch.object(tracker, "fetch_json", return_value=payload), \
             patch.object(tracker, "fetch", return_value=b"ClientVersion=7000\nappID=1422450\n") as fetch:
            found = tracker.discover(stop_at_build=7000)
        self.assertEqual([(entry["build"], entry["commit"]) for entry in found], [(7000, sha)])
        fetch.assert_called_once_with(tracker.raw_url(sha, "game/citadel/steam.inf"))

    def test_discovery_fails_if_page_limit_hides_saved_build(self):
        payload = [{"sha": "new", "commit": {"message": "7001 | files",
                   "committer": {"date": "2026-10-24T00:00:00Z"}}}]
        payload += [{"sha": str(i), "commit": {"message": "unrelated"}} for i in range(99)]
        with patch.object(tracker, "fetch_json", return_value=payload):
            with self.assertRaisesRegex(tracker.SourceError, "Could not reach saved build"):
                tracker.discover(limit_pages=1, stop_at_build=7000)

    def test_only_github_api_receives_workflow_token(self):
        requests = []
        def response(request, timeout):
            requests.append(request)
            return io.BytesIO(b"{}")
        with patch.dict(os.environ, {"GITHUB_TOKEN": "test-token"}), \
             patch.object(tracker, "urlopen", side_effect=response):
            tracker.fetch(tracker.API + "/commits")
            tracker.fetch("https://raw.githubusercontent.com/example/file")
        self.assertEqual(requests[0].get_header("Authorization"), "Bearer test-token")
        self.assertIsNone(requests[1].get_header("Authorization"))

    def test_recent_cards_prefer_an_existing_value_change_within_a_build(self):
        added = {"path": "abilities.ability_artist_pullbrush.m_flMinStrokeDistance",
                 "category": "abilities", "kind": "added", "old": None, "new": 15.0}
        changed = {"path": "heroes.hero_nurse.m_mapStartingStats.EMaxHealth",
                   "category": "heroes", "kind": "changed", "old": 780, "new": 730, "delta": -50}
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder:
            builds = Path(folder)
            for number in (6999, 7000):
                path = builds / str(number) / "snapshot.json"
                path.parent.mkdir()
                path.write_text(json.dumps({"build": number,
                    "upstream_time": f"2026-10-24T{number - 6999:02d}:00:00Z"}), encoding="utf-8")
            with patch.object(tracker, "BUILDS", builds), \
                 patch.object(tracker, "diff_manifests", return_value=[added, changed]):
                entries = tracker.recent_change_entries(limit=1)
        self.assertEqual(entries[0]["change"]["path"], changed["path"])

    def test_gallery_skips_new_fields_without_an_earlier_value(self):
        added = {"path": "abilities.ability_artist_pullbrush.m_flMinStrokeDistance",
                 "category": "abilities", "kind": "added", "old": None, "new": 15.0}
        changed = {"path": "heroes.hero_nurse.m_mapStartingStats.EMaxHealth",
                   "category": "heroes", "kind": "changed", "old": 780, "new": 730, "delta": -50}
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder:
            builds = Path(folder)
            for number in (6998, 6999, 7000):
                target = builds / str(number) / "snapshot.json"
                target.parent.mkdir()
                target.write_text(json.dumps({"build": number,
                    "upstream_time": f"2026-10-24T{number - 6998:02d}:00:00Z"}), encoding="utf-8")
            with patch.object(tracker, "BUILDS", builds), \
                 patch.object(tracker, "diff_manifests",
                              side_effect=lambda old, new: [added] if new["build"] == 7000 else [changed]):
                entries = tracker.recent_change_entries(limit=1)
        self.assertEqual(entries[0]["manifest"]["build"], 6999)
        self.assertEqual(entries[0]["change"], changed)

    def test_validator_rejects_tampered_archived_data(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder:
            root = Path(folder)
            digest = hashlib.sha256(b'{"expected":true}').hexdigest()
            blob = root / "blobs" / f"{digest}.json.gz"
            blob.parent.mkdir()
            blob.write_bytes(gzip.compress(b'{"tampered":true}'))
            commit = "a" * 40
            manifest = {"build": 7000, "commit": commit,
                        "source": f"https://github.com/{tracker.UPSTREAM}/commit/{commit}",
                        "files": {name: {"sha256": digest,
                                   "url": tracker.raw_url(commit, f"{tracker.SCRIPTS}/{name}.vdata")}
                                  for name in tracker.FILES}}
            snapshot = root / "builds" / "7000" / "snapshot.json"
            snapshot.parent.mkdir(parents=True)
            snapshot.write_text(json.dumps(manifest), encoding="utf-8")
            with patch.object(tracker, "BUILDS", root / "builds"), \
                 patch.object(tracker, "BLOBS", root / "blobs"):
                with self.assertRaisesRegex(tracker.SourceError, "hash mismatch"):
                    tracker.validate_archive()

    def test_refresh_uses_saved_community_posts(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder:
            root = Path(folder)
            snapshot = root / "builds" / "7000" / "snapshot.json"
            snapshot.parent.mkdir(parents=True)
            manifest = {"build": 7000, "community_posts": [{"title": "Build chat", "url": "https://example.test"}]}
            snapshot.write_text(json.dumps(manifest), encoding="utf-8")
            with patch.object(tracker, "BUILDS", root / "builds"), \
                 patch.object(tracker, "diff_manifests", return_value=[]), \
                 patch.object(tracker, "report") as report, \
                 patch.object(tracker, "infographic"), \
                 patch.object(tracker, "update_summaries"), \
                 patch.object(tracker, "recent_change_entries", return_value=[]), \
                 patch.object(tracker, "update_recent_gallery"):
                tracker.refresh_presentation()
            self.assertEqual(report.call_args.args[3], manifest["community_posts"])


class CollectionSafetyTests(unittest.TestCase):
    def test_missing_source_revision_stops_before_snapshot(self):
        entry = {"build": 7000, "commit": "a" * 40, "upstream_time": "2026-10-24T00:00:00Z"}
        with patch.object(tracker, "fetch", return_value=b"ClientVersion=7000\nappID=1422450\n") as fetch:
            with self.assertRaisesRegex(tracker.SourceError, "SourceRevision is missing"):
                tracker.collect(entry)
        self.assertEqual(fetch.call_count, 1)

    def test_invalid_source_encoding_has_clear_error(self):
        entry = {"build": 7000, "commit": "a" * 40, "upstream_time": "2026-10-24T00:00:00Z"}
        with patch.object(tracker, "fetch", return_value=b"\xff"):
            with self.assertRaisesRegex(tracker.SourceError, "Cannot decode"):
                tracker.collect(entry)

    def test_feature_card_prefers_measured_change(self):
        added = {"path": "abilities.ability_artist_pullbrush.m_flMinStrokeDistance",
                 "category": "abilities", "kind": "added", "old": None, "new": 15.0}
        changed = {"path": "heroes.hero_nurse.m_mapStartingStats.EMaxHealth",
                   "category": "heroes", "kind": "changed", "old": 780, "new": 730, "delta": -50}
        self.assertEqual(tracker.featured_change({}, [added, changed]), changed)


class PipelineTests(unittest.TestCase):
    def test_hero_card_uses_only_its_game_icon(self):
        class IconResponse(io.BytesIO):
            headers = {"Content-Type": "image/webp"}

        manifest = {"build": 7000, "files": {"heroes": {"sha256": "example"}}}
        change = {"path": "heroes.hero_nurse.m_mapStartingStats.EMaxHealth"}
        data = {"hero_nurse": {"m_strIconImageSmall": "file://{images}/heroes/nurse_sm.psd"}}
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder:
            with patch.object(tracker, "ROOT", Path(folder)), \
                 patch.object(tracker, "hero_blob", return_value=data), \
                 patch.object(tracker, "urlopen", return_value=IconResponse(b"RIFF0000WEBPicon")) as fetch_icon:
                tracker.ensure_icon_for_change(manifest, change)
                icon = Path(folder) / "assets" / "icons" / "heroes__nurse_sm.webp"
                self.assertEqual(icon.read_bytes(), b"RIFF0000WEBPicon")
                self.assertEqual(tracker.icon_for_change(change, manifest), icon.name)
                self.assertIn("/images/heroes/nurse_sm.webp", fetch_icon.call_args.args[0].full_url)

    def test_new_ability_icon_is_cached_from_its_game_image_path(self):
        class IconResponse(io.BytesIO):
            headers = {"Content-Type": "image/webp"}

        manifest = {"build": 7000, "files": {"abilities": {"sha256": "example"}}}
        change = {"path": "abilities.ability_new_dash.m_flSpeed"}
        data = {"ability_new_dash": {"m_strAbilityImage":
                                    "file://{images}/hud/abilities/newhero/new_dash.psd"}}
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder:
            with patch.object(tracker, "ROOT", Path(folder)), \
                 patch.object(tracker, "ability_blob", return_value=data), \
                 patch.object(tracker, "urlopen", return_value=IconResponse(b"RIFF0000WEBPicon")) as fetch_icon:
                tracker.ensure_icon_for_change(manifest, change)
                icon = Path(folder) / "assets" / "icons" / "newhero__new_dash.webp"
                self.assertEqual(icon.read_bytes(), b"RIFF0000WEBPicon")
                sources = json.loads((icon.parent / "auto-sources.json").read_text(encoding="utf-8"))
                self.assertIn("newhero__new_dash.webp", sources)
                self.assertEqual(tracker.icon_for_change(change, manifest), icon.name)
                self.assertIn("newhero/new_dash.webp", fetch_icon.call_args.args[0].full_url)
                icon.write_bytes(b"tampered")
                self.assertIsNone(tracker.icon_for_change(change, manifest))

    def test_missing_new_icon_keeps_card_text_only(self):
        manifest = {"build": 7000, "files": {"abilities": {"sha256": "example"}}}
        change = {"path": "abilities.ability_new_dash.m_flSpeed", "kind": "changed",
                  "old": 50, "new": 65, "delta": 15}
        data = {"ability_new_dash": {"m_strAbilityImage":
                                    "file://{images}/hud/abilities/newhero/new_dash.psd"}}
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder:
            with patch.object(tracker, "ROOT", Path(folder)), \
                 patch.object(tracker, "ability_blob", return_value=data), \
                 patch.object(tracker, "urlopen", side_effect=URLError("offline")):
                tracker.ensure_icon_for_change(manifest, change)
                self.assertIsNone(tracker.icon_for_change(change, manifest))
                self.assertFalse((Path(folder) / "assets" / "icons").exists())

    def test_changed_game_art_does_not_reuse_old_icon(self):
        manifest = {"files": {"abilities": {"sha256": "changed-art"}}}
        change = {"path": "abilities.ability_artist_homingbrush.m_flSpeed"}
        data = {"ability_artist_homingbrush": {"m_strAbilityImage":
                                              "file://{images}/hud/abilities/artist/new_livingink.psd"}}
        with patch.object(tracker, "ability_blob", return_value=data):
            self.assertIsNone(tracker.icon_for_change(change, manifest))

    def test_change_card_uses_matching_game_icon_and_exact_values(self):
        manifest = {"build": 6819, "upstream_time": "2026-10-22T23:53:52Z"}
        change = {"path": "abilities.ability_artist_pullbrush.m_flMinStrokeDistance",
                  "kind": "added", "old": None, "new": 15.0}
        svg = tracker.change_card(manifest, {"build": 6817}, change, 1)
        root = ET.fromstring(svg)
        self.assertEqual(len(root.findall("{http://www.w3.org/2000/svg}image")), 1)
        self.assertIn("New setting: 15.0", svg)
        self.assertNotIn("No earlier value →", svg)
        self.assertIn("Oct 22, 2026 23:53 UTC", svg)
        self.assertNotIn("<rect x=\"220\"", svg)

    def test_unknown_field_card_has_no_generic_icon(self):
        svg = tracker.change_card({"build": 7000, "upstream_time": "2026-10-23T12:00:00Z"},
                                  {"build": 6999},
                                  {"path": "generic_data.m_Example.m_flRange", "kind": "changed",
                                   "old": 50, "new": 65, "delta": 15}, 2)
        root = ET.fromstring(svg)
        self.assertFalse(root.findall("{http://www.w3.org/2000/svg}image"))
        self.assertIn("50 → 65", svg)
        self.assertIn("1 of 2 changes", svg)

    def test_report_leads_with_readable_change_and_keeps_source(self):
        change = {"path": "generic_data.m_StreetBrawl.m_vecBuyTime[4]",
                  "category": "street-brawl", "kind": "changed",
                  "old": 65, "new": 50, "delta": -15, "percent": -23.076923}
        manifest = {"build": 6794, "upstream_time": "2026-10-17T21:32:00Z",
                    "source": "https://example.test/commit", "source_revision": "123",
                    "files": {}, "changed_files": []}
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder:
            with patch.object(tracker, "REPORTS", Path(folder)):
                tracker.report(manifest, {"build": 6793}, [change], [])
                page = (Path(folder) / "builds" / "6794.md").read_text(encoding="utf-8")
                exact = json.loads((Path(folder) / "data" / "6794.json").read_text(encoding="utf-8"))
        self.assertIn("Street Brawl — Buy time, fifth value**: 65 → **50** (Down 15 · 23.08%)", page)
        self.assertIn("<summary>Check the exact source values</summary>", page)
        self.assertIn("[Download every original before and after value](../data/6794.json)", page)
        self.assertEqual(exact["changes"], [change])
        self.assertNotIn("## Heroes", page)
        self.assertNotIn("No exact-build discussion retrieved", page)

    def test_new_field_report_does_not_claim_a_previous_number(self):
        change = {"path": "abilities.ability_artist_pullbrush.m_flMinStrokeDistance",
                  "category": "abilities", "kind": "added", "old": None, "new": 15.0}
        manifest = {"build": 6819, "upstream_time": "2026-10-22T23:53:52Z",
                    "source": "https://example.test/commit", "source_revision": "123",
                    "files": {}, "changed_files": []}
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder:
            with patch.object(tracker, "REPORTS", Path(folder)):
                tracker.report(manifest, {"build": 6817}, [change], [])
                page = (Path(folder) / "builds" / "6819.md").read_text(encoding="utf-8")
        self.assertIn("new setting **15.0**", page)
        self.assertIn("earlier in-game behavior cannot be verified", page)
        self.assertNotIn("No earlier value →", page)

    def test_discovery_deduplicates_and_orders(self):
        def row(number, sha):
            return {"sha": sha, "commit": {"message": f"{number} | files",
                                          "committer": {"date": "2026-10-22T00:00:00Z"}}}
        with patch.object(tracker, "fetch_json", return_value=[row(6819, "new"), row(6817, "old"),
                                                              row(6819, "duplicate"), row(6793, "first")]):
            self.assertEqual([(x["build"], x["commit"]) for x in tracker.discover()],
                             [(6793, "first"), (6817, "old"), (6819, "new")])

    def test_source_failure_cannot_create_snapshot(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder:
            root = Path(folder)
            with patch.object(tracker, "BUILDS", root / "builds"), \
                 patch.object(tracker, "BLOBS", root / "blobs"), \
                 patch.object(tracker, "REPORTS", root / "reports"), \
                 patch.object(tracker, "DATA", root), \
                 patch.object(tracker, "discover", return_value=[{"build": 6793, "commit": "abc"}]), \
                 patch.object(tracker, "fetch", side_effect=tracker.SourceError("download failed")):
                with self.assertRaises(tracker.SourceError):
                    tracker.run()
                self.assertFalse((root / "builds").exists())

    def test_idempotent_run(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder:
            root = Path(folder)
            target = root / "builds" / "6819" / "snapshot.json"
            target.parent.mkdir(parents=True)
            target.write_text(json.dumps({"build": 6819, "commit": "abc"}), encoding="utf-8")
            with patch.object(tracker, "BUILDS", root / "builds"), \
                 patch.object(tracker, "discover", return_value=[{"build": 6819, "commit": "abc"}]), \
                 patch.object(tracker, "collect") as collect, \
                 patch.object(tracker, "refresh_presentation") as refresh, \
                 patch.object(tracker, "validate_archive", return_value=(1, 0)):
                tracker.run()
                collect.assert_not_called()
                refresh.assert_not_called()

    def test_unchanged_build_repairs_stale_presentation(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder:
            builds = Path(folder) / "builds"
            target = builds / "6819" / "snapshot.json"
            target.parent.mkdir(parents=True)
            target.write_text(json.dumps({"build": 6819, "commit": "abc"}), encoding="utf-8")
            with patch.object(tracker, "BUILDS", builds), \
                 patch.object(tracker, "discover", return_value=[{"build": 6819, "commit": "abc"}]), \
                 patch.object(tracker, "refresh_presentation") as refresh, \
                 patch.object(tracker, "validate_archive",
                              side_effect=[tracker.SourceError("stale page"), (1, 0)]) as validate:
                tracker.run()
            refresh.assert_called_once_with()
            self.assertEqual(validate.call_count, 2)

    def test_rewritten_history_rejected(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder:
            root = Path(folder)
            target = root / "builds" / "6819" / "snapshot.json"
            target.parent.mkdir(parents=True)
            target.write_text(json.dumps({"build": 6819, "commit": "original"}), encoding="utf-8")
            with patch.object(tracker, "BUILDS", root / "builds"), \
                 patch.object(tracker, "discover", return_value=[{"build": 6819, "commit": "rewritten"}]):
                with self.assertRaisesRegex(tracker.SourceError, "rewrote archived build"):
                    tracker.run()


if __name__ == "__main__":
    unittest.main()
