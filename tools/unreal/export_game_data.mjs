// Writes the browser game's static data (src/game/data.js) as JSON for the Unreal port:
//   node tools/unreal/export_game_data.mjs            -> unreal/ShatteredOrbit/Data/game_data.json
// data.js stays the single source of truth; Content/Python/import_assets.py turns the JSON into data assets
// (DA_<Archetype> weapon data and DA_LootTables). Name pools that data.js keeps private are read from its source text.
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const root = join(dirname(fileURLToPath(import.meta.url)), '..', '..');
const dataPath = join(root, 'src', 'game', 'data.js');
const D = await import(pathToFileURL(dataPath).href);
const src = readFileSync(dataPath, 'utf8');

function privateConst(name) {
  const m = src.match(new RegExp(`const ${name} = (\\[[^\\]]*\\]|\\{[^}]*\\})`));
  if (!m) throw new Error(`data.js: ${name} not found`);
  return Function(`"use strict"; return (${m[1]});`)();
}

// Unreal-only tuning on top of data.js (the browser build keeps its numbers). gooGrav: gravity scale of the goo arc.
const UNREAL_TUNING = {
  // the brood launcher is the heavy horror launcher: a long, flat lob and a wide burst
  brood: { vel: 46, gooGrav: .16, range: 90, splash: 6.0 },
};

// Every gun has one name, whatever its rarity or rolls (the owner's rule: drops differ by small stat rolls and by
// perks, never by name). The names come from data.js EXOTIC_NAMES; a few are replaced here.
const TITLE_OVERRIDES = { smg: 'Kestrel-X9' };

const archetypes = {};
for (const [id, A] of Object.entries(D.ARCHETYPES)) {
  const h = D.weaponHandling(id);
  archetypes[id] = { ...A, sights: D.sightOptions(id), defaultSight: A.sight || D.sightOptions(id)[0], adsTime: h.ads, sprintOut: h.sprintOut,
    title: TITLE_OVERRIDES[id] || D.EXOTIC_NAMES[id] || A.name, ...(UNREAL_TUNING[id] || {}) };
}

const out = {
  source: 'src/game/data.js',
  archetypes,
  rarity: D.RARITY,
  perks: D.PERKS,
  sights: D.SIGHTS,
  slots: D.SLOT_NAMES,
  classes: D.WEAPON_CLASSES,
  shaders: D.SHADERS,
  names: {
    prefix: privateConst('PREFIX'), noun: privateConst('NOUN'), maker: privateConst('MAKER'), modelCode: privateConst('MODEL_CODE'),
    bioPrefix: privateConst('BIO_PREFIX'), bioNoun: privateConst('BIO_NOUN'), exotic: D.EXOTIC_NAMES,
  },
};
const dest = join(root, 'unreal', 'ShatteredOrbit', 'Data', 'game_data.json');
mkdirSync(dirname(dest), { recursive: true });
writeFileSync(dest, JSON.stringify(out, null, 1) + '\n');
console.log(`game data: ${Object.keys(archetypes).length} archetypes, ${D.RARITY.length} rarities, ${Object.keys(D.PERKS).length} perks -> ${dest}`);
