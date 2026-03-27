#!/usr/bin/env python3
"""
Quality analysis of the Hanzi Etymology Database.

Identifies formation type conflicts between sources, missing data gaps,
confidence scoring, and suspicious entries to improve scholarly rigor.
"""

import json
import re
import sys
from collections import defaultdict, Counter
from pathlib import Path

INPUT_PATH = Path("/home/catalin/hanzi-etymology-dict/output/hanzi_etymology.jsonl")
OUTPUT_PATH = Path("/home/catalin/hanzi-etymology-dict/output/quality_report.json")

# CJK Unified Ideographs basic block
CJK_BASIC_START = 0x4E00
CJK_BASIC_END = 0x9FFF


def load_entries():
    """Load all entries from the JSONL file."""
    entries = {}
    with open(INPUT_PATH, "r", encoding="utf-8") as f:
        for line in f:
            entry = json.loads(line.strip())
            char = entry.get("character", "")
            entries[char] = entry
    return entries


def normalize_formation_type(ft):
    """Normalize formation type labels to a canonical form for comparison.

    The database uses 'phono-semantic', extractors may return 'pictophonetic'.
    We normalize to canonical labels: 'phono-semantic', 'pictographic',
    'ideographic', 'phonetic_loan', 'other'.
    """
    if not ft:
        return ft
    ft = ft.lower().strip()
    # Map all phono-semantic variants to one canonical form
    if ft in ("pictophonetic", "phono-semantic", "phonosemantic"):
        return "phono-semantic"
    # Indicative is a subtype of ideographic in most modern classifications
    if ft == "indicative":
        return "ideographic"
    # Normalize phonetic loan variants
    if ft in ("phonetic_loan", "phonetic-loan"):
        return "phonetic_loan"
    # Already canonical
    if ft in ("pictographic", "ideographic", "other"):
        return ft
    return ft


def is_cjk_basic(char):
    """Check if character is in the CJK Unified Ideographs basic block."""
    if len(char) != 1:
        return False
    cp = ord(char)
    return CJK_BASIC_START <= cp <= CJK_BASIC_END


def get_etymology_note_by_source(entry, source_name):
    """Extract etymology note text for a given source."""
    notes = entry.get("etymology_notes", [])
    if not isinstance(notes, list):
        return ""
    for note in notes:
        if isinstance(note, dict) and note.get("source") == source_name:
            return note.get("text", "")
    return ""


# ---------------------------------------------------------------------------
# 1. Formation type conflicts: Make Me a Hanzi vs Dong Chinese
# ---------------------------------------------------------------------------

def extract_dong_formation_type(dong_text):
    """Parse Dong Chinese text to determine what formation type it claims."""
    if not dong_text:
        return None
    text_lower = dong_text.lower()

    # Order matters: check more specific patterns first
    if "phonosemantic compound" in text_lower or "phono-semantic compound" in text_lower:
        return "pictophonetic"
    if "pictograph" in text_lower and "phonosemantic" not in text_lower:
        return "pictographic"
    if "ideographic compound" in text_lower or "ideogrammic compound" in text_lower:
        return "ideographic"
    if "phonetic loan" in text_lower:
        return "phonetic_loan"
    if "indicative" in text_lower or "ideograph" in text_lower:
        return "ideographic"

    return None


def find_mmah_dong_conflicts(entries):
    """Find characters where Make Me a Hanzi and Dong Chinese disagree on formation type."""
    conflicts = []
    for char, entry in entries.items():
        mmah_type = entry.get("formation_type", "")
        dong_text = get_etymology_note_by_source(entry, "dong_chinese")
        dong_type = extract_dong_formation_type(dong_text)

        if not mmah_type or not dong_type:
            continue

        mmah_norm = normalize_formation_type(mmah_type)
        dong_norm = normalize_formation_type(dong_type)

        if mmah_norm != dong_norm:
            mmah_text = get_etymology_note_by_source(entry, "makemeahanzi")
            conflicts.append({
                "character": char,
                "codepoint": entry.get("codepoint", ""),
                "makemeahanzi_formation_type": mmah_type,
                "dong_chinese_formation_type": dong_type,
                "makemeahanzi_normalized": mmah_norm,
                "dong_chinese_normalized": dong_norm,
                "makemeahanzi_note": mmah_text[:300] if mmah_text else "",
                "dong_chinese_note": dong_text[:300] if dong_text else "",
                "formation_details": entry.get("formation_details", {}),
            })

    # Sort by codepoint for stable output
    conflicts.sort(key=lambda x: x.get("codepoint", ""))
    return conflicts


