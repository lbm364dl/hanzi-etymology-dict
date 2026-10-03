# Locate visual controls before accepting OCR verdicts

The p277 学 parenthetical check returned `correct_raw` for both raw characters
`毚片`. Its first reason claimed a matching 毚 control in an earlier line; its
second claimed that 升 needed an enclosing outline and internal strokes. Direct
inspection of the attached original crops did not support those comparisons.
The original-pixel crop at `[1260,3210,1470,3400]` contains the complete printed
parenthetical; therefore this failure cannot be attributed solely to a clipped
target. The first crop does clip the second character, but the third attachment
supplies it completely.

The genuine conflicting result remains at
`runs/source-enrichment-ziyuan/xue-p277-parenthetical-char-check-20261003/ocr-verification/`.
It is not an approval to keep the raw OCR, and the coordinator's visual reading
is not an independently approved correction. A separate Luna-low blind source
comparison is being used to establish the literal before any producer overlay
or consumer rebuild. The earlier removal of `heat` on the page must be preserved.

This is a general visual-review failure: a fluent reason can invent both a
source control and the geometry expected of a proposed Unicode identity.
OCR reviewer and occurrence instructions now require locating the target and
each claimed control by attachment plus printed anchor or supplied crop label.
They distinguish observed geometry from imagined candidate shapes and retain
uncertainty when the comparison cannot be established. These instructions do
not mechanically prove visual inspection or retroactively certify prior
receipts. No character-specific rule, source mutation, or authored article edit
is introduced. The outstanding repair remains in existing issue #3.
