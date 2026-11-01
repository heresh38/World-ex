// VANTHOS as a dead, ruined, overgrown city: fixed-viewpoint performance (draw calls, triangles, render and update time,
// texture memory under the iPhone cap window.__MAXTEX = 1024), resident enemies (present before any interaction, AI
// throttled far away), no lit windows, and screenshots for review in test-out/ruins/ (street level in several districts,
// an aerial, inside a ruined hall, an overgrowth close-up, enemies roaming, the Spire).
// Usage: python3 -m http.server 8765 &  then  NODE_PATH=$(npm root -g) node tools/test/ruins.js
//   PERF_ONLY=1   only the viewpoint numbers (works against an older build too: BASE=http://localhost:8766)
//   SHOTS=a,b     only these screenshots
const { chromium } = require('playwright');
const fs = require('fs');
const BASE = process.env.BASE || 'http://localhost:8765';
const OUT = (process.env.OUT || 'test-out') + '/ruins';
const PERF_ONLY = !!process.env.PERF_ONLY;
const ONLY = process.env.SHOTS ? new Set(process.env.SHOTS.split(',')) : null;
fs.mkdirSync(OUT, { recursive: true });

(async () => {
  const b = await chromium.launch({ args: ['--ignore-gpu-blocklist', '--enable-unsafe-swiftshader', '--use-angle=swiftshader'] });
  const p = await b.newPage({ viewport: { width: 1280, height: 720 } });
  const errs = [], fails = [];
  p.on('pageerror', e => { errs.push(e.message); console.log('PAGE ERROR', e.message.slice(0, 400)); });
  p.on('console', m => { if (m.type() === 'error') { errs.push(m.text()); console.log('CONSOLE ERROR', m.text().slice(0, 400)); } });
  await p.addInitScript(() => { localStorage.clear(); window.__TEST_QUALITY = 'medium'; window.__MAXTEX = 1024; });
  const ev = (fn, arg) => p.evaluate(fn, arg);
  const wait = ms => p.waitForTimeout(ms);
  const check = (ok, what, info = '') => { console.log((ok ? 'PASS ' : 'FAIL ') + what + (info !== '' ? ' · ' + (typeof info === 'string' ? info : JSON.stringify(info)) : '')); if (!ok) fails.push(what); };
  // the last frame stays on the canvas during the capture (swiftshader frames piling up behind a slow capture eat memory)
  const shot = async n => {
    if (ONLY && !ONLY.has(n)) return;
    await ev(() => { const r = window.__game.renderer; if (!r.__render) { r.__render = r.render; r.render = () => {}; } });
    try { await p.screenshot({ path: `${OUT}/${n}.jpg`, type: 'jpeg', quality: 84, timeout: 300000 }); }
    finally { await ev(() => { const r = window.__game.renderer; if (r.__render) { r.render = r.__render; r.__render = null; } }).catch(() => {}); }
    console.log('shot', n);
  };
  const waitPlay = async () => { await p.waitForFunction(() => window.__game && window.__game.state === 'play', null, { timeout: 900000, polling: 1000 });
    await ev(() => { const g = window.__game; g.paused = false; g.menus.hidePause && g.menus.hidePause(); g.input.locked = true; g.input.enabled = true; }); };
  await p.goto(BASE + '/index.html');
  await p.waitForFunction(() => window.__game && window.__game.state === 'title', null, { timeout: 300000, polling: 500 });
  await ev(() => { const g = window.__game; g.save.settings.quality = 'medium'; g.save.settings.dynamicRes = false; g.renderer.settings = g.save.settings; g.renderer.applyQuality(); });
  await p.click('[data-act="title-play"]');
  await waitPlay();
  const t0 = Date.now();
  await ev(() => { window.__game.cineTime = 99; window.__game.travel('vanthos'); });
  await waitPlay();
  console.log('load seconds', Math.round((Date.now() - t0) / 1000));
  await ev(() => {
    const g = window.__game;
    g.godMode = true;
    window.__sim = sec => { for (let i = 0, n = Math.round(sec * 30); i < n; i++) { g.time += 1 / 30; g.update(1 / 30); } };
    window.__tp = (x, y, z) => { const P = g.player; P.pos.set(x, y, z); P.vel.set(0, 0, 0); P.avatar.root.position.copy(P.pos); P.snapCamera = true; };
  });
  // free camera at a fixed pose; one explicit frame, renderer.info summed over every pass (shadows included)
  const cam = async (pos, look, fov = 60) => ev(([pos, look, fov]) => {
    const g = window.__game, V = g.camera.position.constructor, c = g.camera; g.stationId = 'test';
    c.position.set(...pos); c.lookAt(...look); c.fov = fov; c.updateProjectionMatrix();
    g.camFocus = { pos: new V(...pos), look: new V(...look), orbit: false, q: c.quaternion.clone(), p0: c.position.clone(), q0: c.quaternion.clone(), fov0: fov, t0: 0 };
    const w = g.world; if (w.flora) w.flora.update(c, 0, true); if (w.ruins && w.ruins.update) w.ruins.update(c, 0, true);
  }, [pos, look, fov]);
  const frame = () => ev(() => {
    const g = window.__game, R = g.renderer, info = R.r.info, gl = R.r.getContext();
    info.autoReset = false; info.reset();
    const t = performance.now();
    R.render(g.scene, g.camera); gl.readPixels(0, 0, 1, 1, gl.RGBA, gl.UNSIGNED_BYTE, new Uint8Array(4));
    const ms = performance.now() - t, out = { calls: info.render.calls, tris: info.render.triangles, ms: Math.round(ms), geo: info.memory.geometries, tex: info.memory.textures };
    info.autoReset = true;
    return out;
  });
  const measure = async name => { await frame(); const r = await frame(); console.log('perf', name, JSON.stringify(r)); return r; };
  // the player stands at the view so enemies and streamed props around it are live
  const VIEWS = {
    landing: [[0, 0, 0], 'landing'],
    old_street: [[707, 1.7, 707], [560, 8, 640]],
    crown_street: [[420, 1.8, -60], [300, 20, -60]],
    flooded: [[-1050, 30, 380], [-900, 0, 250]],
    spire: [[260, 60, 320], [0, 200, 0]],
    aerial: [[-700, 160, 1500], [0, 60, 0]],
  };
  const perf = {};
  for (const [k, [pos, look]] of Object.entries(VIEWS)) {
    let P = pos, L = look;
    if (look === 'landing') { const l = await ev(() => window.__game.world.landing.toArray()); P = [l[0], l[1] + 1.7, l[2]]; L = [0, 40, 0]; }
    await ev(([x, z]) => { const g = window.__game, y = g.world.collision.ground(x, z); window.__tp(x, Math.max(y, -2.4), z); window.__sim(1.5); }, [P[0], P[2]]);
    await cam(P, L); perf[k] = await measure(k);
  }
  // CPU: game update time over 3 s of fixed steps at the landing zone and in the Old Quarter (enemies live)
  for (const [k, x, z] of [['upd_landing', null, null], ['upd_old', 707, 707]]) {
    perf[k] = await ev(([x, z]) => {
      const g = window.__game, w = g.world; g.stationId = null; g.camFocus = null;
      if (x === null) { const l = w.landing; x = l.x; z = l.z; }
      window.__tp(x, Math.max(w.collision.ground(x, z), -2.4), z); window.__sim(2);
      const t = performance.now(); window.__sim(3); const ms = (performance.now() - t) / 90;
      const live = g.enemies.list.filter(e => e.alive);
      return { updMs: +ms.toFixed(2), enemies: live.length, near100: live.filter(e => e.pos.distanceTo(g.player.pos) < 100).length };
    }, [x, z]);
    console.log('perf', k, JSON.stringify(perf[k]));
  }
  perf.memory = await ev(() => { const g = window.__game, r = g.renderer.r.info; let tex = 0, px = 0; const seen = new Set();
    g.scene.traverse(o => { for (const m of o.material ? [].concat(o.material) : []) for (const k in m) { const t = m[k]; if (t && t.isTexture && !seen.has(t) && t.image) { seen.add(t); const im = t.image; const w = im.width || 0, h = im.height || 0; tex++; px = Math.max(px, w, h); } } });
    return { textures: r.memory.textures, geometries: r.memory.geometries, maxSide: px, sceneTex: tex, heapMB: Math.round(performance.memory.usedJSHeapSize / 1e6) }; });
  console.log('PERF', JSON.stringify(perf));
  if (PERF_ONLY) { console.log('page errors:', errs.length); await b.close(); process.exit(errs.length ? 1 : 0); }
  await b.close();
  process.exit(fails.length || errs.length ? 1 : 0);
})().catch(e => { console.error(e); process.exit(1); });
