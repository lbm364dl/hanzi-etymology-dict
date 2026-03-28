#!/usr/bin/env python3
"""
Translate Shuowen Jiezi explanations from classical Chinese to English.

Uses the character's own English definition + structural pattern parsing.
Outputs shuowen_translations.json for integration into the build pipeline.
"""

import json
import re


def load_char_glosses():
    """Load single-character definitions from the database."""
    glosses = {}
    with open("output/hanzi_etymology.jsonl", "r", encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            ch = r["character"]
            defs = r.get("definitions", "")
            if defs and len(ch) == 1:
                first = defs.split(";")[0].split(",")[0].strip()
                glosses[ch] = first
    return glosses


def gloss(ch, glosses):
    """Get a short English gloss for a character."""
    return glosses.get(ch, ch)


def comp_gloss(comp, glosses):
    """Translate a component: '水' -> '水 (water)'."""
    comp = comp.strip()
    if not comp:
        return ""
    main = comp[0]
    g = glosses.get(main, "")
    if g and g != main:
        return f"{comp} \"{g}\""
    return comp


def translate_shuowen(explanation, character, glosses):
    """Translate a Shuowen explanation to English."""
    if not explanation:
        return ""

    parts = []
    remaining = explanation

    # 1. Definition section: "X也。" -> use the character's English definition
    eng_def = glosses.get(character, "")
    defs_found = []
    while True:
        m = re.match(r'^([^。]{1,15}?)也[。，]?\s*', remaining)
        if not m:
            break
        def_text = m.group(1).strip()
        if '从' in def_text:
            break
        defs_found.append(def_text)
        remaining = remaining[m.end():]
        if len(defs_found) >= 3:
            break

    if defs_found:
        # Translate each short definition using glosses
        def_parts = []
        for dt in defs_found:
            if len(dt) <= 4:
                chars = [gloss(c, glosses) for c in dt
                         if c not in '之也者所以的' and ord(c) > 0x2E00]
                if chars:
                    def_parts.append(", ".join(chars))
                else:
                    def_parts.append(dt)
            else:
                def_parts.append(dt)
        if eng_def:
            parts.append(f'"{eng_def}." (Shuowen glosses: {"; ".join(def_parts)})')
        else:
            parts.append(f'Shuowen glosses: {"; ".join(def_parts)}.')
    elif eng_def:
        parts.append(f'"{eng_def}."')

    # 2. Pictographic: 象X之形 / 象X形
    m_pict = re.search(r'象(.+?)之?形', remaining)
    if m_pict:
        depicted_raw = m_pict.group(1)
        # Translate depicted thing
        dep_words = []
        for ch in depicted_raw:
            if ord(ch) > 0x2E00:
                dep_words.append(gloss(ch, glosses))
            elif ch not in '，。、':
                dep_words.append(ch)
        parts.append(f"Pictograph depicting {' '.join(dep_words)}.")

    # 3. Phono-semantic: 从X，Y聲 / 从X Y聲 / Y省聲 / Y亦聲
    m_ps = re.search(r'从([^，。从聲]{1,6})[，、\s]([^，。从]{1,6}?)(?:省聲|亦聲|聲)', remaining)
    if m_ps:
        sem = m_ps.group(1).strip()
        phon = m_ps.group(2).strip().rstrip('省亦')
        sem_g = comp_gloss(sem, glosses)
        phon_g = comp_gloss(phon, glosses)
        match_text = remaining[m_ps.start():m_ps.end()]
        if '亦聲' in match_text:
            parts.append(f"Semantic-phonetic compound: {sem_g} (meaning) + {phon_g} (meaning and sound).")
        elif '省聲' in match_text:
            parts.append(f"Semantic-phonetic compound: {sem_g} (meaning) + abbreviated {phon_g} (sound).")
        else:
            parts.append(f"Semantic-phonetic compound: {sem_g} (meaning) + {phon_g} (sound).")
    elif not m_pict:
        # 4. Ideographic compound: 从X从Y / 从X，Y
        froms = re.findall(r'从([^，。从聲\s]{1,4})', remaining)
        if len(froms) >= 2:
            comp_strs = [comp_gloss(f, glosses) for f in froms]
            parts.append(f"Ideographic compound: {' + '.join(comp_strs)}.")
        elif len(froms) == 1:
            parts.append(f"From {comp_gloss(froms[0], glosses)}.")

    # 5. Radical: 凡X之屬皆从X
    m_rad = re.search(r'凡(.{1,3})之屬皆从', remaining)
    if m_rad:
        rad = m_rad.group(1)
        parts.append(f"Radical: all characters in the {gloss(rad, glosses)} ({rad}) group contain this element.")

    # 6. Alternative: 一曰X
    m_alt = re.search(r'一曰(.+?)(?:[。]|$)', remaining)
    if m_alt:
        alt_text = m_alt.group(1).strip()
        if len(alt_text) <= 8:
            alt_words = [gloss(c, glosses) for c in alt_text
                         if ord(c) > 0x2E00 and c not in '之也者']
            if alt_words:
                parts.append(f"Also means: {', '.join(alt_words)}.")

    # 7. Pronunciation: 讀若X
    m_read = re.search(r'讀若(\S+)', remaining)
    if m_read:
        read_ch = m_read.group(1)[0]
        parts.append(f"Pronounced like {m_read.group(1)} ({gloss(read_ch, glosses)}).")

    return " ".join(parts)


def main():
    print("Translating Shuowen Jiezi entries...")
    glosses = load_char_glosses()
    print(f"  Loaded {len(glosses)} character glosses")

    translations = {}
    count = 0

    with open("output/hanzi_etymology.jsonl", "r", encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            sw = r.get("shuowen", {})
            expl = sw.get("explanation", "")
            if not expl:
                continue
            english = translate_shuowen(expl, r["character"], glosses)
            if english:
                translations[r["character"]] = english
                count += 1

    print(f"  Translated {count} entries")

    with open("output/shuowen_translations.json", "w", encoding="utf-8") as f:
        json.dump(translations, ensure_ascii=False, indent=0, fp=f)

    samples = ["一", "人", "水", "河", "好", "馬", "休", "明", "愛", "龍",
               "的", "日", "犬", "林", "東"]
    print("\nSamples:")
    for ch in samples:
        if ch in translations:
            with open("output/hanzi_etymology.jsonl", "r", encoding="utf-8") as f:
                for line in f:
                    r = json.loads(line)
                    if r["character"] == ch:
                        orig = r.get("shuowen", {}).get("explanation", "")
                        print(f"\n  {ch}: {orig}")
                        print(f"  EN: {translations[ch]}")
                        break


if __name__ == "__main__":
    main()
