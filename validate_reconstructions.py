#!/usr/bin/env python3
"""
Cross-validate Baxter-Sagart (BS) and Zhengzhang Shangfang (ZZ) Old Chinese
reconstructions, and perform several other scholarly validation checks on
the hanzi_etymology.jsonl database.

Outputs:
  - output/validation_report.json  (machine-readable)
  - stdout summary (human-readable)
"""

import json
import re
import random
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

# ─── paths ───────────────────────────────────────────────────────────────────
DB_PATH = Path("/home/catalin/hanzi-etymology-dict/output/hanzi_etymology.jsonl")
REPORT_PATH = Path("/home/catalin/hanzi-etymology-dict/output/validation_report.json")

# ─── phonological classification helpers ─────────────────────────────────────

# Initial-consonant classes (articulatory place of articulation)
# We normalise to a small set: labial, dental, retroflex, palatal, velar,
# laryngeal/glottal, lateral, nasal (only where ambiguous).

LABIAL = set("pbmfβɸʙw")
DENTAL = set("tdnszθðrɾ")
RETROFLEX = set("ʈɖɳʂʐɻ")
PALATAL = set("cɟɲʑɕjʝç")
VELAR = set("kgŋxɣɡɢqʁ")       # includes IPA ɡ (U+0261), ɢ, q, ʁ
LARYNGEAL = set("ʔhɦʕħ")
LATERAL = set("lɬɮ")

def _strip_oc_prefix(form: str) -> str:
    """Remove leading * and any Baxter-Sagart-style pre-initials like
    N-, m., s., C., etc.  We want the *main* initial consonant."""
    form = form.strip().lstrip("*")
    # BS uses prefixes like  m.r, s.t, N-, Cə., etc.  Strip up to last '.' or '-'
    # but keep the rest.  Also strip parenthesized material like (dialect: ...).
    form = re.sub(r"\(.*?\)", "", form)
    # strip whitespace artifacts
    form = form.strip()
    # BS pre-initial notation: segments joined by '.' — take last segment as main syllable
    if "." in form:
        form = form.rsplit(".", 1)[-1]
    # Also strip any remaining leading hyphens from prefix residue
    form = form.lstrip("-")
    # BS bracket notation: [X] means "uncertain X" — strip brackets to reveal the consonant
    form = re.sub(r"\[([^\]]*)\]", r"\1", form)
    return form

def classify_initial(form: str) -> str:
    """Return the place-of-articulation class for the initial consonant of an
    OC reconstruction string (after stripping prefix material)."""
    s = _strip_oc_prefix(form)
    if not s:
        return "unknown"

    # Collect the initial consonant cluster (everything before the first vowel-like char)
    # Vowels in OC notation: a e i o u ə ɑ ɐ ɨ ʉ ɯ ɤ æ ɛ ɔ ʊ ɪ
    vowels = set("aeioəuɑɐɨʉɯɤæɛɔʊɪɒʌyøœ")
    # Also treat ː ˤ ˀ ʰ ʷ and combining diacritics as modifiers, not initials
    modifiers = set("ːˤˀʰʷʲˠˁ'·")
    # Add Unicode combining characters (ring below, ring above, tilde, etc.)
    combining_range = set(chr(c) for c in range(0x0300, 0x0370))
    modifiers |= combining_range

    initial_chars = []
    for ch in s:
        if ch in vowels:
            break
        if ch in modifiers:
            continue
        initial_chars.append(ch)

    if not initial_chars:
        # Starts with a vowel — laryngeal / glottal onset (implicit ʔ or null)
        return "laryngeal"

    # Use the first true consonant character for classification
    c = initial_chars[0]

    # Handle digraphs / special ZZ symbols
    # l̥ (voiceless l) → lateral
    if c == "l" or c == "ɬ" or c == "ɮ":
        return "lateral"
    if c in LABIAL:
        return "labial"
    if c in DENTAL:
        return "dental"
    if c in RETROFLEX:
        return "retroflex"
    if c in PALATAL:
        return "palatal"
    if c in VELAR:
        return "velar"
    if c in LARYNGEAL:
        return "laryngeal"
    if c in LATERAL:
        return "lateral"

    return "unknown"

# Broader grouping: merge retroflex into dental, lateral into dental, etc.
BROAD_MAP = {
    "labial": "labial",
    "dental": "coronal",
    "retroflex": "coronal",
    "lateral": "coronal",
    "palatal": "dorsal",
    "velar": "dorsal",
    "laryngeal": "laryngeal",
    "unknown": "unknown",
}

