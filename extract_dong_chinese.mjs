// Extract all etymology data from Dong Chinese / chinese-lexicon using the ESM bundle
import { writeFileSync } from 'fs';

const lib = await import('./sources/chinese-lexicon/dist/index.esm.js');

const results = {};
let count = 0;

// Iterate over all CJK Unified Ideographs basic block
for (let cp = 0x4E00; cp <= 0x9FFF; cp++) {
    const ch = String.fromCodePoint(cp);
    try {
        const etym = lib.getEtymology(ch);
        if (etym && (etym.notes || (etym.components && etym.components.length > 0))) {
            results[ch] = etym;
            count++;
        }
    } catch (e) { /* skip */ }
}

// CJK Extension A
for (let cp = 0x3400; cp <= 0x4DBF; cp++) {
    const ch = String.fromCodePoint(cp);
    try {
        const etym = lib.getEtymology(ch);
        if (etym && (etym.notes || (etym.components && etym.components.length > 0))) {
            results[ch] = etym;
            count++;
        }
    } catch (e) { /* skip */ }
}

console.log(`Extracted ${count} etymology entries`);
writeFileSync('./sources/chinese-lexicon/dong_etymologies.json', JSON.stringify(results));
console.log('Written to sources/chinese-lexicon/dong_etymologies.json');

// Stats
const types = {};
for (const [ch, etym] of Object.entries(results)) {
    const compTypes = (etym.components || []).map(c => c.type);
    const hasSound = compTypes.includes('sound');
    const hasMeaning = compTypes.includes('meaning');
    const hasIconic = compTypes.includes('iconic');

    let formationType;
    if (hasSound && hasMeaning) formationType = 'phono-semantic';
    else if (hasMeaning && !hasSound && !hasIconic) formationType = 'compound-ideographic';
    else if (hasIconic && !hasSound && !hasMeaning) formationType = 'pictographic/ideographic';
    else if (hasIconic) formationType = 'mixed-iconic';
    else formationType = 'other';

    types[formationType] = (types[formationType] || 0) + 1;
}
console.log('Formation types:', JSON.stringify(types, null, 2));
