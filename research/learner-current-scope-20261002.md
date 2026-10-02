# Learner coverage follows the current host graph

The 的 source-enrichment attempt ended with `Learner cards must cover each detailed
component exactly once`. Its detailed account included components scoped to historical
旳 and current 的, while the independent readability review required the current form
to lead the learner section. Requiring all historical cards made that correction fail
the mechanical gate.

The learner contract now requires every current-host component exactly once, permits
historically scoped cards when essential, and still rejects duplicates, missing current
components and invalid indices. This generalizes the already supported Japanese coverage
rule to every language, rather than adding a character-specific exception. Historical
evidence and component metadata remain in the detailed account; omitting an optional
learner card does not erase them or certify disputed functions.

Writer/reviewer instructions and pipeline documentation use the same coverage rule.
Contrasting tests cover current-only cards, optional historical cards, missing current
cards and duplicate historical cards. 79 editorial/source tests passed. Existing valid
entries are still valid because their extra historical cards are optional, not forbidden.
The pending 的 draft requires fresh actual reviews before any publication.
