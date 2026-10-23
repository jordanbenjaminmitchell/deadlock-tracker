"""Archive immutable SteamTracking revisions and report exact extracted values."""

from __future__ import annotations

import argparse
import base64
from datetime import datetime, timezone
from functools import lru_cache
import gzip
import hashlib
import html
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import time
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from diff import category, compare
from kv3 import KV3Error, loads


UPSTREAM = "SteamTracking/GameTracking-Deadlock"
SCRIPTS = "game/citadel/pak01_dir/scripts"
FILES = ("abilities", "generic_data", "heroes", "misc", "modifiers", "npc_units")
API = f"https://api.github.com/repos/{UPSTREAM}"
RAW = f"https://raw.githubusercontent.com/{UPSTREAM}"
ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
BUILDS = DATA / "builds"
BLOBS = DATA / "blobs"
REPORTS = ROOT / "reports"
FIRST_BUILD = 6793
USER_AGENT = "deadlock-tracker/1.0 (+https://github.com/jordanbenjaminmitchell/deadlock-tracker)"
ICON_CDN = "https://assets-bucket.deadlock-api.com/assets-api-res/images/abilities/"


class SourceError(RuntimeError):
    pass


def fetch(url: str, *, retries: int = 3, timeout: int = 30) -> bytes:
    request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    for attempt in range(retries):
        try:
            with urlopen(request, timeout=timeout) as response:
                body = response.read(25_000_001)
                if not body or len(body) > 25_000_000:
                    raise SourceError(f"Empty or oversized response: {url}")
                return body
        except (HTTPError, URLError, TimeoutError, SourceError) as exc:
            if attempt == retries - 1 or isinstance(exc, HTTPError) and exc.code in (401, 403, 404):
                raise SourceError(f"Could not fetch {url}: {exc}") from exc
            time.sleep(2 ** attempt)
    raise AssertionError("unreachable")


def fetch_json(url: str):
    try:
        return json.loads(fetch(url))
    except (ValueError, UnicodeError) as exc:
        raise SourceError(f"Invalid JSON from {url}: {exc}") from exc


def discover(limit_pages: int = 5) -> list[dict]:
    """List distinct client builds from commits that changed steam.inf."""
    found = {}
    for page in range(1, limit_pages + 1):
        query = urlencode({"path": "game/citadel/steam.inf", "per_page": 100, "page": page})
        payload = fetch_json(f"{API}/commits?{query}")
        if not isinstance(payload, list):
            raise SourceError("GitHub commit listing had an unexpected shape")
        for commit in payload:
            message = commit.get("commit", {}).get("message", "")
            match = re.match(r"^(\d{4,7})\s*\|", message)
            if match:
                number = int(match.group(1))
                if number >= FIRST_BUILD and number not in found:
                    changed_files = re.findall(r"([MAD])\t([^,\n]+)", message)
                    steamdb = re.search(r"https://steamdb\.info/patchnotes/\d+/", message)
                    found[number] = {"build": number, "commit": commit["sha"],
                                     "upstream_time": commit["commit"]["committer"]["date"],
                                     "changed_files": [{"status": status, "path": path}
                                                       for status, path in changed_files],
                                     "steamdb_url": steamdb.group() if steamdb else None}
        if len(payload) < 100 or (found and min(found) <= FIRST_BUILD):
            break
    if not found:
        raise SourceError("No client builds found in SteamTracking commit history")
    return [found[key] for key in sorted(found)]


def raw_url(commit: str, path: str) -> str:
    return f"{RAW}/{commit}/{path}"


def load_blob(digest: str):
    path = BLOBS / f"{digest}.json.gz"
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        return json.load(stream)


@lru_cache(maxsize=32)
def ability_blob(digest: str):
    return load_blob(digest)


def write_atomic(path: Path, content: bytes):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
        temporary = Path(stream.name)
        stream.write(content)
    os.replace(temporary, path)