def broad_class(place: str) -> str:
    return BROAD_MAP.get(place, "unknown")


# ─── tone classification ─────────────────────────────────────────────────────

def classify_tone(form: str) -> str:
    """Determine the OC tone category from the reconstruction.

    In OC reconstructions:
      - Final -ʔ or -ʕ  → rising (上 shǎng)
      - Final -s or -h   → departing (去 qù)
      - Final stop -p -t -k  → entering (入 rù)
      - Otherwise → level (平 píng)

    BS notation quirks:
      - *X-s  means departing tone suffix (hyphen before s)
      - *X[t] means uncertain coda [t]  → entering
      - Parenthesized material (dialect:...) should be ignored
    """
    s = form.strip().lstrip("*")
    # Remove parenthesized glosses
    s = re.sub(r"\(.*?\)", "", s).strip()
    # Strip BS bracket notation to reveal actual segments
    s = re.sub(r"\[([^\]]*)\]", r"\1", s)
    # Remove angle brackets <r> etc.
    s = re.sub(r"<[^>]*>", "", s)
    if not s:
        return "unknown"

    # BS departing tone: final -s (often after hyphen)
    # Check for trailing -s pattern
    if re.search(r"-s$", s):
        return "departing"

    last = s[-1]
    # Check last meaningful character
    if last in ("ʔ", "ʕ"):
        return "rising"
    if last == "s":
        # Final -s without hyphen (ZZ notation) → departing
        return "departing"
    if last == "h":
        return "departing"
    if last in ("p", "t", "k"):
        return "entering"
    if last in ("b", "d", "g", "ɡ", "ɢ"):
        # Voiced stop codas also → entering
        return "entering"
    # ŋ, n, m, vowels, etc → level
    return "level"


# ─── vowel extraction ────────────────────────────────────────────────────────

VOWEL_CHARS = set("aeioəuɑɐɨʉɯɤæɛɔʊɪɒʌyøœ")

def extract_main_vowel(form: str) -> str:
    """Extract the 'nuclear' vowel(s) from an OC form."""
    s = _strip_oc_prefix(form)
    s = re.sub(r"\(.*?\)", "", s).strip()
    vowels = []
    for ch in s:
        if ch in VOWEL_CHARS:
            vowels.append(ch)
    return "".join(vowels) if vowels else ""


def vowel_similar(v1: str, v2: str) -> bool:
    """Rough vowel similarity: do the main vowels share at least one
    vowel character, or map to the same broad category?"""
    if not v1 or not v2:
        return False  # can't compare
    if set(v1) & set(v2):
        return True
    # Map broad classes
    HIGH = set("iɨʉɪyɯ")
    MID = set("eəɤøœɛ")
    LOW = set("aɑɐæɒʌ")
    ROUND = set("oɔuʊʉøœ")

    def vclass(v):
        classes = set()
        for c in v:
            if c in HIGH:
                classes.add("high")
            if c in MID:
                classes.add("mid")
            if c in LOW:
                classes.add("low")
            if c in ROUND:
                classes.add("round")
        return classes

    c1, c2 = vclass(v1), vclass(v2)
    return bool(c1 & c2)


# ─── rhyme similarity for phonetic component validation ──────────────────────

def extract_rhyme(form: str) -> str:
    """Extract the rhyme (vowel + coda) from an OC form for rhyme comparison."""
    s = _strip_oc_prefix(form)
    s = re.sub(r"\(.*?\)", "", s).strip()
    # Find first vowel, return everything from there
    for i, ch in enumerate(s):
        if ch in VOWEL_CHARS:
            return s[i:]
    return ""

