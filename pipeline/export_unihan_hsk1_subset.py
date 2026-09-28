"""Build a small, licensed Unihan reading extract for the HSK 1 pilot."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
from datetime import date

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "sources/unihan/Unihan_Readings.txt"
OUTPUT = ROOT / "pipeline/data/unihan-kmandarin-hsk1.tsv"
MANIFEST = ROOT / "pipeline/data/unihan-kmandarin-hsk1.json"


def selected_characters():
    progress = json.loads((ROOT / "output/hsk1-progress.json").read_text(encoding="utf-8"))
    selected = {item["character"] for item in progress["entries"]}

    def add_literal(value):
        if isinstance(value, str) and len(value) == 1:
            selected.add(value)

    for path in (ROOT / "content/entries").glob("*.json"):
        article = json.loads(path.read_text(encoding="utf-8"))
        selected.add(article["character"])
        for relationship in article.get("relationships", []):
            if relationship.get("predicate") == "phonetic_element_in":
                add_literal(relationship.get("object", {}).get("id"))
        for component in article.get("components", []):
            if "phonetic" not in component.get("roles", []):
                continue
            add_literal(component["form"])
            add_literal(component.get("scope_character") or article["character"])
            if component.get("origin_form"):
                add_literal(component["origin_form"])
            for pair in component.get("sound", []):
                add_literal(pair["component_form"])
    return selected


def export(source=SOURCE, output=OUTPUT, manifest=MANIFEST):
    source, output, manifest = Path(source), Path(output), Path(manifest)
    lines = source.read_text(encoding="utf-8").splitlines()
    version = next((m.group(1) for line in lines
                    if (m := re.search(r"Unicode Version ([0-9.]+)", line))), "unknown")
    wanted = selected_characters()
    records = {}
    for line in lines:
        if "\tkMandarin\t" not in line:
            continue
        codepoint, prop, reading = line.split("\t", 2)
        try:
            character = chr(int(codepoint[2:], 16))
        except ValueError:
            continue
        if character in wanted:
            records[character] = line
    ordered = [records[ch] for ch in sorted(records, key=ord)]
    data = "\n".join([
        f"# Project-scoped kMandarin extract from Unicode Unihan {version}.",
        "# Scope: HSK 1 canonical characters plus phonetic forms and host scopes in published pilot entries.",
        "# This incomplete extract is for pronunciation cross-checks; absent rows mean no kMandarin value was found.",
        "# Copyright © 2025 Unicode, Inc. Licensed under Unicode License v3; see LICENSE-UNICODE.txt.",
        *ordered,
        "",
    ])
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(data, encoding="utf-8")
    missing = sorted(wanted - records.keys(), key=ord)
    manifest_data = {
        "source": "Unicode Unihan database, Unihan_Readings.txt",
        "source_version": version,
        "source_url": f"https://www.unicode.org/Public/{version}/ucd/Unihan.zip",
        "property": "kMandarin",
        "scope_character_count": len(wanted),
        "included_row_count": len(records),
        "missing_kMandarin_characters": missing,
        "extracted_at": date.today().isoformat(),
        "sha256": hashlib.sha256(data.encode("utf-8")).hexdigest(),
        "license": "Unicode License v3",
    }
    manifest.write_text(json.dumps(manifest_data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest_data


if __name__ == "__main__":
    print(json.dumps(export(), ensure_ascii=False, indent=2))
