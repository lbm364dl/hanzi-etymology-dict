# Preserve supported records during a narrow array removal

The 学 repair needed to remove one irrelevant asset-catalogue history record while preserving two already researched written-form records. A later factual finding incorrectly treated another record as the removed item, and automated revision deleted additional supported history. Merely allowing the entire history array for a patch could not enforce the intended boundary.

The patch harness now accepts an explicit `preserve_array_items` contract in inputs or feedback. It maps existing array paths to exact existing records that must remain in their original relative order. These records must already occur in the supplied article. The author still chooses the actual patch; the harness rejects removal, alteration or reordering of protected records and restores the invalid array before a bounded repair attempt. Other unprotected records can be removed. This is optional scoped editing machinery, not a universal rule that all historical prose must be frozen.

The coordinator applies this contract only when the authorized repair is a narrow deletion and retained records independently remain supported. A legitimate change to a protected factual claim requires a new scope and fresh reviews, not an automatic bypass. No prose is generated or approved by this check.

Verification: the new regression rejects accidental wholesale history deletion and accepts removing only the unwanted record, preserving the original input. Six existing targeted-patch tests also pass. 学 is the live smoke repair; no published entry is recertified by changing this contract.
