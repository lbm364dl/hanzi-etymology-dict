# Existing glyph review routing (2026-10-02)

大 caption corrections could not reliably reach authorship: source refresh reused the existing Chinese glyph selection, and the ordinary article patch intentionally excludes historical_glyphs. Reusing valid assets should not prevent fresh visual/caption review when a finding requires it.

Additional research context can now explicitly request review_existing_glyphs. The request is frozen in the job and passed to the editorial feedback. The research harness retains existing candidates/assets while asking its separate glyph curator to inspect them and revise justified caption/provenance fields. The resulting article/dossier still requires fresh exact factual and readability approvals. This is generic and does not reacquire an unrelated gallery just to fix a caption.
