# Crop identity does not prove occurrence coverage

Fresh 愛 research proposed the literal quote correction 兒→皃 on 字源 PDF497.
Its first cited crop `(940,3270,1260,3400)` did not contain the suspect character:
the coordinator inspected it and saw only the start of the quotation. The crop's
pixel hash was accurate, but its claimed occurrence coverage was wrong.

The corrected original bounds `(1230,3270,1490,3410)` show the suspect printed
character. Coordinator, researcher and independent source verifier inspected that
region; its RGB-pixel hash is
`642367b36a73862011a0852377f869184e837979002fa8c30db11a79446951c0`.
The upper closed 白-like block and lower 儿 support 皃 rather than 兒.
Codepoint tooling confirms 皃 is U+7683, correcting the earlier mistaken U+76C3 label.
The exact original text span is `[1072,1073)`. The producer verifier is applying the
source-bound correction; this note itself is neither a producer repair nor an article
approval. Actual correction/consumer receipts must demonstrate application separately.

The general research and OCR-verification instructions now explicitly require that
the complete occurrence and adjacent printed anchor be present before a crop supports
a verdict. A clipped/missing target stays unresolved. Hash labels continue distinguishing
source pixels, encoded image files and evidence objects; none establishes glyph identity
by itself. Unicode scalar labels are derived from the literal instead of memory.

No character-name conditionals or hand edits to approved prose were introduced. Prior
mislocated evidence is retained as rejected occurrence proof, rather than silently
rewritten into a genuine independent approval.
