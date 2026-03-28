#!/usr/bin/env python3
"""
Export characters needing expert review as CSV files.

Generates:
  output/review/formation_conflicts.csv   -- Sources disagree on formation type
  output/review/shuowen_corrections.csv   -- Shuowen errors flagged by modern sources
  output/review/shuowen_phonetic_failures.csv -- Shuowen phonetic claims failing OC test
  output/review/classical_only.csv        -- Shuowen-only entries needing modern corroboration
"""

import csv
import json
from pathlib import Path

OUTPUT_DIR = Path("output/review")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = Path("output/hanzi_etymology.jsonl")


def load_records():
    records = []
    with open(DB_PATH, "r", encoding="utf-8") as f:
        for line in f:
            records.append(json.loads(line))
    return records


def export_formation_conflicts(records):
    path = OUTPUT_DIR / "formation_conflicts.csv"
    rows = []
    for r in records:
        conflict = r.get("formation_type_conflict")
        if not conflict:
            continue
        row = {
            "character": r["character"],
            "codepoint": r["codepoint"],
            "frequency_rank": r.get("frequency_rank", ""),
            "consensus": r.get("formation_type", ""),
            "definitions": (r.get("definitions") or "")[:60],
        }
        for src in ["makemeahanzi", "dong_chinese", "shuowen_jiezi", "wiktionary"]:
            row[src] = conflict.get(src, "")
        rows.append(row)

    rows.sort(key=lambda x: x.get("frequency_rank") or 999999)
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else [])
        w.writeheader()
        w.writerows(rows)
    print(f"  {path}: {len(rows)} conflicts")


def export_shuowen_corrections(records):
    path = OUTPUT_DIR / "shuowen_corrections.csv"
    rows = []
    for r in records:
        if r.get("shuowen_accuracy") != "corrected":
            continue
        mc = r.get("shuowen", {}).get("modern_correction", {})
        rows.append({
            "character": r["character"],
            "codepoint": r["codepoint"],
            "frequency_rank": r.get("frequency_rank", ""),
            "definitions": (r.get("definitions") or "")[:60],
            "shuowen_says": mc.get("shuowen_says", ""),
            "modern_says": mc.get("modern_says", ""),
            "shuowen_text": r.get("shuowen", {}).get("explanation", "")[:80],
        })

    rows.sort(key=lambda x: x.get("frequency_rank") or 999999)
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else [])
        w.writeheader()
        w.writerows(rows)
    print(f"  {path}: {len(rows)} corrections")


def export_shuowen_phonetic_failures(records):
    path = OUTPUT_DIR / "shuowen_phonetic_failures.csv"
    rows = []
    for r in records:
        if r.get("shuowen_phonetic_validated") is not False:
            continue
        phon = r.get("formation_details", {}).get("phonetic_component_ytenx", "")
        char_rhymes = set(
            p.get("rhyme_group", "") for p in r.get("historical_phonology", [])
            if p.get("rhyme_group")
        )
        rows.append({
            "character": r["character"],
            "codepoint": r["codepoint"],
            "frequency_rank": r.get("frequency_rank", ""),
            "definitions": (r.get("definitions") or "")[:60],
            "claimed_phonetic": phon,
            "character_rhymes": ",".join(sorted(char_rhymes)),
            "shuowen_text": r.get("shuowen", {}).get("explanation", "")[:80],
        })

    rows.sort(key=lambda x: x.get("frequency_rank") or 999999)
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else [])
        w.writeheader()
        w.writerows(rows)
    print(f"  {path}: {len(rows)} phonetic failures")


def export_classical_only(records):
    path = OUTPUT_DIR / "classical_only.csv"
    rows = []
    for r in records:
        if r.get("verification_status") != "classical-only":
            continue
        rows.append({
            "character": r["character"],
            "codepoint": r["codepoint"],
            "frequency_rank": r.get("frequency_rank", ""),
            "definitions": (r.get("definitions") or "")[:60],
            "formation_type": r.get("formation_type", ""),
            "shuowen_text": r.get("shuowen", {}).get("explanation", "")[:80],
            "has_oc": "Y" if r.get("historical_phonology") else "N",
            "shuowen_phonetic_ok": {True: "Y", False: "N"}.get(
                r.get("shuowen_phonetic_validated"), "?"),
        })

    rows.sort(key=lambda x: x.get("frequency_rank") or 999999)
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else [])
        w.writeheader()
        w.writerows(rows)
    print(f"  {path}: {len(rows)} classical-only entries")


def main():
    print("Exporting review CSVs...")
    records = load_records()
    export_formation_conflicts(records)
    export_shuowen_corrections(records)
    export_shuowen_phonetic_failures(records)
    export_classical_only(records)
    print(f"\nAll files in {OUTPUT_DIR}/")


if __name__ == "__main__":
    main()
