# Noncharacter mark graph and reader presentation verification

The typed component contract in
`research/noncharacter-mark-component-representation-20261003.md` now has graph
and public renderer support. Ordinary glyphs retain their literal forms and links.
A declared noncharacter mark exports its exact scoped element ID, display label and
host context; it has no `form` and no character-entry destination. Role certainty
continues to follow the cited relationship.

## Checks

- 122 combined graph, structure, agent-schema and editorial tests passed.
- Graph regression publishes explicit test fixtures, verifies neutral mark identity,
  retained citations, no invented glyph form/link, and unchanged ordinary 木 node.
  Test receipts are fixtures, not approvals for a real entry.
- Separate Playwright session used local docs preview on port 8767. Real published 木
  loaded with its existing glyph/link treatment. An explicitly labelled browser-only
  rendering fixture exercised `noncharacter_mark`: both learner and deeper headings
  showed “short horizontal mark,” no opaque ID was leaked, no glyph link was created,
  and the probable indicator edge produced “Likely indicating mark.”
- At 390px viewport, the label used 14.4px type and there was no horizontal overflow.
  Inspected screenshot `.playwright-mcp/page-2026-10-03T13-12-21-450Z.png`.
- Console showed only the preview server's missing favicon, no application error.

No authored canonical entry was changed. 本 still requires regeneration and fresh
independent factual/readability approvals. This contract does not resolve unidentified
rare characters or unread historical glyphs: their occurrence identity gaps remain.
