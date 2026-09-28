# Japanese kanji research sources and reuse

Updated 2026-09-27. The Japanese pipeline writes English explanations for Japanese learners; Japanese mode is a language-specific editorial profile, not a translation of a Mandarin learner entry.

## Selection and level provenance

`content/cohorts/jlpt-n5.json` freezes **79** characters selected strictly by `jlpt_new == 5` in `sources/kanji-data/kanji.json`. `content/jlpt-levels.json` uses the same snapshot for N5–N1, preserving source order and the source SHA-256. These are disjoint study groups, not cumulative lists and not official test specifications.

- [kanji-data](https://github.com/davidluzgouveia/kanji-data) provides the local JSON. Its README attributes JLPT estimates to [Jonathan Waller / Tanos](https://www.tanos.co.uk/jlpt/), not the test organizers. The repository's MIT label does not replace the terms of upstream material.
- [Official JLPT FAQ](https://www.jlpt.jp/e/faq/index.html), studying-for-the-test question on post-2010 specifications: no definitive kanji/vocabulary/grammar list is published. Never call our 79-character set official or exhaustive.
- [Official N5 item purposes](https://jlpt.jp/e/guideline/pdf/n5_e_revised.pdf): the reading task tests readings of **words** written in kanji. Membership is therefore not evidence that every reading or every word containing the character is N5.
- KANJIDIC's `jlpt` field is the **pre-2010 1–4 system**, per [its documentation](https://www.edrdg.org/wiki/KANJIDIC_Project.html). Preserve it as `jlpt_old`; no numeric fallback into modern N1–N5.

## Research sources

| Source | Exact role | Limits |
|---|---|---|
| [KANJIDIC2 documentation](https://www.edrdg.org/wiki/KANJIDIC_Project.html); [XML download](https://www.edrdg.org/kanjidic/kanjidic2.xml.gz) | Local `sources/kanjidic2/kanjidic2.xml`: on/kun readings, nanori, glosses, school grade, stroke count, variant leads. | Glosses are not a meaning chronology. Nanori are name readings, not ordinary kun readings. Variant cross-references need interpretation. Data CC BY-SA 4.0; descriptor-code subfields may have distinct terms. |
| [JMdict project](https://www.edrdg.org/wiki/JMdict-EDICT_Dictionary_Project.html); [download](https://ftp.edrdg.org/pub/Nihongo/JMdict_e.gz); [WWWJDIC](https://www.edrdg.org/cgi-bin/wwwjdic/wwwjdic?1C) | Consult when a character meaning requires lexical clarification; vocabulary example cards are outside the entry scope. Local JMdict is not installed at this date. | Do not assign every dictionary reading to every spelling. Keep sense and spelling restrictions. Dictionary examples/definitions do not prove historical origin. Preserve applicable EDRDG attribution/license with downloaded data. |
| [JMdict spelling/reading fields](https://www.edrdg.org/wiki/Kanji_and_Reading_Information_Fields.html) | Interpret ateji, obsolete spelling (`oK`), rare forms, irregular readings, rather than stripping those labels. | A word-level irregular reading cannot be redistributed as each kanji's independently compositional reading. |
| [Kanjipedia](https://www.kanjipedia.jp/) (Japan Kanji Aptitude Testing Foundation) | Character-specific Japanese meanings, on/kun readings, compound examples, old forms and `なりたち`. Formation sections can name their dictionary source (e.g. *角川新字源 改訂新版*). Follow exact character URL and cited reference. | Site displays All Rights Reserved. Consult and independently summarize; no bulk republication of prose or glyph assets. Its analysis is a cited scholarly interpretation, not automatic consensus. Do not confuse educational mnemonics with historical formation. Example source-bearing page: [始](https://www.kanjipedia.jp/kanji/0002756200). |
| [Agency for Cultural Affairs: 2010 Jōyō kanji table](https://www.bunka.go.jp/kokugo_nihongo/sisaku/joho/joho/kijun/naikaku/kanji/) | Authoritative standard Japanese forms and listed readings, notes and old-form correspondences. Use to verify Japanese shinjitai/kyūjitai claims. | A standard form table does not supply the ancient etymology. Chinese simplified/traditional metadata does not establish a Japanese orthographic relation. |
| [Agency: typeface/shape guidance](https://www.bunka.go.jp/seisaku/bunkashingikai/kokugo/kokugo/kokugo_60/pdf/shiryo_2.pdf) | Distinguish printed/handwritten variation, shape and character identity before claiming corruption or replacement. | Differences of font presentation are not necessarily different components or different characters. Preserve PDF printed-page references. |
| Chinese research dossiers and published entries | Shared ancient construction, earlier meanings, primary citations, verified historical glyphs and scholarly disagreement can be reused after identity and relevance checks. | Chinese article prose is an internal editorial artifact, not an independent external source. Reuse the cited evidence and provenance. Mandarin readings are not Japanese on readings; native kun words do not follow from ancient phonetic components. |

## Japanese adaptation checks

1. Match exact character first; if absent, inspect explicit Japanese old-form links and Chinese variants. Never pick a visual lookalike automatically. Record source character, article/dossier hash, reusable claims and adaptation limitations.
2. Explain the present Japanese form. Recheck component scope when Japanese and Chinese simplifications differ (e.g. 気 versus 气, both needing analysis of 氣). A shared modern character such as 国 or 学 still needs a separately verified Japanese form-history claim.
3. Reuse ancient phonetic roles with their Chinese historical context. A Japanese on-reading correspondence can illustrate the inherited pattern only when supported; a kun reading does not become the component's ancient sound. Historical Chinese readings remain clearly labeled.
4. Keep readings as compact character metadata. Explain historical Chinese sound relationships and useful on-reading comparisons in component analysis. Kun readings normally reflect meaning associations with Japanese words. Do not require vocabulary examples or explanations for every reading.
5. Distinguish character etymology, borrowing into Japanese, native Japanese words written with it, and later Japanese usage. Do not invent a single uninterrupted semantic transition linking them.
6. Curate old glyph images for the shared ancient history and label region/context accurately. A Chinese oracle glyph is not a historical Japanese attestation.
7. Consult Japanese sources independently even when the Chinese entry passed its reviews. Keep one Japanese-specific factual review and a learner readability review before publication.

## Suggested first smoke cohort

All six belong to the frozen N5 list: **日・学・国・気・生・聞**.

- 日: same-character reuse; word-dependent readings and special combinations.
- 学: exact Chinese entry exists, but Japanese 学/學 correspondence needs its own evidence.
- 国: same modern graph in both languages, different current usage and readings.
- 気: Japanese form differs from Mandarin 气; explicit traditional-family matching.
- 生: multiple productive kun readings; keep the learner section selective.
- 聞: no exact authored Chinese entry in the HSK1 set; consider 闻 only through a verified form relation and adapt to Japanese uses.

Production remains a small smoke run first; list membership does not authorize writing every N5 character in one batch.
