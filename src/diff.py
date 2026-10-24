"""Exact recursive comparisons of normalized game data."""

from __future__ import annotations

from decimal import Decimal


MISSING = object()


def _number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def compare(old, new, path=""):
    changes = []
    if isinstance(old, dict) and isinstance(new, dict):
        for key in sorted(old.keys() | new.keys()):
            child = f"{path}.{key}" if path else str(key)
            changes.extend(compare(old.get(key, MISSING), new.get(key, MISSING), child))
    elif isinstance(old, list) and isinstance(new, list):
        for index in range(max(len(old), len(new))):
            child = f"{path}[{index}]"
            changes.extend(compare(old[index] if index < len(old) else MISSING,
                                   new[index] if index < len(new) else MISSING, child))
    elif old is MISSING or new is MISSING or type(old) is not type(new) or old != new:
        kind = "added" if old is MISSING else "removed" if new is MISSING else "changed"
        change = {"path": path, "kind": kind,
                  "old": None if old is MISSING else old,
                  "new": None if new is MISSING else new}
        if kind == "changed" and _number(old) and _number(new):
            delta = Decimal(str(new)) - Decimal(str(old))
            change["delta"] = float(delta) if isinstance(old, float) or isinstance(new, float) else int(delta)
            if old > 0:
                change["percent"] = float(delta / Decimal(str(old)) * 100)
        changes.append(change)
    return changes


def category(path: str) -> str:
    lower = path.lower()
    if "streetbrawl" in lower or "street_brawl" in lower or "street brawl" in lower:
        return "street-brawl"
    if lower.startswith("heroes."):
        return "heroes"
    if lower.startswith("abilities."):
        return "abilities"
    if lower.startswith("npc_units.") or "map" in lower or "camp" in lower:
        return "map-and-npcs"
    if lower.startswith("modifiers."):
        return "modifiers"
    return "other-data"
