# Independent review context after an author repair

The 边 continuation exposed a repeated failure: a reviewer referred to a historical component using an earlier array index, although the current candidate had a different record at that position. Other follow-ups repeated already completed editing requests. Passing old author instructions and verdicts into fresh independent reviews made these errors easier to repeat.

Fresh factual/readability review packets now omit author repair commands, prior verdicts, citation correction requests and editorial adjudication. Authors still receive the full repair feedback. Reviewers retain the exact current article and dossier, supplied factual scan attachments, additional research context and superseded evidence IDs. Exact approved-base comparisons remain available only through the existing validated scope mechanism. This changes no approval or published prose.

A contract test checks both sides: the author receives the full feedback, while independent reviews receive only source context and the factual reviewer retains the scan. 茶 is the next actual source-repair smoke case; its changed dossier requires full new reviews. Existing entries are not certified by this packet change.

## Invalid array deletion during the 茶 smoke run

The actual author returned `null` at array-item paths to request deletions, despite the whole-array replacement contract. This reached relationship processing and raised an AttributeError instead of giving the author normal repair feedback. The patch helper now rejects null array items and null array replacements before mutating that target. It preserves optional nullable object fields, and reports the containing-array replacement instruction through the existing bounded repair loop. Regression cases cover individual component deletion, whole component arrays and relationship arrays; invalid values leave the candidate intact. No failed author result is treated as an approval.
