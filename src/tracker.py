"""Archive immutable SteamTracking revisions and report exact extracted values."""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
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
    prior_text = f"build {prior['build']}" if prior else "no archived baseline"
    counts = Counter(change["category"] for change in changes)
    lines = [f"# Deadlock build {number}", "",
             f"- Source: [SteamTracking commit]({manifest['source']}) (decompiled game files)",
             f"- Client version: `{number}`; source revision: `{manifest['source_revision']}`",
             f"- Upstream commit time: {manifest['upstream_time']}",
             f"- Compared with: {prior_text}",
             "- Verification: values below are confirmed in extracted VData; gameplay effects require separate interpretation.",
             "- Scope: six tracked VData files. Executable, map geometry, and other files may change independently.", ""]
    if not prior:
        lines += ["This is the first snapshot; there are no old values to compare.", ""]
    elif not changes:
        lines += ["No values changed in the tracked VData files. This does not establish that gameplay code was unchanged.", ""]
    else:
        lines += [f"**{len(changes)} exact data changes** across {sum(value > 0 for value in counts.values())} categories.", ""]
    sections = [("Street Brawl", "street-brawl"), ("Heroes", "heroes"),
                ("Abilities and items", "abilities"), ("Map and NPC data", "map-and-npcs"),
                ("Modifiers", "modifiers"), ("Other data", "other-data")]
    for title, key in sections:
        selected = [change for change in changes if change["category"] == key]
        lines += [f"## {title} ({len(selected)})", ""]
        if not selected:
            lines += ["No confirmed value change in tracked fields.", ""]
            continue
        for change in selected:
            tail = ""
            if "delta" in change:
                tail = f" (Δ {change['delta']:+g}"
                if "percent" in change:
                    tail += f", {change['percent']:+.2f}%"
                tail += ")"
            lines.append(f"- `{change['path']}`: `{fmt(change['old'])}` → `{fmt(change['new'])}`{tail} [{change['kind']}]")
        lines.append("")
    ignored = {"game/citadel/steam.inf", *(f"{SCRIPTS}/{name}.vdata" for name in FILES)}
    other_files = [item for item in manifest.get("changed_files", [])
                   if item["path"] not in ignored and not item["path"].startswith("manifests/")]
    lines += [f"## Other upstream file changes ({len(other_files)})", "",
              "File-level evidence only. Gameplay effects are unknown unless a tracked value above confirms them.", ""]
    lines += [f"- `{item['status']}` `{item['path']}`" for item in other_files[:40]] or ["None listed in the upstream commit."]
    if len(other_files) > 40:
        lines.append(f"- … and {len(other_files) - 40} more; see the upstream commit.")
    lines.append("")
    lines += ["## Community discussion", ""]
    lines += [f"- [{post['title']}]({post['url']}) (unverified community discussion)" for post in posts] or ["No exact-build discussion retrieved."]
    lines += ["", "## Data and provenance", ""]
    for name, file in manifest["files"].items():
        lines.append(f"- `{name}.vdata`: [upstream file]({file['url']}), normalized SHA-256 `{file['sha256']}`")
    lines += ["", "The normalized snapshots are stored in `data/blobs/` and indexed by `data/builds/<build>/snapshot.json`.", ""]
    write_atomic(REPORTS / "builds" / f"{number}.md", "\n".join(lines).encode("utf-8"))
    return counts


