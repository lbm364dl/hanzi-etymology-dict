# Attention-repair runtime and OCR findings (2026-10-04)

## Pipeline repairs

The attention-repair CLI previously let model work start even when the selected
Python lacked the dependencies used later by glyph review. That allowed authorship
to finish before factual review failed while rendering glyphs. `run_many` now checks
Pillow and CairoSVG before scheduling any character. The error names the active
interpreter and the install command from `pipeline/requirements.txt`. Each attempt
records its executable, Python version, prefixes, and renderer package versions.

`editorial.Runner` now prepends the coordinator's virtual-environment `bin` to the
child `PATH` when the coordinator runs in a venv, retaining the rest of the inherited
path. It records the coordinator interpreter in stage metadata and cache identity.
The path uses the executable's absolute spelling rather than resolving the venv
symlink, which would incorrectly select `/usr/bin`.

Attention attempts now checkpoint the exact prior source findings before the first
authoring stage and save the full current locator in `source_checkpoint.json`.
That keeps the original scan packet available to source resolution after a failed
patch. Retry routing follows `attention_repair.json` ancestry when an early failed
attempt never reached its findings checkpoint; validated raw-occurrence proof
references also survive that ancestry. A correct-raw proof releases only its exact
replacement blocker for authoring. It does not remove the finding, mutate OCR, or
clear the final source-resolution gate.

Verification: `/tmp/hanzi-etymology-venv/bin/python -m unittest
pipeline.test_attention_repair pipeline.test_editorial pipeline.test_source_enrichment -q`
passed 159 tests before the added checkpoint/proof regressions; the final focused
run passed 159 tests after those additions (109 attention/editorial tests plus 50
source-enrichment tests).

## Exact OCR occurrence checks

The three independent Luna-low checks used original page rasters plus context crops.
Raw OCR, page pixels, crop bounds, attachments, model receipts and results are
retained below `runs/ocr-verification-20261003-occurrences/`.

| Occurrence | Source-bound span and crop | Genuine result | Effect |
|---|---|---|---|
| 錯 entry, PDF p.1239 / printed p.1224 | Raw `错`, `[487,488)`, anchor `古通作错`; crop bounds `[80,1510,1480,2600]`; decoded source pixels `228082642421550d2be75c54f4afd920f6feb7857b73dcd0e1105b4ef8602d8d` | `correct_raw`, result hash `ee50afc571cee093eeedf47ed0e4d4069567cec045f6609786eee621c5ecd156` | The scan prints `错`; the proposed `錯` replacement is unsupported. Do not patch the producer. |
| 關 entry, PDF p.1058 | Raw `𢇦`, `[1298,1299)`, anchor `形声字。从門,𢇦声。`; crop bounds `[1400,1600,2920,2700]`; decoded source pixels `68341019e2f0bfcb44d1f8f3bda0f449d0e3815ffdf7896d12e6861ddf100bf3` | `unresolved_identity`, result hash `ebfc42b27ffbbc6ec1e1e8513c063c6a82537a79467ee0f92b8c9bb8822d8aac` | The pixel reading does not distinguish the proposed rare scalar. Preserve the finding; this receipt does not authorize mutation. |
| 沔 entry, PDF p.976 | Raw `上源`, `[176,178)`, anchor `形声字。从水,丏声。汉水上源。`; crop bounds `[50,500,1500,1600]`; decoded source pixels `06f77f37046a7a24a8fe8a351647e9b70b05ca5e735e9a3c2f5c40cf4169ea7e` | `correct_raw`, result hash `91d6b1c907526ebb5417b760e0fca87ecfcd1078027a54f57e947eef88a3f2e7` | The printed phrase is `汉水上源`. The finding attached to 漢 PDF p.975 has the wrong page/headword scope and does not establish an OCR correction. Preserve its receipt for triage. |

No producer overlay or consumer corpus was changed for these checks. The 关 identity
remains unresolved. The 错 and 汉 proposals are scan-disconfirmed and need finding
triage before a source gate can close.

## Active attention repairs

The first fresh 后/电/歌 attempt is retained at
`runs/attention-repair-smoke-20261003-identities/ziyuan-2012/` and reached round 3
with `needs_revision`. A second bounded continuation is running at
`runs/attention-repair-smoke-20261004-retry1/ziyuan-2012/` with fresh authorship and
reviews. It carries all scan findings and does not publish. Earlier unrelated
repair failures and contradictory review receipts remain preserved in their source
attempts.
