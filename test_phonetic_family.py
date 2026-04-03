"""Tests for the phonetic/semantic series and siblings building logic."""

from collections import defaultdict

# Subset of radical_variants from build_database.py
RADICAL_VARIANTS = {
    "亻": "人", "氵": "水", "扌": "手", "忄": "心", "犭": "犬",
    "礻": "示", "衤": "衣", "饣": "食", "钅": "金", "纟": "糸",
    "讠": "言", "刂": "刀", "灬": "火", "攵": "攴", "糹": "糸",
}


def build_series_and_siblings(merged, radical_variants=None):
    """Replica of the post-merge logic from build_database.py."""
    if radical_variants is None:
        radical_variants = RADICAL_VARIANTS

    canonical_to_variants = defaultdict(set)
    for variant, canonical in radical_variants.items():
        canonical_to_variants[canonical].add(variant)

    phonetic_to_chars = defaultdict(set)
    semantic_to_chars = defaultdict(set)
    for ch, record in merged.items():
        fd = record.get("formation_details", {})
        phon = fd.get("phonetic")
        sem = fd.get("semantic")
        if phon:
            canon = radical_variants.get(phon, phon)
            phonetic_to_chars[canon].add(ch)
        if sem:
            canon = radical_variants.get(sem, sem)
            semantic_to_chars[canon].add(ch)

    def get_series(ch, comp_to_chars):
        canon = radical_variants.get(ch, ch)
        derivs = set()
        if canon == ch:
            derivs |= comp_to_chars.get(ch, set())
            for var in canonical_to_variants.get(ch, set()):
                derivs |= comp_to_chars.get(var, set())
        else:
            derivs |= comp_to_chars.get(canon, set())
        return derivs

    def get_siblings(comp, comp_to_chars):
        canon = radical_variants.get(comp, comp)
        return comp_to_chars.get(canon, set())

    for ch, record in merged.items():
        fd = record.get("formation_details", {})
        derivs = get_series(ch, phonetic_to_chars)
        if derivs:
            record["phonetic_series"] = sorted(derivs)[:30]
        derivs = get_series(ch, semantic_to_chars)
        if derivs:
            record["semantic_series"] = sorted(derivs)[:30]
        phon = fd.get("phonetic")
        if phon:
            siblings = get_siblings(phon, phonetic_to_chars) - {ch}
            if siblings:
                record["phonetic_siblings"] = sorted(siblings)[:30]
        sem = fd.get("semantic")
        if sem:
            siblings = get_siblings(sem, semantic_to_chars) - {ch}
            if siblings:
                record["semantic_siblings"] = sorted(siblings)[:30]


def test_phonetic_series():
    """工 is the phonetic in 功, 攻, 江 → phonetic series on 工."""
    merged = {
        "工": {"formation_details": {}},
        "功": {"formation_details": {"semantic": "力", "phonetic": "工"}},
        "攻": {"formation_details": {"semantic": "攵", "phonetic": "工"}},
        "江": {"formation_details": {"semantic": "氵", "phonetic": "工"}},
    }
    build_series_and_siblings(merged)

    assert set(merged["工"]["phonetic_series"]) == {"功", "攻", "江"}
    assert "phonetic_series" not in merged["功"]


def test_semantic_series():
    """糹 is the semantic in 繼, 細, 絲 → semantic series on 糹."""
    merged = {
        "糹": {"formation_details": {}},
        "繼": {"formation_details": {"semantic": "糹", "phonetic": "㡭"}},
        "細": {"formation_details": {"semantic": "糹", "phonetic": "田"}},
        "絲": {"formation_details": {"semantic": "糹", "phonetic": "糸"}},
    }
    build_series_and_siblings(merged)

    assert set(merged["糹"]["semantic_series"]) == {"繼", "細", "絲"}
    assert "semantic_series" not in merged["繼"]


def test_phonetic_siblings():
    """功, 攻, 江 all have phonetic 工 → they are phonetic siblings of each other."""
    merged = {
        "工": {"formation_details": {}},
        "功": {"formation_details": {"semantic": "力", "phonetic": "工"}},
        "攻": {"formation_details": {"semantic": "攵", "phonetic": "工"}},
        "江": {"formation_details": {"semantic": "氵", "phonetic": "工"}},
    }
    build_series_and_siblings(merged)

    assert set(merged["功"]["phonetic_siblings"]) == {"攻", "江"}
    assert set(merged["攻"]["phonetic_siblings"]) == {"功", "江"}
    assert set(merged["江"]["phonetic_siblings"]) == {"功", "攻"}
    assert "phonetic_siblings" not in merged["工"]


