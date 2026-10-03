# Expose the actual rejected reader token in author repair feedback

## Observed failure class

The genuine 唱 enrichment job at
`runs/source-enrichment-scale-20261003/ziyuan-2012/5531` exhausted its author
validation repairs while repeatedly appending inline `refNNN` aliases at the end
of a long explanation. The validation contract correctly rejected reader-facing
aliases, but the error showed only the paragraph's first 120 characters. Its
repair agent could not see the offending suffix in that feedback.

This is a general feedback visibility failure, not a character-specific editorial
exception. The author instructions already require citations in `evidence_ids`.

## Change

`validate_reader_prose` now supplies the rejected token, section index, text offset
and bounded surrounding context for both citation aliases and dossier workflow
references. It continues to reject these outputs; it does not rewrite prose or
construct a review approval.

## Verification and remaining entry work

A meaningful repair-flow regression places the inline alias after a long paragraph,
checks that a fresh repair call receives that exact token and suffix context, and
checks that its valid replacement retains evidence links. The editorial and
structured suites passed: 109 tests.

唱 still needs a genuine new author continuation and independent factual/readability
approvals before publication. Prompt/feedback changes do not certify its failed
candidate or any other existing entry.
