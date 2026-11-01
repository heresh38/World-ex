// Downtown New Meridian check (src/worlds/meridian/downtown.js, kit tools/blender/downtown.py): loads Earth, counts the
// distinct building designs placed, checks the colliders (walking into a tower stops the player), reports draw calls
// and triangles (renderer.info summed over every pass of a frame, shadows included) at fixed camera viewpoints, and saves
// screenshots: the heritage avenue at street level, a view up the towers, the construction site with its crane, an
// aerial over the core, a skywalk, the transit mall with a tram. Fails on page errors.
// Usage: python3 -m http.server 8765 &  then  NODE_PATH=$(npm root -g) node tools/test/downtown.js   (test-out/downtown)
// PERF_ONLY=1 only measures the fixed viewpoints (also works against an older build: BASE=http://localhost:8766).
const { chromium } = require('playwright');
const fs = require('fs');
const BASE = process.env.BASE || 'http://localhost:8765';
const OUT = process.env.OUT || 'test-out/downtown';
const PERF_ONLY = !!process.env.PERF_ONLY;
fs.mkdirSync(OUT, { recursive: true });

(async () => {
  const b = await chromium.launch({ args: ['--ignore-gpu-blocklist', '--enable-unsafe-swiftshader', '--use-angle=swiftshader'] });
  const p = await b.newPage({ viewport: { width: 960, height: 540 } });
  const errs = [], fails = [];
  p.on('pageerror', e => { errs.push(e.message); console.log('PAGE ERROR', e.message.slice(0, 400), (e.stack || '').split('\n').slice(0, 4).join(' | ')); });
  p.on('console', m => { if (m.type() === 'error') { errs.push(m.text()); console.log('CONSOLE ERROR', m.text().slice(0, 400)); } });
  await p.addInitScript(() => { localStorage.clear(); window.__TEST_QUALITY = 'low'; window.__MAXTEX = 1024; });
  const ev = (fn, arg) => p.evaluate(fn, arg);
  const wait = ms => p.waitForTimeout(ms);
  const check = (ok, what, info = '') => { console.log((ok ? 'PASS ' : 'FAIL ') + what + (info !== '' ? ' · ' + (typeof info === 'string' ? info : JSON.stringify(info)) : '')); if (!ok) fails.push(what); };
  // freeze rendering while the capture runs (swiftshader frames piling up behind a slow capture balloon Chrome's memory)
  const shot = async n => {
    await ev(() => { const r = window.__game.renderer; if (!r.__render) { r.__render = r.render; r.render = () => {}; } });
    try { await p.screenshot({ path: `${OUT}/${n}.jpg`, type: 'jpeg', quality: 84, timeout: 300000 }); }
    finally { await ev(() => { const r = window.__game.renderer; if (r.__render) { r.render = r.__render; r.__render = null; } }).catch(() => {}); }
    console.log('shot', n);
  };
  const waitPlay = async () => { await p.waitForFunction(() => window.__game && window.__game.state === 'play', null, { timeout: 1200000, polling: 1000 });
    await ev(() => { const g = window.__game; g.paused = false; g.menus.hidePause && g.menus.hidePause(); g.input.locked = true; g.input.enabled = true; }); };
  await p.goto(BASE + '/index.html');
  await p.waitForFunction(() => window.__game && window.__game.state === 'title', null, { timeout: 600000, polling: 500 });
  await ev(() => { const g = window.__game; g.save.settings.quality = 'low'; g.save.settings.dynamicRes = false; g.renderer.settings = g.save.settings; g.renderer.applyQuality(); g.startGame(true); });
  await waitPlay();
  const t0 = Date.now();
  await ev(() => { window.__game.cineTime = 99; window.__game.travel('earth'); });
  await waitPlay();
  await ev(() => { window.__game.cineTime = null; });
  console.log('earth load seconds', Math.round((Date.now() - t0) / 1000));
  await wait(3000);

  // free camera at a fixed pose (works on both builds). Software rendering takes seconds per frame, so each view renders
  // one frame explicitly and reads renderer.info summed over every pass of it (shadow maps included).
  const cam = async (pos, look) => ev(([pos, look]) => {
    const g = window.__game, V = g.camera.position.constructor, c = g.camera; g.stationId = 'test';
    c.position.set(...pos); c.lookAt(...look); c.fov = 55; c.updateProjectionMatrix();
    g.camFocus = { pos: new V(...pos), look: new V(...look), orbit: false, q: c.quaternion.clone(), p0: c.position.clone(), q0: c.quaternion.clone(), fov0: 55, t0: 0 };
    const w = g.world; if (w.flora) w.flora.update(c, 0, true); if (w.downtown) w.downtown.update(c, 0, true);
  }, [pos, look]);
  const frame = () => ev(() => {
    const g = window.__game, R = g.renderer, info = R.r.info;
    info.autoReset = false; info.reset();
    const t = performance.now();
    R.render(g.scene, g.camera);
    const ms = performance.now() - t, out = { calls: info.render.calls, tris: info.render.triangles, ms: Math.round(ms), geometries: info.memory.geometries, textures: info.memory.textures };
    info.autoReset = true;
    return out;
  });
  const measure = async name => { await frame(); const r = await frame(); console.log('perf', name, JSON.stringify(r)); return r; };
  const VIEWS = {
    street: [[-30, 1.7, -104], [60, 6, -110]],                // heritage avenue, eye height, looking east
    aerial: [[260, 210, 330], [-20, 30, -60]],                 // over the core from the south-east
    towers: [[-110, 1.8, 30], [-110, 120, -40]],               // plaza in front of the crescent, looking up
  };
  const perf = {};
  for (const [k, [pos, look]] of Object.entries(VIEWS)) { await cam(pos, look); perf[k] = await measure(k); }
  if (PERF_ONLY) { console.log('PERF', JSON.stringify(perf)); console.log('page errors:', errs.length); await b.close(); process.exit(errs.length ? 1 : 0); }

  const st = await ev(() => window.__game.world.downtown.stats());
  console.log('downtown', JSON.stringify(st));
  check(st.designs >= 14, 'at least 14 distinct building designs placed', st.designs);
  check(st.skywalks >= 4, 'skywalks link neighbouring buildings', st.skywalks);
  check(st.cranes === 2 && st.trams === 2, 'two cranes and two trams', { cranes: st.cranes, trams: st.trams });
  const colInfo = await ev(() => { const w = window.__game.world, B = w.collision.boxes; return { buildings: B.filter(b => b.tag === 'building').length, skywalk: B.filter(b => b.tag === 'skywalk').length, props: B.filter(b => b.tag === 'prop').length }; });
  check(colInfo.buildings > st.buildings, 'building colliders', colInfo);
  // nothing downtown on a traffic lane
  const onLane = await ev(() => {
    const w = window.__game.world, bad = [];
    for (const P of w.downtown.placed) for (const l of w.map.lanes) if (l.city) {
      const a = l.pts[0], z = l.pts[l.pts.length - 1];
      if (Math.abs(a.x - z.x) < .1) { if (a.x > P.rect[0] - 1 && a.x < P.rect[2] + 1) { bad.push(P.name); break; } }
      else if (a.z > P.rect[1] - 1 && a.z < P.rect[3] + 1) { bad.push(P.name); break; }
    }
    return bad;
  });
  check(onLane.length === 0, 'no building stands on a traffic lane', onLane.slice(0, 5));
  // walk into the tallest tower (capsule moves of the player controller, stepped directly: the render loop is too slow)
  await ev(() => { const g = window.__game; g.stationId = null; g.camFocus = null; });
  const walk = await ev(() => {
    const g = window.__game, w = g.world;
    const P = [...w.downtown.placed].filter(q => /DT_(glass_tower|crown|ribbed|slab70)/.test(q.name)).sort((a, b) => b.h - a.h)[0];   // box-plan towers: the footprint is the wall
    const z = (P.rect[1] + P.rect[3]) / 2, x = P.rect[0] - 4, pos = new (g.player.pos.constructor)(x, 0.05, z), vel = pos.clone();
    for (let i = 0; i < 120; i++) { vel.set(4.4, -9, 0); w.collision.moveCapsule(pos, vel, .35, 1.7, 1 / 30); }
    return { tower: P.name, face: +P.rect[0].toFixed(2), end: +pos.x.toFixed(2), start: x };
  });
  check(walk.end < walk.face + .3 && walk.end > walk.start + 2, 'walking into a tower stops at its wall', walk);

  // screenshots
  const view = async (n, pos, look) => { await cam(pos, look); await wait(500); const r = await frame(); console.log('view', n, JSON.stringify(r)); await shot(n); };
  await view('d01_heritage_street', [-30, 1.7, -104], [60, 5, -112]);
  await view('d02_heritage_wide', [-58, 9, -118], [40, 10, -104]);
  await view('d03_towers_up', [-110, 1.8, 30], [-110, 120, -40]);
  const site = await ev(() => { const P = window.__game.world.downtown.placed.find(q => q.name === 'DT_construction'); return P ? [(P.rect[0] + P.rect[2]) / 2, (P.rect[1] + P.rect[3]) / 2] : [0, 110]; });
  await view('d04_construction', [site[0] + 70, 22, site[1] + 85], [site[0], 40, site[1]]);
  await view('d05_aerial_core', [260, 210, 330], [-20, 30, -60]);
  await view('d06_aerial_north', [-60, 160, -480], [0, 20, -80]);
  const sk = await ev(() => { const s = window.__game.world.downtown.skywalks[0]; return s ? [(s.rect[0] + s.rect[2]) / 2, (s.rect[1] + s.rect[3]) / 2, s.ax] : null; });
  if (sk) await view('d07_skywalk', sk[2] === 'x' ? [sk[0] - 2, 1.8, sk[1] + 22] : [sk[0] + 22, 1.8, sk[1] - 2], [sk[0], 7, sk[1]]);
  await view('d08_transit_mall', [-150, 3.5, -212], [-90, 3, -222]);
  await view('d09_plaza_crescent', [-80, 6, 30], [-110, 30, -30]);
  await view('d10_obs_tower', [170, 2, 60], [90, 80, -20]);
  // on foot, first person, on the heritage avenue among the crowd
  await ev(() => { const g = window.__game; g.stationId = null; g.camFocus = null; const pl = g.player; pl.pos.set(-20, .05, -108); pl.vel.set(0, 0, 0); pl.avatar.root.position.copy(pl.pos); pl.camYaw = -Math.PI / 2; pl.camPitch = .05; pl.snapCamera = true; });
  await wait(3000); await frame();
  const life = await ev(() => { const g = window.__game, w = g.world, P = g.player.pos; return { pedsNear60: w.population.peds.filter(q => q.alive && q.pos.distanceTo(P) < 60).length, district: w.districtName, fps: Math.round(g.fps) }; });
  console.log('street life', JSON.stringify(life));
  await shot('d11_on_foot');
  console.log('PERF', JSON.stringify(perf));
  console.log('fails:', fails.length, fails.join('; '));
  console.log('page errors:', errs.length);
  await b.close();
  process.exit(errs.length || fails.length ? 1 : 0);
})().catch(e => { console.error('DOWNTOWN FAILED', e); process.exit(2); });