# ---------------------------------------------------------------------------
# 2. Wiktionary formation type extraction and comparison
# ---------------------------------------------------------------------------

WIKTIONARY_PATTERNS = {
    "pictographic": [
        r"[Pp]ictogram\b",
        r"象形",
    ],
    "ideographic": [
        r"[Ii]deogrammic\s+compound",
        r"[Ii]deographic\s+compound",
        r"會意",
        r"会意",
    ],
    "pictophonetic": [
        r"[Pp]hono-semantic\s+compound",
        r"形聲",
        r"形声",
    ],
    "phonetic_loan": [
        r"[Pp]honetic\s+loan",
        r"假借",
    ],
    "indicative": [
        r"[Ii]ndicative",
        r"指事",
    ],
}


def extract_wiktionary_formation_type(wiki_text):
    """Parse Wiktionary etymology text to extract formation type."""
    if not wiki_text:
        return None
    for ftype, patterns in WIKTIONARY_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, wiki_text):
                return ftype
    return None


def find_wiktionary_conflicts(entries):
    """Compare Wiktionary formation types against MMAH/Dong classifications."""
    conflicts = []
    agreement_count = 0
    wikt_extracted_count = 0

    for char, entry in entries.items():
        wiki_text = get_etymology_note_by_source(entry, "wiktionary")
        wiki_type = extract_wiktionary_formation_type(wiki_text)
        if not wiki_type:
            continue
        wikt_extracted_count += 1

        mmah_type = entry.get("formation_type", "")
        dong_text = get_etymology_note_by_source(entry, "dong_chinese")
        dong_type = extract_dong_formation_type(dong_text)

        wiki_norm = normalize_formation_type(wiki_type)
        mmah_norm = normalize_formation_type(mmah_type) if mmah_type else None
        dong_norm = normalize_formation_type(dong_type) if dong_type else None

        has_conflict = False
        conflict_entry = {
            "character": char,
            "codepoint": entry.get("codepoint", ""),
            "wiktionary_formation_type": wiki_type,
            "wiktionary_normalized": wiki_norm,
            "wiktionary_text": wiki_text[:300],
            "conflicts_with": [],
        }

        if mmah_norm and mmah_norm != wiki_norm:
            has_conflict = True
            conflict_entry["makemeahanzi_formation_type"] = mmah_type
            conflict_entry["conflicts_with"].append("makemeahanzi")

        if dong_norm and dong_norm != wiki_norm:
            has_conflict = True
            conflict_entry["dong_chinese_formation_type"] = dong_type
            conflict_entry["conflicts_with"].append("dong_chinese")

        if has_conflict:
            conflicts.append(conflict_entry)
        elif mmah_norm or dong_norm:
            agreement_count += 1

    conflicts.sort(key=lambda x: x.get("codepoint", ""))
    return {
        "total_wiktionary_formation_types_extracted": wikt_extracted_count,
        "agreements_with_other_sources": agreement_count,
        "conflicts": conflicts,
    }


# ---------------------------------------------------------------------------
# 3. Shuowen vs modern analysis conflicts
# ---------------------------------------------------------------------------