def rhyme_distance(r1: str, r2: str) -> float:
    """Simple similarity score for two rhyme strings.  0 = identical, higher = more different.
    Returns a float in [0, 1] where 0 is best match."""
    if not r1 or not r2:
        return 1.0
    # Normalize length markers
    r1 = r1.replace("ː", "").replace("ˤ", "")
    r2 = r2.replace("ː", "").replace("ˤ", "")
    if r1 == r2:
        return 0.0
    # Check if one is a substring of the other
    if r1 in r2 or r2 in r1:
        return 0.2
    # Compare vowel nuclei and codas
    score = 0.0
    v1 = "".join(c for c in r1 if c in VOWEL_CHARS)
    v2 = "".join(c for c in r2 if c in VOWEL_CHARS)
    c1 = "".join(c for c in r1 if c not in VOWEL_CHARS and c not in set("ːˤˀʰʷʲˠˁ"))
    c2 = "".join(c for c in r2 if c not in VOWEL_CHARS and c not in set("ːˤˀʰʷʲˠˁ"))

    # Vowel match
    if v1 and v2:
        if v1 == v2:
            score += 0.0
        elif set(v1) & set(v2):
            score += 0.2
        elif vowel_similar(v1, v2):
            score += 0.4
        else:
            score += 0.6

    # Coda match
    if c1 == c2:
        score += 0.0
    elif c1 and c2:
        # Check same manner
        nasals = set("nmŋɲ")
        stops = set("ptk")
        if (c1[-1] in nasals and c2[-1] in nasals) or (c1[-1] in stops and c2[-1] in stops):
            score += 0.15
        else:
            score += 0.4
    elif c1 or c2:
        score += 0.3

    return min(score, 1.0)


# ─── load database ───────────────────────────────────────────────────────────

def load_db():
    records = {}
    with open(DB_PATH) as f:
        for line in f:
            rec = json.loads(line)
            ch = rec.get("character", "")
            if ch:
                records[ch] = rec
    return records


# ─── Task 1 & 2: BS vs ZZ comparison ────────────────────────────────────────

def compare_bs_zz(records):
    """Find chars with both BS and ZZ reconstructions, compare initial/tone/vowel."""
    results = {
        "total_with_both": 0,
        "initial_agree": 0,
        "initial_broad_agree": 0,
        "initial_disagree": 0,
        "tone_agree": 0,
        "tone_disagree": 0,
        "vowel_similar": 0,
        "vowel_dissimilar": 0,
        "vowel_unknown": 0,
        "significant_divergences": [],
    }

    for ch, rec in records.items():
        hp = rec.get("historical_phonology", [])
        bs_forms = []
        zz_forms = []
        for e in hp:
            if "old_chinese" in e:
                bs_forms.append(e["old_chinese"])
            if "old_chinese_zhengzhang" in e:
                zz_forms.append(e["old_chinese_zhengzhang"])

        if not bs_forms or not zz_forms:
            continue

        results["total_with_both"] += 1

        # Compare the first (primary) form from each system
        bs = bs_forms[0]
        zz = zz_forms[0]

        bs_init = classify_initial(bs)
        zz_init = classify_initial(zz)
        bs_broad = broad_class(bs_init)
        zz_broad = broad_class(zz_init)

        bs_tone = classify_tone(bs)
        zz_tone = classify_tone(zz)

        bs_vowel = extract_main_vowel(bs)
        zz_vowel = extract_main_vowel(zz)

        # Initial agreement
        if bs_init == zz_init:
            results["initial_agree"] += 1
            results["initial_broad_agree"] += 1
        elif bs_broad == zz_broad:
            results["initial_broad_agree"] += 1
            results["initial_disagree"] += 1
        else:
            results["initial_disagree"] += 1
            # This is a significant divergence
            if bs_broad != "unknown" and zz_broad != "unknown":
                results["significant_divergences"].append({
                    "character": ch,
                    "bs_form": bs,
                    "zz_form": zz,
                    "bs_initial_class": bs_init,
                    "zz_initial_class": zz_init,
                    "bs_broad": bs_broad,
                    "zz_broad": zz_broad,
                    "bs_tone": bs_tone,
                    "zz_tone": zz_tone,
                    "divergence_type": "initial_place",
                })

        # Tone agreement
        if bs_tone == zz_tone:
            results["tone_agree"] += 1
        else:
            results["tone_disagree"] += 1
            if bs_tone != "unknown" and zz_tone != "unknown":
                # Check if already in divergences
                existing = [d for d in results["significant_divergences"]
                            if d["character"] == ch]
                if existing:
                    existing[0]["divergence_type"] += "+tone"
                else:
                    results["significant_divergences"].append({
                        "character": ch,
                        "bs_form": bs,
                        "zz_form": zz,
                        "bs_tone": bs_tone,
                        "zz_tone": zz_tone,
                        "divergence_type": "tone",
                    })

        # Vowel similarity
        if bs_vowel and zz_vowel:
            if vowel_similar(bs_vowel, zz_vowel):
                results["vowel_similar"] += 1
            else:
                results["vowel_dissimilar"] += 1
        else:
            results["vowel_unknown"] += 1

    # Compute rates
    t = results["total_with_both"]
    if t > 0:
        results["initial_exact_agree_rate"] = round(results["initial_agree"] / t, 4)
        results["initial_broad_agree_rate"] = round(results["initial_broad_agree"] / t, 4)
        results["tone_agree_rate"] = round(results["tone_agree"] / t, 4)
        v_total = results["vowel_similar"] + results["vowel_dissimilar"]
        if v_total:
            results["vowel_similarity_rate"] = round(results["vowel_similar"] / v_total, 4)

    # Limit divergences list for report
    results["significant_divergences_count"] = len(results["significant_divergences"])
    results["significant_divergences"] = results["significant_divergences"][:100]

    return results


