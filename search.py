#!/usr/bin/env python3
"""
Search the hanzi etymology database from the command line.

Usage:
    python3 search.py 馬              # Look up a character
    python3 search.py --pinyin ma     # Search by pinyin
    python3 search.py --english horse # Search by English definition
    python3 search.py --radical 馬    # Find characters with this radical
    python3 search.py --phonetic 馬   # Find characters sharing phonetic component
    python3 search.py --conflicts     # Show formation type conflicts
    python3 search.py --unverified    # Show chars needing verification
"""

import argparse
import json
import sqlite3
import sys
from pathlib import Path

DB_PATH = Path(__file__).parent / "output" / "hanzi_etymology.db"


def lookup_character(ch, conn):
    """Look up a single character and display its full etymology."""
    c = conn.cursor()
    c.execute("SELECT data FROM characters WHERE character = ?", (ch,))
    row = c.fetchone()
    if not row:
        print(f"Character '{ch}' not found in database.")
        return

    r = json.loads(row[0])

    # Header
    defs = r.get("definitions", "")
    readings = r.get("readings", {})
    mandarin = readings.get("mandarin", "")
    print(f"\n{'='*60}")
    print(f"  {ch}  {mandarin}  {defs}")
    print(f"{'='*60}")

    # Basic info
    print(f"  Codepoint:    {r.get('codepoint', '')}")
    if r.get("frequency_rank"):
        print(f"  Frequency:    #{r['frequency_rank']}", end="")
        if r.get("hsk_level"):
            print(f"  (HSK {r['hsk_level']})", end="")
        print()
    print(f"  Strokes:      {r.get('total_strokes', '?')}")
    print(f"  Radical:      {r.get('radical_stroke', '')}")
    if r.get("variants"):
        for vtype, vval in r["variants"].items():
            print(f"  {vtype.title()} variant: {vval}")

    # Formation
    ft = r.get("formation_type", "")
    if ft:
        inferred = " (inferred)" if r.get("formation_type_inferred") else ""
        print(f"\n  Formation:    {ft}{inferred}")
        details = r.get("formation_details", {})
        if details.get("semantic"):
            print(f"    Semantic:   {details['semantic']}")
        if details.get("phonetic"):
            inf = " (inferred)" if details.get("inferred") else ""
            print(f"    Phonetic:   {details['phonetic']}{inf}")

    # Verification
    vs = r.get("verification_status", "")
    conf = r.get("confidence", 0)
    if vs:
        print(f"  Verification: {vs} (confidence: {conf})")

    # Conflict
    conflict = r.get("formation_type_conflict")
    if conflict:
        print(f"\n  CONFLICT -- sources disagree on formation type:")
        for src, claim in sorted(conflict.items()):
            print(f"    {src:20s}: {claim}")

    # Decomposition
    ids = r.get("ids", "") or r.get("decomposition_ids", "")
    if ids:
        print(f"\n  IDS decomposition: {ids}")

    # Etymology notes
    notes = r.get("etymology_notes", [])
    if notes:
        print(f"\n  Etymology ({len(notes)} sources):")
        for note in notes:
            src = note.get("source", "?")
            text = note.get("text", "")
            caveat = note.get("caveat", "")
            # Truncate very long texts
            if len(text) > 300:
                text = text[:297] + "..."
            print(f"    [{src}] {text}")
            if caveat:
                print(f"      NOTE: {caveat}")

    # Historical phonology
    phon = r.get("historical_phonology", [])
    if phon:
        print(f"\n  Historical phonology:")
        for p in phon[:5]:
            parts = []
            if p.get("old_chinese"):
                parts.append(f"OC(BS): {p['old_chinese']}")
            if p.get("old_chinese_zhengzhang"):
                parts.append(f"OC(ZZ): {p['old_chinese_zhengzhang']}")
            if p.get("middle_chinese"):
                parts.append(f"MC: {p['middle_chinese']}")
            if p.get("gloss"):
                parts.append(f"\"{p['gloss']}\"")
            print(f"    {', '.join(parts)}")

    # Shuowen
    sw = r.get("shuowen")
    if sw:
        print(f"\n  Shuowen Jiezi: {sw.get('explanation', '')}")
        if sw.get("pronunciation_fanqie"):
            print(f"    Fanqie: {sw['pronunciation_fanqie']}")

    # Guangyun
    gy = r.get("guangyun", [])
    if gy:
        print(f"\n  Guangyun ({len(gy)} readings):")
        for g in gy[:3]:
            print(f"    {g.get('phonological_position', '')}  fanqie: {g.get('fanqie', '')}")

    # Phonetic family
    family = r.get("phonetic_family", [])
    if family:
        print(f"\n  Phonetic family: {''.join(family[:20])}" +
              (f"... ({len(family)} total)" if len(family) > 20 else ""))

    # Historical glyphs
    glyphs = r.get("historical_glyphs", {})
    if glyphs.get("image_count"):
        print(f"\n  Historical glyphs: {glyphs['image_count']} images")
        print(f"    Eras: {', '.join(glyphs.get('eras_available', []))}")

    # Readings
    if readings and len(readings) > 1:
        print(f"\n  Readings:")
        for rtype, rval in readings.items():
            print(f"    {rtype:15s}: {rval}")

    print(f"\n  Sources ({r.get('source_count', 0)}): {', '.join(r.get('sources', []))}")
    print()


