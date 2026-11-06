// Pop-in check: walks a free camera toward subjects in small steps and measures how much the picture changes when the
// level-of-detail state changes. At every step the frame is rendered twice from the SAME camera: once with the LOD state
// of the previous step (A) and once with the state of this step (B); |A - B| is exactly what the player would see pop.
// Subjects: a park tree cluster, a lowland forest, a rock, downtown towers (aerial approach and street level) and a
// frontier-planet forest (thalassa jungle, chunks streamed while the player walks; there A/B are 0.25 s apart).
// Reports per subject: the worst step (mean |diff| over the frame in 0-255 after a 2x box filter, % of pixels changed by
// more than 12, and the subject's distance and screen size there), the sum over the walk, and fixed-viewpoint perf
// (draw calls / triangles summed over every pass incl. shadows, ms per software frame). Saves A/B/diff images of the worst
// step of each subject to test-out/popin/.
// Usage: python3 -m http.server 8765 &  then
//   flock /tmp/claude-0/locks/browser.lock env NODE_PATH=$(npm root -g) node tools/test/popin.js
// Env: QUALITY=low|medium|high (default low), TOUCH=1 (1024 px textures like a phone), SUBJECTS=park,forest,rock,tower,street,planet,perf
//      TAG=after (file prefix), BASE=http://localhost:8766 (measure another build), STEP=1.06 (distance ratio per step).
const { chromium } = require('playwright');
const fs = require('fs');
const BASE = process.env.BASE || 'http://localhost:8765';
const OUT = process.env.OUT || 'test-out/popin';
const Q = process.env.QUALITY || 'low';
const TAG = (process.env.TAG || 'run') + '_' + Q + (process.env.TOUCH ? '_touch' : '');
const SUBJ = new Set((process.env.SUBJECTS || 'park,forest,rock,tower,street,planet,perf').split(','));
const STEP = +(process.env.STEP || 1.06);
const W = +(process.env.W || 800), H = +(process.env.H || 450);
fs.mkdirSync(OUT, { recursive: true });

