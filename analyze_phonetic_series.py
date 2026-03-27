#!/usr/bin/env python3
"""
Analyze the reliability of phonetic component claims in the hanzi etymology database.

Tests:
1. Intra-class phonetic similarity (Mandarin) for kPhonetic series
2. Cross-validation of phonetic components across sources
3. Old Chinese phonetic regularity within phonetic-component groups
4. Most productive phonetic components and their reading consistency
"""

import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
DB_PATH = Path("/home/catalin/hanzi-etymology-dict/output/hanzi_etymology.jsonl")
OUT_PATH = Path("/home/catalin/hanzi-etymology-dict/output/phonetic_analysis.json")

# ---------------------------------------------------------------------------
# Pinyin helpers
# ---------------------------------------------------------------------------

# Mapping of pinyin syllable → (initial, final/rhyme)
# We strip the tone mark first, then split.

TONE_MARKS = str.maketrans(
    "āáǎàēéěèīíǐìōóǒòūúǔùǖǘǚǜ",
    "aaaaeeeeiiiioooouuuuüüüü",
)

# Pinyin initials (longest-first so we match zh before z, etc.)
INITIALS = sorted(
    [
        "zh", "ch", "sh",
        "b", "p", "m", "f",
        "d", "t", "n", "l",
        "g", "k", "h",
        "j", "q", "x",
        "z", "c", "s",
        "r", "y", "w",
    ],
    key=len,
    reverse=True,
)


def strip_tone(syllable: str) -> str:
    """Remove tone diacritics from a pinyin syllable."""
    return syllable.translate(TONE_MARKS)


def split_pinyin(syllable: str) -> tuple:
    """Return (initial, final) for one pinyin syllable.

    If there is no initial consonant the initial is '' (zero initial).
    """
    s = strip_tone(syllable.strip().lower())
    for ini in INITIALS:
        if s.startswith(ini):
            return (ini, s[len(ini):])
    return ("", s)


def parse_mandarin(raw: str) -> list:
    """Parse a mandarin reading string into a list of syllables.

    Handles comma/space separated multi-readings.
    """
    if not raw:
        return []
    # Split on comma, space, or slash
    parts = re.split(r"[,/\s]+", raw.strip())
    return [p for p in parts if p]

# ---------------------------------------------------------------------------
# OC rhyme helpers
# ---------------------------------------------------------------------------

# For Baxter-Sagart, extract the "main vowel + coda" portion as rhyme proxy.
# The reconstruction looks like *t[ə][n]ʔ – we want the part after the
# initial consonant cluster.  A rough heuristic: take everything from the
# first vowel-like character onward (including brackets).

_BS_VOWELS = set("aeioəuæɨɯɑɒ")


def bs_rhyme(oc: str) -> str:
    """Extract a rough rhyme portion from a Baxter-Sagart OC reconstruction."""
    oc = oc.lstrip("*")
    for i, ch in enumerate(oc):
        if ch in _BS_VOWELS or ch == "[":
            return oc[i:]
    return oc  # fallback


# ---------------------------------------------------------------------------
# Load database
# ---------------------------------------------------------------------------