def json_bytes(value) -> bytes:
    return (json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")


def latest_manifest():
    paths = sorted(BUILDS.glob("*/snapshot.json"), key=lambda path: int(path.parent.name))
    return json.loads(paths[-1].read_text(encoding="utf-8")) if paths else None


def collect(entry: dict) -> dict:
    number, commit = entry["build"], entry["commit"]
    inf_path = "game/citadel/steam.inf"
    inf = fetch(raw_url(commit, inf_path)).decode("utf-8")
    props = dict(re.findall(r"^([^=\r\n]+)=([^\r\n]*)", inf, flags=re.MULTILINE))
    if props.get("ClientVersion") != str(number) or props.get("appID") != "1422450":
        raise SourceError(f"ClientVersion/appID mismatch for commit {commit}")
    parsed = {}
    for name in FILES:
        path = f"{SCRIPTS}/{name}.vdata"
        body = fetch(raw_url(commit, path)).decode("utf-8-sig")
        try:
            parsed[name] = loads(body)
        except (KV3Error, UnicodeError) as exc:
            raise SourceError(f"Cannot parse {path} at {commit}: {exc}") from exc
        if not parsed[name]:
            raise SourceError(f"Empty parsed data for {path} at {commit}")
    hashes = {}
    for name, value in parsed.items():
        encoded = json_bytes(value)
        digest = hashlib.sha256(encoded).hexdigest()
        hashes[name] = digest
        target = BLOBS / f"{digest}.json.gz"
        if not target.exists():
            write_atomic(target, gzip.compress(encoded, compresslevel=9, mtime=0))
    return {"build": number, "commit": commit, "upstream_time": entry["upstream_time"],
            "collected_at": datetime.now(timezone.utc).isoformat(),
            "source_revision": props.get("SourceRevision"),
            "compiled_at": f"{props.get('VersionDate', '')} {props.get('VersionTime', '')}".strip(),
            "source": f"https://github.com/{UPSTREAM}/commit/{commit}",
            "steamdb_url": entry.get("steamdb_url"),
            "changed_files": entry.get("changed_files", []),
            "files": {name: {"sha256": digest,
                             "url": raw_url(commit, f"{SCRIPTS}/{name}.vdata")}
                      for name, digest in hashes.items()}}


def snapshot_data(manifest: dict):
    return {name: load_blob(record["sha256"]) for name, record in manifest["files"].items()}


def diff_manifests(old: dict | None, new: dict) -> list[dict]:
    if old is None:
        return []
    changes = []
    for name in FILES:
        old_hash = old["files"][name]["sha256"]
        new_hash = new["files"][name]["sha256"]
        if old_hash != new_hash:
            changes.extend(compare(load_blob(old_hash), load_blob(new_hash), name))
    for change in changes:
        change["category"] = category(change["path"])
    return changes


def community(number: int) -> list[dict]:
    # Public search is supplemental. A 403 or rate limit never aborts collection.
    url = "https://www.reddit.com/r/DeadlockTheGame/search.json?" + urlencode(
        {"q": f'"{number}"', "restrict_sr": "on", "sort": "new", "limit": 10})
    try:
        listing = fetch_json(url)
        posts = listing.get("data", {}).get("children", [])
        return [{"title": post["data"]["title"],
                 "url": "https://www.reddit.com" + post["data"]["permalink"]}
                for post in posts if re.search(rf"\b{number}\b", post["data"]["title"])]
    except (SourceError, KeyError, TypeError):
        return []


def fmt(value):
    if isinstance(value, (dict, list)):
        rendered = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        return rendered[:200] + ("…" if len(rendered) > 200 else "")
    return json.dumps(value, ensure_ascii=False)


def report(manifest: dict, prior: dict | None, changes: list[dict], posts: list[dict]):
    number = manifest["build"]
    stamp = datetime.fromisoformat(manifest["upstream_time"].replace("Z", "+00:00"))
    when = stamp.strftime("%b %d, %Y at %H:%M UTC")
    lines = [f"# Deadlock build {number}", "",
             f"Recorded {when}. " + (f"Compared with build {prior['build']}." if prior else
                                     "This is the first saved build, so there is no earlier value to compare."), ""]
    if prior:
        lines += [f"**{len(changes)} tracked {'change' if len(changes) == 1 else 'changes'}.**", ""]
    if prior and not changes:
        lines += ["No value changed in the game data we track for this build.", ""]
    lines += ["These are values found in extracted game data. They do not confirm how a change felt in a match.", ""]
    sections = [("Street Brawl", "street-brawl"), ("Heroes", "heroes"),
                ("Abilities and items", "abilities"), ("Map and NPC data", "map-and-npcs"),
                ("Modifiers", "modifiers"), ("Other data", "other-data")]
    shown = 0
    for title, key in sections:
        selected = [change for change in changes if change["category"] == key and is_public_change(change)]
        if not selected:
            continue
        groups = {}
        for change in selected:
            view = public_change(change)
            groups[view] = groups.get(view, 0) + 1
        lines += [f"## {title} ({len(selected)})", ""]
        for (context, field, before, after, note), count in groups.items():
            lines.append(f"- **{context} — {field}**: {before} → **{after}**"
                         + (f" ({note})" if note else "")
                         + (f" · {count} matching values" if count > 1 else ""))
        lines.append("")
        shown += len(selected)
    if shown < len(changes):
        lines += [f"**{shown} readable value changes are shown above.** The other {len(changes) - shown} "
                  "changes involve game data references or structures. Their exact before and after values "
                  "are under ‘Check the exact source values’ below.", ""]
    if posts:
        lines += ["## Community discussion", "",
                  "These posts may add context; the values above come from game data.", ""]
        lines += [f"- [{post['title']}]({post['url']})" for post in posts]
        lines.append("")
    lines += ["[See the source commit](" + manifest["source"] + ")", "",
              "<details>", "<summary>Check the exact source values</summary>", "",
              f"Client build `{number}` · Source revision `{manifest['source_revision']}`", "",
              "The lines below preserve the original field names and values used for this comparison.", ""]
    for change in changes:
        lines.append(f"- `{change['path']}`: `{fmt(change['old'])}` → `{fmt(change['new'])}`")
    ignored = {"game/citadel/steam.inf", *(f"{SCRIPTS}/{name}.vdata" for name in FILES)}
    other_files = [item for item in manifest.get("changed_files", [])
                   if item["path"] not in ignored and not item["path"].startswith("manifests/")]
    if other_files:
        lines += ["", f"Other files in the same upstream commit ({len(other_files)}):", ""]
        lines += [f"- `{item['status']}` `{item['path']}`" for item in other_files[:40]]
        if len(other_files) > 40:
            lines.append(f"- … and {len(other_files) - 40} more.")
    lines += ["", "Tracked source files:", ""]
    for name, file in manifest["files"].items():
        lines.append(f"- `{name}.vdata`: [upstream file]({file['url']}), normalized SHA-256 `{file['sha256']}`")
    lines += ["", f"[Archived snapshot](../../data/builds/{number}/snapshot.json)", "", "</details>", ""]
    write_atomic(REPORTS / "builds" / f"{number}.md", "\n".join(lines).encode("utf-8"))


def infographic(manifest: dict, prior: dict | None, changes: list[dict]):
    """Show one actual change; link to the report for the rest of the build."""
    number = manifest["build"]
    featured = featured_change(manifest, changes)
    svg = change_card(manifest, prior, featured, len(changes))
    write_atomic(REPORTS / "infographics" / f"{number}.svg", svg.encode("utf-8"))


def update_summaries(manifest: dict, changes: list[dict]):
    number = manifest["build"]
    path = REPORTS / "builds" / f"{number}.md"
    write_atomic(REPORTS / "latest.md",
                 path.read_text(encoding="utf-8").replace("../../data/", "../data/").encode("utf-8"))
    write_atomic(REPORTS / "infographics" / "latest.svg",
                 (REPORTS / "infographics" / f"{number}.svg").read_bytes())
    brawl = [change for change in changes if change["category"] == "street-brawl"]
    lines = ["# Street Brawl changes", "",
             f"The latest archived build is [{number}](builds/{number}.md). "
             + (f"It has {len(brawl)} confirmed Street Brawl {'change' if len(brawl) == 1 else 'changes'}."
                if brawl else "It has no confirmed Street Brawl value change."), ""]
    latest_brawl = None
    manifests = [json.loads(path.read_text(encoding="utf-8")) for path in
                 sorted(BUILDS.glob("*/snapshot.json"), key=lambda path: int(path.parent.name))]
    for position in range(len(manifests) - 1, 0, -1):
        found = [change for change in diff_manifests(manifests[position - 1], manifests[position])
                 if change["category"] == "street-brawl"]
        if found:
            latest_brawl = (manifests[position], found)
            break
    if latest_brawl:
        source, found = latest_brawl
        stamp = datetime.fromisoformat(source["upstream_time"].replace("Z", "+00:00"))
        lines += [f"## Most recent confirmed change: build {source['build']}", "",
                  f"Recorded {stamp.strftime('%b %d, %Y at %H:%M UTC')}. "
                  f"[Read the build report](builds/{source['build']}.md) or "
                  f"[check the source commit]({source['source']}).", ""]
        for change in found:
            context, field, before, after, note = public_change(change)
            lines.append(f"- **{context} — {field}**: {before} → **{after}**"
                         + (f" ({note})" if note else ""))
    else:
        lines.append("No Street Brawl value change appears in the archived comparisons yet.")
    lines += ["", "[Browse all builds](index.md) · [See the latest change card](infographics/latest.svg)", ""]
    write_atomic(REPORTS / "street-brawl.md", "\n".join(lines).encode("utf-8"))
    write_atomic(DATA / "state.json", json_bytes({"latest_build": number, "latest_commit": manifest["commit"]}))


def recent_change_entries(limit: int = 5) -> list[dict]:
    """Select the newest scalar VData changes; field paths break ties within a build."""
    manifests = [json.loads(path.read_text(encoding="utf-8")) for path in
                 sorted(BUILDS.glob("*/snapshot.json"), key=lambda path: int(path.parent.name))]
    comparisons = [(manifests[position], manifests[position - 1])
                   for position in range(1, len(manifests))]
    comparisons.sort(key=lambda pair: (pair[0]["upstream_time"], pair[0]["build"]), reverse=True)
    entries = []
    for manifest, prior in comparisons:
        changes = diff_manifests(prior, manifest)
        scalar = (change for change in changes
                  if not isinstance(change["old"], (dict, list))
                  and not isinstance(change["new"], (dict, list))
                  and is_public_change(change))
        for change in sorted(scalar, key=lambda item: item["path"]):
            entries.append({"manifest": manifest, "prior": prior, "change": change})
            if len(entries) == limit:
                return entries
    return entries


ABILITY_LABELS = {
    "ability_artist_pullbrush": "Violet · Living Ink",
    "ability_artist_bamboogrove": "Violet · Abstract Landscape",
    "ability_artist_homingbrush": "Violet · Living Ink",
    "ability_warden_riot_protocol": "Warden · Last Stand",
}
ABILITY_ICONS = {
    "ability_artist_pullbrush": "living-ink.webp",
    "ability_artist_homingbrush": "living-ink.webp",
    "ability_artist_bamboogrove": "abstract-landscape.webp",
    "ability_warden_riot_protocol": "last-stand.webp",
}
KNOWN_ICON_GAME_PATHS = {
    "ability_artist_pullbrush": "file://{images}/hud/abilities/artist/artist_livingink.psd",
    "ability_artist_homingbrush": "file://{images}/hud/abilities/artist/artist_livingink.psd",
    "ability_artist_bamboogrove": "file://{images}/hud/abilities/artist/artist_landscape.psd",
    "ability_warden_riot_protocol": "file://{images}/hud/abilities/warden/warden_riot_protocol.psd",
}
FIELD_LABELS = {
    "m_flMinStrokeDistance": "Minimum stroke distance",
    "m_bDurationReducible": "Duration reduction allowed",
    "m_bDurationExtendible": "Duration extension allowed",
    "m_nEnabledStateMask": "Enabled state flags",
}


def readable_words(identifier: str) -> str:
    """Turn an internal identifier into a cautious display label."""
    identifier = re.sub(r"^m_(?:fl|vec|str|n|b|e)(?=[A-Z])", "", identifier)
    identifier = identifier.removeprefix("m_").removeprefix("ability_").removeprefix("hero_")
    identifier = re.sub(r"^E(?=[A-Z])", "", identifier)
    words = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", identifier).replace("_", " ").lower()
    words = re.sub(r"\bmin\b", "minimum", re.sub(r"\bmax\b", "maximum", words))
    words = re.sub(r"\bui\b", "UI", words)
    return words[:1].upper() + words[1:]


def readable_change(change: dict) -> tuple[str, str, str]:
    """Return context, field label, and a concise, evidence-limited value summary."""
    parts = change["path"].split(".")
    if parts[0] == "abilities" and len(parts) > 1:
        context = ABILITY_LABELS.get(parts[1], readable_words(parts[1]))
    elif len(parts) > 1:
        context = "Street Brawl" if parts[1] == "m_StreetBrawl" else readable_words(parts[1])
    else:
        context = readable_words(parts[0])
    field = FIELD_LABELS.get(parts[-1], readable_words(parts[-1]))
    if change["path"] == "generic_data.m_StreetBrawl.m_vecBuyTime[4]":
        field = "Buy time, fifth value"
    if parts[-1] == "m_nEnabledStateMask" and len(parts) > 3:
        parent = {"m_AutoCastDelayModifier": "Auto-cast delay",
                  "m_WardenBuffModifier": "Warden buff"}.get(parts[-2], readable_words(parts[-2]))
        field = f"{parent} state flags"
    if parts[-1] == "m_nEnabledStateMask" and isinstance(change["new"], str):
        old_flags = set(change["old"].split(" | ")) if isinstance(change["old"], str) else set()
        added = set(change["new"].split(" | ")) - old_flags
        if added == {"MODIFIER_STATE_FEAR_IMMUNE"}:
            return context, field, "Fear-immunity flag added"
    if change["kind"] == "added":
        if isinstance(change["new"], (dict, list)):
            return context, field, "Structured value added"
        value = "on" if change["new"] is True else "off" if change["new"] is False else fmt(change["new"])
        return context, field, f"Now {value}" if isinstance(change["new"], bool) else f"Added {value}"
    if change["kind"] == "removed":
        return context, field, "Field removed"
    if "delta" in change:
        return context, field, f"{fmt(change['old'])} → {fmt(change['new'])} ({change['delta']:+g})"
    if isinstance(change["old"], bool) and isinstance(change["new"], bool):
        return context, field, f"{'On' if change['old'] else 'Off'} → {'on' if change['new'] else 'off'}"
    return context, field, f"{fmt(change['old'])} → {fmt(change['new'])}"


def public_change(change: dict) -> tuple[str, str, str, str, str]:
    """Show archived before/after values without exposing internal field names."""
    context, field, _ = readable_change(change)
    old, new = change["old"], change["new"]
    if change["path"].endswith("m_nEnabledStateMask") and isinstance(new, str):
        flag = "MODIFIER_STATE_FEAR_IMMUNE"
        old_flags = set(old.split(" | ")) if isinstance(old, str) else set()
        new_flags = set(new.split(" | "))
        if flag in new_flags and flag not in old_flags:
            field = field.replace(" state flags", " fear immunity")
            before = "Not listed" if change["kind"] == "added" else "Off"
            return context, field, before, "On", "Fear immunity added"

    def value(item):
        if item is True:
            return "On"
        if item is False:
            return "Off"
        if isinstance(item, (dict, list)):
            return "Structured data"
        if isinstance(item, str):
            states = {"EHeroDevState_PreRelease": "Pre-release",
                      "EHeroDevState_Release": "Released"}
            if item in states:
                return states[item]
            if item.startswith("E") and "_" in item:
                parts = item.split(" | ")
                if all(re.fullmatch(r"E[A-Za-z]+_[A-Za-z0-9_]+", part) for part in parts):
                    return ", ".join(readable_words(part.split("_", 1)[1]) for part in parts)
            if (item.startswith(("MODIFIER_STATE_", "ability_", "citadel_", "#"))
                    or "/" in item or ".vdata" in item or "_" in item or "." in item):
                return "Game data reference"
            return item
        return fmt(item)

    before = "Not listed" if change["kind"] == "added" else value(old)
    after = "Removed" if change["kind"] == "removed" else value(new)
    note = f"Change {change['delta']:+g}" if "delta" in change else ""
    if note and "percent" in change:
        note += f" · {change['percent']:+.2f}%"
    return context, field, before, after, note


def public_change(change: dict) -> tuple[str, str, str, str, str]:
    """Show archived before/after values without exposing internal field names."""
    context, field, _ = readable_change(change)
    old, new = change["old"], change["new"]
    if change["path"].endswith("m_nEnabledStateMask") and isinstance(new, str):
        flag = "MODIFIER_STATE_FEAR_IMMUNE"
        old_flags = set(old.split(" | ")) if isinstance(old, str) else set()
        new_flags = set(new.split(" | "))
        if flag in new_flags and flag not in old_flags:
            field = field.replace(" state flags", " fear immunity")
            before = "Not listed" if change["kind"] == "added" else "Off"
            return context, field, before, "On", "Fear immunity added"

    def value(item):
        if item is True:
            return "On"
        if item is False:
            return "Off"
        if isinstance(item, (dict, list)):
            return "Structured data"
        if isinstance(item, str):
            states = {"EHeroDevState_PreRelease": "Pre-release",
                      "EHeroDevState_Release": "Released"}
            if item in states:
                return states[item]
            if item.startswith("E") and "_" in item:
                parts = item.split(" | ")
                if all(re.fullmatch(r"E[A-Za-z]+_[A-Za-z0-9_]+", part) for part in parts):
                    return ", ".join(readable_words(part.split("_", 1)[1]) for part in parts)
            if (item.startswith(("MODIFIER_STATE_", "ability_", "citadel_", "#"))
                    or "/" in item or ".vdata" in item or "_" in item or "." in item):
                return "Game data reference"
            return item
        return fmt(item)

    before = "Not listed" if change["kind"] == "added" else value(old)
    after = "Removed" if change["kind"] == "removed" else value(new)
    note = f"Change {change['delta']:+g}" if "delta" in change else ""
    if note and "percent" in change:
        note += f" · {change['percent']:+.2f}%"
    return context, field, before, after, note


def public_change(change: dict) -> tuple[str, str, str, str, str]:
    """Show archived before/after values without exposing internal field names."""
    context, field, _ = readable_change(change)
    old, new = change["old"], change["new"]
    if change["path"].endswith("m_nEnabledStateMask") and isinstance(new, str):
        flag = "MODIFIER_STATE_FEAR_IMMUNE"
        old_flags = set(old.split(" | ")) if isinstance(old, str) else set()
        new_flags = set(new.split(" | "))
        if flag in new_flags and flag not in old_flags:
            field = field.replace(" state flags", " fear immunity")
            before = "Not listed" if change["kind"] == "added" else "Off"
            return context, field, before, "On", "Fear immunity added"

    def value(item):
        if item is True:
            return "On"
        if item is False:
            return "Off"
        if isinstance(item, (dict, list)):
            return "Structured data"
        if isinstance(item, str):
            states = {"EHeroDevState_PreRelease": "Pre-release",
                      "EHeroDevState_Release": "Released"}
            if item in states:
                return states[item]
            if item.startswith("E") and "_" in item:
                parts = item.split(" | ")
                if all(re.fullmatch(r"E[A-Za-z]+_[A-Za-z0-9_]+", part) for part in parts):
                    return ", ".join(readable_words(part.split("_", 1)[1]) for part in parts)
            if (item.startswith(("MODIFIER_STATE_", "ability_", "citadel_", "#"))
                    or "/" in item or ".vdata" in item or "_" in item or "." in item):
                return "Game data reference"
            return item
        return fmt(item)

    before = "Not listed" if change["kind"] == "added" else value(old)
    after = "Removed" if change["kind"] == "removed" else value(new)
    note = f"Change {change['delta']:+g}" if "delta" in change else ""
    if note and "percent" in change:
        note += f" · {change['percent']:+.2f}%"
    return context, field, before, after, note


def is_public_change(change: dict) -> bool:
    """Keep readable values in the main view; exact excluded values stay in source details."""
    if "._include[" in change["path"]:
        return False
    _, _, before, after, _ = public_change(change)
    opaque = {"Structured data", "Game data reference"}
    return before not in opaque and after not in opaque


def game_icon_spec(manifest: dict, change: dict) -> tuple[str, str, str] | None:
    """Resolve an ability's own image path from its archived game data."""
    parts = change["path"].split(".")
    record = manifest.get("files", {}).get("abilities")
    if len(parts) < 2 or parts[0] != "abilities" or not record:
        return None
    ability = ability_blob(record["sha256"]).get(parts[1], {})
    image = ability.get("m_strAbilityImage", "") if isinstance(ability, dict) else ""
    match = re.fullmatch(r"file://\{images\}/hud/abilities/([A-Za-z0-9_/-]+)\.psd", image)
    if not match:
        return None
    relative = match.group(1)
    if any(word in relative.lower() for word in ("default", "placeholder", "missing", "generic")):
        return None
    filename = relative.replace("/", "__") + ".webp"
    return filename, ICON_CDN + relative + ".webp", image


def icon_for_change(change: dict, manifest: dict | None = None) -> str | None:
    parts = change["path"].split(".")
    if len(parts) < 2 or parts[0] != "abilities":
        return None
    known = ABILITY_ICONS.get(parts[1])
    spec = game_icon_spec(manifest, change) if manifest else None
    if known and (ROOT / "assets" / "icons" / known).exists() and (
        not manifest or not manifest.get("files", {}).get("abilities") or
        spec and spec[2] == KNOWN_ICON_GAME_PATHS[parts[1]]
    ):
        return known
    return spec[0] if spec and (ROOT / "assets" / "icons" / spec[0]).exists() else None


def ensure_icon_for_change(manifest: dict, change: dict | None) -> None:
    """Cache an exact game icon when possible; icon failures never block a build."""
    if not change or icon_for_change(change, manifest):
        return
    spec = game_icon_spec(manifest, change)
    if not spec:
        return
    filename, url, game_path = spec
    try:
        request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "image/webp"})
        with urlopen(request, timeout=15) as response:
            if not response.headers.get("Content-Type", "").startswith("image/webp"):
                return
            body = response.read(1_000_001)
        if len(body) > 1_000_000 or not body.startswith(b"RIFF") or body[8:12] != b"WEBP":
            return
        folder = ROOT / "assets" / "icons"
        write_atomic(folder / filename, body)
        sources_path = folder / "auto-sources.json"
        sources = json.loads(sources_path.read_text(encoding="utf-8")) if sources_path.exists() else {}
        sources[filename] = {"ability": change["path"].split(".")[1],
                             "game_image": game_path, "source": url,
                             "sha256": hashlib.sha256(body).hexdigest(),
                             "first_seen_build": manifest["build"]}
        write_atomic(sources_path, json_bytes(sources))
    except (HTTPError, URLError, OSError, TimeoutError, ValueError) as exc:
        print(f"Icon unavailable for {change['path']}: {exc}", file=sys.stderr)


