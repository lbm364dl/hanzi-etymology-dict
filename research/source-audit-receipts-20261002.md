# Source audit receipts (2026-10-02)

The 的 continuation returned a research-shaped JSON response without recorded source searches or page inspections. The Runner correctly marked that attempt failed, but the book-evidence audit previously inspected result files without checking their stage receipts. Matching a book title, page and retained dossier text could therefore falsely certify an unsuccessful attempt.

The general audit now requires a complete research receipt, the prescribed gpt-6-luna/low configuration, a matching result hash, and recorded search or page-opening activity. Accepted citations retain receipt and result hashes. Failed outputs remain available as research hypotheses and OCR leads; they do not establish verified book coverage.

Regression tests cover missing, failed, changed-hash, tool-free and wrong-model receipts, plus a successful hash-bound fixture. Existing authored entries are not newly approved by this harness change.