def extract_shuowen_formation_type(entry):
    """Determine formation type from Shuowen explanation text."""
    sw = entry.get("shuowen", {})
    if not isinstance(sw, dict):
        return None
    expl = sw.get("explanation", "")
    if not expl:
        return None

    # Check for explicit 象形
    if "象形" in expl:
        return "pictographic"

    # Check for phono-semantic: 从X Y聲 pattern
    if "聲" in expl and "从" in expl:
        return "pictophonetic"

    # Check for 指事
    if "指事" in expl:
        return "indicative"

    # Check for ideographic compound: 从X从Y without 聲
    if re.search(r"从.+从", expl) and "聲" not in expl:
        return "ideographic"

    # Also check Duan Yucai's notes for explicit categorization
    for dn in sw.get("duan_notes", []):
        if not isinstance(dn, dict):
            continue
        note_text = dn.get("note", "")
        if "象形" in note_text and ("非象形" not in note_text):
            # Only if main explanation didn't already give us something
            return "pictographic"
        if "形聲" in note_text:
            return "pictophonetic"
        if "會意" in note_text:
            return "ideographic"
        if "指事" in note_text:
            return "indicative"

    return None


def find_shuowen_modern_conflicts(entries):
    """Find characters where Shuowen and modern scholarship disagree."""
    conflicts = []

    for char, entry in entries.items():
        sw_type = extract_shuowen_formation_type(entry)
        modern_type = entry.get("formation_type", "")
        dong_text = get_etymology_note_by_source(entry, "dong_chinese")
        dong_type = extract_dong_formation_type(dong_text)

        if not sw_type:
            continue

        sw_norm = normalize_formation_type(sw_type)

        # Compare against modern sources
        modern_sources_disagree = []
        if modern_type and normalize_formation_type(modern_type) != sw_norm:
            modern_sources_disagree.append({
                "source": "makemeahanzi",
                "formation_type": modern_type,
            })
        if dong_type and normalize_formation_type(dong_type) != sw_norm:
            modern_sources_disagree.append({
                "source": "dong_chinese",
                "formation_type": dong_type,
            })

        if modern_sources_disagree:
            sw = entry.get("shuowen", {})
            conflicts.append({
                "character": char,
                "codepoint": entry.get("codepoint", ""),
                "shuowen_formation_type": sw_type,
                "shuowen_normalized": sw_norm,
                "shuowen_explanation": sw.get("explanation", "")[:200] if isinstance(sw, dict) else "",
                "modern_disagreements": modern_sources_disagree,
                "formation_details": entry.get("formation_details", {}),
            })

    conflicts.sort(key=lambda x: x.get("codepoint", ""))
    return conflicts


# ---------------------------------------------------------------------------
# 4. Missing data gaps (CJK basic block)
# ---------------------------------------------------------------------------

def find_missing_data_gaps(entries):
    """Identify missing data for CJK basic block characters."""
    cjk_chars = {}
    for char, entry in entries.items():
        if is_cjk_basic(char):
            cjk_chars[char] = entry

    # Also find CJK basic block chars not in the database at all
    all_cjk_in_db = set(cjk_chars.keys())
    total_possible = CJK_BASIC_END - CJK_BASIC_START + 1

    missing_etymology_notes = []
    missing_formation_type = []
    missing_phonology = []
    missing_component_analysis = []

    for char, entry in cjk_chars.items():
        cp = entry.get("codepoint", "")

        # Missing etymology notes entirely
        notes = entry.get("etymology_notes", [])
        if not notes or not isinstance(notes, list) or len(notes) == 0:
            missing_etymology_notes.append({"character": char, "codepoint": cp})

        # Missing formation type
        if not entry.get("formation_type"):
            missing_formation_type.append({"character": char, "codepoint": cp})

        # Missing historical phonology (Baxter-Sagart)
        if not entry.get("historical_phonology"):
            missing_phonology.append({"character": char, "codepoint": cp})

        # Missing component analysis (semantic/phonetic identification)
        fd = entry.get("formation_details", {})
        has_components = (isinstance(fd, dict) and
                          (fd.get("semantic") or fd.get("phonetic")))
        if not has_components:
            missing_component_analysis.append({"character": char, "codepoint": cp})

    # Sort each list
    for lst in [missing_etymology_notes, missing_formation_type,
                missing_phonology, missing_component_analysis]:
        lst.sort(key=lambda x: x["codepoint"])

    return {
        "cjk_basic_block_range": f"U+{CJK_BASIC_START:04X}-U+{CJK_BASIC_END:04X}",
        "total_possible_cjk_basic": total_possible,
        "total_in_database": len(cjk_chars),
        "not_in_database": total_possible - len(cjk_chars),
        "missing_etymology_notes": {
            "count": len(missing_etymology_notes),
            "characters": missing_etymology_notes[:200],
            "truncated": len(missing_etymology_notes) > 200,
        },
        "missing_formation_type": {
            "count": len(missing_formation_type),
            "characters": missing_formation_type[:200],
            "truncated": len(missing_formation_type) > 200,
        },
        "missing_historical_phonology": {
            "count": len(missing_phonology),
            "characters": missing_phonology[:200],
            "truncated": len(missing_phonology) > 200,
        },
        "missing_component_analysis": {
            "count": len(missing_component_analysis),
            "characters": missing_component_analysis[:200],
            "truncated": len(missing_component_analysis) > 200,
        },
    }


