"""Build auditable evidence packets from the local source aggregation.

These are excerpts of imported records, not newly verified primary evidence.
Algorithmic classifications are deliberately kept out of the evidence list.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PILOT = "木本休明好信東來馬水河清青字安武我国働峠"


def prepare(characters: str = PILOT, root: Path = ROOT) -> list[Path]:
    wanted = set(characters)
    records: dict[str, dict] = {}
    japanese: dict[str, dict] = {}
    for name, target in [("hanzi", records), ("kanji", japanese)]:
        path = root / "output" / f"{name}_etymology.jsonl"
        if not path.exists():
            if name == "hanzi":
                raise FileNotFoundError(path)
            continue
        with path.open(encoding="utf-8") as stream:
            for line in stream:
                record = json.loads(line)
                # Related traditional forms retain their own identity in evidence.
                if record["character"] in wanted | {"國", "人", "動", "山", "上", "下"}:
                    target[record["character"]] = record
    # Include traditional counterparts from the source mapping, not just the original pilot cases.
    related = {}
    for char in dict.fromkeys(characters):
        value = records.get(char, {}).get("variants", {}).get("traditional", "")
        forms = []
        if isinstance(value, str):
            codes = re.findall(r"U\+([0-9A-Fa-f]{4,6})", value)
            forms = [chr(int(code, 16)) for code in codes if int(code, 16) <= 0x10FFFF]
            if not codes:
                forms = [c for c in value if "\u3400" <= c <= "\u9fff" or "\U00020000" <= c <= "\U000323af"]
        related[char] = list(dict.fromkeys(c for c in forms if c != char))
    needed = {c for forms in related.values() for c in forms}
    for name, target in [("hanzi", records), ("kanji", japanese)]:
        missing = needed - target.keys()
        path = root / "output" / f"{name}_etymology.jsonl"
        if missing and path.exists():
            with path.open(encoding="utf-8") as stream:
                for line in stream:
                    record = json.loads(line)
                    if record["character"] in missing:
                        target[record["character"]] = record
                        missing.remove(record["character"])
                        if not missing:
                            break
    out = root / "content" / "dossiers"
    out.mkdir(parents=True, exist_ok=True)
    paths = []
    for char in dict.fromkeys(characters):
        if char not in records and char not in japanese:
            raise ValueError(f"No local record for {char}")
        evidence = []

        def add(source, field, value, owner, kind="imported_excerpt"):
            if not value:
                return
            text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, sort_keys=True)
            evidence.append(dict(id=f"E{len(evidence)+1}", source=source,
                                 field=field, text=text, record_character=owner, kind=kind))

        owners = list(dict.fromkeys([char, *related[char], *({"国": ["國"], "働": ["人", "動"], "峠": ["山", "上", "下"]}.get(char, []))]))
        for owner in owners:
            record = records.get(owner, {})
            for i, note in enumerate(record.get("etymology_notes", [])):
                add(note["source"], f"hanzi.etymology_notes[{i}]", note["text"], note.get("via_traditional") or owner)
            add("shuowen_jiezi", "hanzi.shuowen.explanation", record.get("shuowen", {}).get("explanation"), owner)
            add("merged_record", "hanzi.definitions", record.get("definitions"), owner, "imported_metadata")
            add("merged_record", "hanzi.readings", record.get("readings"), owner, "imported_metadata")
            add("merged_record", "hanzi.historical_phonology", record.get("historical_phonology"), owner, "imported_metadata")
            ja = japanese.get(owner, {})
            add("kanjidic2_via_build_kanji", "kanji.definition", ja.get("definition"), owner, "imported_metadata")
            add("kanjidic2_via_build_kanji", "kanji.readings", {k:v for k,v in ja.get("readings", {}).items() if k.startswith("japanese")}, owner, "imported_metadata")
            for i, note in enumerate(ja.get("etymology_notes", [])):
                if note.get("source") == "ids_analysis":
                    add("ids_analysis", f"kanji.etymology_notes[{i}]", note["text"], owner)
        context = {
            "provenance": "Base evidence consists of imported local JSONL excerpts. Source names identify upstream datasets; extraction may lose sense and language boundaries. Further external evidence and research activity are documented separately in the dossier.",
            "editorial_rules": [
                "Write about the character's graphic history; distinguish it from the history of a spoken word.",
                "Separate historical explanation from mnemonics. Do not infer history from modern shapes or readings.",
                "Sources may repeat one another. A source count is not independent corroboration.",
                "Treat Shuowen as a historical account, not automatic confirmation. Its generated English glosses are excluded.",
                "Unrelated word senses may appear in Wiktionary excerpts. Do not merge them into a character origin.",
                "Related-character evidence retains its record_character. Do not silently transfer a traditional form's components to a simplified form.",
                "No glyph image has been visually inspected in this packet. Do not claim to have inspected one.",
                "Explain missing evidence explicitly, especially for Japanese-created characters. A Chinese spelling pronunciation is not evidence for a Japanese origin.",
            ],
            "unverified_pipeline_metadata": {
                k: records.get(char, {}).get(k) for k in ("formation_type", "formation_type_conflict", "formation_details", "variants")
            },
        }
        path = out / f"{ord(char):04X}.json"
        existing = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        external = [item for item in existing.get("evidence", [])
                    if item.get("url") or item.get("id", "").startswith("X-")]
        ids = {item["id"] for item in evidence}
        if any(item["id"] in ids for item in external):
            raise ValueError(f"Research evidence ID collides with imported evidence for {char}")
        evidence.extend(external)
        packet = {**existing, "character": char, "evidence": evidence, "context": context}
        path.write_text(json.dumps(packet, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        paths.append(path)
    return paths


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--characters", default=PILOT)
    args = parser.parse_args()
    for path in prepare(args.characters):
        print(path)