def test_semantic_siblings():
    """河, 海, 湖 all have semantic 氵 → they are semantic siblings of each other."""
    merged = {
        "氵": {"formation_details": {}},
        "河": {"formation_details": {"semantic": "氵", "phonetic": "可"}},
        "海": {"formation_details": {"semantic": "氵", "phonetic": "每"}},
        "湖": {"formation_details": {"semantic": "氵", "phonetic": "胡"}},
    }
    build_series_and_siblings(merged)

    assert set(merged["河"]["semantic_siblings"]) == {"海", "湖"}
    assert set(merged["海"]["semantic_siblings"]) == {"河", "湖"}
    assert set(merged["湖"]["semantic_siblings"]) == {"河", "海"}
    assert "semantic_siblings" not in merged["氵"]


def test_ito_no_cross_contamination():
    """糸 is semantic in 繼. 繼 should NOT appear in 糸's phonetic series."""
    merged = {
        "糸": {"formation_details": {}},
        "糹": {"formation_details": {}},
        "繼": {"formation_details": {"semantic": "糹", "phonetic": "㡭"}},
        "㡭": {"formation_details": {}},
    }
    build_series_and_siblings(merged)

    assert merged["㡭"]["phonetic_series"] == ["繼"]
    # 糹→糸, so 糸 gets the semantic series
    assert merged["糸"]["semantic_series"] == ["繼"]
    # 糹 is a variant of 糸, so it also gets the same semantic series
    assert merged["糹"]["semantic_series"] == ["繼"]
    assert "phonetic_series" not in merged["糸"]
    assert "phonetic_siblings" not in merged["繼"]
    assert "semantic_siblings" not in merged["繼"]


def test_chained_phonetic():
    """何 is a derivative of 可 AND a phonetic component for 荷."""
    merged = {
        "可": {"formation_details": {}},
        "何": {"formation_details": {"semantic": "亻", "phonetic": "可"}},
        "河": {"formation_details": {"semantic": "氵", "phonetic": "可"}},
        "荷": {"formation_details": {"semantic": "艹", "phonetic": "何"}},
    }
    build_series_and_siblings(merged)

    assert set(merged["可"]["phonetic_series"]) == {"何", "河"}
    assert merged["何"]["phonetic_series"] == ["荷"]
    assert merged["何"]["phonetic_siblings"] == ["河"]
    assert merged["河"]["phonetic_siblings"] == ["何"]


def test_radical_variant_semantic_series():
    """刀 and 刂 are the same radical. Characters with semantic 刂 should
    appear in 刀's semantic series, and vice versa."""
    merged = {
        "刀": {"formation_details": {}},
        "刂": {"formation_details": {}},
        "切": {"formation_details": {"semantic": "刀", "phonetic": "七"}},
        "判": {"formation_details": {"semantic": "刂", "phonetic": "半"}},
        "別": {"formation_details": {"semantic": "刂", "phonetic": "另"}},
        "刻": {"formation_details": {"semantic": "刂", "phonetic": "亥"}},
    }
    build_series_and_siblings(merged)

    # 刀 (canonical) should see ALL derivatives: 切 (via 刀) + 判,別,刻 (via 刂)
    assert set(merged["刀"]["semantic_series"]) == {"切", "判", "別", "刻"}
    # 刂 (variant) should also see the same derivatives
    assert set(merged["刂"]["semantic_series"]) == {"切", "判", "別", "刻"}

    # 切 (semantic=刀) should be sibling of 判,別,刻 (semantic=刂, same canonical)
    assert set(merged["切"]["semantic_siblings"]) == {"判", "別", "刻"}
    # 判 should be sibling of 切,別,刻
    assert set(merged["判"]["semantic_siblings"]) == {"切", "別", "刻"}


def test_radical_variant_phonetic_series():
    """水 and 氵 are variants. Characters with phonetic 氵 should appear
    in 水's phonetic series."""
    merged = {
        "水": {"formation_details": {}},
        "氵": {"formation_details": {}},
        "泉": {"formation_details": {"semantic": "白", "phonetic": "水"}},
        "沝": {"formation_details": {"semantic": "口", "phonetic": "氵"}},
    }
    build_series_and_siblings(merged)

    # 水 sees derivatives from both 水 and 氵
    assert set(merged["水"]["phonetic_series"]) == {"泉", "沝"}
    assert set(merged["氵"]["phonetic_series"]) == {"泉", "沝"}
    # They are phonetic siblings (same canonical phonetic component)
    assert merged["泉"]["phonetic_siblings"] == ["沝"]
    assert merged["沝"]["phonetic_siblings"] == ["泉"]


if __name__ == "__main__":
    test_phonetic_series()
    test_semantic_series()
    test_phonetic_siblings()
    test_semantic_siblings()
    test_ito_no_cross_contamination()
    test_chained_phonetic()
    test_radical_variant_semantic_series()
    test_radical_variant_phonetic_series()
    print("All tests passed!")
