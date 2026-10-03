# Keep remote sync retries out of editorial triage inputs

The genuine approved 边 source job completed a Luna-low finding triage, then
failed to acquire the repository GitHub sync lock within90seconds. The retry
changes issue_sync_status and issue_receipts_hash, which previously changed the
model packet despite unchanged article, dossier, source resolution and findings.
A second publication retry using the exact retained completed triage reached GitHub
but the create command failed; source/publication gates remain held.

The general triage packet now excludes only those two remote workflow fields.
Review status, source verification, candidate hashes, evidence and current corpus
metadata stay in the packet. The Runner exact-input cache can therefore reuse a
completed finding result across a pure remote retry, while any changed candidate
still invalidates reuse. No root-made triage result or approval is introduced.

17 issue tests passed. The added retry regression proves the packet is identical
across a remote workflow failure and changes when the article hash changes.
Older completed receipts are preserved; root's explicit 边 remote-only replay
checked actual completed Luna-low result/hash, exact article+dossier, resolution,
current page metadata and exact normalized finding records before writing GitHub.
