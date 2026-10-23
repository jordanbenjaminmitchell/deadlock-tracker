import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
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


class PipelineTests(unittest.TestCase):
    def test_change_card_uses_matching_game_icon_and_exact_values(self):
        manifest = {"build": 6819, "upstream_time": "2026-10-22T23:53:52Z"}
        change = {"path": "abilities.ability_artist_pullbrush.m_flMinStrokeDistance",
                  "kind": "added", "old": None, "new": 15.0}
        svg = tracker.change_card(manifest, {"build": 6817}, change, 1)
        root = ET.fromstring(svg)
        self.assertEqual(len(root.findall("{http://www.w3.org/2000/svg}image")), 1)
        self.assertIn("unset → 15.0", svg)
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
        self.assertIn("Street Brawl — Buy time, fifth value: 65 → 50 (-15) · -23.08%", page)
        self.assertIn("Source: `generic_data.m_StreetBrawl.m_vecBuyTime[4]`", page)
        self.assertNotIn("## Heroes", page)
        self.assertNotIn("No exact-build discussion retrieved", page)

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
                 patch.object(tracker, "collect") as collect:
                tracker.run()
                collect.assert_not_called()

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