def infographic(manifest: dict, prior: dict | None, changes: list[dict]):
    number = manifest["build"]
    counts = Counter(change["category"] for change in changes)
    labels = [("Street Brawl", "street-brawl"), ("Heroes", "heroes"),
              ("Abilities / items", "abilities"), ("Map / NPCs", "map-and-npcs"),
              ("Modifiers", "modifiers"), ("Other", "other-data")]
    maximum = max([counts[key] for _, key in labels] + [1])
    bars = []
    for index, (label, key) in enumerate(labels):
        y = 178 + index * 48
        width = round(450 * counts[key] / maximum)
        bars.append(f'<text x="38" y="{y}" class="label">{label}</text>'
                    f'<rect x="220" y="{y-19}" width="450" height="23" rx="4" fill="#243341"/>'
                    f'<rect x="220" y="{y-19}" width="{width}" height="23" rx="4" fill="{ "#ffbe68" if key == "street-brawl" else "#73d9d1" }"/>'
                    f'<text x="690" y="{y}" class="count">{counts[key]}</text>')
    old = prior["build"] if prior else "baseline"
    note = "Exact VData field changes; no gameplay effect inferred."
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="760" height="520" viewBox="0 0 760 520" role="img" '
           f'aria-label="Deadlock build {number} change summary"><style>'
           '.title{font:700 36px system-ui;fill:#f2f5ef}.sub{font:17px system-ui;fill:#b9cad0}'
           '.label{font:17px system-ui;fill:#eff2ec}.count{font:700 18px system-ui;fill:#eff2ec}'
           '.foot{font:14px system-ui;fill:#aabdc4}</style>'
           '<rect width="760" height="520" fill="#111b26"/>'
           '<rect x="0" width="760" height="8" fill="#ffbe68"/>'
           f'<text x="38" y="67" class="title">BUILD {number}</text>'
           f'<text x="38" y="101" class="sub">vs {old} · {len(changes)} confirmed data changes</text>'
           '<line x1="38" x2="722" y1="125" y2="125" stroke="#41515d"/>'
           + "".join(bars) +
           f'<text x="38" y="490" class="foot">{html.escape(note)}</text></svg>')
    write_atomic(REPORTS / "infographics" / f"{number}.svg", svg.encode("utf-8"))


def update_summaries(manifest: dict, changes: list[dict]):
    number = manifest["build"]
    path = REPORTS / "builds" / f"{number}.md"
    write_atomic(REPORTS / "latest.md", path.read_bytes())
    write_atomic(REPORTS / "infographics" / "latest.svg",
                 (REPORTS / "infographics" / f"{number}.svg").read_bytes())
    brawl = [change for change in changes if change["category"] == "street-brawl"]
    lines = ["# Street Brawl tracker", "", f"Latest archived build: [{number}](builds/{number}.md).", ""]
    if brawl:
        lines += ["## Latest confirmed changes", ""]
        for change in brawl:
            lines.append(f"- `{change['path']}`: `{fmt(change['old'])}` → `{fmt(change['new'])}`")
    else:
        lines.append("No Street Brawl field change in the latest comparison.")
    lines += ["", "[Browse all build reports](builds/) · [Latest infographic](infographics/" + str(number) + ".svg)", ""]
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
                  and "._include[" not in change["path"])
        for change in sorted(scalar, key=lambda item: item["path"]):
            entries.append({"manifest": manifest, "prior": prior, "change": change})
            if len(entries) == limit:
                return entries
    return entries


def recent_card(entry: dict) -> str:
    """Render one source-backed field change as a compact data-only SVG."""
    manifest, prior, change = entry["manifest"], entry["prior"], entry["change"]
    stamp = datetime.fromisoformat(manifest["upstream_time"].replace("Z", "+00:00"))
    when = stamp.strftime("%b %d, %Y %H:%M UTC")
    field = change["path"].split(".")[-1]

    def short(value, width=31):
        rendered = fmt(value)
        return html.escape(rendered if len(rendered) <= width else rendered[:width - 1] + "…")

    path_label = html.escape(field if len(field) <= 37 else field[:36] + "…")
    old, new = short(change["old"]), short(change["new"])
    description = html.escape(f'Build {manifest["build"]}: {change["path"]}, '
                              f'{fmt(change["old"])} to {fmt(change["new"])} ({change["kind"]})')
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="340" height="238" viewBox="0 0 340 238" '
            f'role="img" aria-label="{description}"><title>{description}</title>'
            '<style>text{font-family:system-ui,sans-serif}.title{font-size:26px;font-weight:700;fill:#f2f5ef}'
            '.meta{font-size:13px;fill:#b9cad0}.field{font-size:15px;font-weight:600;fill:#eff2ec}'
            '.value{font-size:17px;fill:#73d9d1}.foot{font-size:12px;fill:#b9cad0}</style>'
            '<rect width="340" height="238" rx="12" fill="#111b26"/>'
            '<rect width="340" height="6" fill="#ffbe68"/>'
            f'<text x="20" y="44" class="title">BUILD {manifest["build"]}</text>'
            f'<text x="20" y="68" class="meta">vs {prior["build"]} · {html.escape(change["kind"])}</text>'
            '<line x1="20" x2="320" y1="82" y2="82" stroke="#41515d"/>'
            f'<text x="20" y="108" class="field">{path_label}</text>'
            f'<text x="20" y="139" class="meta">FROM  {old}</text>'
            f'<text x="20" y="169" class="value">TO  {new}</text>'
            '<line x1="20" x2="320" y1="187" y2="187" stroke="#41515d"/>'
            f'<text x="20" y="213" class="foot">{html.escape(when)} · upstream commit</text>'
            '</svg>')