(async () => {
  const b = await chromium.launch({ args: ['--ignore-gpu-blocklist', '--enable-unsafe-swiftshader', '--use-angle=swiftshader', '--mute-audio'] });
  const p = await b.newPage({ viewport: { width: W, height: H } });
  const errs = [];
  p.on('pageerror', e => { errs.push(e.message); console.log('PAGE ERROR', e.message.slice(0, 400), (e.stack || '').split('\n').slice(0, 4).join(' | ')); });
  p.on('console', m => { if (process.env.DBG && m.type() === 'log') console.log('page:', m.text().slice(0, 300)); if (m.type() === 'error') { errs.push(m.text()); console.log('CONSOLE ERROR', m.text().slice(0, 400)); } });
  await p.addInitScript(([q, touch, dbg]) => { localStorage.clear(); window.__TEST_QUALITY = q; window.__POPDBG = !!dbg; if (touch) window.__MAXTEX = 1024; }, [Q, !!process.env.TOUCH, process.env.DBG]);
  const ev = (fn, arg) => p.evaluate(fn, arg);
  const waitPlay = async () => { await p.waitForFunction(() => window.__game && window.__game.state === 'play', null, { timeout: 1200000, polling: 1000 });
    await ev(() => { const g = window.__game; g.paused = false; g.menus.hidePause && g.menus.hidePause(); g.input.locked = true; g.input.enabled = true; }); };
  await p.goto(BASE + '/index.html');
  await p.waitForFunction(() => window.__game && window.__game.state === 'title', null, { timeout: 600000, polling: 500 });
  await ev(q => { const g = window.__game; g.save.settings.quality = q; g.save.settings.dynamicRes = false; g.renderer.settings = g.save.settings; g.renderer.applyQuality(); g.startGame(true); }, Q);
  await waitPlay();

  // page-side helpers: the game loop keeps running but its render is a no-op; we render explicitly
  const install = () => ev(([W, H]) => {
    const g = window.__game, R = g.renderer;
    if (!R.__render) { R.__render = R.render; R.render = () => {}; }
    g.paused = true; g.stationId = 'test';
    // (procedural audio with no output device piles up buffers in headless Chrome: memory grows until the OOM killer)
    try { g.audio.ctx && g.audio.ctx.suspend(); } catch (e) { /* none */ }
    // hide the page (canvas + HUD): frames are read back from the WebGL drawing buffer, and a visible canvas makes the
    // headless compositor keep every presented frame of these slow software renders (the browser process balloons)
    for (const el of document.body.children) el.style.visibility = 'hidden';
    R.r.domElement.style.display = 'none';
    if (g.clock) { g.clock.set(12.5); g.clock.paused = true; }
    const cv = document.createElement('canvas'); cv.width = W / 2; cv.height = H / 2; const cx = cv.getContext('2d', { willReadFrequently: true });
    const V = g.camera.position.constructor;
    const P = window.__pop = {
      look: new V(),
      cam(pos, look) { const c = g.camera; c.position.set(...pos); this.look.set(...look); c.lookAt(this.look); c.fov = 70; c.aspect = W / H; c.updateProjectionMatrix(); c.updateMatrixWorld(); },
      lod(pos, dt = 0, force = true) {
        const c = g.camera, keep = c.position.clone(); if (pos) c.position.set(...pos);
        const w = g.world; if (w.flora) w.flora.update(c, dt, force); if (w.downtown) w.downtown.update(c, dt, force);
        c.position.copy(keep);
      },
      // checksum of every visible instanced mesh (count, matrices, fade attribute): equal sums mean an identical picture
      sig() {
        let s = 0;
        g.scene.traverseVisible(o => {
          if (!o.isInstancedMesh) return;
          const a = o.instanceMatrix.array, n = Math.min(o.count, a.length / 16); s += n * 7.13;
          for (let i = 0; i < n; i++) s += a[i * 16 + 12] * .37 + a[i * 16 + 14] * .91;
          const f = o.geometry.attributes.aFade; if (f) for (let i = 0; i < n; i++) s += f.array[i] * (i % 7 + 1);
        });
        return s;
      },
      grab() {
        const t0 = performance.now();
        R.__render.call(R, g.scene, g.camera);
        const t1 = performance.now();
        cx.drawImage(R.r.domElement, 0, 0, W / 2, H / 2);       // 2x box filter (canvas downscale) -> dither averages out
        const d = cx.getImageData(0, 0, W / 2, H / 2).data;
        if (window.__POPDBG) console.log('grab render', Math.round(t1 - t0), 'copy', Math.round(performance.now() - t1));
        return d;
      },
      diff(a, b) {
        let s = 0, n = 0, big = 0; const N = a.length / 4;
        for (let i = 0; i < a.length; i += 4) { const d = (Math.abs(a[i] - b[i]) + Math.abs(a[i + 1] - b[i + 1]) + Math.abs(a[i + 2] - b[i + 2])) / 3; s += d; if (d > 12) big++; n++; }
        return { mean: +(s / n).toFixed(3), changed: +(100 * big / N).toFixed(3) };
      },
      png(d) { const im = new ImageData(new Uint8ClampedArray(d), W / 2, H / 2); cx.putImageData(im, 0, 0); return cv.toDataURL('image/png'); },
      heat(a, b) { const o = new Uint8ClampedArray(a.length); for (let i = 0; i < a.length; i += 4) { const d = (Math.abs(a[i] - b[i]) + Math.abs(a[i + 1] - b[i + 1]) + Math.abs(a[i + 2] - b[i + 2])) / 3 * 4; o[i] = d; o[i + 1] = d * .5; o[i + 2] = 0; o[i + 3] = 255; } return this.png(o); },
      ppm(d) { return H / (2 * d * Math.tan(35 * Math.PI / 180)); },     // screen pixels per metre at distance d (960x540 view)
    };
    return !!P;
  }, [W, H]);
  const save = (name, url) => fs.writeFileSync(`${OUT}/${name}.png`, Buffer.from(url.split(',')[1], 'base64'));

  // walk the camera from `from` to `to` (distance to target shrinking by STEP per step); returns the per-step pops
  const walk = async (name, target, from, to, size, lookY = 0) => {
    const r = await ev(async ([target, from, to, size, lookY, STEP]) => {
      const P = window.__pop, dist = (a) => Math.hypot(a[0] - target[0], a[1] - target[1], a[2] - target[2]);
      const D0 = dist(from), D1 = dist(to), pts = [];
      for (let d = D0; d > D1; d /= STEP) pts.push(d);
      pts.push(D1);
      const at = d => { const k = (D0 - d) / (D0 - D1); return from.map((v, i) => v + (to[i] - v) * k); };
      const look = [target[0], target[1] + lookY, target[2]];
      const steps = []; let worst = null, total = 0, prev = at(pts[0]);
      P.lod(prev);
      for (let i = 1; i < pts.length; i++) {
        const pos = at(pts[i]); P.cam(pos, look);
        P.lod(prev); const s0 = P.sig();
        P.lod(pos); const s1 = P.sig();
        let d = { mean: 0, changed: 0 };
        if (Math.abs(s0 - s1) > 1e-6) {
          P.lod(prev); const A = P.grab(); await new Promise(r => setTimeout(r, 30));
          P.lod(pos); const B = P.grab(); await new Promise(r => setTimeout(r, 30));
          d = P.diff(A, B);
          if (!worst || d.mean > worst.mean) worst = { ...d, i, dist: +pts[i].toFixed(1), px: Math.round(size * P.ppm(pts[i])), A: P.png(A), B: P.png(B), heat: P.heat(A, B) };
        }
        total += d.mean;
        if (d.mean > 0) steps.push([+pts[i].toFixed(1), d.mean, d.changed]);
        prev = pos;
      }
      // a reference: how much the picture changes between two neighbouring camera positions (parallax only)
      return { steps, worst, total: +total.toFixed(3), n: pts.length };
    }, [target, from, to, size, lookY, STEP]);
    if (r.worst) { save(`${TAG}_${name}_A`, r.worst.A); save(`${TAG}_${name}_B`, r.worst.B); save(`${TAG}_${name}_diff`, r.worst.heat); delete r.worst.A; delete r.worst.B; delete r.worst.heat; }
    console.log('walk', name, JSON.stringify({ worst: r.worst, total: r.total, steps: r.n, changes: r.steps.length }));
    console.log('  steps', JSON.stringify(r.steps));
    return r;
  };

  const perf = async (name, pos, look) => {
    const r = await ev(([pos, look]) => {
      const g = window.__game, P = window.__pop, R = g.renderer, info = R.r.info, gl = R.r.getContext();
      P.cam(pos, look); P.lod(null);
      const px = new Uint8Array(4);
      R.__render.call(R, g.scene, g.camera); gl.readPixels(0, 0, 1, 1, gl.RGBA, gl.UNSIGNED_BYTE, px);
      info.autoReset = false; info.reset();
      const t = performance.now();
      R.__render.call(R, g.scene, g.camera); gl.readPixels(0, 0, 1, 1, gl.RGBA, gl.UNSIGNED_BYTE, px);
      const ms = Math.round(performance.now() - t), calls = info.render.calls, tris = info.render.triangles; info.autoReset = true;
      // the share of it that is level-of-detail kit (trees, rocks, downtown buildings): what this test changes
      let kitTris = 0; const w = g.world, kit = new Set();
      if (w.flora) for (const k of w.flora.kinds.values()) if (k.meshes) for (const T of k.meshes) if (T) T.ms.forEach(m => kit.add(m));
      if (w.downtown) for (const S of w.downtown.lods || []) for (const T of S.tiers) if (T) T.ms.forEach(m => kit.add(m));
      for (const m of kit) if (m.visible) kitTris += (m.geometry.index ? m.geometry.index.count : m.geometry.attributes.position.count) / 3 * m.count;
      return { calls, tris, kitTris: Math.round(kitTris), ms };
    }, [pos, look]);
    console.log('perf', name, JSON.stringify(r));
    const url = await ev(() => { const P = window.__pop; return P.png(P.grab()); }); save(`${TAG}_perf_${name}`, url);
    return r;
  };

  const results = { quality: Q, touch: !!process.env.TOUCH, walks: {}, perf: {} };
  // ------------------------------------------------------------------ Earth
  if (['park', 'forest', 'rock', 'tower', 'street', 'perf'].some(s => SUBJ.has(s))) {
    const t0 = Date.now();
    await ev(() => { window.__game.cineTime = 99; window.__game.travel('earth'); });
    await waitPlay();
    console.log('earth load seconds', Math.round((Date.now() - t0) / 1000));
    await p.waitForTimeout(3000);
    await install();
    const spots = await ev(() => {
      const w = window.__game.world, f = w.flora, H = (x, z) => w.map.height(x, z);
      const find = (names, test) => { for (const n of names) { const k = f.kinds.get(n); if (!k) continue; for (const m of k.list) { const x = m.elements[12], y = m.elements[13], z = m.elements[14]; if (test(x, y, z)) return [x, y, z, k.h]; } } return null; };
      const out = (x, z) => Math.abs(x) > 650 || Math.abs(z) > 650;
      const lowland = find(['TR_oak_a', 'TR_ash_a', 'TR_maple_a', 'TR_birch_b', 'TR_oak_b'], (x, y, z) => out(x, z) && y < 25 && y > 3 && Math.abs(H(x + 300, z) - y) < 25);
      const rock = find(['TR_rock_a', 'TR_rock_c', 'TR_rock_b'], (x, y, z) => true);
      const D = w.downtown; let tower = null; for (const P of D.placed) if (!tower || P.h > tower.h) tower = P;
      return { lowland, rock, tower: tower && [tower.x, 0, tower.z, tower.h], H0: H(0, 0) };
    });
    console.log('spots', JSON.stringify(spots));
    const H = (x, z) => ev(([x, z]) => window.__game.world.map.height(x, z), [x, z]);
    if (SUBJ.has('perf')) {
      results.perf.park = await perf('park', [262, 7, -262], [220, 3, -220]);
      results.perf.street = await perf('downtown_street', [-30, 1.7, -104], [60, 6, -110]);
      results.perf.aerial = await perf('aerial', [260, 210, 330], [-20, 30, -60]);
      if (spots.lowland) { const [x, y, z] = spots.lowland; results.perf.forest = await perf('forest', [x + 40, y + 6, z + 40], [x, y + 5, z]); }
    }
    if (SUBJ.has('park')) {
      // Founders' Park cherry ring round the fountain (block 2,-2), approached from the south-east at 8 m
      const t = [220, await H(220, -220), -220];
      results.walks.park = await walk('park', t, [220 + 330, t[1] + 9, -220 + 330], [220 + 14, t[1] + 4, -220 + 14], 9, 3);
    }
    if (SUBJ.has('forest') && spots.lowland) {
      const [x, y, z, h] = spots.lowland, hf = await H(x + 420, z), hn = await H(x + 12, z);
      results.walks.forest = await walk('forest', [x, y, z], [x + 420, Math.max(hf, y) + 5, z], [x + 12, hn + 2, z], h, h * .45);
    }
    if (SUBJ.has('rock') && spots.rock) {
      const [x, y, z, h] = spots.rock, hf = await H(x - 300, z - 60), hn = await H(x - 5, z - 1);
      results.walks.rock = await walk('rock', [x, y, z], [x - 300, Math.max(hf, y) + 4, z - 60], [x - 5, hn + 1.7, z - 1], h, .5);
    }
    if (SUBJ.has('tower') && spots.tower) {
      const [x, , z, h] = spots.tower;
      results.walks.tower = await walk('tower', [x, 0, z], [x + 650, 40, z + 380], [x + 70, 25, z + 40], h, h * .5);
    }
    if (SUBJ.has('street')) {
      results.walks.street = await walk('street', [140, 0, -110], [-260, 1.7, -104], [100, 1.7, -108], 20, 8);
    }
    // the same tree drawn by each tier at a few distances (needs flora.forceTier): how different the tiers look
    if (SUBJ.has('tiers') && spots.lowland) {
      const [x, y, z, h] = spots.lowland;
      for (const d of [40, 80, 160, 300]) {
        const r = await ev(([x, y, z, h, d]) => {
          const g = window.__game, P = window.__pop, f = g.world.flora, w = g.world;
          const cx = x + d, cy = Math.max(w.map.height(cx, z), y) + 3;
          P.cam([cx, cy, z], [x, y + h * .45, z]);
          const shots = [], ims = [];
          for (const t of [0, 1, 2]) { f.forceTier = t; f.update(g.camera, 0, true); const im = P.grab(); ims.push(im); shots.push(P.png(im)); }
          f.forceTier = null; f.update(g.camera, 0, true);
          return { d, h01: P.diff(ims[0], ims[1]), h12: P.diff(ims[1], ims[2]), h02: P.diff(ims[0], ims[2]), px: Math.round(h * P.ppm(d)), shots };
        }, [x, y, z, h, d]);
        r.shots.forEach((u, t) => save(`${TAG}_tier${t}_${d}m`, u)); delete r.shots;
        console.log('tiers', JSON.stringify(r));
      }
    }
  }
  // ------------------------------------------------------------------ frontier planet: jungle streamed while walking
  if (SUBJ.has('planet')) {
    await ev(() => { const g = window.__game; const R = g.renderer; if (R.__render) { R.render = R.__render; R.__render = null; } g.paused = false; g.stationId = null; });
    await ev(() => window.__game.travel('thalassa'));
    await waitPlay(); await p.waitForTimeout(3000);
    await install();
    if (SUBJ.has('perf')) {
      const v = await ev(() => { const g = window.__game, f = g.world.flora; let best = null, bd = 1e9;
        for (const k of f.kinds.values()) if (k.alive && k.species !== 'bush') for (let i = 0; i < k.n; i++) if (k.alive[i]) { const d = Math.hypot(k.pos[i * 3] - 120, k.pos[i * 3 + 2]); if (d < bd) { bd = d; best = [k.pos[i * 3], k.pos[i * 3 + 1], k.pos[i * 3 + 2]]; } }
        return best; });
      if (v) results.perf.planet_forest = await perf('planet_forest', [v[0] - 40, v[1] + 8, v[2] - 25], [v[0], v[1] + 6, v[2]]);
    }
    // walk the player east at 12 m/s; every 0.25 s render before/after the world update at a fixed camera
    const r = await ev(async () => {
      const g = window.__game, P = window.__pop, w = g.world, pl = g.player;
      const steps = []; let worst = null, total = 0, spawnMin = 1e9, spawned = 0;
      const pos = pl.pos.clone(); pos.set(40, 0, 10);
      const count = () => { let n = 0; for (const pool of Object.values(w.pools || {})) for (const pp of [].concat(pool || [])) n += pp.cap - pp.free.length; if (w.flora) n += w.flora.count; return n; };
      for (let s = 0; s < 220; s++) {
        pos.x += 3; pos.y = w.height(pos.x, pos.z); pl.pos.copy(pos);
        const eye = [pos.x, pos.y + 1.7, pos.z], look = [pos.x + 50, pos.y + 1, pos.z + 6];
        P.cam(eye, look);
        const n0 = count(); const s0 = P.sig();
        const A = s % 2 === 0 ? P.grab() : null;
        for (let k = 0; k < 15; k++) { w.update(1 / 60); g.time += 1 / 60; }
        const n1 = count();
        if (n1 > n0) { spawned += n1 - n0; }
        if (!A) continue;
        if (Math.abs(P.sig() - s0) < 1e-6) continue;
        const B = P.grab(), d = P.diff(A, B);
        total += d.mean; steps.push([s, d.mean, d.changed]);
        if (!worst || d.mean > worst.mean) worst = { ...d, step: s, A: P.png(A), B: P.png(B), heat: P.heat(A, B) };
      }
      // nearest live prop to the path that was created during the walk is not tracked by the old build; report density
      return { steps, worst, total: +total.toFixed(3), spawned };
    });
    if (r.worst) { save(`${TAG}_planet_A`, r.worst.A); save(`${TAG}_planet_B`, r.worst.B); save(`${TAG}_planet_diff`, r.worst.heat); delete r.worst.A; delete r.worst.B; delete r.worst.heat; }
    console.log('walk planet', JSON.stringify({ worst: r.worst, total: r.total, spawned: r.spawned, changes: r.steps.length }));
    console.log('  steps', JSON.stringify(r.steps));
    results.walks.planet = r;
  }
  fs.writeFileSync(`${OUT}/${TAG}.json`, JSON.stringify(results, (k, v) => (k === 'steps' ? undefined : v), 1));
  console.log('page errors:', errs.length);
  await b.close();
  process.exit(errs.length ? 1 : 0);
})().catch(e => { console.error('POPIN FAILED', e); process.exit(2); });
