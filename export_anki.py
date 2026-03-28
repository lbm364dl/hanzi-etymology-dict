#!/usr/bin/env python3
"""
Export etymology data as Anki-importable TSV files.

Generates frequency-ordered flashcards with etymology on the back.

Output:
  output/anki/etymology_hsk1.tsv    -- HSK 1 characters
  output/anki/etymology_hsk2.tsv    -- HSK 2 characters
  output/anki/etymology_hsk3.tsv    -- HSK 3 characters
  output/anki/etymology_top500.tsv  -- Top 500 by frequency
  output/anki/etymology_top1000.tsv -- Top 1000 by frequency
  output/anki/etymology_top3000.tsv -- Top 3000 by frequency

Each TSV has columns: character, pinyin, definition, formation_type,
components, etymology, old_chinese, semantic_field

Import into Anki: File > Import, set separator to Tab.
"""

import json
import csv
from pathlib import Path

OUTPUT_DIR = Path("output/anki")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def load_records():
    records = []
    with open("output/hanzi_etymology.jsonl", "r", encoding="utf-8") as f:
        for line in f:
            records.append(json.loads(line))
    return records


def make_card(r):
    """Build an Anki card from a record."""
    readings = r.get("readings", {})
    pinyin = readings.get("mandarin", "")
    defs = r.get("definitions", "")

    # Formation info
    ft = r.get("formation_type", "")
    fd = r.get("formation_details", {})
    components = ""
    if fd.get("semantic") and fd.get("phonetic"):
        components = f"{fd['semantic']} (meaning) + {fd['phonetic']} (sound)"
    elif fd.get("semantic"):
        components = f"{fd['semantic']} (meaning)"

    # Best etymology note (prefer Dong Chinese > Wiktionary > MakeMe > Shuowen)
    etym = ""
    source_priority = {"dong_chinese": 0, "wiktionary": 1, "makemeahanzi": 2, "shuowen_jiezi": 3}
    notes = sorted(r.get("etymology_notes", []),
                   key=lambda n: source_priority.get(n.get("source", ""), 99))
    if notes:
        best = notes[0]
        text = best.get("text", "")
        if len(text) > 300:
            text = text[:297] + "..."
        etym = text

    # Old Chinese
    oc = ""
    for p in r.get("historical_phonology", []):
        if p.get("old_chinese"):
            oc = p["old_chinese"]
            break
        if p.get("old_chinese_zhengzhang"):
            oc = p["old_chinese_zhengzhang"]
            break

    sf = r.get("semantic_field", "")

    return {
        "character": r["character"],
        "pinyin": pinyin,
        "definition": defs,
        "formation_type": ft,
        "components": components,
        "etymology": etym,
        "old_chinese": oc,
        "semantic_field": sf,
    }


def write_tsv(cards, path):
    if not cards:
        return
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(cards[0].keys()), delimiter="\t")
        w.writeheader()
        w.writerows(cards)
    print(f"  {path}: {len(cards)} cards")


def main():
    print("Exporting Anki decks...")
    records = load_records()

    # Frequency-ordered sets
    ranked = sorted(
        [r for r in records if r.get("frequency_rank") and r.get("etymology_notes")],
        key=lambda r: r["frequency_rank"],
    )

    for name, limit in [("top500", 500), ("top1000", 1000), ("top3000", 3000)]:
        cards = [make_card(r) for r in ranked if r["frequency_rank"] <= limit]
        write_tsv(cards, OUTPUT_DIR / f"etymology_{name}.tsv")

    # HSK-level sets (using HSK 3.0 or old HSK)
    for level in range(1, 7):
        hsk_chars = [
            r for r in records
            if (r.get("hsk3_level") == level or r.get("hsk_level") == level)
            and r.get("etymology_notes")
        ]
        hsk_chars.sort(key=lambda r: r.get("frequency_rank") or 999999)
        if hsk_chars:
            cards = [make_card(r) for r in hsk_chars]
            write_tsv(cards, OUTPUT_DIR / f"etymology_hsk{level}.tsv")

    print(f"\nAll decks in {OUTPUT_DIR}/")


if __name__ == "__main__":
    main()