def featured_change(manifest: dict, changes: list[dict]) -> dict | None:
    scalar = [change for change in changes if is_public_change(change)]
    illustrated = [change for change in scalar
                   if icon_for_change(change, manifest) or game_icon_spec(manifest, change)]
    return next(iter(illustrated or scalar), None)


def change_card(manifest: dict, prior: dict | None, change: dict | None, total: int) -> str:
    """A single, source-backed change card. Missing icons leave the card text-only."""
    number = manifest["build"]
    stamp = datetime.fromisoformat(manifest["upstream_time"].replace("Z", "+00:00"))
    when = stamp.strftime("%b %d, %Y %H:%M UTC")
    icon = icon_for_change(change, manifest) if change else None
    icon_markup = ""
    if icon:
        binary = (ROOT / "assets" / "icons" / icon).read_bytes()
        encoded = base64.b64encode(binary).decode("ascii")
        icon_markup = (f'<rect x="326" y="22" width="72" height="72" rx="15" fill="#303d4b"/>'
                       f'<image x="335" y="31" width="54" height="54" '
                       f'href="data:image/webp;base64,{encoded}"/>')

    if change:
        context, field, before, after, note = public_change(change)
        main = f"{before} → {after}"
        detail = note or "Before and after from saved game data"
        footer = (f"1 of {total} changes · See the full build report" if total > 1
                  else f"Compared with build {prior['build']}" if prior else "First archived build")
        description = f"Build {number}, {context}, {field}: before {before}; now {after}."
    else:
        context = ("No simple value change" if total else "No tracked change") if prior else "First archived build"
        field = "Game data checked" if not total else f"{total} data changes found"
        main = "See build report" if total else "No values changed" if prior else "Starting point"
        detail = ("The report has the exact before and after data" if total else
                  "Other game files may still have changed" if prior else
                  "There are no earlier values to compare")
        footer = f"Compared with build {prior['build']}" if prior else "Browse the archived build report"
        description = f"Build {number}: {main}."

    def escaped_short(value: str, limit: int) -> str:
        return html.escape(value if len(value) <= limit else value[:limit - 1] + "…")

    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="420" height="260" '
            f'viewBox="0 0 420 260" role="img" aria-label="{html.escape(description, quote=True)}">'
            f'<title>{html.escape(description)}</title>'
            '<style>text{font-family:system-ui,sans-serif}.title{font-size:19px;font-weight:700;fill:#f7f3e9}'
            '.meta{font-size:12px;fill:#bdc6ce}.field{font-size:16px;font-weight:600;fill:#e0e8e9}'
            '.value{font-size:29px;font-weight:750;fill:#80e3d5}.detail{font-size:15px;fill:#f0c686}'
            '.foot{font-size:13px;fill:#bdc6ce}</style>'
            '<rect width="420" height="260" rx="18" fill="#121e2a"/>'
            '<rect x="0" y="0" width="420" height="7" rx="3" fill="#efbe79"/>'
            + icon_markup +
            f'<text x="22" y="43" class="title">{escaped_short(context, 29 if icon else 39)}</text>'
            f'<text x="22" y="66" class="meta">Build {number} · {html.escape(when)}</text>'
            '<line x1="22" x2="398" y1="106" y2="106" stroke="#3a4d5d"/>'
            f'<text x="22" y="137" class="field">{escaped_short(field, 39)}</text>'
            f'<text x="22" y="177" class="value">{escaped_short(main, 25)}</text>'
            f'<text x="22" y="200" class="detail">{escaped_short(detail, 47)}</text>'
            '<line x1="22" x2="398" y1="221" y2="221" stroke="#3a4d5d"/>'
            f'<text x="22" y="244" class="foot">{escaped_short(footer, 55)}</text>'
            '</svg>')


