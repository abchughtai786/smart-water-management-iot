#!/usr/bin/env python3
"""Checks that every entity an automation or template uses is defined.

Home Assistant's own config check validates the schema but not whether
`sensor.ohwt_level` actually exists. This script derives the entity IDs
defined in configuration.yaml and fails if anything else is referenced.
It also checks that automation IDs and unique_ids are not duplicated.
"""

import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent


class Loader(yaml.SafeLoader):
    pass


Loader.add_constructor("!secret", lambda loader, node: f"<secret:{node.value}>")
Loader.add_constructor("!include", lambda loader, node: f"<include:{node.value}>")


def load(name):
    return yaml.load((ROOT / name).read_text(encoding="utf-8"), Loader=Loader)


def slug(name):
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def main():
    config = load("configuration.yaml")
    automations = load("automations.yaml")
    defined, unique_ids, errors = set(), [], []

    for domain, items in (config.get("mqtt") or {}).items():
        for item in items:
            defined.add(f"{domain}.{slug(item['name'])}")
            unique_ids.append(item.get("unique_id"))

    for block in config.get("template") or []:
        for domain, items in block.items():
            for item in items:
                defined.add(f"{domain}.{slug(item['name'])}")
                unique_ids.append(item.get("unique_id"))

    for resource in config.get("rest") or []:
        for domain in ("sensor", "binary_sensor"):
            for item in resource.get(domain) or []:
                defined.add(f"{domain}.{slug(item['name'])}")
                unique_ids.append(item.get("unique_id"))

    for name in config.get("rest_command") or {}:
        defined.add(f"rest_command.{name}")
    for group in config.get("notify") or []:
        defined.add(f"notify.{group['name']}")

    text = (ROOT / "configuration.yaml").read_text() + (ROOT / "automations.yaml").read_text()
    used = set(re.findall(r"\b(?:sensor|binary_sensor|switch|notify|rest_command)\.[a-z0-9_]+", text))
    builtin_actions = {"switch.turn_on", "switch.turn_off", "switch.toggle", "notify.send_message"}
    for ref in sorted(used - builtin_actions):
        if ref not in defined:
            errors.append(f"undefined entity referenced: {ref}")

    for label, values in (("unique_id", unique_ids), ("automation id", [a["id"] for a in automations])):
        missing = [v for v in values if not v]
        dupes = sorted({v for v in values if v and values.count(v) > 1})
        if missing:
            errors.append(f"{len(missing)} item(s) without {label}")
        if dupes:
            errors.append(f"duplicate {label}: {', '.join(dupes)}")

    if errors:
        print("\n".join(errors))
        return 1
    print(f"OK: {len(defined)} entities defined, {len(used - builtin_actions)} referenced, {len(automations)} automations")
    return 0


if __name__ == "__main__":
    sys.exit(main())
