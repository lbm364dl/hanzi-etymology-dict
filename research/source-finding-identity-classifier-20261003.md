# Source finding identity classification, 2026-10-03

The source finding classifier recognized identity gaps phrased as “identity is
unresolved” or “identity was not verified,” but missed the equivalent inverse
word order “I did not establish the Unicode identity.” A retained finding with
that wording was consequently treated as generic, so source resolution did not
require the exact article-claim inventory intended for occurrence-specific
identity gaps.

The classifier now recognizes explicit `did not establish`, `determine`, or
`ascertain` wording followed by an identity term. It still requires the finding
to state that identity was not established; this does not infer an identity gap
from a generic scan concern. The regression test uses the previously missed
phrase. Resolution still requires an exact-pair Luna-low review and the normal
identity-support checks. This classification change does not identify a glyph,
resolve a source finding, or approve publication.
