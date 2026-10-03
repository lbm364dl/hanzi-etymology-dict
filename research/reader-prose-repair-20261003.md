# Citation labels in repair output

The actual 帮 author and prose-repair stages returned bracketed evidence IDs in explanation text despite the existing citation instructions. This is a general output-contract failure, not a character exception. The repair schema now forbids known evidence IDs and transport aliases in text. Up to three distinct genuine agent attempts retain validation feedback; exhaustion still rejects the candidate. Only flagged prose leaves can change, citations and metadata remain frozen, and changed prose still requires fresh independent reviews.

A fixture regression verifies rejection of the first invalid response, a clean second response, separate stage paths, preserved input and unchanged citation and certainty fields. The reader-style and issue-triage suites pass 21 tests. Synthetic fixtures are not production review approvals.
