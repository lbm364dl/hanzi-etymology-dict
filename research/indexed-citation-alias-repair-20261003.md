# Indexed citation alias restoration

The 学 genuine patch selected `formation/evidence_ids/11` and returned `ref114`.
Its actual alias file mapped that alias to `X-cf69d0b8705473133e06`, but patch
application passed the leaf index `11` as the citation field name. Alias
restoration only recognized whole `evidence_ids` arrays, so retries repeated
the same unknown-reference validation failure.

Indexed evidence edits now inherit their parent `evidence_ids` field context,
and scalar aliases in that context are expanded through the actual transport
map. Other strings retain their original semantics. A reproduction test applies
a genuine-shaped indexed patch through schema/citation validation, checks the
expanded known ID and verifies the input article remains unchanged. Existing
whole-array patch coverage remains in place. No approved article or receipt was
hand-edited; the failed stage is preserved and requires real new review work.
