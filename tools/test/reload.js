// Reload check: for every kinetic and horror archetype (and one energy gun) the mag is emptied, a reload is started and
// the sequence is stepped with a fixed dt (the game loop is paused, frames are rendered on demand). First-person frames
// at evenly spaced moments go to test-out/reload/<arch>_NN.jpg (+ <arch>_sheet.jpg contact sheet via python3/PIL when
// available) and one third-person frame mid reload. Checks: ammo arrives only when the new mag seats / each shell goes
// in, the old mag (or brass / husk) exists as a world drop, falls and comes to rest on the floor, a tactical reload
// keeps its rounds until seated, cancel paths (weapon swap, sprint, vehicle, death) leave every part at rest, no page errors.
// Usage: flock /tmp/claude-0/locks/browser.lock env NODE_PATH=$(npm root -g) node tools/test/reload.js
// Env: ARCHS (comma list), FRAMES (per arch, default 8), BASE, OUT (default test-out/reload), NOSHOTS=1 (logic only)
const { chromium } = require('playwright');
const fs = require('fs');
const { execFileSync } = require('child_process');
const BASE = process.env.BASE || 'http://localhost:8765';
const OUT = process.env.OUT || 'test-out/reload';
const ARCHS = (process.env.ARCHS || 'rifle,carbine,dmr,ksmg,pistol,revolver,pump,bolt,spitter,bile,brood,auto').split(',').filter(Boolean);
const FRAMES = +(process.env.FRAMES || 8);
fs.mkdirSync(OUT, { recursive: true });

