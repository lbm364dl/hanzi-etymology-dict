# 比 current-reading source follow-up, 2026-10-03

## Finding and source check

Issue #177 identified that the published modern Mandarin comparison cited two local Unihan row paraphrases (`X-d97900d69eb3aaabaa7e`, `X-6ca2e73762d1840ebd36`). Both records say that the official per-character pages were not opened; these rows are useful local input but do not document direct inspection of the source records.

A bounded Luna-low research stage directly searched and opened the official Taiwan Ministry of Education dictionary entries. It verified:

- `X-b58bc9da45c6f0a58606`: 比 in the Revised Mandarin Chinese Dictionary, actual entry ID 331, lists bǐ among readings bǐ, bì, and pí. URL: <https://dict.revised.moe.edu.tw/dictView.jsp?ID=331&la=0&powerMode=0>.
- `X-c85ace227a5107eb53c9`: 匕 in the Dictionary of Chinese Character Variants, entry A00414, gives bǐ. URL: <https://dict.variants.moe.edu.tw/dictView.jsp?educode=A00414>.

The official Variant Dictionary's 比 entry (A02102; `X-3efcb64deaf4048ff20a`) independently lists the same three readings. The author correctly did not use it in the paired comparison because it supplies no reading for 匕. The research attempt also discovered that the initial requested Revised Dictionary ID 319 resolves to 鼻; the actual 比 entry is ID 331. No claim about ancient phonetic structure follows from modern homophony.

## Authorship and exact reviews

The Luna-low citation author changed only `components[1].sound[1].evidence_ids`, replacing the two local Unihan IDs with `X-b58bc9da45c6f0a58606` and `X-c85ace227a5107eb53c9`. The explanation, readings, component metadata, graph and every other citation remain unchanged.

The prior published approved pair was article `af520bb72233261e3d30c198850197cb1c35e9ac849eac371aadc9a8ab1bf70d`, dossier `6f9afaf0a741a72530273e57d1c6224cdcdb4020ad917dcd5aaaa35d910959c2`. The corrected candidate pair is article `15b6001fa16dcfafea1d11ed37ba37b068b1fa6cb7c62a7dfa1c58f365bde4f3`, dossier `b1591978d77b85f6780a3b665489f3ead4ec0ec8aeb3c47d1532144db1785f5c`.

Fresh exact-pair factual and readability checks both passed with no findings. They were separately bound to that candidate pair and to the exact two changed citation leaves, with the prior approved pair provided as context only. The actual review receipts and binding are in `runs/source-enrichment-ziyuan/bi-issue177-current-readings-20261003/ziyuan-2012/6BD4/citation-only-exact-review/`.

A first broad review attempt is also preserved under `.../exact-review/`; its reviewers requested learner edits unrelated to the citation correction, so that attempt was not used to certify the pair. The fresh scoped reviews addressed the exact citation changes and checked that all other article fields match the approved baseline.

## State

The approved source-level correction pair is ready for root's canonical publication workflow. No canonical content, publication receipts, GitHub issues or site outputs were changed by this follow-up. Issue #177 remains pending until root links the exact published pair and closes it after the publication gate succeeds.