def gallery_markup(entries: list[dict], prefix: str) -> str:
    lines = ["## Latest verified field changes", "",
             "Five most recent scalar changes in tracked VData. Times are upstream commit timestamps in UTC; "
             "changes within one build share a timestamp and are ordered by field path. "
             "Each build report contains its full set of changes.", ""]
    if not entries:
        return "\n".join(lines + ["No comparable field changes are archived yet.", ""])
    lines += ["<table>", "<tr>"]
    for entry in entries:
        manifest, change = entry["manifest"], entry["change"]
        build = manifest["build"]
        stamp = datetime.fromisoformat(manifest["upstream_time"].replace("Z", "+00:00"))
        when = stamp.strftime("%b %d, %Y %H:%M UTC")
        card = hashlib.sha256(change["path"].encode("utf-8")).hexdigest()[:12]
        image_path = f"{prefix}infographics/recent/{build}-{card}.svg"
        report_path = f"{prefix}builds/{build}.md"
        path = html.escape(change["path"])
        old, new = html.escape(fmt(change["old"])), html.escape(fmt(change["new"]))
        lines += ["<td width=\"20%\" valign=\"top\">",
                  f'<a href="{report_path}"><img src="{image_path}" width="220" alt="Build {build}: {path}, {old} to {new}"></a><br>',
                  f'<strong><a href="{report_path}">Build {build}</a></strong><br>',
                  f'<small>{html.escape(when)} · <a href="{html.escape(manifest["source"], quote=True)}">upstream commit</a></small><br>',
                  f'<code>{path}</code><br>',
                  f'<code>{old}</code> → <code>{new}</code> ({html.escape(change["kind"])})',
                  "</td>"]
    lines += ["</tr>", "</table>", ""]
    return "\n".join(lines)


def update_recent_gallery():
    """Refresh the README landing gallery and the browsable report index offline."""
    entries = recent_change_entries()
    for entry in entries:
        build, change = entry["manifest"]["build"], entry["change"]
        card = hashlib.sha256(change["path"].encode("utf-8")).hexdigest()[:12]
        write_atomic(REPORTS / "infographics" / "recent" / f"{build}-{card}.svg",
                     recent_card(entry).encode("utf-8"))
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
    index = ["# Deadlock build history", "", "Generated from archived SteamTracking VData snapshots.", "",
             "[View the latest five field changes](recent-changes.md) · [Latest report](latest.md) · "
             "[Street Brawl](street-brawl.md)", "",
             "![Latest build changes](infographics/latest.svg)", "",
             "| Build | Report | Infographic |", "|---:|---|---|"]
    for build in all_builds:
        index.append(f"| {build} | [Exact changes](builds/{build}.md) | [View](infographics/{build}.svg) |")
    index.append("")
    write_atomic(REPORTS / "index.md", "\n".join(index).encode("utf-8"))


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
        infographic(manifest, last, changes)
        update_summaries(manifest, changes)
        print(f"Archived {number}: {len(changes)} exact data changes", flush=True)
        last = manifest
    update_recent_gallery()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-builds", type=int, default=None, help="Bound work for local smoke runs")
    parser.add_argument("--refresh-gallery", action="store_true", help="Rebuild the recent-change gallery from archived data without network access")
    args = parser.parse_args()
    try:
        if args.refresh_gallery:
            update_recent_gallery()
        else:
            run(args.max_builds)
    except SourceError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
