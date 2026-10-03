# Keep local scan evidence out of the web audit

边's initial book-enrichment research and first repair both failed the existing local validator: search_audit.urls contained non-HTTP(S) values. The source images were legitimate local research material; their paths were placed in the wrong record. Real external tool activity and scan inspection must each retain their provenance without pretending local file access was an inspected web URL.

The research response schema now requires the simple supported `^https?://` prefix for search-audit URLs. Research instructions explicitly place local paths/file URLs in source evidence/access records, and allow an empty URL array for an actual failed web lookup. Existing tool-activity checks still require genuine external research; an empty array does not fabricate a search or waive that gate. Book evidence metadata remains able to identify local scan paths under its separate contract.

A contract test accepts HTTP(S) addresses and a failed lookup with no URL, and rejects file URLs, absolute paths and bare filenames. The five research-schema/agent-schema tests pass. Prior failed receipts remain unchanged; the already-running batch is allowed to reach its terminal result before any continuation is launched. No prior article is certified by this schema improvement.