# ---------------------------------------------------------------------------
# 5. Confidence scoring
# ---------------------------------------------------------------------------

# Sources that provide meaningful etymology information
ETYMOLOGY_SOURCES = {
    "makemeahanzi", "dong_chinese", "wiktionary", "shuowen_jiezi", "baxter_sagart"
}


def compute_confidence_score(entry, all_entries):
    """Compute a confidence score (0-100) for a character's etymology data."""
    score = 0.0

    # --- Source coverage (up to 30 points) ---
    notes = entry.get("etymology_notes", [])
    note_sources = set()
    if isinstance(notes, list):
        for note in notes:
            if isinstance(note, dict):
                note_sources.add(note.get("source", ""))
    # Each etymology source adds points (diminishing returns)
    source_count = len(note_sources & ETYMOLOGY_SOURCES)
    # 0->0, 1->10, 2->18, 3->24, 4->28, 5->30
    if source_count >= 1:
        score += 10
    if source_count >= 2:
        score += 8
    if source_count >= 3:
        score += 6
    if source_count >= 4:
        score += 4
    if source_count >= 5:
        score += 2

    # --- Formation type agreement (up to 25 points) ---
    ft_classifications = []
    mmah_type = entry.get("formation_type", "")
    if mmah_type:
        ft_classifications.append(normalize_formation_type(mmah_type))

    dong_text = get_etymology_note_by_source(entry, "dong_chinese")
    dong_type = extract_dong_formation_type(dong_text)
    if dong_type:
        ft_classifications.append(normalize_formation_type(dong_type))

    wiki_text = get_etymology_note_by_source(entry, "wiktionary")
    wiki_type = extract_wiktionary_formation_type(wiki_text)
    if wiki_type:
        ft_classifications.append(normalize_formation_type(wiki_type))

    if len(ft_classifications) == 0:
        score += 0  # No formation type info
    elif len(ft_classifications) == 1:
        score += 8  # Only one source
    else:
        # Check agreement
        unique_types = set(ft_classifications)
        if len(unique_types) == 1:
            score += 25  # Full agreement
        elif len(unique_types) == 2 and len(ft_classifications) >= 3:
            score += 15  # Majority agreement
        else:
            score += 5  # Disagreement

    # --- Shuowen entry exists (up to 15 points) ---
    if entry.get("shuowen"):
        score += 10
        sw = entry["shuowen"]
        if isinstance(sw, dict):
            if sw.get("duan_notes"):
                score += 5  # Duan Yucai commentary adds depth

    # --- Baxter-Sagart phonology (up to 15 points) ---
    if entry.get("historical_phonology"):
        hp = entry["historical_phonology"]
        if isinstance(hp, list) and len(hp) > 0:
            score += 10
            # Multiple readings documented
            if len(hp) > 1:
                score += 5

    # --- Historical glyphs (up to 15 points) ---
    hg = entry.get("historical_glyphs", {})
    if isinstance(hg, dict) and hg.get("image_count", 0) > 0:
        img_count = hg["image_count"]
        eras = hg.get("eras_available", [])
        score += 5
        if "oracle_bone" in eras:
            score += 5  # Earliest evidence
        if img_count >= 5:
            score += 3
        elif img_count >= 2:
            score += 2

    # Cap at 100
    return min(round(score), 100)


