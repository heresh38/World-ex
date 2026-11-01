// Earth flora check: travels to New Meridian and looks at the Blender-grown trees (tools/blender/trees.py) in a park,
// a lowland forest, the conifer belt, the snow line on the Meridian Peaks and a suburb, with free-camera views, plus one
// on-foot view inside a wood. Reports LOD bucket counts, colliders and fps; fails on page errors.
// Usage: python3 -m http.server 8765 &  then  NODE_PATH=$(npm root -g) node tools/test/trees.js   (screenshots in test-out/trees)
const { chromium } = require('playwright');
const fs = require('fs');
const BASE = process.env.BASE || 'http://localhost:8765';
const OUT = process.env.OUT || 'test-out/trees';
fs.mkdirSync(OUT, { recursive: true });

(async () => {
  const b = await chromium.launch({ args: ['--ignore-gpu-blocklist', '--enable-unsafe-swiftshader', '--use-angle=swiftshader'] });
  const p = await b.newPage({ viewport: { width: 960, height: 540 } });
  const errs = [];
  p.on('pageerror', e => { errs.push(e.message); console.log('PAGE ERROR', e.message.slice(0, 400), (e.stack || '').split('\n').slice(0, 3).join(' | ')); });
  p.on('console', m => { if (m.type() === 'error') { errs.push(m.text()); console.log('CONSOLE ERROR', m.text().slice(0, 400)); } });
  await p.addInitScript(() => { localStorage.clear(); window.__TEST_QUALITY = 'low'; });
  const ev = (fn, arg) => p.evaluate(fn, arg);
  const wait = ms => p.waitForTimeout(ms);
  const shot = async n => { await p.screenshot({ path: `${OUT}/${n}.jpg`, type: 'jpeg', quality: 82, timeout: 600000 }); console.log('shot', n); };
  const waitPlay = async () => { await p.waitForFunction(() => window.__game && window.__game.state === 'play', null, { timeout: 1200000, polling: 1000 });
    await p.evaluate(() => { const g = window.__game; g.paused = false; g.menus.hidePause && g.menus.hidePause(); g.input.locked = true; g.input.enabled = true; }); };
  await p.goto(BASE + '/index.html');
  await p.waitForFunction(() => window.__game && window.__game.state === 'title', null, { timeout: 600000, polling: 500 });
  await ev(() => { const g = window.__game; g.save.settings.quality = 'low'; g.save.settings.dynamicRes = false; g.renderer.settings = g.save.settings; g.renderer.applyQuality(); g.startGame(true); });
  await waitPlay();
  const cam = async (n, pos, look) => {
    await ev(([pos, look]) => { const g = window.__game, V = g.camera.position.constructor; g.stationId = 'test'; const c = g.camera; c.position.set(...pos); c.lookAt(...look);
      g.camFocus = { pos: new V(...pos), look: new V(...look), orbit: false, q: c.quaternion.clone(), p0: c.position.clone(), q0: c.quaternion.clone(), fov0: 60, t0: 0 };
      g.world.flora.update(c, 0, true); }, [pos, look]);
    await wait(4500); await shot(n);
    console.log(n, JSON.stringify(await ev(() => { const g = window.__game, f = g.world.flora, t = [0, 0, 0];
      for (const k of f.kinds.values()) if (k.meshes) k.meshes.forEach((m, i) => { if (m) t[i] += m.ms[0].count; });
      return { fps: Math.round(g.fps), hero: t[0], mid: t[1], lod: t[2] }; })));
  };
  if (process.env.EARTH !== '0') {
  const t0 = Date.now();
  await ev(() => window.__game.travel('earth'));
  await waitPlay();
  console.log('earth load seconds', Math.round((Date.now() - t0) / 1000));
  await wait(4000);
  const info = await ev(() => {
    const w = window.__game.world, f = w.flora, per = {};
    for (const k of f.kinds.values()) if (k.list.length) per[k.name] = k.list.length;
    return { trees: w.treeCount, kinds: Object.keys(per).length, per, treeColliders: w.collision.boxes ? w.collision.boxes.filter(b => b.tag === 'tree').length : 'n/a' };
  });
  console.log('flora', JSON.stringify(info));
  // pick real instances to look at
  const spots = await ev(() => {
    const w = window.__game.world, f = w.flora, map = w.map;
    const at = (names, test) => { for (const n of names) { const k = f.kinds.get(n); if (!k) continue; for (const m of k.list) { const x = m.elements[12], y = m.elements[13], z = m.elements[14]; if (test(x, y, z)) return [x, y, z]; } } return null; };
    const out = (x, z) => Math.abs(x) > 600 || Math.abs(z) > 600;
    return {
      lowland: at(['TR_oak_a', 'TR_ash_a', 'TR_maple_a', 'TR_birch_b'], (x, y, z) => out(x, z) && y < 25 && y > 3),
      rain: at(['TR_emergent_a', 'TR_emergent_b'], (x, y, z) => out(x, z)),
      conifer: at(['TR_spruce_a', 'TR_spruce_c', 'TR_pine_b'], (x, y, z) => out(x, z) && y > 45),
      snow: at(['TR_spruce_snow_a', 'TR_spruce_snow_b', 'TR_pine_snow'], (x, y, z) => true),
      suburb: at(['TR_birch_a', 'TR_birch_b', 'TR_maple_autumn_a', 'TR_maple_b'], (x, y, z) => Math.max(Math.abs(x), Math.abs(z)) > 400 && Math.max(Math.abs(x), Math.abs(z)) < 495),
      field: at(['TR_umbrella_a', 'TR_umbrella_b', 'TR_oak_gold'], (x, y, z) => out(x, z)),
    };
  });
  console.log('spots', JSON.stringify(spots));

  const H = (x, z) => ev(([x, z]) => window.__game.world.map.height(x, z), [x, z]);
  // park (Founders' Park block at 2,-2: cherry ring round the fountain)
  await cam('t01_park', [262, 7, -262], [220, 3, -220]);
  await cam('t02_park_cherries', [205, 2.2, -242], [220, 4, -220]);
  // riverside promenade
  await cam('t03_riverside', [-120, 4, -300], [-40, 3, -333]);
  if (spots.suburb) { const [x, y, z] = spots.suburb; await cam('t04_suburb', [x - 30, 8, z + 30], [x, 4, z]); }
  if (spots.lowland) { const [x, y, z] = spots.lowland; await cam('t05_forest', [x + 40, y + 14, z + 40], [x, y + 5, z]); }
  if (spots.rain) { const [x, y, z] = spots.rain; await cam('t06_rainforest', [x + 60, y + 18, z + 60], [x, y + 14, z]); }
  if (spots.conifer) { const [x, y, z] = spots.conifer; await cam('t07_conifers', [x + 45, y + 15, z + 35], [x, y + 6, z]); }
  if (spots.snow) { const [x, y, z] = spots.snow; await cam('t08_snowline', [x + 35, y + 10, z + 45], [x, y + 4, z]); }
  if (spots.field) { const [x, y, z] = spots.field; await cam('t09_lone_tree', [x + 26, y + 4, z + 22], [x, y + 6, z]); }
  // the Meridian Peaks from the north edge of the city, and from the air
  await cam('t10_peaks', [-60, 40, -560], [-60, 110, -1100]);
  await cam('t11_peaks_air', [400, 220, -600], [-100, 90, -1050]);
  await ev(() => { const g = window.__game; g.stationId = null; g.camFocus = null; });
  // on foot in a wood (first person), trunk collision: walk into a tree
  if (spots.lowland) {
    const [x, y, z] = spots.lowland;
    const r = await ev(async ([x, y, z]) => {
      const g = window.__game, pl = g.player, map = g.world.map;
      pl.pos.set(x + 6, map.height(x + 6, z) + .2, z); pl.vel.set(0, 0, 0); pl.avatar.root.position.copy(pl.pos);
      pl.camYaw = Math.PI / 2; pl.camPitch = .12; pl.snapCamera = true; g.paused = false; g.input.locked = true; g.input.enabled = true;
      g.input.down.add('KeyW'); await new Promise(r => setTimeout(r, 3500)); g.input.down.delete('KeyW');
      return { start: x + 6, end: +pl.pos.x.toFixed(2), tree: x, blocked: Math.abs(pl.pos.x - x) > .2 };
    }, [x, y, z]);
    console.log('walk into trunk', JSON.stringify(r));
    await wait(2500); await shot('t12_on_foot');
    console.log('fps on foot', await ev(() => Math.round(window.__game.fps)));
  }
  }
  // frontier worlds: snowy conifers on the glacier shelf, jungle canopy, savanna trees on the mesas (streamed per chunk)
  for (const id of (process.env.PLANETS ?? 'vesper,thalassa,ares').split(',').filter(Boolean)) {
    await ev(i => window.__game.travel(i), id);
    await waitPlay(); await wait(5000);
    const t = await ev(() => {
      const g = window.__game, f = g.world.flora; if (!f) return null;
      let best = null, bd = 1e9;
      for (const k of f.kinds.values()) if (k.alive && k.species !== 'rock' && k.species !== 'bush') for (let i = 0; i < k.n; i++) if (k.alive[i]) {
        const d = Math.hypot(k.pos[i * 3], k.pos[i * 3 + 2]); if (d > 40 && d < bd) { bd = d; best = [k.pos[i * 3], k.pos[i * 3 + 1], k.pos[i * 3 + 2], k.h]; }
      }
      if (best) {   // a camera between the landing site and the tree, clear of the ground
        const [x, y, z, h] = best, L = Math.hypot(x, z), r = h * 1.5 + 14, cx = x - x / L * r, cz = z - z / L * r;
        best = [cx, Math.max(g.world.height(cx, cz) + 3, y + h * .5), cz, x, y + h * .45, z];
      }
      return { trees: f.count, best };
    });
    console.log(id, JSON.stringify(t));
    if (t && t.best) await cam('t20_' + id, t.best.slice(0, 3), t.best.slice(3));
    await ev(() => { const g = window.__game; g.stationId = null; g.camFocus = null; });
  }
  console.log('page errors:', errs.length);
  await b.close();
  process.exit(errs.length ? 1 : 0);
})().catch(e => { console.error('TREES FAILED', e); process.exit(2); });
