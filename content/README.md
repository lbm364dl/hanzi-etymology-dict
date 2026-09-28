# Editorial pilot

Each character has an evidence dossier in `dossiers/`, an analysis in `analyses/`, a candidate article in `drafts/`, and review receipts in `reviews/`. Approved articles in `entries/` are included in both dictionary modes for the exact character concerned. Filenames use the uppercase hexadecimal Unicode codepoint.

The current pilot was researched and written in two groups by the `pilot_writer` and `reading_interface` agents. Each agent fact-checked the other group's entries, including the external source pages; the coordinating agent reviewed readability. All twenty revised entries passed both reviews. Final individual receipts live in `factual_reviews/` and `readability_reviews/`.

The first pilot is preserved in `review_history/v1-published/`, and its original drafts and first-round findings in `review_history/round-0/`. The current version replaces source-name narration with neutral explanations and adds researched component analyses. It uses the component presentation of the user's open Outlier entry in Pleco as a design reference; the research records identify the independently consulted sources supporting the new prose.

Run `python3 -m pipeline.pilot check` to check every saved article, citation, and review hash. `python3 -m pipeline.pilot publish` validates the complete batch before writing approved local entries.

The twenty-character pilot samples pictures (木、水、馬), an added indicator (本), compounds (休), differing interpretations (明、好、信、東、青、安、武), sound-based components (河、清、字), borrowed uses (來、我), a simplified form (国), and Japanese-created characters (働、峠). These groups are editorial test cases, not definitive formation classifications.

## Reading and evidence

The opening explains the character in ordinary English. The component breakdown identifies each functional part, explains what it contributes, and distinguishes preserved or variant forms from stylization, replacement, simplification, and documented corruption. A form component works through what it depicts; a meaning component uses a word meaning; a sound component supplies a pronunciation cue. An indicating mark, replacement element, or empty element has its own explicit role. Labels describe the part's function in this character, not an intrinsic property of that shape in every character.

Sound components also show the component's pronunciation beside the character's pronunciation, with the language and pronunciation system identified. A short cited explanation describes the relationship and any limits. Where modern sounds differ, a supported historical comparison can make the connection clearer. Japanese on'yomi comparisons are distinguished from native kun'yomi.

The main entry contains the authored explanation, components, and history of forms and meanings. It has no appended source inventory or legacy data sections. Historical paragraphs explain older meanings and semantic development where supported; they distinguish a change of meaning from borrowing a graph for another word. Uncertainties identify specific competing interpretations or missing support.

Each citation opens a popup containing only the sources for that passage. References resolve to imported excerpts or clearly recorded paraphrases of consulted external pages. External references include the original URL, title, and access date. The popup leads with readable research summaries, names each source, and groups references from the same page. Short dictionary excerpts are readable directly; long excerpts and structured reading records are available on expansion. Structured records render as labeled values rather than JSON. Component role labels likewise open a short definition on request. A reference establishes where a claim came from; it does not establish that the source is correct. Characters without an authored entry show basic dictionary information and a pending notice rather than a raw source dump.

Base dossiers are reproducible from the local JSONL databases with `python3 -m pipeline.dossiers`; rebuilding preserves separately recorded external research. The current dossiers also include new research from the Chinese University of Hong Kong's multifunction character database, Kanjipedia, and other cited dictionary or specialist pages. Search and access records, including failures and remaining gaps, are saved in `research/` and embedded in each dossier. Missing repository data triggers research; it is not evidence that a character's origin is unknown.

Imported Wiktionary extraction can mix languages and senses. Sources may repeat other sources. Classical analyses and modern reconstructions need interpretation. Generated Shuowen English glosses are excluded because the existing translations can be misleading. Algorithmic formation labels are context only and cannot independently justify a historical claim.

The pilot does not claim direct paleographic examination of original inscriptions. Statements about early forms are supported by the cited descriptions. Further source acquisition and specialist review can improve or replace these explanations without discarding the original evidence and reviews.

## Provenance and reuse