def compute_all_confidence_scores(entries):
    """Compute confidence scores for all entries."""
    scores = {}
    score_distribution = Counter()

    for char, entry in entries.items():
        s = compute_confidence_score(entry, entries)
        scores[char] = s
        bucket = (s // 10) * 10  # 0-9, 10-19, etc.
        score_distribution[bucket] += 1

    # Summary statistics
    all_scores = list(scores.values())
    all_scores.sort()
    n = len(all_scores)

    # Get lowest-scoring CJK basic block characters
    cjk_scores = [(char, s) for char, s in scores.items() if is_cjk_basic(char)]
    cjk_scores.sort(key=lambda x: x[1])

    # Get highest-scoring characters
    high_scores = sorted(scores.items(), key=lambda x: -x[1])

    return {
        "total_characters_scored": n,
        "mean_score": round(sum(all_scores) / n, 1) if n else 0,
        "median_score": all_scores[n // 2] if n else 0,
        "min_score": all_scores[0] if n else 0,
        "max_score": all_scores[-1] if n else 0,
        "distribution": {f"{k}-{k+9}": v for k, v in sorted(score_distribution.items())},
        "lowest_scoring_cjk_basic": [
            {"character": c, "score": s} for c, s in cjk_scores[:50]
        ],
        "highest_scoring_characters": [
            {"character": c, "score": s} for c, s in high_scores[:50]
        ],
    }


# ---------------------------------------------------------------------------
# 6. Suspicious entries
# ---------------------------------------------------------------------------

def find_suspicious_entries(entries):
    """Flag entries with specific quality concerns."""

    # 6a. Shuowen says 象形 but character has a clear phonetic component
    shuowen_pictographic_with_phonetic = []
    for char, entry in entries.items():
        sw = entry.get("shuowen", {})
        if not isinstance(sw, dict):
            continue
        expl = sw.get("explanation", "")
        if "象形" not in expl:
            continue

        # Check if modern sources identify a phonetic component
        fd = entry.get("formation_details", {})
        phonetic = fd.get("phonetic", "") if isinstance(fd, dict) else ""
        dong_text = get_etymology_note_by_source(entry, "dong_chinese")
        dong_type = extract_dong_formation_type(dong_text)
        modern_type = entry.get("formation_type", "")

        has_phonetic_evidence = False
        reason = []
        if phonetic:
            has_phonetic_evidence = True
            reason.append(f"formation_details identifies phonetic component: {phonetic}")
        if dong_type and normalize_formation_type(dong_type) == "phono-semantic":
            has_phonetic_evidence = True
            reason.append(f"Dong Chinese classifies as phonosemantic")
        if modern_type and normalize_formation_type(modern_type) == "phono-semantic":
            has_phonetic_evidence = True
            reason.append(f"formation_type is phono-semantic")

        if has_phonetic_evidence:
            shuowen_pictographic_with_phonetic.append({
                "character": char,
                "codepoint": entry.get("codepoint", ""),
                "shuowen_explanation": expl[:200],
                "reasons": reason,
                "formation_details": fd if isinstance(fd, dict) else {},
            })

    shuowen_pictographic_with_phonetic.sort(key=lambda x: x["codepoint"])

    # 6b. Classified as phono-semantic but no phonetic component identified
    pictophonetic_no_phonetic = []
    for char, entry in entries.items():
        ft = entry.get("formation_type", "")
        if normalize_formation_type(ft) != "phono-semantic":
            continue
        fd = entry.get("formation_details", {})
        if isinstance(fd, dict) and fd.get("phonetic"):
            continue
        # No phonetic identified
        pictophonetic_no_phonetic.append({
            "character": char,
            "codepoint": entry.get("codepoint", ""),
            "formation_details": fd if isinstance(fd, dict) else {},
            "dong_chinese_note": get_etymology_note_by_source(entry, "dong_chinese")[:200],
        })

    pictophonetic_no_phonetic.sort(key=lambda x: x["codepoint"])

    # 6c. Etymology from only one source
    single_source_etymology = []
    for char, entry in entries.items():
        if not is_cjk_basic(char):
            continue
        notes = entry.get("etymology_notes", [])
        note_sources = set()
        if isinstance(notes, list):
            for note in notes:
                if isinstance(note, dict):
                    note_sources.add(note.get("source", ""))
        etym_sources = note_sources & ETYMOLOGY_SOURCES
        if len(etym_sources) == 1:
            single_source_etymology.append({
                "character": char,
                "codepoint": entry.get("codepoint", ""),
                "sole_source": list(etym_sources)[0],
            })

    single_source_etymology.sort(key=lambda x: x["codepoint"])

    # Count by sole source
    sole_source_counts = Counter(e["sole_source"] for e in single_source_etymology)

    return {
        "shuowen_pictographic_but_has_phonetic_component": {
            "description": "Shuowen classifies as 象形 (pictographic) but modern analysis identifies a phonetic component",
            "count": len(shuowen_pictographic_with_phonetic),
            "entries": shuowen_pictographic_with_phonetic[:100],
            "truncated": len(shuowen_pictographic_with_phonetic) > 100,
        },
        "pictophonetic_without_identified_phonetic": {
            "description": "Classified as pictophonetic but no phonetic component is identified in formation_details",
            "count": len(pictophonetic_no_phonetic),
            "entries": pictophonetic_no_phonetic[:100],
            "truncated": len(pictophonetic_no_phonetic) > 100,
        },
        "single_source_etymology_cjk_basic": {
            "description": "CJK basic block characters with etymology from only one source (less verified)",
            "count": len(single_source_etymology),
            "by_sole_source": dict(sole_source_counts.most_common()),
            "entries": single_source_etymology[:100],
            "truncated": len(single_source_etymology) > 100,
        },
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("Loading entries...")
    entries = load_entries()
    print(f"Loaded {len(entries)} entries.")

    report = {}

    # 1. MMAH vs Dong Chinese conflicts
    print("\n[1/6] Finding Make Me a Hanzi vs Dong Chinese formation type conflicts...")
    mmah_dong = find_mmah_dong_conflicts(entries)
    report["formation_type_conflicts_mmah_vs_dong"] = {
        "description": "Characters where Make Me a Hanzi and Dong Chinese disagree on formation type",
        "count": len(mmah_dong),
        "conflicts": mmah_dong[:200],
        "truncated": len(mmah_dong) > 200,
    }
    print(f"  Found {len(mmah_dong)} conflicts.")

    # 2. Wiktionary formation type extraction and comparison
    print("\n[2/6] Extracting Wiktionary formation types and comparing...")
    wikt_results = find_wiktionary_conflicts(entries)
    report["wiktionary_formation_type_analysis"] = {
        "description": "Wiktionary formation types extracted from etymology text, compared against MMAH/Dong",
        "total_extracted": wikt_results["total_wiktionary_formation_types_extracted"],
        "agreements": wikt_results["agreements_with_other_sources"],
        "conflict_count": len(wikt_results["conflicts"]),
        "conflicts": wikt_results["conflicts"][:200],
        "truncated": len(wikt_results["conflicts"]) > 200,
    }
    print(f"  Extracted {wikt_results['total_wiktionary_formation_types_extracted']} Wiktionary formation types.")
    print(f"  Agreements: {wikt_results['agreements_with_other_sources']}")
    print(f"  Conflicts: {len(wikt_results['conflicts'])}")

    # 3. Shuowen vs modern analysis
    print("\n[3/6] Finding Shuowen vs modern scholarship conflicts...")
    sw_conflicts = find_shuowen_modern_conflicts(entries)
    report["shuowen_vs_modern_conflicts"] = {
        "description": "Characters where Shuowen Jiezi classification differs from modern scholarship",
        "count": len(sw_conflicts),
        "conflicts": sw_conflicts[:200],
        "truncated": len(sw_conflicts) > 200,
    }
    print(f"  Found {len(sw_conflicts)} conflicts.")

    # 4. Missing data gaps
    print("\n[4/6] Analyzing missing data gaps in CJK basic block...")
    gaps = find_missing_data_gaps(entries)
    report["missing_data_gaps"] = gaps
    print(f"  CJK basic block characters in DB: {gaps['total_in_database']} / {gaps['total_possible_cjk_basic']}")
    print(f"  Missing etymology notes: {gaps['missing_etymology_notes']['count']}")
    print(f"  Missing formation type: {gaps['missing_formation_type']['count']}")
    print(f"  Missing historical phonology: {gaps['missing_historical_phonology']['count']}")
    print(f"  Missing component analysis: {gaps['missing_component_analysis']['count']}")

    # 5. Confidence scoring
    print("\n[5/6] Computing confidence scores...")
    confidence = compute_all_confidence_scores(entries)
    report["confidence_scores"] = confidence
    print(f"  Mean score: {confidence['mean_score']}")
    print(f"  Median score: {confidence['median_score']}")
    print(f"  Distribution: {json.dumps(confidence['distribution'], indent=4)}")

    # 6. Suspicious entries
    print("\n[6/6] Flagging suspicious entries...")
    suspicious = find_suspicious_entries(entries)
    report["suspicious_entries"] = suspicious
    print(f"  Shuowen 象形 with phonetic component: {suspicious['shuowen_pictographic_but_has_phonetic_component']['count']}")
    print(f"  Pictophonetic without phonetic ID: {suspicious['pictophonetic_without_identified_phonetic']['count']}")
    print(f"  Single-source etymology (CJK basic): {suspicious['single_source_etymology_cjk_basic']['count']}")
    print(f"    Breakdown: {json.dumps(suspicious['single_source_etymology_cjk_basic']['by_sole_source'], indent=6)}")

    # Write report
    print(f"\nWriting report to {OUTPUT_PATH}...")
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print("Done.")

    # Print executive summary
    print("\n" + "=" * 70)
    print("EXECUTIVE SUMMARY")
    print("=" * 70)
    total_issues = (
        len(mmah_dong) +
        len(wikt_results["conflicts"]) +
        len(sw_conflicts) +
        suspicious["shuowen_pictographic_but_has_phonetic_component"]["count"] +
        suspicious["pictophonetic_without_identified_phonetic"]["count"] +
        suspicious["single_source_etymology_cjk_basic"]["count"]
    )
    print(f"\nTotal quality issues flagged: {total_issues}")
    print(f"\n1. Formation type conflicts (MMAH vs Dong):      {len(mmah_dong):>5}")
    print(f"2. Wiktionary vs other source conflicts:          {len(wikt_results['conflicts']):>5}")
    print(f"3. Shuowen vs modern scholarship conflicts:       {len(sw_conflicts):>5}")
    print(f"4. Missing data (CJK basic block):")
    print(f"   - No etymology notes:                          {gaps['missing_etymology_notes']['count']:>5}")
    print(f"   - No formation type:                           {gaps['missing_formation_type']['count']:>5}")
    print(f"   - No historical phonology:                     {gaps['missing_historical_phonology']['count']:>5}")
    print(f"   - No component analysis:                       {gaps['missing_component_analysis']['count']:>5}")
    print(f"5. Confidence score: mean={confidence['mean_score']}, median={confidence['median_score']}")
    print(f"6. Suspicious entries:")
    print(f"   - Shuowen 象形 + phonetic component:           {suspicious['shuowen_pictographic_but_has_phonetic_component']['count']:>5}")
    print(f"   - Pictophonetic w/o phonetic ID:               {suspicious['pictophonetic_without_identified_phonetic']['count']:>5}")
    print(f"   - Single-source etymology (CJK basic):         {suspicious['single_source_etymology_cjk_basic']['count']:>5}")


if __name__ == "__main__":
    main()
