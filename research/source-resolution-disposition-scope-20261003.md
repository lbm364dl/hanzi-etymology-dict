# Identity gaps are not rejected OCR proposals

The genuine 木 source-resolution worker selected `rejected_proposal_scan_matches_corpus`
for a finding that only recorded unverified individual glyph identities in a
chart. It preserved those uncertainties and proposed no replacement, but the
disposition label still implied rejection of an exact OCR proposal that did not exist.

The schema now offers rejection only when actual literal checks are supplied,
and the live gate requires each rejected key to have its exact checked occurrence.
Applied repairs retain their separate actual producer/consumer validation.
Unused identity gaps must receive a genuine independent
`unresolved_identity_not_used` judgment, or stay pending. Original findings and
fallible receipts remain unchanged. A fresh check is required for the 木 pair;
its authored article and independent factual/readability approvals are preserved.

The existing receipt-binding test now verifies that an unsupported rejection
cannot release the gate, while the exact observed-literal case can. This general
contract applies to any registered source rather than special-casing 木.