def load_records():
    records = []
    with open(DB_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


# ---------------------------------------------------------------------------
# Analysis 1: Intra-class phonetic similarity (Mandarin)
# ---------------------------------------------------------------------------

def analyze_phonetic_series(records):
    """Group characters by kPhonetic class and measure Mandarin similarity."""
    # Build a lookup: character → mandarin readings
    char_to_mandarin = {}
    for r in records:
        m = r.get("readings", {}).get("mandarin")
        if m:
            char_to_mandarin[r["character"]] = parse_mandarin(m)

    # Build phonetic class → set of member characters
    # We use phonetic_family lists (which contain sibling characters)
    # plus the character itself, grouped by each phonetic_series class.
    class_members = defaultdict(set)
    for r in records:
        series = r.get("phonetic_series", [])
        family = r.get("phonetic_family", [])
        ch = r["character"]
        for cls in series:
            class_members[cls].add(ch)
            for fam_ch in family:
                class_members[cls].add(fam_ch)

    # For each class, compute similarity metrics
    class_stats = []
    initial_match_rates = []
    rhyme_match_rates = []

    for cls, members in class_members.items():
        # Get readings for members that have mandarin
        member_readings = {}
        for m in members:
            if m in char_to_mandarin:
                member_readings[m] = char_to_mandarin[m]

        if len(member_readings) < 2:
            continue

        # For each character, check if it shares initial or rhyme with
        # at least one other member.
        all_initials = []
        all_finals = []
        for ch, syls in member_readings.items():
            for syl in syls:
                ini, fin = split_pinyin(syl)
                all_initials.append(ini)
                all_finals.append(fin)

        initial_counts = Counter(all_initials)
        final_counts = Counter(all_finals)

        chars_sharing_initial = 0
        chars_sharing_rhyme = 0
        total_chars = 0

        for ch, syls in member_readings.items():
            total_chars += 1
            ch_initials = set()
            ch_finals = set()
            for syl in syls:
                ini, fin = split_pinyin(syl)
                ch_initials.add(ini)
                ch_finals.add(fin)

            # Check if any of this character's initials appear in another member
            shares_initial = any(initial_counts[ini] > 1 for ini in ch_initials)
            shares_rhyme = any(final_counts[fin] > 1 for fin in ch_finals)

            if shares_initial:
                chars_sharing_initial += 1
            if shares_rhyme:
                chars_sharing_rhyme += 1

        init_rate = chars_sharing_initial / total_chars if total_chars > 0 else 0
        rhyme_rate = chars_sharing_rhyme / total_chars if total_chars > 0 else 0

        initial_match_rates.append(init_rate)
        rhyme_match_rates.append(rhyme_rate)

        class_stats.append({
            "class": cls,
            "member_count": len(members),
            "with_reading": len(member_readings),
            "initial_match_rate": round(init_rate, 4),
            "rhyme_match_rate": round(rhyme_rate, 4),
        })

    # Summary statistics
    avg_initial = sum(initial_match_rates) / len(initial_match_rates) if initial_match_rates else 0
    avg_rhyme = sum(rhyme_match_rates) / len(rhyme_match_rates) if rhyme_match_rates else 0

    # Distribution buckets
    def bucket_distribution(rates):
        buckets = {"0-20%": 0, "20-40%": 0, "40-60%": 0, "60-80%": 0, "80-100%": 0}
        for r in rates:
            pct = r * 100
            if pct < 20:
                buckets["0-20%"] += 1
            elif pct < 40:
                buckets["20-40%"] += 1
            elif pct < 60:
                buckets["40-60%"] += 1
            elif pct < 80:
                buckets["60-80%"] += 1
            else:
                buckets["80-100%"] += 1
        return buckets

    initial_dist = bucket_distribution(initial_match_rates)
    rhyme_dist = bucket_distribution(rhyme_match_rates)

    # Sort by rhyme match rate for examples
    class_stats.sort(key=lambda x: x["rhyme_match_rate"])
    worst_classes = class_stats[:10]
    best_classes = class_stats[-10:][::-1]

    return {
        "total_classes_analyzed": len(class_stats),
        "average_initial_match_rate": round(avg_initial, 4),
        "average_rhyme_match_rate": round(avg_rhyme, 4),
        "initial_match_distribution": initial_dist,
        "rhyme_match_distribution": rhyme_dist,
        "best_rhyme_classes": best_classes,
        "worst_rhyme_classes": worst_classes,
    }


# ---------------------------------------------------------------------------
# Analysis 2: Cross-validate phonetic components
# ---------------------------------------------------------------------------

def analyze_phonetic_cross_validation(records):
    """Compare phonetic from MakeMe/Dong/IDS vs ytenx."""
    agree = 0
    disagree = 0
    disagreements = []

    for r in records:
        fd = r.get("formation_details", {})
        ph_main = fd.get("phonetic", "")
        ph_ytenx = fd.get("phonetic_component_ytenx", "")

        if not ph_main or not ph_ytenx:
            continue

        if ph_main == ph_ytenx:
            agree += 1
        else:
            disagree += 1
            if len(disagreements) < 200:
                disagreements.append({
                    "character": r["character"],
                    "phonetic_main": ph_main,
                    "phonetic_ytenx": ph_ytenx,
                    "mandarin": r.get("readings", {}).get("mandarin", ""),
                })

    total = agree + disagree
    agreement_rate = agree / total if total > 0 else 0

    # Analyze patterns in disagreements
    pattern_counter = Counter()
    for d in disagreements:
        pattern_counter[(d["phonetic_main"], d["phonetic_ytenx"])] += 1

    common_disagreements = [
        {"main": k[0], "ytenx": k[1], "count": v}
        for k, v in pattern_counter.most_common(20)
    ]

    return {
        "total_compared": total,
        "agree": agree,
        "disagree": disagree,
        "agreement_rate": round(agreement_rate, 4),
        "sample_disagreements": disagreements[:30],
        "common_disagreement_patterns": common_disagreements,
    }


# ---------------------------------------------------------------------------
# Analysis 3: Old Chinese phonetic regularity
# ---------------------------------------------------------------------------

def analyze_oc_regularity(records):
    """Group by phonetic component, check OC rhyme consistency."""
    # Build: phonetic_component → list of (character, oc_reconstruction, rhyme_info)
    component_group_zz = defaultdict(list)  # Zhengzhang
    component_group_bs = defaultdict(list)  # Baxter-Sagart

    for r in records:
        fd = r.get("formation_details", {})
        phonetic = fd.get("phonetic", "")
        if not phonetic:
            continue

        for hp in r.get("historical_phonology", []):
            if "old_chinese_zhengzhang" in hp and "rhyme_group" in hp:
                component_group_zz[phonetic].append({
                    "character": r["character"],
                    "oc": hp["old_chinese_zhengzhang"],
                    "rhyme_group": hp["rhyme_group"],
                })
            if "old_chinese" in hp:
                rhyme = bs_rhyme(hp["old_chinese"])
                component_group_bs[phonetic].append({
                    "character": r["character"],
                    "oc": hp["old_chinese"],
                    "rhyme_extracted": rhyme,
                })

    # Zhengzhang analysis: for each group, measure the share of characters
    # that belong to the most common rhyme_group.
    zz_stats = []
    for comp, entries in component_group_zz.items():
        if len(entries) < 3:
            continue
        rhyme_counts = Counter(e["rhyme_group"] for e in entries)
        most_common_rhyme, most_common_count = rhyme_counts.most_common(1)[0]
        consistency = most_common_count / len(entries)
        zz_stats.append({
            "phonetic_component": comp,
            "member_count": len(entries),
            "dominant_rhyme": most_common_rhyme,
            "dominant_rhyme_count": most_common_count,
            "total_rhymes": len(rhyme_counts),
            "consistency": round(consistency, 4),
            "rhyme_distribution": dict(rhyme_counts),
        })

    # Baxter-Sagart analysis: group by extracted rhyme
    bs_stats = []
    for comp, entries in component_group_bs.items():
        if len(entries) < 3:
            continue
        rhyme_counts = Counter(e["rhyme_extracted"] for e in entries)
        most_common_rhyme, most_common_count = rhyme_counts.most_common(1)[0]
        consistency = most_common_count / len(entries)
        bs_stats.append({
            "phonetic_component": comp,
            "member_count": len(entries),
            "dominant_rhyme": most_common_rhyme,
            "dominant_rhyme_count": most_common_count,
            "total_rhymes": len(rhyme_counts),
            "consistency": round(consistency, 4),
        })

    # Summary
    zz_consistencies = [s["consistency"] for s in zz_stats]
    bs_consistencies = [s["consistency"] for s in bs_stats]

    avg_zz = sum(zz_consistencies) / len(zz_consistencies) if zz_consistencies else 0
    avg_bs = sum(bs_consistencies) / len(bs_consistencies) if bs_consistencies else 0

    def bucket_distribution(rates):
        buckets = {"0-20%": 0, "20-40%": 0, "40-60%": 0, "60-80%": 0, "80-100%": 0}
        for r in rates:
            pct = r * 100
            if pct < 20:
                buckets["0-20%"] += 1
            elif pct < 40:
                buckets["20-40%"] += 1
            elif pct < 60:
                buckets["40-60%"] += 1
            elif pct < 80:
                buckets["60-80%"] += 1
            else:
                buckets["80-100%"] += 1
        return buckets

    zz_dist = bucket_distribution(zz_consistencies)
    bs_dist = bucket_distribution(bs_consistencies)

    # Sort for best/worst examples
    zz_stats.sort(key=lambda x: x["consistency"])
    bs_stats.sort(key=lambda x: x["consistency"])

    return {
        "zhengzhang": {
            "groups_analyzed": len(zz_stats),
            "average_rhyme_consistency": round(avg_zz, 4),
            "consistency_distribution": zz_dist,
            "most_consistent": zz_stats[-10:][::-1] if zz_stats else [],
            "least_consistent": zz_stats[:10] if zz_stats else [],
        },
        "baxter_sagart": {
            "groups_analyzed": len(bs_stats),
            "average_rhyme_consistency": round(avg_bs, 4),
            "consistency_distribution": bs_dist,
            "most_consistent": bs_stats[-10:][::-1] if bs_stats else [],
            "least_consistent": bs_stats[:10] if bs_stats else [],
        },
    }


# ---------------------------------------------------------------------------
# Analysis 4: Most productive phonetic components
# ---------------------------------------------------------------------------

def analyze_productive_components(records):
    """Find the most productive phonetic components and measure reading consistency."""
    # Build: phonetic → list of (character, mandarin_readings)
    char_to_mandarin = {}
    for r in records:
        m = r.get("readings", {}).get("mandarin")
        if m:
            char_to_mandarin[r["character"]] = parse_mandarin(m)

    component_chars = defaultdict(list)
    for r in records:
        fd = r.get("formation_details", {})
        phonetic = fd.get("phonetic", "")
        if not phonetic:
            continue
        ch = r["character"]
        mandarin = r.get("readings", {}).get("mandarin", "")
        component_chars[phonetic].append({
            "character": ch,
            "mandarin": mandarin,
        })

    # Rank by number of characters
    ranked = sorted(component_chars.items(), key=lambda x: len(x[1]), reverse=True)

    top_components = []
    for comp, chars in ranked[:50]:
        # Analyze reading consistency
        all_initials = []
        all_finals = []
        readings_list = []

        for entry in chars:
            syls = parse_mandarin(entry["mandarin"])
            for syl in syls:
                ini, fin = split_pinyin(syl)
                all_initials.append(ini)
                all_finals.append(fin)
            readings_list.append({
                "character": entry["character"],
                "mandarin": entry["mandarin"],
            })

        initial_counts = Counter(all_initials)
        final_counts = Counter(all_finals)

        # Dominant initial and final
        if initial_counts:
            dom_initial, dom_initial_count = initial_counts.most_common(1)[0]
            initial_consistency = dom_initial_count / sum(initial_counts.values())
        else:
            dom_initial = ""
            initial_consistency = 0

        if final_counts:
            dom_final, dom_final_count = final_counts.most_common(1)[0]
            final_consistency = dom_final_count / sum(final_counts.values())
        else:
            dom_final = ""
            final_consistency = 0

        # Reading of the component itself (if available)
        comp_reading = char_to_mandarin.get(comp, [])

        top_components.append({
            "component": comp,
            "component_reading": " ".join(comp_reading) if comp_reading else "N/A",
            "character_count": len(chars),
            "dominant_initial": dom_initial,
            "initial_consistency": round(initial_consistency, 4),
            "dominant_final": dom_final,
            "final_consistency": round(final_consistency, 4),
            "initial_distribution": dict(initial_counts.most_common(5)),
            "final_distribution": dict(final_counts.most_common(5)),
            "sample_characters": readings_list[:15],
        })

    return {
        "total_distinct_phonetic_components": len(component_chars),
        "top_50_components": top_components,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("Loading database...", flush=True)
    records = load_records()
    print(f"  Loaded {len(records):,} records.\n", flush=True)

    results = {}

    # --- Analysis 1 ---
    print("=" * 70)
    print("ANALYSIS 1: Intra-class phonetic similarity (Mandarin)")
    print("=" * 70, flush=True)
    a1 = analyze_phonetic_series(records)
    results["phonetic_series_similarity"] = a1

    print(f"  Classes analyzed: {a1['total_classes_analyzed']}")
    print(f"  Avg % members sharing initial with another member: "
          f"{a1['average_initial_match_rate']*100:.1f}%")
    print(f"  Avg % members sharing rhyme with another member:   "
          f"{a1['average_rhyme_match_rate']*100:.1f}%")
    print(f"\n  Initial-match distribution across classes:")
    for bucket, count in a1["initial_match_distribution"].items():
        bar = "#" * (count // max(1, a1["total_classes_analyzed"] // 60))
        print(f"    {bucket:>8s}: {count:5d}  {bar}")
    print(f"\n  Rhyme-match distribution across classes:")
    for bucket, count in a1["rhyme_match_distribution"].items():
        bar = "#" * (count // max(1, a1["total_classes_analyzed"] // 60))
        print(f"    {bucket:>8s}: {count:5d}  {bar}")
    print(f"\n  Best rhyme-matching classes (top 5):")
    for c in a1["best_rhyme_classes"][:5]:
        print(f"    Class {c['class']:>5s}: {c['with_reading']:3d} chars, "
              f"initial={c['initial_match_rate']*100:.0f}%, "
              f"rhyme={c['rhyme_match_rate']*100:.0f}%")
    print(f"\n  Worst rhyme-matching classes (bottom 5):")
    for c in a1["worst_rhyme_classes"][:5]:
        print(f"    Class {c['class']:>5s}: {c['with_reading']:3d} chars, "
              f"initial={c['initial_match_rate']*100:.0f}%, "
              f"rhyme={c['rhyme_match_rate']*100:.0f}%")

    # --- Analysis 2 ---
    print()
    print("=" * 70)
    print("ANALYSIS 2: Cross-validation of phonetic components")
    print("=" * 70, flush=True)
    a2 = analyze_phonetic_cross_validation(records)
    results["phonetic_cross_validation"] = a2

    print(f"  Characters with both sources: {a2['total_compared']}")
    print(f"  Agreement:  {a2['agree']:5d} ({a2['agreement_rate']*100:.1f}%)")
    print(f"  Disagreement: {a2['disagree']:5d} ({(1-a2['agreement_rate'])*100:.1f}%)")
    print(f"\n  Most common disagreement patterns (main vs ytenx):")
    for d in a2["common_disagreement_patterns"][:10]:
        print(f"    {d['main']:>4s} vs {d['ytenx']:<4s}  ({d['count']} cases)")
    print(f"\n  Sample disagreements:")
    for d in a2["sample_disagreements"][:10]:
        print(f"    {d['character']}  main={d['phonetic_main']}  "
              f"ytenx={d['phonetic_ytenx']}  mandarin={d['mandarin']}")

    # --- Analysis 3 ---
    print()
    print("=" * 70)
    print("ANALYSIS 3: Old Chinese phonetic regularity")
    print("=" * 70, flush=True)
    a3 = analyze_oc_regularity(records)
    results["oc_regularity"] = a3

    for label, sub in [("Zhengzhang", a3["zhengzhang"]), ("Baxter-Sagart", a3["baxter_sagart"])]:
        print(f"\n  [{label}]")
        print(f"    Groups analyzed: {sub['groups_analyzed']}")
        print(f"    Avg rhyme consistency: {sub['average_rhyme_consistency']*100:.1f}%")
        print(f"    Consistency distribution:")
        for bucket, count in sub["consistency_distribution"].items():
            bar = "#" * (count // max(1, sub["groups_analyzed"] // 60))
            print(f"      {bucket:>8s}: {count:5d}  {bar}")
        print(f"    Most consistent (top 5):")
        for s in sub["most_consistent"][:5]:
            print(f"      {s['phonetic_component']:>4s}: {s['member_count']:3d} chars, "
                  f"consistency={s['consistency']*100:.0f}%, "
                  f"dominant rhyme={s['dominant_rhyme']}")
        print(f"    Least consistent (bottom 5):")
        for s in sub["least_consistent"][:5]:
            comp = s["phonetic_component"]
            dist = s.get("rhyme_distribution", {})
            dist_str = ", ".join(f"{k}:{v}" for k, v in sorted(dist.items(), key=lambda x: -x[1])[:4])
            print(f"      {comp:>4s}: {s['member_count']:3d} chars, "
                  f"consistency={s['consistency']*100:.0f}%, "
                  f"rhymes=[{dist_str}]")

    # --- Analysis 4 ---
    print()
    print("=" * 70)
    print("ANALYSIS 4: Most productive phonetic components")
    print("=" * 70, flush=True)
    a4 = analyze_productive_components(records)
    results["productive_components"] = a4

    print(f"  Total distinct phonetic components: {a4['total_distinct_phonetic_components']}")
    print(f"\n  Top 20 most productive components:")
    print(f"  {'Comp':>5s} {'Read':>6s} {'#Chars':>6s} {'Init%':>6s} {'Rhyme%':>7s}  Sample readings")
    print(f"  {'─'*5} {'─'*6} {'─'*6} {'─'*6} {'─'*7}  {'─'*30}")
    for c in a4["top_50_components"][:20]:
        samples = ", ".join(
            f"{s['character']}({s['mandarin']})"
            for s in c["sample_characters"][:5]
            if s["mandarin"]
        )
        print(f"  {c['component']:>5s} {c['component_reading']:>6s} "
              f"{c['character_count']:>6d} "
              f"{c['initial_consistency']*100:>5.0f}% "
              f"{c['final_consistency']*100:>6.0f}%  {samples}")

    # --- Save ---
    print()
    print("=" * 70)

    # Trim large lists for JSON output to keep file manageable
    # (full data for top-level stats, but limit per-class details)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"Full results saved to {OUT_PATH}")
    print(f"  File size: {OUT_PATH.stat().st_size / 1024:.0f} KB")

    # --- Final summary ---
    print()
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print()
    print(f"  1. Mandarin phonetic-series similarity:")
    print(f"     {a1['total_classes_analyzed']} kPhonetic classes tested.")
    print(f"     On average, {a1['average_rhyme_match_rate']*100:.1f}% of members "
          f"share a rhyme with at least one sibling.")
    print(f"     On average, {a1['average_initial_match_rate']*100:.1f}% share an initial consonant.")
    high_rhyme = a1["rhyme_match_distribution"].get("80-100%", 0)
    pct_high = high_rhyme / max(1, a1["total_classes_analyzed"]) * 100
    print(f"     {high_rhyme} classes ({pct_high:.0f}%) have 80-100% rhyme overlap.")
    print()
    print(f"  2. Phonetic component cross-validation:")
    print(f"     {a2['total_compared']} characters with both main and ytenx phonetic data.")
    print(f"     Agreement rate: {a2['agreement_rate']*100:.1f}%.")
    if a2["common_disagreement_patterns"]:
        top_dis = a2["common_disagreement_patterns"][0]
        print(f"     Most common disagreement: {top_dis['main']} vs {top_dis['ytenx']} "
              f"({top_dis['count']} cases).")
    print()
    print(f"  3. Old Chinese rhyme regularity:")
    print(f"     Zhengzhang: {a3['zhengzhang']['groups_analyzed']} groups, "
          f"avg consistency {a3['zhengzhang']['average_rhyme_consistency']*100:.1f}%.")
    print(f"     Baxter-Sagart: {a3['baxter_sagart']['groups_analyzed']} groups, "
          f"avg consistency {a3['baxter_sagart']['average_rhyme_consistency']*100:.1f}%.")
    print(f"     (High consistency confirms phonetic components preserved ancient rhymes.)")
    print()
    print(f"  4. Most productive phonetic components:")
    if a4["top_50_components"]:
        top = a4["top_50_components"][0]
        print(f"     Most productive: '{top['component']}' with {top['character_count']} characters.")
        print(f"     Its dominant rhyme covers {top['final_consistency']*100:.0f}% of derived characters.")


if __name__ == "__main__":
    main()
