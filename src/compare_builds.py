"""Compare any two archived client builds without fetching current data."""

import argparse
import json
from pathlib import Path
import sys

from tracker import BUILDS, diff_manifests, fmt


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("old", type=int)
    parser.add_argument("new", type=int)
    parser.add_argument("--json", action="store_true", help="Emit machine-readable changes")
    args = parser.parse_args()
    if args.old == args.new:
        parser.error("Choose two different builds")
    manifests = []
    for number in (args.old, args.new):
        path = BUILDS / str(number) / "snapshot.json"
        if not path.exists():
            parser.error(f"Build {number} is not archived")
        manifests.append(json.loads(path.read_text(encoding="utf-8")))
    changes = diff_manifests(*manifests)
    if args.json:
        print(json.dumps({"old_build": args.old, "new_build": args.new, "changes": changes},
                         ensure_ascii=False, indent=2))
    else:
        print(f"# Build {args.old} → {args.new}\n")
        print(f"{len(changes)} exact changes in tracked VData.\n")
        for change in changes:
            delta = f" (Δ {change['delta']:+g})" if "delta" in change else ""
            print(f"- [{change['category']}] `{change['path']}`: `{fmt(change['old'])}` → `{fmt(change['new'])}`{delta}")


if __name__ == "__main__":
    main()
