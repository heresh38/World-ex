// Wardrobe check: opens the pod, walks every tab, applies face presets, sliders, colours and clothing slots for both
// frames, and screenshots the result. Usage: python3 -m http.server 8765 &  then  node tools/test/wardrobe.js
const { chromium } = require('playwright');
const fs = require('fs');
const BASE = process.env.BASE || 'http://localhost:8765';
const OUT = process.env.OUT || 'test-out';
fs.mkdirSync(OUT, { recursive: true });

(async () => {
  const b = await chromium.launch({ args: ['--ignore-gpu-blocklist', '--enable-unsafe-swiftshader', '--use-angle=swiftshader'] });
  const p = await b.newPage({ viewport: { width: 960, height: 540 } });
  const errs = [];
  p.on('pageerror', e => { errs.push(e.message); console.log('PAGE ERROR', e.message.slice(0, 400)); });
  p.on('console', m => { if (m.type() === 'error') { errs.push(m.text()); console.log('CONSOLE ERROR', m.text().slice(0, 400)); } });
  await p.addInitScript(() => { localStorage.clear(); window.__TEST_QUALITY = 'low'; });
  const ev = (fn, arg) => p.evaluate(fn, arg);
  const wait = ms => p.waitForTimeout(ms);
  const shot = async n => { await p.screenshot({ path: `${OUT}/${n}.jpg`, type: 'jpeg', quality: 82, timeout: 300000 }); console.log('shot', n); };
  const click = async sel => { await p.click(sel, { timeout: 60000 }); await wait(700); };
  // every hair style of the current body (hair tab open), plus a turned-around view of each
  const hairTour = async tag => {
    await click('[data-act="tab"][data-v="hair"]');
    const ids = await ev(() => Object.keys(window.__game.player.avatar.wardrobe.hair || {}));
    console.log('hair styles', tag, ids.join(', '));
    for (const id of ids) {
      await click(`[data-act="wear"][data-k="hair"][data-v="${id}"]`);
      const vis = await ev(id => { const o = window.__game.player.avatar.items.hair[id]; let v = 0; o.traverse(m => { if (m.isMesh && m.visible) v++; }); return v; }, id);
      if (!vis) errs.push('hair ' + id + ' not visible');
      await shot(`h_${tag}_${id}`);
      await ev(() => { const g = window.__game; g.wardrobeSpin = (g.wardrobeSpin || 0) + 1.57; });
      await wait(900); await shot(`h_${tag}_${id}_side`);
      await ev(() => { const g = window.__game; g.wardrobeSpin += 1.57; });
      await wait(900); await shot(`h_${tag}_${id}_back`);
      await ev(() => { const g = window.__game; g.wardrobeSpin -= 3.14; });
      await wait(500);
    }
  };
  // every clothing item per slot (wear tab), screenshot each
  const wearTour = async tag => {
    await click('[data-act="tab"][data-v="wear"]');
    const W = await ev(() => Object.fromEntries(Object.entries(window.__game.player.avatar.wardrobe).filter(([k]) => k !== 'hair' && !k.startsWith('under')).map(([k, v]) => [k, Object.keys(v)])));
    console.log('wardrobe', tag, JSON.stringify(W));
    for (const [slot, ids] of Object.entries(W)) {
      for (const id of ids) { await click(`[data-act="wear"][data-k="${slot}"][data-v="${id}"]`); await shot(`c_${tag}_${slot}_${id}`); }
      if (slot === 'head' || slot === 'dress' || slot === 'outer') await click(`[data-act="wear"][data-k="${slot}"][data-v="none"]`);
    }
    const mask = await ev(() => window.__game.player.avatar.coverU && window.__game.player.avatar.coverU.value);
    console.log('skin cover mask', tag, mask);
  };

  await p.goto(BASE + '/index.html');
  await p.waitForFunction(() => window.__game && window.__game.state === 'title', null, { timeout: 300000, polling: 500 });
  await ev(() => { const g = window.__game; g.save.settings.quality = 'low'; g.save.settings.dynamicRes = false; g.renderer.settings = g.save.settings; g.renderer.applyQuality(); });
  await click('[data-act="title-play"]');
  await p.waitForFunction(() => window.__game && window.__game.state === 'play', null, { timeout: 900000, polling: 1000 });
  await wait(2500);
  const open = async () => {
    await ev(() => { const g = window.__game, s = g.world.stations.wardrobe; g.player.pos.set(...s.pos); g.player.avatar.root.position.set(...s.pos); g.input.locked = true; g.input.enabled = true; });
    await wait(300); await p.keyboard.press('KeyE'); await wait(2600);
  };
  await open();
  const info = await ev(() => { const a = window.__game.player.avatar; return { body: a.meta && a.meta.sex, regions: Object.keys(a.regions), items: Object.fromEntries(Object.entries(a.items).map(([k, v]) => [k, Object.keys(v)])), morphMeshes: a.morphMeshes.length, wear: a.wear }; });
  console.log('avatar', JSON.stringify(info));
  await shot('w01_face_default');
  // face presets + eye colour + brows
  for (const [k, v] of [['nose', 'nose_button'], ['mouth', 'mouth_full'], ['eyes', 'eyes_almond'], ['ears', 'ears_elven']]) await click(`[data-act="face"][data-k="${k}"][data-v="${v}"]`);
  await click('[data-act="eyecol"][data-v="#8aa05a"]');
  await click('[data-act="brow"][data-v="1"]');
  await ev(() => { const el = document.querySelector('[data-slider="cheekbones"]'); el.value = .8; el.dispatchEvent(new Event('input', { bubbles: true })); });
  await wait(600);
  const morph = await ev(() => { const a = window.__game.player.avatar, o = a.morphMeshes[0]; return { nose: o.morphTargetInfluences[o.morphTargetDictionary.nose_button], cheek: o.morphTargetInfluences[o.morphTargetDictionary.cheekbones] }; });
  console.log('morphs', morph);
  await shot('w02_face_custom');
  // hair
  await click('[data-act="tab"][data-v="hair"]');
  await click('[data-act="wear"][data-k="hair"][data-v="bob"]');
  await click('[data-act="haircol"][data-v="#b9a3e8"]');
  await shot('w03_hair_bob');
  await hairTour('female');
  // clothing: default set, then strip to the base body, then mixed
  await click('[data-act="tab"][data-v="wear"]');
  await shot('w04_wear_default');
  for (const slot of ['outer', 'vest', 'hands']) await click(`[data-act="wear"][data-k="${slot}"][data-v="none"]`);
  await click('[data-act="tint"][data-k="top"][data-v="#8c1d26"]');
  await shot('w05_wear_mixed');
  for (const slot of ['top', 'legs', 'feet']) await click(`[data-act="wear"][data-k="${slot}"][data-v="none"]`);
  const under = await ev(() => { const a = window.__game.player.avatar; return Object.fromEntries(['undertop', 'underbottom'].filter(k => a.items[k]).map(k => [k, Object.values(a.items[k]).some(o => o.visible)])); });
  console.log('underwear visible with clothes off', JSON.stringify(under));
  if (Object.values(under).some(v => !v)) errs.push('underwear hidden while body uncovered');
  await click('[data-act="tab"][data-v="body"]');
  await click('[data-act="skin"][data-v="#8d5638"]');
  await shot('w06_base_body');
  await wearTour('female');
  // male frame
  await click('[data-act="tab"][data-v="body"]');
  await click('[data-act="body"][data-v="male"]');
  await wait(3000);
  await click('[data-act="tab"][data-v="wear"]');
  await shot('w07_male_default');
  await click('[data-act="wear"][data-k="head"][data-v="pioneer"]');
  await shot('w08_male_helmet');
  await click('[data-act="wear"][data-k="head"][data-v="none"]');
  await hairTour('male');
  await wearTour('male');
  await click('[data-act="tab"][data-v="face"]');
  for (const [k, v] of [['nose', 'nose_aquiline'], ['mouth', 'mouth_thin'], ['eyes', 'eyes_hooded']]) await click(`[data-act="face"][data-k="${k}"][data-v="${v}"]`);
  await shot('w09_male_face');
  const saved = await ev(() => JSON.stringify(window.__game.save.character));
  console.log('saved character', saved);
  // leave and walk in third person to see the clothed skinned body move
  await p.keyboard.press('Escape'); await wait(800);
  await ev(() => { const g = window.__game; if (g.save.settings.view !== 'third') g.toggleView(); g.input.locked = true; g.input.enabled = true; });
  await p.keyboard.down('KeyW'); await wait(1800); await shot('w10_male_walk'); await p.keyboard.up('KeyW');
  console.log('page errors:', errs.length);
  await b.close();
  process.exit(errs.length ? 1 : 0);
})().catch(e => { console.error('WARDROBE FAILED', e); process.exit(2); });