(async () => {
  const b = await chromium.launch({ args: ['--ignore-gpu-blocklist', '--enable-unsafe-swiftshader', '--use-angle=swiftshader'] });
  const p = await b.newPage({ viewport: { width: 800, height: 450 } });
  const errs = [];
  p.on('pageerror', e => { errs.push(e.message); console.log('PAGE ERROR', e.message.slice(0, 400)); });
  p.on('console', m => { if (m.type() === 'error') { errs.push(m.text()); console.log('CONSOLE ERROR', m.text().slice(0, 300)); } });
  await p.addInitScript(() => { localStorage.clear(); window.__TEST_QUALITY = 'low'; });
  // the ship only: heavy city / planet models are swapped for a small stand-in to keep memory down
  await p.route(/assets\/models\/[^/]+\.glb$/, (route, req) => {
    const f = 'assets/models/' + req.url().split('/').pop();
    if (fs.existsSync(f) && !/\/(vanthos|city_buildings|rural|civ_male|player_female_npc|player_male_npc|downtown|trees)\.glb$/.test(f)) return route.continue();
    return route.fulfill({ status: 200, contentType: 'model/gltf-binary', body: fs.readFileSync('assets/models/npc_vendor.glb') });
  });
  const ev = (fn, arg) => p.evaluate(fn, arg);
  const shot = async name => {
    if (process.env.NOSHOTS) return;
    await ev(() => { const g = window.__game; g.renderer.render(g.scene, g.camera, g.viewmodel.active ? g.viewmodel.scene : null); window.__r = g.renderer.render; g.renderer.render = () => {}; });
    await p.screenshot({ path: `${OUT}/${name}.jpg`, type: 'jpeg', quality: 80, timeout: 300000 });
    await ev(() => { window.__game.renderer.render = window.__r; });
  };
  await p.goto(BASE + '/index.html');
  await p.waitForFunction(() => window.__game && window.__game.state === 'title', null, { timeout: 300000, polling: 500 });
  await ev(() => { window.__game.save.settings.dynamicRes = false; });
  await p.click('[data-act="title-play"]');
  await p.waitForFunction(() => window.__game && window.__game.state === 'play', null, { timeout: 900000, polling: 1000 });
  await p.waitForTimeout(2500);
  await ev(() => {
    const g = window.__game, pl = g.player; g.menus.hidePause(); g.input.locked = true; g.input.enabled = true;
    g.enemies.clear(); if (g.save.settings.view !== 'first') g.toggleView();
    // face the most open direction, look slightly down so dropped mags are in frame
    let yaw = pl.camYaw, free = 0; const V = pl.pos.constructor;
    for (let k = 0; k < 16; k++) {
      const y = pl.camYaw + k * Math.PI / 8, d = new V(-Math.sin(y), 0, -Math.cos(y)), o = pl.pos.clone(); o.y += 1.2;
      const h = g.world.collision.raycast(o, d, 60), f = h ? h.dist : 60;
      if (f > free + .5) { free = f; yaw = y; }
    }
    window.__U = { yaw, pos: pl.pos.clone() };
    g.paused = true;           // the test steps the simulation itself
    window.__step = (n, dt = 1 / 60) => { for (let i = 0; i < n; i++) { g.time += dt; g.update(dt); g.input.endFrame(); } };
  });

  const results = {};
  for (const arch of ARCHS) {
    const r = await ev(async ({ arch, FRAMES }) => {
      const g = window.__game, pl = g.player, W = g.weapons, st = await import('/src/game/state.js'), data = await import('/src/game/data.js');
      const w = st.makeWeapon(arch, 3, 30); w.perks = w.perks.filter(k => k !== 'quickdraw' && k !== 'autoload'); g.addWeapon(w);
      const A = data.ARCHETYPES[arch];
      g.save.equipped[A.slot] = w.uid; W.slot = A.slot; delete W.ammo[w.uid];
      pl.armed = true; W.refreshModel(); W.swap = 0; W.cancelReload();
      const U = window.__U; pl.pos.copy(U.pos); pl.avatar.root.position.copy(U.pos); pl.vel.set(0, 0, 0); pl.camYaw = U.yaw; pl.camPitch = -.25;
      window.__step(70);          // raise animation
      const S = st.weaponStats(w), a = W.ammoOf(w);
      const out = { arch, reload: +S.reload.toFixed(2), log: [], frames: [] };
      // ---- empty reload, stepped
      a.mag = 0; a.reserve = S.mag * 3;
      W.rl.drops.clear(); const drops0 = 0;
      W.startReload(S);
      const dur = W.reloadTotal; out.dur = +dur.toFixed(2);
      const dt = 1 / 60, N = Math.ceil(dur / dt) + 4;
      const shots = new Set(Array.from({ length: FRAMES }, (_, i) => Math.round((i + .5) / FRAMES * (N - 4))));
      let prev = a.mag, firstGain = null, gains = [];
      let dropSeen = null;
      for (let i = 0; i < N; i++) {
        window.__step(1, dt);
        const t = (i + 1) * dt;
        if (a.mag !== prev) { gains.push([+t.toFixed(2), a.mag - prev]); if (firstGain === null) firstGain = t; prev = a.mag; }
        if (!dropSeen && W.rl.drops.list.length > drops0) { const d = W.rl.drops.list[W.rl.drops.list.length - 1]; dropSeen = { t: +t.toFixed(2), y0: +d.root.position.y.toFixed(3), kind: d.kind }; window.__lastDrop = d; }
        if (shots.has(i)) out.frames.push(i);
      }
      out.firstGain = firstGain === null ? null : +(firstGain / dur).toFixed(2);
      out.gains = gains.length > 8 ? gains.length + ' steps' : gains;
      out.magAfter = a.mag; out.full = a.mag === S.mag; out.stillReloading = W.reloading > 0;
      // the drop falls and settles on the floor
      if (dropSeen) {
        window.__step(240);
        const d = window.__lastDrop, col = g.world.collision, rp = d.root.position;
        out.drop = { ...dropSeen, kind: d.kind, rest: d.rest, y: +rp.y.toFixed(3), floor: +col.support(rp.x, rp.z, rp.y + .05).toFixed(3), live: W.rl.drops.list.includes(d) };
      } else out.drop = A.cls === 'energy' ? 'n/a' : 'NONE';
      // ---- tactical reload keeps the old count until the seat
      if (A.cls !== 'energy') {
        a.mag = Math.max(1, Math.floor(S.mag / 2)); const before = a.mag; W.startReload(S);
        window.__step(Math.round(W.reloadTotal * .3 * 60));
        out.tacticalMid = a.mag === before || ['pump', 'bolt'].includes(arch);
        W.cancelReload(); window.__step(2);
      }
      // ---- cancel paths: every part back at rest, the arm back on the foregrip
      const restCheck = () => {
        const vm = g.viewmodel, R = vm.gr, bad = [];
        const lock = arch === 'pistol' && a.mag <= 0;      // an empty pistol keeps its slide locked back (correct, not a leftover)
        if (R) for (const [k, rr] of Object.entries(R.rest)) {
          const o = R.p[k]; if (!o || (lock && k === 'slide')) continue;
          if (o.position.distanceTo(rr.pos) > 1e-5 || o.quaternion.angleTo(rr.q) > 1e-4) bad.push(k);
          if (o.visible === k.startsWith('x_')) bad.push(k + ':vis');
        }
        if (R) for (const [k, o] of Object.entries(R.extra)) if (o && o.visible) bad.push('extra:' + k);
        if (vm.foreRest && vm.armL.position.distanceTo(vm.foreRest) > 1e-5) bad.push('armL');
        const av = W.avRig; if (av) for (const [k, rr] of Object.entries(av.rest)) { const o = av.p[k]; if (o && !(lock && k === 'slide') && (o.position.distanceTo(rr.pos) > 1e-5 || o.quaternion.angleTo(rr.q) > 1e-4)) bad.push('av:' + k); }
        return bad;
      };
      const mid = () => { a.mag = 0; a.reserve = S.mag * 3; W.startReload(S); window.__step(Math.round(W.reloadTotal * .45 * 60)); };
      const cancels = {};
      // swap weapon (to an empty slot falls back to holstering: give a second gun)
      mid(); { const s2 = (A.slot + 1) % 3; if (!W.equipped(s2)) { const w2 = st.makeWeapon('pistol', 1, 1); g.addWeapon(w2); g.save.equipped[s2] = w2.uid; }
        W.select(s2); window.__step(3); cancels.swap = [W.reloading === 0]; W.select(A.slot); window.__step(40); cancels.swap.push(...restCheck()); }
      // sprint
      mid(); g.input.down.add('ShiftLeft'); g.input.down.add('KeyW'); window.__step(4); g.input.down.delete('ShiftLeft'); g.input.down.delete('KeyW');
      cancels.sprint = [W.reloading === 0, ...restCheck()]; pl.vel.set(0, 0, 0); pl.pos.copy(U.pos); window.__step(30);
      // vehicle (mode change)
      mid(); pl.mode = 'car'; window.__step(2); pl.mode = 'foot'; window.__step(2);
      cancels.car = [W.reloading === 0, ...restCheck()];
      // death
      mid(); pl.dead = true; window.__step(2); pl.dead = false; window.__step(2);
      cancels.death = [W.reloading === 0, ...restCheck()];
      out.cancels = Object.fromEntries(Object.entries(cancels).map(([k, v]) => [k, v[0] && v.length === 1 ? 'ok' : v.join(',')]));
      // per-round reloads: firing interrupts
      if (arch === 'pump' || arch === 'bolt') {
        a.mag = 1; a.reserve = 20; W.startReload(S); window.__step(Math.round(W.reloadTotal * .45 * 60));
        const m0 = a.mag; W.rl.interrupt(); window.__step(Math.round(2 * 60));
        out.interrupt = { magAtInterrupt: m0, after: a.mag, done: W.reloading === 0 };
      }
      pl.pos.copy(U.pos); pl.camPitch = -.25;
      return out;
    }, { arch, FRAMES }).catch(e => ({ arch, error: String(e).slice(0, 300) }));
    results[arch] = r;
    console.log(JSON.stringify(r));
  }
  // second pass for screenshots (await inside page code cannot screenshot): replay each reload to the frame indices
  if (!process.env.NOSHOTS) {
    for (const arch of ARCHS) {
      const r = results[arch]; if (!r || !r.frames) continue;
      await ev(async arch => {
        const g = window.__game, pl = g.player, W = g.weapons, st = await import('/src/game/state.js'), data = await import('/src/game/data.js');
        const A = data.ARCHETYPES[arch];
        const w = g.save.inventory.find(x => x.arch === arch); g.save.equipped[A.slot] = w.uid; W.slot = A.slot; W.cancelReload();
        pl.armed = true; W.refreshModel(); W.swap = 0;
        const U = window.__U; pl.pos.copy(U.pos); pl.avatar.root.position.copy(U.pos); pl.vel.set(0, 0, 0); pl.camYaw = U.yaw; pl.camPitch = -.25;
        W.rl.drops.clear();
        window.__step(70);
        const S = st.weaponStats(w), a = W.ammoOf(w); a.mag = 0; a.reserve = S.mag * 3;
        W.startReload(S); window.__ri = 0;
      }, arch);
      let at = 0;
      for (let k = 0; k < r.frames.length; k++) {
        const fi = r.frames[k];
        await ev(n => window.__step(n), fi + 1 - at); at = fi + 1;
        await shot(`${arch}_${String(k).padStart(2, '0')}`);
      }
      // third person at ~45 % of a fresh reload
      await ev(async arch => {
        const g = window.__game, W = g.weapons, st = await import('/src/game/state.js'), w = W.equipped(), S = st.weaponStats(w), a = W.ammoOf(w);
        W.cancelReload(); window.__step(5); g.toggleView(); window.__step(5);
        a.mag = 0; W.startReload(S); window.__step(Math.round(W.reloadTotal * .45 * 60));
      }, arch);
      await shot(`${arch}_3p`);
      await ev(() => { const g = window.__game; g.weapons.cancelReload(); g.toggleView(); window.__step(5); });
      try {
        const files = r.frames.map((_, k) => `${OUT}/${arch}_${String(k).padStart(2, '0')}.jpg`).concat([`${OUT}/${arch}_3p.jpg`]);
        execFileSync('python3', ['-c', `
import sys
from PIL import Image
fs = sys.argv[2:]; ims = [Image.open(f) for f in fs]
w, h = ims[0].size; w2, h2 = w // 2, h // 2; cols = 3; rows = (len(ims) + cols - 1) // cols
sheet = Image.new('RGB', (w2 * cols, h2 * rows))
for i, im in enumerate(ims): sheet.paste(im.resize((w2, h2)), ((i % cols) * w2, (i // cols) * h2))
sheet.save(sys.argv[1], quality=82)`, `${OUT}/${arch}_sheet.jpg`, ...files]);
      } catch (e) { console.log('sheet failed', String(e).slice(0, 200)); }
    }
  }
  fs.writeFileSync(`${OUT}/results.json`, JSON.stringify(results, null, 1));
  // verdict
  const fails = [];
  for (const [arch, r] of Object.entries(results)) {
    if (r.error) { fails.push(arch + ': ' + r.error); continue; }
    if (!r.full) fails.push(arch + ': mag not full after reload');
    if (r.stillReloading) fails.push(arch + ': reload did not finish');
    const perRound = arch === 'pump' || arch === 'bolt';      // +1 per shell / round after the intro
    if (arch !== 'auto' && (r.firstGain === null || r.firstGain < (perRound ? .1 : .3))) fails.push(arch + ': ammo granted too early (' + r.firstGain + ')');
    if (r.drop === 'NONE' && !perRound) fails.push(arch + ': no drop');
    if (r.drop && r.drop.kind && (!r.drop.rest || Math.abs(r.drop.y - r.drop.floor) > .08)) fails.push(arch + ': drop not resting on the floor ' + JSON.stringify(r.drop));
    if (r.tacticalMid === false) fails.push(arch + ': tactical reload changed ammo early');
    for (const [k, v] of Object.entries(r.cancels || {})) if (v !== 'ok') fails.push(arch + ': cancel ' + k + ' -> ' + v);
    if (r.interrupt && !r.interrupt.done) fails.push(arch + ': interrupt did not finish');
  }
  console.log('page errors:', errs.length);
  console.log(fails.length ? 'FAIL\n  ' + fails.join('\n  ') : 'PASS');
  await b.close();
  process.exit(fails.length || errs.length ? 1 : 0);
})();
