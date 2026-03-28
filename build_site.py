#!/usr/bin/env python3
"""Build the static site data for GitHub Pages (docs/ folder)."""

import json
import gzip
from pathlib import Path


def main():
    print("Building site data for docs/...")
    docs = Path("docs")
    docs.mkdir(exist_ok=True)

    records = []
    with open("output/hanzi_etymology.jsonl", "r", encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            if not (r.get("definitions") or r.get("etymology_notes") or r.get("formation_type")):
                continue

            compact = {"c": r["character"], "p": r.get("codepoint", "")}
            rd = r.get("readings", {})
            if rd.get("mandarin"): compact["py"] = rd["mandarin"]
            if rd.get("cantonese"): compact["ca"] = rd["cantonese"]
            if r.get("definitions"): compact["d"] = r["definitions"]
            if r.get("formation_type"): compact["ft"] = r["formation_type"]
            fd = r.get("formation_details", {})
            if fd.get("semantic"): compact["sem"] = fd["semantic"]
            if fd.get("phonetic"): compact["phon"] = fd["phonetic"]
            if r.get("ids") or r.get("decomposition_ids"):
                compact["ids"] = r.get("ids") or r.get("decomposition_ids")
            if r.get("etymology_notes"):
                compact["en"] = [
                    {"s": n["source"], "t": n["text"][:500],
                     **({" v": n["via_traditional"]} if n.get("via_traditional") else {}),
                     **({"w": 1} if n.get("caveat") else {})}
                    for n in r["etymology_notes"][:5]
                ]
            sw = r.get("shuowen", {})
            if sw.get("explanation"):
                compact["sw"] = sw["explanation"]
                if sw.get("english"): compact["swe"] = sw["english"]
                if sw.get("modern_correction"): compact["swc"] = sw["modern_correction"]
                if sw.get("pronunciation_fanqie"): compact["swf"] = sw["pronunciation_fanqie"]
            ph = r.get("historical_phonology", [])
            if ph: compact["hp"] = ph[:4]
            gy = r.get("guangyun", [])
            if gy: compact["gy"] = gy[:3]
            if r.get("formation_type_conflict"): compact["ftc"] = r["formation_type_conflict"]
            if r.get("confidence"): compact["conf"] = r["confidence"]
            if r.get("verification_status"): compact["vs"] = r["verification_status"]
            if r.get("frequency_rank"): compact["fr"] = r["frequency_rank"]
            if r.get("hsk3_level"): compact["hsk"] = r["hsk3_level"]
            elif r.get("hsk_level"): compact["hsk"] = r["hsk_level"]
            if r.get("semantic_field"): compact["sf"] = r["semantic_field"]
            if r.get("phonetic_family"): compact["pf"] = r["phonetic_family"][:20]
            if r.get("sino_tibetan_cognates"): compact["stc"] = r["sino_tibetan_cognates"]
            lg = r.get("local_glyphs", {})
            if lg: compact["lg"] = lg
            kx = r.get("kangxi", {})
            if kx.get("fanqie_citations"): compact["kxf"] = kx["fanqie_citations"]
            if r.get("shuowen_accuracy"): compact["sa"] = r["shuowen_accuracy"]
            if r.get("total_strokes"): compact["str"] = r["total_strokes"]
            if r.get("radical_stroke"): compact["rs"] = r["radical_stroke"]
            v = r.get("variants", {})
            if v: compact["var"] = v
            for k, sk in [("japanese_on", "jo"), ("japanese_kun", "jk"),
                          ("korean", "ko"), ("vietnamese", "vi")]:
                if rd.get(k): compact[sk] = rd[k]

            records.append(compact)

    data = json.dumps(records, ensure_ascii=False, separators=(",", ":"))
    with gzip.open(docs / "data.json.gz", "wb") as f:
        f.write(data.encode("utf-8"))

    import os
    import shutil
    gz = os.path.getsize(docs / "data.json.gz")
    print(f"  {len(records)} records, {gz/1024/1024:.1f} MB gzipped")

    # Copy Dong Chinese glyph SVGs if available
    dong_src = Path("output/glyphs/dong_chinese")
    dong_dst = docs / "glyphs" / "dong_chinese"
    if dong_src.exists():
        if dong_dst.exists():
            shutil.rmtree(dong_dst)
        shutil.copytree(dong_src, dong_dst)
        n_dirs = sum(1 for d in dong_dst.iterdir() if d.is_dir())
        print(f"  Copied {n_dirs} character glyph folders to docs/glyphs/")


if __name__ == "__main__":
    main()
