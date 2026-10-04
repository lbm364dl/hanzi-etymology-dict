# 媽 / 妈 字源 source check (2026-10-04)

## Finding

The 2012 three-volume edition of 李學勤主編《字源》 contains a relevant simplified/traditional correspondence in its appendix, although the occurrence is not a standalone 媽 article. On PDF p.1326 (printed p.1311), a simplified-character correspondence table is headed **马**; the listed row is **妈〔媽〕**. The printed heading is simplified 马 (not traditional 馬). This directly supports the current article's narrow statement that 妈 is the simplified counterpart of 媽. It does not explain the historical formation of 媽 or independently assign 馬 a phonetic role.

The corpus locator already searched both `妈` and `媽`, and returned PDF p.1326 as a text-mention candidate. Its locator packet had no scan attachments. `pipeline/local_sources.py` attaches scans only for a headword-like candidate or a candidate with zero text matches; a relevant appendix mention such as this one is therefore not automatically attached. The failure was downstream evidence selection/inspection, not a missing traditional-form search. The previous source-enrichment research attempt timed out before returning a valid result, so it did not establish rejection of the appendix.

## Page checks

- **PDF p.1326 / printed p.1311:** Original scan inspected. Appendix table under 马 includes `妈〔媽〕`. The corpus text reproduces this row. Decoded RGB source-pixel SHA-256: `23b215d69a50832b37a8dcbad2520ab9dddace44c72ac3e98082abaafa1db739`. The attached PNG-file SHA-256 is a different digest (`6ce8c12000d8a9f076e7200a8ec971e256004572bb849460cded1477f7ef111d`); these represent different hash inputs, not a mismatch.
- **PDF p.1102 / printed p.1087:** Original scan inspected. In the 妘 entry, the corpus currently has `“媽”类推简化作“妫”` at text offsets 1363–1369; the printed text reads `“媯”类推简化作“妫”`. This is a confirmed OCR substitution at offset 1364 (`媽` → `媯`), in an unrelated analogy, not a 媽 headword analysis. Decoded RGB source-pixel SHA-256: `02405906c0bf1483e693a04c5ff3328cca2ef452382640a0da0df5bc1ce6325a`. A target crop with nearby punctuation is `runs/ma-traditional-source-check-20261004/p1102-suspect-bbox.png`; source bounds are x=2050–2220, y=1030–1140 on the 3000×4095 page image. The raw OCR response remains unmodified; this note is not a producer overlay or source repair.
- **PDF p.1106 / printed p.1091:** The body passage inspected is the 妹 entry; its examples concern 妹. It is not evidence about 媽. The page-top running header OCR at text offsets 0–12 reads `娠魅母媽媽姐姐姑威妣姊妹`. The scan shows a shorter sequence of 11 glyphs; the forms around positions 3–5 do not straightforwardly match the OCR sequence. Exact identities and a complete correction are left unresolved here; do not use the header OCR as evidence for 妈/媽. Decoded RGB source-pixel SHA-256: `e28aa0a05695875fef0f6bef2479550c1724bd644571944d5504e153de463ee6`.
- **PDF p.1334 / printed p.1319:** Original scan inspected. 妈 appears in the six-stroke index. This is an index listing, not a character account.

A full-corpus search of exact forms `妈`, `媽`, `馬`, and `马` returned candidate mentions and indexes, but no verified headed 妈/媽 entry in the bounded inspected hits. This is not proof that no such entry exists elsewhere in the book.

## Independent reference

The Taiwan Ministry of Education Dictionary of Chinese Character Variants entry A00958 identifies 媽 as its standard form, describes 女 on the left and 馬 on the right, and links a simplified-form variant to the mainland Simplified Character Table. It separately reports that 媽 is absent from 說文 and gives the cited senses. It does not itself establish the phonetic role proposed in the current article. Page: [A00958 媽](https://dict.variants.moe.edu.tw/dictView.jsp?ID=10182&la=1).

## Pipeline implication

The relevant weakness is a general one: locator match type distinguishes headword-like lines from mentions, but not a substantively useful table/appendix from an incidental mention. The candidate list can surface the page and form pair while withholding the scan. Source research must assess each candidate against the exact current claims, including tables and appendices, and inspect its page image before declaring it irrelevant. Any such claim-based fix belongs in the shared source policy/research loop, not in a 妈-specific exception. Separately, precise source-page/hash association in returned evidence needs validation: the Luna research receipt below incorrectly attached p.1106's pixel hash to its p.1102 note and called the p.1326 heading 馬. Its useful p.1326 correspondence should be retained only after those details are corrected from pixels.

## Run provenance and limitations

A genuine `gpt-6-luna` / low research stage ran through `editorial.research_dossier` with `SOURCE_POLICY`, `RESEARCH_SCHEMA`, AgentSlots capacity 3, the current canonical article and dossier, and original scans for PDF pp.1326, 1102, 1106 and 1334. The frozen input is `runs/ma-traditional-source-check-20261004/research-input.json`; stage files are under `runs/ma-traditional-source-check-20261004/research/research/`. Research-result digest: `578f3f27eeb409532fae980c0c24ec727d89f5ca51818fa0971fb5872abcccd1`. The raw result is not accepted wholesale: p.1102's transcription/hash and p.1326's heading identity are wrong as described above. A fresh normal source job must independently author any article change and obtain new factual/readability reviews. No article or dossier was edited here, and no OCR overlay or source repair has been applied.
