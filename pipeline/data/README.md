# Curated Unihan readings

## Bibliographic research leads

`bibliographic-leads.json` records book references discovered while inspecting the user's Pleco Outlier entry for 啚, a component of 圖. It contains bibliographic metadata only, not dictionary prose or images. The research harness supplies matching leads for named characters and components. Researchers must inspect the actual cited study or obtain independently verifiable evidence before using its analysis. These records are not automatically added to article citations.

The cited pages of 季旭昇's *說文新證* and 裘錫圭's *文字學概要* are not currently available in this repository. Preserve edition and page information when seeking access; catalogue records and later editions do not establish the contents or pagination of the cited edition.

## Commons image metadata leads

`commons-imageinfo-hsk1.json` caches official Commons `imageinfo` results for 74 exact file titles found in the HSK 1 historical glyph coverage audit. It records the query URLs, check time, image and file-page URLs, and reported license. This avoids substituting guessed character filenames for the actual local manifest titles.

The pipeline supplies matching records as `api_metadata_lead` in local glyph hints. These records are research leads: agents must still inspect the image, establish its character identity and historical label, and verify attribution and reuse requirements. A metadata record does not approve an image or prove its date. No image content or descriptive source prose is included in this cache.

`unihan-kmandarin-hsk1.tsv` is a project-scoped extract of the `kMandarin` rows from Unicode Unihan 17.0.0. It covers the 300 canonical HSK 1 characters and the phonetic forms and host scopes used in published pilot entries. It is not a complete character dictionary. A missing row means this extract found no `kMandarin` value; it does not prove that a character has no reading in another source.

The pipeline checks `sources/unihan/Unihan_Readings.txt` when the full local source is installed, then falls back to this smaller extract. Writers still cite the official Unicode record for each character used in an entry. These current readings help check modern pronunciation pairs; they do not establish historical sound relationships.

The extract was generated from the local official UCD file with:

```sh
python3 pipeline/export_unihan_hsk1_subset.py
```

The Unicode source is distributed under Unicode License v3. Its copyright and permission notice is in [LICENSE-UNICODE.txt](LICENSE-UNICODE.txt). The source version, scope, missing rows and SHA-256 are recorded in `unihan-kmandarin-hsk1.json`.

The acquisition ranking and digitization suggestions are maintained in [research/source-acquisition-priorities.md](../../research/source-acquisition-priorities.md). Phone access is temporary and optional: production research must remain operational using local materials and accessible external sources when Pleco is unavailable.
