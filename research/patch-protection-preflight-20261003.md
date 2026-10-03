# Contradictory patch scopes

The 百 source repair supplied both exact preservation of a relationship record and permission to edit that record's text and citations. Actual agent retries could not satisfy both. The failed packet and outputs remain retained; no proposal from it was accepted.

The generic patch helper now rejects this contradiction before invoking an agent. Explicit edit paths targeting a protected array record or its descendants are incompatible with exact preservation. An ancestor array edit remains allowed so an author may remove an unprotected item while retaining protected records in order. A regression verifies rejection before invocation; the existing array-removal preservation regression verifies that valid repair workflow remains supported. The coordinator must repair its packet, not ask agents to override an invariant.

The coordinating 包 packet later attempted to preserve generated meaning edges while editing the relationship array. Those edges are regenerated from protected source sense/development records and cannot be directly authored. The failed actual attempt is retained. Preflight now rejects direct protection of generated relationship records before agent invocation, directing the coordinator to protect the source records instead. The corrected 包 packet leaves the meaning-history fields outside its edit scope and receives fresh actual reviews.
