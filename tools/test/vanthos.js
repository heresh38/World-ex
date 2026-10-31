// VANTHOS check: land, look around the districts, stream enemies, ride a lift, go down the metro and come back.
// Usage: python3 -m http.server 8765 &  then  node tools/test/vanthos.js   (screenshots in test-out/)
const { chromium } = require('playwright');
const fs = require('fs');
const BASE = process.env.BASE || 'http://localhost:8765';
const OUT = process.env.OUT || 'test-out';
fs.mkdirSync(OUT, { recursive: true });

(async () => {
  const b = await chromium.launch({ args: ['--ignore-gpu-blocklist', '--enable-unsafe-swiftshader', '--use-angle=swiftshader'] });
  const p = await b.newPage({ viewport: { width: 1280, height: 720 } });
  const errs = [];
  p.on('pageerror', e => { errs.push(e.message); console.log('PAGE ERROR', e.message.slice(0, 400)); });
  p.on('console', m => { if (m.type() === 'error') { errs.push(m.text()); console.log('CONSOLE ERROR', m.text().slice(0, 400)); } });
  await p.addInitScript(() => { localStorage.clear(); window.__TEST_QUALITY = 'medium'; });
  const ev = (fn, arg) => p.evaluate(fn, arg);
  const wait = ms => p.waitForTimeout(ms);
  const shot = async n => { await p.screenshot({ path: `${OUT}/${n}.jpg`, type: 'jpeg', quality: 82, timeout: 300000 }); console.log('shot', n); };
  const waitPlay = async () => { await p.waitForFunction(() => window.__game && window.__game.state === 'play', null, { timeout: 900000, polling: 1000 });
    await p.evaluate(() => { const g = window.__game; g.paused = false; g.menus.hidePause(); g.input.locked = true; g.input.enabled = true; }); };
  await p.goto(BASE + '/index.html');
  await p.waitForFunction(() => window.__game && window.__game.state === 'title', null, { timeout: 300000, polling: 500 });
  await ev(() => { const g = window.__game; g.save.settings.quality = 'medium'; g.save.settings.dynamicRes = false; g.renderer.settings = g.save.settings; g.renderer.applyQuality(); });
  await p.click('[data-act="title-play"]');
  await waitPlay();
  const t0 = Date.now();
  await ev(() => window.__game.travel('vanthos'));
  await waitPlay();
  console.log('load seconds', Math.round((Date.now() - t0) / 1000));
  await wait(3000); await shot('v01_landing');
  const info = await ev(() => { const w = window.__game.world; return { blocks: w.map.blocks.length, lots: w.map.lots.length, sites: w.sites.length, caches: w.caches.length, lifts: w.lifts.length, metros: (w.metros || []).length, shards: w.shards.length, district: w.D && w.D.name }; });
  console.log('city', JSON.stringify(info));
  // free camera views
  const cam = async (n, pos, look) => {
    await ev(([pos, look]) => { const g = window.__game, V = g.camera.position.constructor; g.stationId = 'test'; const c = g.camera; c.position.set(...pos); c.lookAt(...look);
      g.camFocus = { pos: new V(...pos), look: new V(...look), orbit: false, q: c.quaternion.clone(), p0: c.position.clone(), q0: c.quaternion.clone(), fov0: 60, t0: 0 }; }, [pos, look]);
    await wait(3500); await shot(n);
  };
  await cam('v02_skyline', [-700, 160, 1500], [0, 140, 0]);
  await cam('v03_spire', [260, 60, 320], [0, 200, 0]);
  await cam('v04_crown_street', [420, 6, -60], [300, 30, -60]);
  await cam('v05_flooded', [-1050, 30, 380], [-900, 0, 250]);
  await cam('v06_industrial', [1100, 40, -150], [900, 0, -300]);
  await cam('v07_elevated_hwy', [-150, 40, 1150], [-260, 12, 950]);
  await ev(() => { const g = window.__game; g.stationId = null; g.camFocus = null; });
  // walk into the Old Quarter: packs stream in
  const stream = await ev(async () => {
    const g = window.__game, w = g.world, V = g.player.pos.constructor;
    const st = w.sites.find(s => s.D.id === 'old');
    g.player.pos.set(st.pos.x + 30, 0, st.pos.z); g.player.avatar.root.position.copy(g.player.pos);
    g.paused = false; g.input.locked = true; g.input.enabled = true;
    await new Promise(r => setTimeout(r, 2500));
    return { spawned: st.spawned, live: st.live.length, types: st.live.map(e => e.type), enemies: g.enemies.list.length };
  });
  console.log('stream', JSON.stringify(stream));
  await ev(() => { const g = window.__game; g.input.locked = true; g.input.enabled = true; if (g.save.settings.view !== 'third') g.toggleView(); });
  await wait(2500); await shot('v08_aliens');
  // faction war in the Industrial Spine: aliens vs raiders
  const war = await ev(async () => {
    const g = window.__game, w = g.world, V = g.player.pos.constructor;
    const x = 1000, z = -250;
    g.player.pos.set(x + 200, 0, z); g.player.avatar.root.position.copy(g.player.pos);
    const a = g.enemies.spawn('hulk', new V(x, 0, z), 10), r = g.enemies.spawn('trooper', new V(x + 12, 0, z), 10);
    const h0 = a.hp, r0 = r.hp; g.paused = false;
    await new Promise(res => setTimeout(res, 7000));
    return { factionWar: w.factionWar, hulkHurt: a.hp < h0, trooperHurt: r.hp < r0 };
  });
  console.log('war', JSON.stringify(war));
  // ride a lift to a rooftop
  const lift = await ev(async () => {
    const g = window.__game, w = g.world;
    const it = w.interactables.find(i => i.id === 'lift' && i.verb === 'Ride to the roof');
    if (!it) return 'none';
    g.player.pos.copy(it.pos); g.player.avatar.root.position.copy(it.pos);
    it.action(); await new Promise(r => setTimeout(r, 2500));
    return { y: +g.player.pos.y.toFixed(1), grounded: g.player.grounded };
  });
  console.log('lift', JSON.stringify(lift));
  await shot('v09_rooftop');
  // the metro
  await ev(() => { const g = window.__game, w = g.world; const it = w.interactables.find(i => i.id === 'metro'); g.player.pos.copy(it.pos); it.action(); });
  await p.waitForFunction(() => window.__game.state === 'loading', null, { timeout: 60000 }).catch(() => {});
  await waitPlay(); await wait(3000); await shot('v10_metro');
  const metro = await ev(async () => { const g = window.__game, w = g.world;
    const far = [...w.cells.values()].sort((a, b) => b.pos.length() - a.pos.length())[0];
    g.player.pos.copy(far.pos).setY(0.2); g.player.avatar.root.position.copy(g.player.pos);
    await new Promise(r => setTimeout(r, 2500));
    return { cells: w.cells.size, caches: w.caches.length, enemies: g.enemies.list.length, kind: w.kind }; });
  console.log('metro', JSON.stringify(metro));
  await shot('v11_metro_deep');
  await ev(() => { const g = window.__game, w = g.world; const it = w.interactables.find(i => i.id === 'exit'); it.action(); });
  await p.waitForFunction(() => window.__game.state === 'loading', null, { timeout: 60000 }).catch(() => {});
  await waitPlay(); await wait(2000);
  console.log('back', await ev(() => window.__game.world.kind));
  console.log('fps', await ev(() => Math.round(window.__game.fps)));
  console.log('page errors:', errs.length);
  await b.close();
  process.exit(errs.length ? 1 : 0);
})().catch(e => { console.error('VANTHOS FAILED', e); process.exit(2); });
