# Contradictory patch scopes

The 百 source repair supplied both exact preservation of a relationship record and permission to edit that record's text and citations. Actual agent retries could not satisfy both. The failed packet and outputs remain retained; no proposal from it was accepted.

The generic patch helper now rejects this contradiction before invoking an agent. Explicit edit paths targeting a protected array record or its descendants are incompatible with exact preservation. An ancestor array edit remains allowed so an author may remove an unprotected item while retaining protected records in order. A regression verifies rejection before invocation; the existing array-removal preservation regression verifies that valid repair workflow remains supported. The coordinator must repair its packet, not ask agents to override an invariant.