def search_by_field(conn, field_desc, sql, params, limit=20):
    """Search and display results."""
    c = conn.cursor()
    c.execute(sql, params)
    rows = c.fetchall()
    if not rows:
        print(f"No results found.")
        return
    print(f"\n{len(rows)} result(s) for {field_desc}:\n")
    for row in rows[:limit]:
        ch, defs, ft, conf = row[0], row[1] or "", row[2] or "", row[3] or 0
        print(f"  {ch}  conf={conf:>3}  {ft:20s}  {defs[:50]}")
    if len(rows) > limit:
        print(f"  ... and {len(rows) - limit} more")
    print()


def main():
    parser = argparse.ArgumentParser(description="Search the hanzi etymology database")
    parser.add_argument("character", nargs="?", help="Character to look up")
    parser.add_argument("--pinyin", "-p", help="Search by pinyin")
    parser.add_argument("--english", "-e", help="Search by English definition")
    parser.add_argument("--radical", "-r", help="Find chars with this radical component")
    parser.add_argument("--phonetic", help="Find chars sharing this phonetic component")
    parser.add_argument("--conflicts", action="store_true", help="Show formation type conflicts")
    parser.add_argument("--unverified", action="store_true", help="Show classical-only entries needing verification")
    parser.add_argument("--stats", action="store_true", help="Show database statistics")
    args = parser.parse_args()

    if not DB_PATH.exists():
        print(f"Database not found at {DB_PATH}")
        print("Run: python3 build_database.py")
        sys.exit(1)

    conn = sqlite3.connect(str(DB_PATH))

    if args.character:
        for ch in args.character:
            lookup_character(ch, conn)
    elif args.pinyin:
        search_by_field(conn, f"pinyin '{args.pinyin}'",
            "SELECT character, definitions, formation_type, confidence FROM characters "
            "WHERE data LIKE ? ORDER BY confidence DESC LIMIT 30",
            (f'%"mandarin": "{args.pinyin}"%',))
    elif args.english:
        search_by_field(conn, f"definition '{args.english}'",
            "SELECT character, definitions, formation_type, confidence FROM characters "
            "WHERE definitions LIKE ? ORDER BY confidence DESC LIMIT 30",
            (f'%{args.english}%',))
    elif args.phonetic:
        search_by_field(conn, f"phonetic component '{args.phonetic}'",
            "SELECT character, definitions, formation_type, confidence FROM characters "
            "WHERE data LIKE ? ORDER BY confidence DESC LIMIT 30",
            (f'%"phonetic": "{args.phonetic}"%',))
    elif args.conflicts:
        search_by_field(conn, "formation type conflicts",
            "SELECT character, definitions, formation_type, confidence FROM characters "
            "WHERE formation_type_conflict IS NOT NULL ORDER BY confidence DESC LIMIT 30",
            (), limit=30)
    elif args.unverified:
        search_by_field(conn, "classical-only entries (need modern verification)",
            "SELECT character, definitions, formation_type, confidence FROM characters "
            "WHERE verification_status = 'classical-only' AND frequency_rank IS NOT NULL "
            "ORDER BY frequency_rank LIMIT 30",
            (), limit=30)
    elif args.stats:
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM characters")
        print(f"\nTotal characters: {c.fetchone()[0]:,}")
        for vs in ["cross-verified", "single-source", "classical-only", "unverified"]:
            c.execute("SELECT COUNT(*) FROM characters WHERE verification_status = ?", (vs,))
            print(f"  {vs}: {c.fetchone()[0]:,}")
        c.execute("SELECT COUNT(*) FROM characters WHERE formation_type_conflict IS NOT NULL")
        print(f"  conflicts: {c.fetchone()[0]:,}")
        print()
    else:
        parser.print_help()

    conn.close()


if __name__ == "__main__":
    main()
