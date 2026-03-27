/**
 * Extract historical character form SVG images from Dong Chinese's etymology data.
 *
 * Reads etymologyImages.js, extracts inline SVG strings for each script type
 * (oracle, bronze, seal, cursive, traditional), and writes them as individual
 * SVG files organized by character. Also produces a JSON manifest.
 *
 * Usage:  node extract_dong_svgs.mjs
 */

import { readFileSync, mkdirSync, writeFileSync } from "node:fs";
import { join } from "node:path";

const SRC = join(
  import.meta.dirname,
  "sources/chinese-lexicon/etymology/etymologyImages.js"
);
const OUT_DIR = join(import.meta.dirname, "output/glyphs/dong_chinese");

// ---------------------------------------------------------------------------
// 1. Read the source file
// ---------------------------------------------------------------------------
const src = readFileSync(SRC, "utf-8");

// ---------------------------------------------------------------------------
// 2. Parse the etymologyImages object
//
// The file defines a JS object with top-level keys (oracle, bronze, seal,
// cursive, traditional).  Under each key, entries look like one of:
//
//   "女": svg(`<svg ...>...</svg> `),
//   '亟': svg(`<svg ...>...</svg>`),
//   "頭": createSVG("頭"),
//
// We iterate through the sections and extract every character + SVG pair.
// ---------------------------------------------------------------------------

const SCRIPT_TYPES = ["oracle", "bronze", "seal", "cursive", "traditional"];

// Map from scriptType -> { character: svgString }
const data = {};

// Identify section boundaries.  Each section starts with a line like
//     oracle: {
// and ends when the next section (or the closing `};`) is reached.
const sectionRanges = [];
for (const st of SCRIPT_TYPES) {
  // Match "    oracle: {" at the beginning of a line
  const re = new RegExp(`^\\s+${st}:\\s*\\{`, "m");
  const m = re.exec(src);
  if (m) {
    sectionRanges.push({ type: st, start: m.index });
  }
}
// Sort by position
sectionRanges.sort((a, b) => a.start - b.start);

for (let i = 0; i < sectionRanges.length; i++) {
  const { type, start } = sectionRanges[i];
  const end =
    i + 1 < sectionRanges.length ? sectionRanges[i + 1].start : src.length;
  const section = src.slice(start, end);

  data[type] = {};

  // --- Entries using svg(`...`) ---
  // Pattern: "char": svg(`<svg ...>`)  or  'char': svg(`<svg ...>`)
  // The SVG content is inside svg(` ... `)
  const svgEntryRe = /["'](.+?)["']\s*:\s*svg\(\s*`([\s\S]*?)`\s*\)/g;
  let em;
  while ((em = svgEntryRe.exec(section)) !== null) {
    const char = em[1];
    const svgContent = em[2].trim();
    data[type][char] = svgContent;
  }

  // --- Entries using createSVG("char") ---
  const createSvgRe = /["'](.+?)["']\s*:\s*createSVG\(\s*["'](.+?)["']\s*\)/g;
  while ((em = createSvgRe.exec(section)) !== null) {
    const char = em[1];
    const innerChar = em[2];
    // Reproduce the createSVG function output
    const svgContent =
      `<svg version="1.0" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" preserveAspectRatio="xMidYMid meet">` +
      ` <text x="50%" y="50%" text-anchor="middle" alignment-baseline="central" dominant-baseline="central" >${innerChar}</text>` +
      ` </svg>`;
    data[type][char] = svgContent;
  }
}

// ---------------------------------------------------------------------------
// 3. Write SVG files and build the manifest
// ---------------------------------------------------------------------------
const manifest = {};
const stats = { totalCharacters: 0, totalImages: 0, byScriptType: {} };

for (const st of SCRIPT_TYPES) {
  stats.byScriptType[st] = 0;
}

// Collect all unique characters across all script types
const allChars = new Set();
for (const st of SCRIPT_TYPES) {
  for (const ch of Object.keys(data[st] || {})) {
    allChars.add(ch);
  }
}

for (const char of [...allChars].sort()) {
  const charDir = join(OUT_DIR, char);
  mkdirSync(charDir, { recursive: true });

  manifest[char] = {};

  for (const st of SCRIPT_TYPES) {
    if (data[st] && data[st][char]) {
      const fileName = `${char}_${st}.svg`;
      const filePath = join(charDir, fileName);
      writeFileSync(filePath, data[st][char] + "\n", "utf-8");
      manifest[char][st] = fileName;
      stats.byScriptType[st]++;
      stats.totalImages++;
    }
  }
}

stats.totalCharacters = allChars.size;

// Write manifest
mkdirSync(OUT_DIR, { recursive: true });
writeFileSync(
  join(OUT_DIR, "manifest.json"),
  JSON.stringify(manifest, null, 2) + "\n",
  "utf-8"
);

// ---------------------------------------------------------------------------
// 4. Report statistics
// ---------------------------------------------------------------------------
console.log("=== Dong Chinese SVG Extraction Complete ===\n");
console.log(`Total characters: ${stats.totalCharacters}`);
console.log(`Total images:     ${stats.totalImages}\n`);
console.log("Images per script type:");
for (const st of SCRIPT_TYPES) {
  console.log(`  ${st.padEnd(14)} ${stats.byScriptType[st]}`);
}
console.log(`\nOutput directory: ${OUT_DIR}`);
console.log(`Manifest:         ${join(OUT_DIR, "manifest.json")}`);
