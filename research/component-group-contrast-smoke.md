# Component group contrast smoke audit

Date: 2026-09-27

Scope: diagnostic spot check of the new learner policy in `pipeline/structured.py` against two currently published v2 Chinese entries. This is not a new publication review and does not alter either entry or its review receipt.

## Result: pass, with one useful wording refinement

### 清 — ordinary side/full positional form

The published article and dossier are `content/entries/6E05.json` and `content/dossiers/6E05.json`. The component card for 氵 has `origin_form: 水`, `origin_relation: full_form`, and `form_status: stylized`; its detailed text calls 氵 the compressed, stylized side form of 水. The learner card likewise says “side form of 水.” Its cited dossier evidence includes the received 說文 analysis “从水青聲,” together with external dictionary/research notes explicitly identifying 氵 as the conventional side form of 水 and explaining its water-category contribution. The article does not claim that 水 was historically replaced by 氵, and its phonetic evidence is attached only to 青. This is consistent with the policy’s distinction between a current positional form and a chronological predecessor.

The article’s recorded independent factual and readability reviews both passed for the exact stored article and dossier hashes. These receipts are provenance context only; this audit does not renew them.

### 脑 — whole-character simplification with contested traditional analysis

The published article and dossier are `content/entries/8111.json` and `content/dossiers/8111.json`. The article has no internal components for 脑 and describes it as a simplified form of 腦. Its learner overview is limited to the useful current meaning and counterpart, then says the traditional graph’s construction is disputed. In the expert formation account, the source-derived 匘 analyses are kept distinct: the Shuowen-derived account describes 匕, hair-like 巛 and 囟, while a competing modern proposal attributes a figure/axe picture and possible sound role to 夒. The dossier states that this competing sound assignment is not independently established and lacks a verified same-system sound comparison. Modern matching nǎo readings for 脑 and 腦 are explicitly not treated as proof of ancient phonetic function. Nothing assigns the historical proposal to the visibly simplified 㐫 shape.

The inspected external records are secondary lexicographic/database accounts and the dossier records that early glyph images were not directly verified. Accordingly, the pass here is specifically that the learner policy does not collapse simplification into a historical component analysis or transfer a disputed traditional phonetic role to the replacement shape; this audit does not decide 腦/匘’s palaeographic origin.

## Pipeline implication

The policy’s existing explicit rule for 氵/水 and 亻/人 is effective in this contrast, and its separate instruction not to transfer a historical component’s role to a modern entry is also reflected in 脑. One small general clarification could make that protection harder to misread: whenever current component identity is established but its ancient role or continuity is uncertain, state the current component relation and function at its supported scope, then limit the uncertainty to the historical claim. Do not let “uncertain origin” erase a supported modern positional form; equally, a standardized simplified counterpart or visual retention alone does not establish historical continuity or phonetic inheritance. This is a general instruction only; these two entries need no repair based on this smoke check.