def recent_card(entry: dict) -> str:
    """Render the same single-change card used by per-build graphics."""
    return change_card(entry["manifest"], entry["prior"], entry["change"], 1)


def recent_card_filename(entry: dict) -> str:
    digest = hashlib.sha256(recent_card(entry).encode("utf-8")).hexdigest()[:12]
    return f'{entry["manifest"]["build"]}-{digest}.svg'


def gallery_markup(entries: list[dict], prefix: str) -> str:
    lines = ["## The latest five changes", "",
             "Each card shows one value before and after the update. The date is when SteamTracking recorded that build (UTC). "
             "If a value was added, ‘Not listed’ means the previous saved build had no value for that field.", ""]
    if not entries:
        return "\n".join(lines + ["No comparable changes are saved yet.", ""])
    lines += ["<table>", "<tr>"]
    for entry in entries:
        manifest, change = entry["manifest"], entry["change"]
        build = manifest["build"]
        image_path = f"{prefix}infographics/recent/{recent_card_filename(entry)}"
        context, field, before, after, _ = public_change(change)
        alt = html.escape(f"Build {build}: {context}, {field}, before {before}, now {after}", quote=True)
        lines += ["<td width=\"20%\">",
                  f'<a href="{image_path}"><img src="{image_path}" width="185" alt="{alt}"></a>',
                  "</td>"]
    lines += ["</tr>", "</table>", "", "### What changed, and when", "", "<ol>"]
    for entry in entries:
        manifest, change = entry["manifest"], entry["change"]
        build = manifest["build"]
        stamp = datetime.fromisoformat(manifest["upstream_time"].replace("Z", "+00:00"))
        when = stamp.strftime("%b %d, %Y %H:%M UTC")
        context, field, before, after, note = public_change(change)
        report_path = f"{prefix}builds/{build}.md"
        image_path = f"{prefix}infographics/recent/{recent_card_filename(entry)}"
        line = (f'<li><strong>{html.escape(context)} — {html.escape(field)}</strong><br>'
                f'{html.escape(before)} → <strong>{html.escape(after)}</strong>'
                + (f' ({html.escape(note)})' if note else '')
                + f'<br>Recorded {html.escape(when)} · Build {build} '
                f'(<a href="{image_path}">view card</a>; <a href="{report_path}">all changes</a>)</li>')
        lines.append(line)
    lines += ["</ol>", ""]
    return "\n".join(lines)


