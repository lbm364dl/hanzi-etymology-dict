# Working on this project

## Purpose

Build coherent, independently researched explanations of individual characters. Sources support authored explanations; the site starts with a concise learner account and offers deeper history and clickable citations. Keep the focus on the character, its components, sound roles, historical forms and meaning development.

## Improve the pipeline from every finding

Every user correction, source discovery, failed review and smoke-entry observation must be considered for its broader implications. Identify the failure class and check the research prompts, schemas, writer instructions, review criteria and presentation that allowed it. Implement the applicable general improvement and record the reasoning in `research/` or a batch review. If a finding is genuinely character-specific, explain why and store it as cited character evidence.

Do not solve recurring editorial problems through character-name conditionals, UI substitutions or manual edits to approved prose. Character repairs must use the updated pipeline and receive fresh independent reviews. Do not generalize a particular source's interpretation into a universal etymological rule. Use a small relevant smoke subset before expanding a batch; include contrasting cases when a rule could affect them differently.

## Research and authorship

Agents may use all available tools freely for their assigned work, including shell scripts, web/browser access, additional source pages, rendering and image crops. Do not impose a read-only sandbox, an arbitrary page cap or a requirement to ask permission for further investigation. Coordinate shared-file writes to avoid collisions and preserve the independent research, authorship and review gates. All introduced agents remain `gpt-6-luna` with low reasoning.

Use separate `gpt-6-luna` agents with low reasoning for research, authorship and independent factual/readability review, following `pipeline/README.md`. Consult repository sources, acquired scholarly books described in `research/local-book-sources.md`, and external authoritative references. The coordinating agent implements the harness and instructions; it must not fabricate agent work, review approvals or research logs. Reuse historical research across languages only with exact character identity, provenance and verification; research Japanese meanings and form conventions separately.

Outlier/Pleco, when the user's phone is available, is inspiration and a source-finding aid. Record bibliography, edition and page leads; consult the underlying references where possible. Distinguish observing a citation from reading its cited pages. Do not reproduce proprietary prose or make phone access a pipeline dependency.

## Editorial standards

- Start with a useful meaning and logical current-form component explanation. Keep expert details after the learner section.
- Distinguish visible component identity, current function, earlier function and the evidence for continuity. An unresolved ancient interpretation does not erase a supported modern decomposition.
- Research grouped components as units when relevant; do not assume the smallest stroke split is the historically meaningful split. Distinguish simplification, positional variants, deliberate replacement and corruption.
- Explain supported sound roles with the component's reading and the character's reading in an identified system. For inherited Japanese kanji, historical Chinese sounds establish ancient phonetic relationships; on readings may illustrate them, while kun readings normally reflect meaning associations. Do not require vocabulary cards or explanations for every reading.
- Qualify the uncertain claim precisely. Missing local evidence is a research gap, not proof that scholarship has no explanation. Keep competing analyses and detailed limitations in the expert account.
- Show selected historical glyphs only when they illuminate the explanation. Use short titles and keep provenance in citations.
- Crosslink related characters and counterparts. Keep a separate variant's full component analysis in its own entry unless its structure is essential to explain the entry's development.
- Cite substantive claims through evidence IDs and reader-friendly source details. Keep source names and workflow commentary out of explanatory prose.
- Distinguish attested meanings, proposed original meanings, semantic extensions and phonetic loans. Preserve uncertainty and scoped graph relationships in metadata.

## Publication and verification

Preserve genuine review receipts and exact article/dossier hashes. Never hand-edit a published article to bypass the gates. Changed authored facts or prose require fresh factual and readability approvals; prompt changes alone do not certify existing entries. Keep legacy fallback available for unpublished characters.

Run meaningful tests for changed contracts and use a separate Playwright session for presentation changes. Report what was changed and verified, and explicitly identify any entries that still await regeneration. Read `pipeline/README.md`, the language profile and relevant research notes before changing the pipeline.