# ─── Task 3: Classical-only entry analysis ───────────────────────────────────

def analyse_classical_only(records):
    """For the ~4,367 classical-only entries, check Shuowen claims, OC data, etc."""
    results = {
        "total_classical_only": 0,
        "has_shuowen": 0,
        "has_shuowen_formation_claim": 0,
        "has_shuowen_phono_semantic": 0,
        "has_wiktionary_notes": 0,
        "has_oc_reconstruction": 0,
        "phono_semantic_with_oc": 0,
        "phonetic_rhyme_validated": 0,
        "phonetic_rhyme_failed": 0,
        "phonetic_rhyme_no_data": 0,
        "sample_validations": [],
        "sample_failures": [],
    }

    for ch, rec in records.items():
        if rec.get("verification_status") != "classical-only":
            continue
        results["total_classical_only"] += 1

        sw = rec.get("shuowen")
        if sw:
            results["has_shuowen"] += 1
            expl = sw.get("explanation", "")
            # Check for formation type claims
            if "聲" in expl or "从" in expl or "象形" in expl or "指事" in expl:
                results["has_shuowen_formation_claim"] += 1
            # Specifically phono-semantic (X聲)
            if "聲" in expl:
                results["has_shuowen_phono_semantic"] += 1

                # Try to extract the claimed phonetic component
                # Pattern: 从X Y聲 or 从X从Y Y聲
                phonetic_match = re.search(r"(\S)聲", expl)
                phonetic_comp = phonetic_match.group(1) if phonetic_match else None

                # Check if we have OC data for both char and phonetic
                hp = rec.get("historical_phonology", [])
                char_oc = None
                for e in hp:
                    oc = e.get("old_chinese_zhengzhang") or e.get("old_chinese")
                    if oc:
                        char_oc = oc
                        break

                if char_oc and phonetic_comp:
                    results["phono_semantic_with_oc"] += 1
                    # Get OC for the phonetic component
                    comp_rec = records.get(phonetic_comp)
                    comp_oc = None
                    if comp_rec:
                        for e in comp_rec.get("historical_phonology", []):
                            oc = e.get("old_chinese_zhengzhang") or e.get("old_chinese")
                            if oc:
                                comp_oc = oc
                                break

                    if comp_oc:
                        char_rhyme = extract_rhyme(char_oc)
                        comp_rhyme = extract_rhyme(comp_oc)
                        dist = rhyme_distance(char_rhyme, comp_rhyme)
                        if dist <= 0.5:
                            results["phonetic_rhyme_validated"] += 1
                            if len(results["sample_validations"]) < 20:
                                results["sample_validations"].append({
                                    "character": ch,
                                    "phonetic_component": phonetic_comp,
                                    "char_oc": char_oc,
                                    "comp_oc": comp_oc,
                                    "rhyme_distance": round(dist, 3),
                                    "shuowen": expl[:80],
                                })
                        else:
                            results["phonetic_rhyme_failed"] += 1
                            if len(results["sample_failures"]) < 20:
                                results["sample_failures"].append({
                                    "character": ch,
                                    "phonetic_component": phonetic_comp,
                                    "char_oc": char_oc,
                                    "comp_oc": comp_oc,
                                    "rhyme_distance": round(dist, 3),
                                    "shuowen": expl[:80],
                                })
                    else:
                        results["phonetic_rhyme_no_data"] += 1
                elif not char_oc:
                    results["phonetic_rhyme_no_data"] += 1

        # Wiktionary notes
        en = rec.get("etymology_notes", [])
        if any("wiktionary" in e.get("source", "") or "wikt" in e.get("source", "")
               for e in en):
            results["has_wiktionary_notes"] += 1

        # OC reconstruction
        hp = rec.get("historical_phonology", [])
        if hp:
            results["has_oc_reconstruction"] += 1

    # Rates
    t = results["total_classical_only"]
    if t > 0:
        results["shuowen_coverage_rate"] = round(results["has_shuowen"] / t, 4)
        results["oc_coverage_rate"] = round(results["has_oc_reconstruction"] / t, 4)
        results["wiktionary_coverage_rate"] = round(results["has_wiktionary_notes"] / t, 4)
    ps = results["phono_semantic_with_oc"]
    validated = results["phonetic_rhyme_validated"]
    failed = results["phonetic_rhyme_failed"]
    if validated + failed > 0:
        results["phonetic_validation_rate"] = round(validated / (validated + failed), 4)

    return results