def update_recent_gallery():
    """Refresh the README landing gallery and the browsable report index offline."""
    entries = recent_change_entries()
    card_dir = REPORTS / "infographics" / "recent"
    expected = set()
    for entry in entries:
        name = recent_card_filename(entry)
        expected.add(name)
        write_atomic(card_dir / name,
                     recent_card(entry).encode("utf-8"))
    for obsolete in card_dir.glob("*.svg"):
        if obsolete.name not in expected:
            obsolete.unlink()
    write_atomic(REPORTS / "recent-changes.md", gallery_markup(entries, "").encode("utf-8"))

    readme_path = ROOT / "README.md"
    readme = readme_path.read_text(encoding="utf-8")
    start, end = "<!-- RECENT_CHANGES_START -->", "<!-- RECENT_CHANGES_END -->"
    if readme.count(start) != 1 or readme.count(end) != 1:
        raise SourceError("README gallery markers are missing or duplicated")
    before, remainder = readme.split(start, 1)
    _, after = remainder.split(end, 1)
    readme = before + start + "\n" + gallery_markup(entries, "reports/") + end + after
    write_atomic(readme_path, readme.encode("utf-8"))

    all_builds = sorted((int(p.parent.name) for p in BUILDS.glob("*/snapshot.json")), reverse=True)
    index = ["# Deadlock build history", "", "Browse the builds we have archived, newest first. "
             "Dates show when SteamTracking recorded each build (UTC).", "",
             "[See the latest five changes](recent-changes.md) · [Latest report](latest.md) · "
             "[Street Brawl](street-brawl.md)", "",
             "![One change from the latest build](infographics/latest.svg)", "",
             "| Build | Recorded (UTC) | Changes | Report | Card |", "|---:|---|---:|---|---|"]
    for build in all_builds:
        manifest = json.loads((BUILDS / str(build) / "snapshot.json").read_text(encoding="utf-8"))
        prior_builds = [older for older in all_builds if older < build]
        count = "Baseline" if not prior_builds else str(len(diff_manifests(
            json.loads((BUILDS / str(max(prior_builds)) / "snapshot.json").read_text(encoding="utf-8")), manifest)))
        stamp = datetime.fromisoformat(manifest["upstream_time"].replace("Z", "+00:00"))
        index.append(f"| {build} | {stamp.strftime('%b %d, %Y %H:%M')} | {count} | "
                     f"[Read](builds/{build}.md) | [View](infographics/{build}.svg) |")
    index.append("")
    write_atomic(REPORTS / "index.md", "\n".join(index).encode("utf-8"))


