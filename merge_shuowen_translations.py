#!/usr/bin/env python3
"""Merge Shuowen translation batches into a single file."""

import json
from pathlib import Path

def main():
    merged = {}
    for i in range(5):
        fpath = Path(f"output/shuowen_translated_{i}.json")
        if fpath.exists():
            with open(fpath, "r", encoding="utf-8") as f:
                batch = json.load(f)
            merged.update(batch)
            print(f"  Batch {i}: {len(batch)} entries")
        else:
            print(f"  Batch {i}: NOT FOUND")

    print(f"\n  Total merged: {len(merged)} entries")

    with open("output/shuowen_translations.json", "w", encoding="utf-8") as f:
        json.dump(merged, ensure_ascii=False, fp=f)

    print("  Written to output/shuowen_translations.json")

    # Show samples
    for ch in ["一", "人", "水", "好", "馬", "河", "明", "愛", "龍", "的"]:
        if ch in merged:
            print(f"\n  {ch}: {merged[ch]}")

if __name__ == "__main__":
    main()