# ─── Task 4: Validate inferred formation types ──────────────────────────────

def validate_inferred_formations(records):
    """Sample 500 inferred formation types, check against Shuowen/Wiktionary."""
    # Collect all inferred characters
    inferred_chars = []
    for ch, rec in records.items():
        fd = rec.get("formation_details", {})
        if fd and fd.get("inferred"):
            inferred_chars.append(ch)

    results = {
        "total_inferred": len(inferred_chars),
        "sample_size": 0,
        "has_shuowen_claim": 0,
        "has_wiktionary_claim": 0,
        "has_any_external_claim": 0,
        "agree_with_shuowen": 0,
        "disagree_with_shuowen": 0,
        "agree_with_wiktionary": 0,
        "disagree_with_wiktionary": 0,
        "sample_agreements": [],
        "sample_disagreements": [],
    }

    random.seed(42)
    sample = random.sample(inferred_chars, min(500, len(inferred_chars)))
    results["sample_size"] = len(sample)

    for ch in sample:
        rec = records[ch]
        ft = rec.get("formation_type", "")
        fd = rec.get("formation_details", {})
        sw = rec.get("shuowen")
        conflict = rec.get("formation_type_conflict", {})

        # Check Shuowen
        sw_ft = None
        if sw:
            expl = sw.get("explanation", "")
            if "聲" in expl:
                sw_ft = "phono-semantic"
            elif "象形" in expl:
                sw_ft = "pictographic"
            elif "指事" in expl:
                sw_ft = "indicative"
            elif "从" in expl:
                sw_ft = "ideographic"  # 会意 (compound ideograph)

        # Check conflict dict for Shuowen / Wiktionary claims
        sw_claim = conflict.get("shuowen_jiezi") or sw_ft
        wikt_claim = conflict.get("wiktionary")

        if sw_claim:
            results["has_shuowen_claim"] += 1
            results["has_any_external_claim"] += 1
            if ft == sw_claim:
                results["agree_with_shuowen"] += 1
                if len(results["sample_agreements"]) < 10:
                    results["sample_agreements"].append({
                        "character": ch,
                        "inferred": ft,
                        "shuowen_claim": sw_claim,
                        "status": "agree",
                    })
            else:
                results["disagree_with_shuowen"] += 1
                if len(results["sample_disagreements"]) < 15:
                    results["sample_disagreements"].append({
                        "character": ch,
                        "inferred": ft,
                        "shuowen_claim": sw_claim,
                        "shuowen_text": sw.get("explanation", "")[:100] if sw else "",
                        "status": "disagree_shuowen",
                    })

        if wikt_claim:
            results["has_wiktionary_claim"] += 1
            if not sw_claim:
                results["has_any_external_claim"] += 1
            if ft == wikt_claim:
                results["agree_with_wiktionary"] += 1
            else:
                results["disagree_with_wiktionary"] += 1
                if len(results["sample_disagreements"]) < 15:
                    results["sample_disagreements"].append({
                        "character": ch,
                        "inferred": ft,
                        "wiktionary_claim": wikt_claim,
                        "status": "disagree_wiktionary",
                    })

    # Rates
    if results["has_shuowen_claim"] > 0:
        results["shuowen_agreement_rate"] = round(
            results["agree_with_shuowen"] / results["has_shuowen_claim"], 4)
    if results["has_wiktionary_claim"] > 0:
        results["wiktionary_agreement_rate"] = round(
            results["agree_with_wiktionary"] / results["has_wiktionary_claim"], 4)
    if results["has_any_external_claim"] > 0:
        total_agree = results["agree_with_shuowen"] + results["agree_with_wiktionary"]
        total_claims = results["has_shuowen_claim"] + results["has_wiktionary_claim"]
        results["overall_external_agreement_rate"] = round(total_agree / total_claims, 4) if total_claims else None

    return results


