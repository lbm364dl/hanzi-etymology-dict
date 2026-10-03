# 好 p.1109 neighboring literal correction (2026-10-03)

This is a separate correction to the p.1109 statement in `hao-p1110-verification-20261003.md` and to finding 2 in its source-coverage result. Preserve the original source-coverage receipt unchanged. Its statement that the bronze example reads `虘鐘` is false for the neighboring character: the inspected scan passage reads `虘钟`. The p.1110 continuation finding remains unaffected.

The exact source-bound neighboring occurrence was already covered by an independent Luna-low OCR verification; no duplicate check or producer edit was needed. In `runs/source-enrichment-ziyuan/hao-evidence-caption-continuation/ziyuan-2012/597D/ocr-verification-charwise/occurrences.json`, PDF p. 1109 / printed p. 1094 raw span `[1439,1440)` is `钟`, with proposed alternative `鐘`. The matching `verified-occurrences.json` records `printed_text: "钟"`, verdict `correct_raw`, and the observed distinction: the left component is 钅 and the right is 中, not the 金 component and the right side of 鐘. It also separately checks raw `[1438,1439)` 虐 versus 虘, but that first-character finding is outside this follow-up.

The actual Luna-low review result hash is `2104871ac4faf55af7943ebc27b77a4c0ac0334da04a1b7b220f7b1159bd2371`; the occurrence-packet hash is `d6661e60e78c50558525ac6fdfa83c45102b35027b8c9386d0852e7a30903083`. Its saved prompt attached the original full scan and targeted crop. The scan identity is encoded PNG SHA-256 `8c2cad410c397a9d1bbab4f627fc9c973b942739f4c0063ceb9021b4dd5ad155`, decoded RGB pixels `f57b420e60d20032f8df525c5dcae08228f9a01195720435613d53d0c14df040`; the targeted crop SHA-256 is `cdbbd5305b30c93418b1efbd75654e776f7b832e778764fc04d22bf2d7801f88`. A byte-for-byte copy is retained at [p1109-target-wide-previous-review.png](source-crops/hao-ziyuan-pages-20261003/p1109-target-wide-previous-review.png).

Producer state was independently read with the actual `/home/catalin/hanzi-etymology-books/scripts/research_corrections.py` `load_effective` implementation under `/tmp/hanzi-etymology-venv/bin/python`:

- Raw OCR context at `[1435,1442)`: `也。”虐钟：“`.
- Effective OCR context at `[1435,1442)`: `也。”虘钟：“`.
- Only source-bound producer patch: raw `[1438,1439)` 虐→虘; the following raw `钟` is untouched.
- Raw OCR evidence SHA-256 `4ad1c5141bed8484c5d9088ce5888c2293aa5357267fc4ba04554e6f41620b56`; effective evidence SHA-256 `83da0aaef5c5f850afd23793440be39bf5847b19a5f1d4cdec8fb68e8d6a6022`; correction-file SHA-256 `381f92482366f9b54b42e7a46dab4bff55570d44bf1654ea3c60b1ee3c4eac8f`.

The newer source-coverage result `d03eee071acd4abdbab0856bac52e8bd42726ca4872e612e2aca8b59608905d3` returned `pass` but includes the incorrect p. 1109 `虘鐘` observation. Do not use that result as confirmation of the second character or as a clean overall coverage pass. It does independently attach and verify the separate p. 1110 continuation crop/full page; that finding still supports the page-boundary and `hào` continuation only.

No change was made to raw OCR, producer overlays, consumer corpus, canonical 好 entry/dossier, or GitHub issue status. No neighbor correction is proposed: the targeted scan receipt establishes raw/effective `钟` as printed.

## Reviewer reference follow-up

The producer overlay had paired the correct morphology-highres result path with the hash of a contrary named-identity check. Read-only independent control inspection confirms PDF446 is 虘 (closed lower rectangle), PDF447 is 虐 (open right edges), and the high-resolution composite's right control is PDF446. Its actual completed result digest is `57da5e5c67578541b0fcaf419425fde74bb48fa50005c356d2f9de3c4d09b787`, matching its metadata. The old `59401444...` hash belongs to a preserved contrary review that wrongly names the closed control 虐.

Only that supporting reviewer reference was corrected in the producer overlay. Before/after overlays are preserved in `research/source-corrections/hao-p1109-review-provenance-20261003/`. The actual producer validator/export and full 1,435-page consumer rebuild pass. Effective text and evidence remain unchanged (`83da0aa...`). The old applied-repair wrapper is no longer current because its overlay hash differs; fresh independent repair and continuation observations are required. No published article or dossier was edited.

This is a provenance pairing failure: a correct path alone does not identify the supporting invocation. Coordinator verification must read the actual result and its metadata and compare the complete digest before recording it. Existing source-repair gates bind the complete overlay, so a provenance-only change still requires fresh independent source resolution. Old contrary outputs remain evidence of the review failure and are never overwritten.