Source excerpts retain upstream attribution. The repository's [source inventory](../README.md#sources-integrated) and [license inventory](../LICENSE) describe the imported datasets and their recorded terms. Generated prose does not remove the underlying sources' attribution or reuse obligations. `merged_record` means that the existing database combined metadata; it is not a new independent source. `kanjidic2_via_build_kanji` identifies Japanese readings and definitions imported by the kanji builder. `ids_analysis` identifies the imported CJKVI analysis.

Review receipts record the reviewer identity and hashes of the precise article and dossier. The pilot is AI-written and AI-reviewed. An approved status means it passed the editorial checks against that dossier; it does not mean all historical questions are resolved.

## Version-two smoke entries

The next pipeline version adds three reviewed products to each independently generated entry:

- `meaning_history`: identified senses, their attestation scope, supported developments or phonetic loans, and explicit gaps. The `history` field now covers the written form.
- `historical_glyphs`: a curated selection with captions explaining what to notice, approximate periods, source and reuse provenance, and accessible image descriptions. A variant is not automatically a stage in a chronological chain.
- `relationships`: cited, contextual claims linking characters, components, and senses, with certainty retained on each relationship. These are reviewed alongside the prose.

New generation uses separate Luna low research, glyph candidate sourcing, visual curation, analysis, writing, copy editing, factual review, and readability review calls. Visual curation and both reviewers receive rendered snapshots as image attachments. Existing version-one publications retain their original reviewed artifacts. A new schema does not retroactively establish new claims for them. The version-two smoke subset is 木, 來, 我 and 清; the pilot inventory remains 20 characters.

`python3 -m pipeline.graph` exports only reviewed version-two relationships to `output/editorial-graph.json`. Each edge includes the approving article/dossier hashes and its cited evidence. The export reports older entries without graph data explicitly; it does not reconstruct their relationships from displayed shapes.

## Two reading depths

The 木, 來, 我 and 清 smoke entries now include a separately authored `learner` layer: a short overview, a cited explanation for each component, and an optional takeaway. The component cards reuse the reviewed role, earlier form, and pronunciation data. Indivisible pictographs are shown as one whole picture.

The website leads with **Understand the character**. **Explore its history** expands the detailed component analysis, selected historical forms, meaning history, and differing interpretations. Citations work in either layer. The learner text is reviewed against the detailed claims and evidence; brevity must not conceal a material uncertainty or invent a mnemonic. Other pilot entries keep their existing presentation until independently regenerated with this layer.

我 explains the proposed borrowing of an implement graph for a similar-sounding pronoun and the missing evidence for the implement name. 清 contrasts semantic 氵 with phonetic 青 and supplies modern and historical sound comparisons. No historical image for 清 is published yet: the research did not establish an adequately verified reusable candidate. Glyph headings use short script labels; source catalog descriptions, dating qualifications and attribution are available through Image details.

## Component-form relationships

A component's `origin_relation` classifies its link to `origin_form`: `full_form` for a positional form and its full character form, `earlier_form` for a supported historical predecessor or replaced form, `variant_form` for a nonchronological alternative, and `uncertain` when the relation is not established. `none` applies when no distinct counterpart is recorded. These classifications are authored and reviewed against the component citations; the interface does not infer them from specific character pairs or from `form_status`. Unannotated relationships have the neutral label “Related form.”
## Homepage HSK lists

`hsk-levels.json` contains 3,000 distinct characters introduced at each HSK 3.0 (2021) level: 300 each for levels 1–6 and a combined 1,200 for levels 7–9. Lists were imported from `~/hsk-graded-readers/data/chinese/characters`; source filenames and SHA-256 values are retained. HSK 1 exactly matches the production cohort. These are character lists, not vocabulary-word lists or cumulative totals.

The site builder copies this file to `docs/hsk-levels.json`. The homepage uses these lists rather than mixing legacy HSK tags from different versions. Approved articles are highlighted; other character links open legacy source details. Publishing an approved article automatically changes its homepage status and character view on the next site build.