# ─── Task 5: Adjudicate phonetic component disagreements ────────────────────

def adjudicate_phonetic_disagreements(records):
    """For chars where ytenx and MakeMe/Dong disagree on phonetic component,
    use OC rhyme similarity to pick a winner."""

    results = {
        "total_disagreements": 0,
        "could_adjudicate": 0,
        "could_not_adjudicate": 0,
        "ytenx_wins": 0,
        "makeme_dong_wins": 0,
        "ties": 0,
        "sample_adjudications": [],
    }

    for ch, rec in records.items():
        fd = rec.get("formation_details", {})
        if not fd:
            continue
        py = fd.get("phonetic_component_ytenx", "")
        pm = fd.get("phonetic", "")  # MakeMe/Dong phonetic

        if not py or not pm or py == pm:
            continue

        results["total_disagreements"] += 1

        # Get OC for the character itself
        hp = rec.get("historical_phonology", [])
        char_oc_forms = []
        for e in hp:
            oc = e.get("old_chinese_zhengzhang") or e.get("old_chinese")
            if oc:
                char_oc_forms.append(oc)
        if not char_oc_forms:
            results["could_not_adjudicate"] += 1
            continue

        char_rhymes = [extract_rhyme(f) for f in char_oc_forms]
        char_rhymes = [r for r in char_rhymes if r]
        if not char_rhymes:
            results["could_not_adjudicate"] += 1
            continue

        # Get OC for ytenx phonetic component
        ytenx_rec = records.get(py)
        ytenx_rhymes = []
        if ytenx_rec:
            for e in ytenx_rec.get("historical_phonology", []):
                oc = e.get("old_chinese_zhengzhang") or e.get("old_chinese")
                if oc:
                    r = extract_rhyme(oc)
                    if r:
                        ytenx_rhymes.append(r)

        # Get OC for MakeMe/Dong phonetic component
        makeme_rec = records.get(pm)
        makeme_rhymes = []
        if makeme_rec:
            for e in makeme_rec.get("historical_phonology", []):
                oc = e.get("old_chinese_zhengzhang") or e.get("old_chinese")
                if oc:
                    r = extract_rhyme(oc)
                    if r:
                        makeme_rhymes.append(r)

        if not ytenx_rhymes and not makeme_rhymes:
            results["could_not_adjudicate"] += 1
            continue

        # Calculate best rhyme distance for each candidate
        def best_distance(comp_rhymes, char_rhymes):
            if not comp_rhymes:
                return 1.0
            best = 1.0
            for cr in char_rhymes:
                for pr in comp_rhymes:
                    d = rhyme_distance(cr, pr)
                    best = min(best, d)
            return best

        y_dist = best_distance(ytenx_rhymes, char_rhymes)
        m_dist = best_distance(makeme_rhymes, char_rhymes)

        results["could_adjudicate"] += 1

        winner = None
        if abs(y_dist - m_dist) < 0.05:
            results["ties"] += 1
            winner = "tie"
        elif y_dist < m_dist:
            results["ytenx_wins"] += 1
            winner = "ytenx"
        else:
            results["makeme_dong_wins"] += 1
            winner = "makeme_dong"

        if len(results["sample_adjudications"]) < 30:
            results["sample_adjudications"].append({
                "character": ch,
                "ytenx_phonetic": py,
                "makeme_dong_phonetic": pm,
                "char_oc": char_oc_forms[0],
                "ytenx_comp_oc": ytenx_rhymes[0] if ytenx_rhymes else None,
                "makeme_comp_oc": makeme_rhymes[0] if makeme_rhymes else None,
                "ytenx_rhyme_dist": round(y_dist, 3),
                "makeme_rhyme_dist": round(m_dist, 3),
                "winner": winner,
            })

    # Rates
    adj = results["could_adjudicate"]
    if adj:
        results["ytenx_win_rate"] = round(results["ytenx_wins"] / adj, 4)
        results["makeme_dong_win_rate"] = round(results["makeme_dong_wins"] / adj, 4)
        results["tie_rate"] = round(results["ties"] / adj, 4)

    return results


# ─── Main ────────────────────────────────────────────────────────────────────