def refresh_presentation():
    """Rewrite public pages and graphics from the existing archive, without fetching data."""
    manifests = [json.loads(path.read_text(encoding="utf-8")) for path in
                 sorted(BUILDS.glob("*/snapshot.json"), key=lambda path: int(path.parent.name))]
    for position, manifest in enumerate(manifests):
        prior = manifests[position - 1] if position else None
        changes = diff_manifests(prior, manifest)
        report(manifest, prior, changes, [])
        infographic(manifest, prior, changes)
    if manifests:
        latest = manifests[-1]
        update_summaries(latest, diff_manifests(manifests[-2], latest) if len(manifests) > 1 else [])
    update_recent_gallery()


def run(max_builds: int | None = None):
    available = discover()
    last = latest_manifest()
    for entry in available:
        archived = BUILDS / str(entry["build"]) / "snapshot.json"
        if archived.exists() and json.loads(archived.read_text(encoding="utf-8"))["commit"] != entry["commit"]:
            raise SourceError(f"Upstream rewrote archived build {entry['build']}; investigate before proceeding")
    if last and last["build"] not in {entry["build"] for entry in available} and available[0]["build"] > last["build"]:
        raise SourceError("Known build has fallen outside the fetched history window; increase limit_pages")
    pending = [entry for entry in available if last is None or entry["build"] > last["build"]]
    if max_builds is not None:
        pending = pending[:max_builds]
    if not pending:
        print("No new client build; repository unchanged.")
        return
    for entry in pending:
        number = entry["build"]
        target = BUILDS / str(number) / "snapshot.json"
        if target.exists():
            raise SourceError(f"Refusing to overwrite historical build {number}")
        print(f"Collecting build {number} from {entry['commit'][:12]}", flush=True)
        manifest = collect(entry)
        changes = diff_manifests(last, manifest)
        posts = community(number)
        write_atomic(target, json_bytes(manifest))
        report(manifest, last, changes, posts)
        ensure_icon_for_change(manifest, featured_change(manifest, changes))
        infographic(manifest, last, changes)
        update_summaries(manifest, changes)
        print(f"Archived {number}: {len(changes)} exact data changes", flush=True)
        last = manifest
    for entry in recent_change_entries():
        ensure_icon_for_change(entry["manifest"], entry["change"])
    update_recent_gallery()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-builds", type=int, default=None, help="Bound work for local smoke runs")
    parser.add_argument("--refresh-gallery", action="store_true", help="Rebuild the recent-change gallery from archived data without network access")
    parser.add_argument("--refresh-presentation", action="store_true", help="Rebuild all public reports and graphics from archived data without network access")
    args = parser.parse_args()
    try:
        if args.refresh_presentation:
            refresh_presentation()
        elif args.refresh_gallery:
            update_recent_gallery()
        else:
            run(args.max_builds)
    except SourceError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
