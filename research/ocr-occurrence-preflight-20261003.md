# Duplicate raw-span proposals

The genuine 的 pronunciation OCR verification initially received 37 differently named proposals for four overlapping target locations because of an occurrence enumeration bug. Its result was retained but rejected as invalid evidence. Unique occurrence IDs alone did not protect against duplicated raw spans.

The generic OCR packet now rejects duplicate and overlapping spans before any agent invocation. Distinct adjacent occurrences remain valid. Tests cover identical spans with different IDs, a contained overlap, and separate occurrences of the same literal text. The researcher is rebuilding the packet with four exact targets and obtaining a new independent scan receipt; the rejected attempt does not authorize a correction.