def main():
    print("Loading database...")
    records = load_db()
    print(f"  Loaded {len(records)} records.\n")

    # Task 1 & 2: BS vs ZZ
    print("=" * 72)
    print("TASK 1 & 2: Baxter-Sagart vs Zhengzhang cross-validation")
    print("=" * 72)
    bs_zz = compare_bs_zz(records)
    t = bs_zz["total_with_both"]
    print(f"  Characters with both BS and ZZ reconstructions: {t}")
    print(f"  Initial consonant (exact place) agreement:  "
          f"{bs_zz['initial_agree']}/{t}  = {bs_zz.get('initial_exact_agree_rate', 0):.1%}")
    print(f"  Initial consonant (broad class) agreement:  "
          f"{bs_zz['initial_broad_agree']}/{t}  = {bs_zz.get('initial_broad_agree_rate', 0):.1%}")
    print(f"  Tone category agreement:                    "
          f"{bs_zz['tone_agree']}/{t}  = {bs_zz.get('tone_agree_rate', 0):.1%}")
    vt = bs_zz["vowel_similar"] + bs_zz["vowel_dissimilar"]
    print(f"  Vowel similarity (where comparable):        "
          f"{bs_zz['vowel_similar']}/{vt}  = {bs_zz.get('vowel_similarity_rate', 0):.1%}")
    print(f"  Significant divergences (broad initial mismatch): "
          f"{bs_zz['significant_divergences_count']}")
    if bs_zz["significant_divergences"]:
        print(f"\n  Sample divergences (first 10):")
        for d in bs_zz["significant_divergences"][:10]:
            print(f"    {d['character']}  BS: {d['bs_form']:20s}  ZZ: {d['zz_form']:20s}  "
                  f"BS={d.get('bs_broad','?'):10s}  ZZ={d.get('zz_broad','?'):10s}  "
                  f"type={d['divergence_type']}")

    # Task 3: Classical-only
    print(f"\n{'=' * 72}")
    print("TASK 3: Classical-only entries analysis")
    print("=" * 72)
    classical = analyse_classical_only(records)
    ct = classical["total_classical_only"]
    print(f"  Total classical-only entries: {ct}")
    print(f"  Have Shuowen data:           {classical['has_shuowen']}  "
          f"({classical.get('shuowen_coverage_rate', 0):.1%})")
    print(f"  Have Shuowen formation claim: {classical['has_shuowen_formation_claim']}")
    print(f"  Have Shuowen phono-semantic:  {classical['has_shuowen_phono_semantic']}")
    print(f"  Have Wiktionary notes:        {classical['has_wiktionary_notes']}  "
          f"({classical.get('wiktionary_coverage_rate', 0):.1%})")
    print(f"  Have OC reconstruction:       {classical['has_oc_reconstruction']}  "
          f"({classical.get('oc_coverage_rate', 0):.1%})")
    print(f"\n  Phono-semantic validation (Shuowen claim vs OC rhyme):")
    print(f"    Testable (char + phonetic both have OC): {classical['phono_semantic_with_oc']}")
    v = classical["phonetic_rhyme_validated"]
    f_ = classical["phonetic_rhyme_failed"]
    print(f"    Rhyme validated:  {v}")
    print(f"    Rhyme failed:     {f_}")
    if v + f_ > 0:
        print(f"    Validation rate:  {classical.get('phonetic_validation_rate', 0):.1%}")
    print(f"    No OC data:       {classical['phonetic_rhyme_no_data']}")

    if classical["sample_validations"]:
        print(f"\n  Sample validated phono-semantic claims:")
        for s in classical["sample_validations"][:5]:
            print(f"    {s['character']} (phonetic={s['phonetic_component']})  "
                  f"char_OC={s['char_oc']}  comp_OC={s['comp_oc']}  "
                  f"dist={s['rhyme_distance']:.3f}")
    if classical["sample_failures"]:
        print(f"\n  Sample failed phono-semantic claims (potential Shuowen errors):")
        for s in classical["sample_failures"][:5]:
            print(f"    {s['character']} (phonetic={s['phonetic_component']})  "
                  f"char_OC={s['char_oc']}  comp_OC={s['comp_oc']}  "
                  f"dist={s['rhyme_distance']:.3f}  sw={s['shuowen'][:50]}")

    # Task 4: Inferred formation types
    print(f"\n{'=' * 72}")
    print("TASK 4: Inferred formation type validation")
    print("=" * 72)
    inferred = validate_inferred_formations(records)
    print(f"  Total inferred formation types: {inferred['total_inferred']}")
    print(f"  Sample size: {inferred['sample_size']}")
    print(f"  Have Shuowen claim:    {inferred['has_shuowen_claim']}")
    print(f"  Have Wiktionary claim: {inferred['has_wiktionary_claim']}")
    print(f"  Have any external:     {inferred['has_any_external_claim']}")
    if inferred["has_shuowen_claim"]:
        print(f"  Agree with Shuowen:    {inferred['agree_with_shuowen']}/{inferred['has_shuowen_claim']}  "
              f"= {inferred.get('shuowen_agreement_rate', 0):.1%}")
        print(f"  Disagree with Shuowen: {inferred['disagree_with_shuowen']}/{inferred['has_shuowen_claim']}")
    if inferred["has_wiktionary_claim"]:
        print(f"  Agree with Wiktionary:    {inferred['agree_with_wiktionary']}/{inferred['has_wiktionary_claim']}  "
              f"= {inferred.get('wiktionary_agreement_rate', 0):.1%}")
        print(f"  Disagree with Wiktionary: {inferred['disagree_with_wiktionary']}/{inferred['has_wiktionary_claim']}")
    if inferred.get("overall_external_agreement_rate") is not None:
        print(f"  Overall external agreement rate: {inferred['overall_external_agreement_rate']:.1%}")

    if inferred["sample_disagreements"]:
        print(f"\n  Sample disagreements (inferred vs external):")
        for s in inferred["sample_disagreements"][:10]:
            ext = s.get("shuowen_claim") or s.get("wiktionary_claim", "?")
            print(f"    {s['character']}  inferred={s['inferred']:15s}  "
                  f"external={ext:15s}  source={s['status']}")

    # Task 5: Phonetic component adjudication
    print(f"\n{'=' * 72}")
    print("TASK 5: Phonetic component disagreement adjudication")
    print("=" * 72)
    phonetic = adjudicate_phonetic_disagreements(records)
    print(f"  Total ytenx vs MakeMe/Dong disagreements: {phonetic['total_disagreements']}")
    print(f"  Could adjudicate (OC data available):     {phonetic['could_adjudicate']}")
    print(f"  Could not adjudicate (no OC data):        {phonetic['could_not_adjudicate']}")
    adj = phonetic["could_adjudicate"]
    if adj:
        print(f"\n  Results:")
        print(f"    ytenx wins:       {phonetic['ytenx_wins']}  "
              f"({phonetic.get('ytenx_win_rate', 0):.1%})")
        print(f"    MakeMe/Dong wins: {phonetic['makeme_dong_wins']}  "
              f"({phonetic.get('makeme_dong_win_rate', 0):.1%})")
        print(f"    Ties:             {phonetic['ties']}  "
              f"({phonetic.get('tie_rate', 0):.1%})")

    if phonetic["sample_adjudications"]:
        print(f"\n  Sample adjudications:")
        for s in phonetic["sample_adjudications"][:10]:
            print(f"    {s['character']}  ytenx={s['ytenx_phonetic']}(d={s['ytenx_rhyme_dist']:.2f})  "
                  f"makeme={s['makeme_dong_phonetic']}(d={s['makeme_rhyme_dist']:.2f})  "
                  f"-> {s['winner']}")

    # ─── Build and save report ───────────────────────────────────────────
    report = {
        "bs_zz_comparison": bs_zz,
        "classical_only_analysis": classical,
        "inferred_formation_validation": inferred,
        "phonetic_disagreement_adjudication": phonetic,
        "summary": {
            "bs_zz_broad_initial_agreement": bs_zz.get("initial_broad_agree_rate"),
            "bs_zz_tone_agreement": bs_zz.get("tone_agree_rate"),
            "bs_zz_vowel_similarity": bs_zz.get("vowel_similarity_rate"),
            "bs_zz_significant_divergences": bs_zz["significant_divergences_count"],
            "classical_only_shuowen_phonetic_validation_rate": classical.get("phonetic_validation_rate"),
            "inferred_shuowen_agreement_rate": inferred.get("shuowen_agreement_rate"),
            "inferred_wiktionary_agreement_rate": inferred.get("wiktionary_agreement_rate"),
            "phonetic_adjudication_ytenx_win_rate": phonetic.get("ytenx_win_rate"),
            "phonetic_adjudication_makeme_win_rate": phonetic.get("makeme_dong_win_rate"),
        },
    }

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(REPORT_PATH, "w") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print(f"\n{'=' * 72}")
    print(f"Report saved to: {REPORT_PATH}")
    print("=" * 72)


if __name__ == "__main__":
    main()
