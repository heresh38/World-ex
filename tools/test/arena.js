// Shellbreak (src/worlds/arena, src/game/bots.js) end to end: enter from the ship's briefing table, the loadout screen,
// deploy, a full 6v6 match simulated with fixed 1/30 s steps on an accelerated clock (bots navigate, fight, die, respawn
// at sensible spawns; scores count; the match ends with a winner and the rewards screen), AI cost per frame, no page
// errors; plus the player movement numbers (top speeds, ADS speed, slide distance / chaining, jump height, sprint-to-fire
// delay, ADS time per class). Screenshots in test-out/arena/: overview, loadout, firefight, scoreboard, end screen.
// Usage: python3 -m http.server 8765 &  then  NODE_PATH=$(npm root -g) flock /tmp/claude-0/locks/browser.lock node tools/test/arena.js
// Env: MATCH_MIN (simulated minutes cap, default 10), DIFF (easy|normal|hard), SKIP_MOVE=1, SKIP_MATCH=1, TOUCH=1
const { chromium } = require('playwright');
const fs = require('fs');
const BASE = process.env.BASE || 'http://localhost:8765';
const OUT = (process.env.OUT || 'test-out') + '/arena';
fs.mkdirSync(OUT, { recursive: true });

(async () => {
  const b = await chromium.launch({ args: ['--ignore-gpu-blocklist', '--enable-unsafe-swiftshader', '--use-angle=swiftshader'] });
  const p = await b.newPage({ viewport: { width: 1280, height: 720 } });
  const errs = [], fails = [];
  p.on('pageerror', e => { errs.push(e.message); console.log('PAGE ERROR', e.message.slice(0, 500)); });
  p.on('console', m => { if (m.type() === 'error') { errs.push(m.text()); console.log('CONSOLE ERROR', m.text().slice(0, 400)); } });
  await p.addInitScript(() => { localStorage.clear(); window.__TEST_QUALITY = 'low'; window.__MAXTEX = 1024; });
  const ev = (fn, arg) => p.evaluate(fn, arg);
  const check = (ok, what, info = '') => { console.log((ok ? 'PASS ' : 'FAIL ') + what + (info !== '' ? ' · ' + (typeof info === 'string' ? info : JSON.stringify(info)) : '')); if (!ok) fails.push(what); };
  // the last rendered frame stays on the canvas while the capture runs (no swiftshader frames pile up)
  const shot = async n => {
    await ev(() => { const g = window.__game; g.renderer.render(g.scene, g.camera, g.viewmodel && g.viewmodel.active ? g.viewmodel.scene : null); const r = g.renderer; if (!r.__render) { r.__render = r.render; r.render = () => {}; } });
    try { await p.screenshot({ path: `${OUT}/${n}.jpg`, type: 'jpeg', quality: 86, timeout: 300000 }); }
    finally { await ev(() => { const r = window.__game.renderer; if (r.__render) { r.render = r.__render; r.__render = null; } }).catch(() => {}); }
    console.log('shot', n);
  };
  const live = () => ev(() => { const g = window.__game; g.paused = false; g.menus.hidePause && g.menus.hidePause(); g.input.locked = true; g.input.enabled = true; });
  const waitPlay = async () => { await p.waitForFunction(() => window.__game && window.__game.state === 'play', null, { timeout: 900000, polling: 1000 }); };

  await p.goto(BASE + '/index.html' + (process.env.TOUCH ? '?touch=1' : ''));
  await p.waitForFunction(() => window.__game && window.__game.state === 'title', null, { timeout: 300000, polling: 500 });
  await ev(() => { const g = window.__game; g.save.settings.quality = 'low'; g.save.settings.dynamicRes = false; g.renderer.settings = g.save.settings; g.renderer.applyQuality(); });
  await p.click('[data-act="title-play"]');
  await waitPlay(); await live();
  await ev(() => {
    const g = window.__game;
    window.__sim = (sec, dt = 1 / 30) => { for (let i = 0, n = Math.round(sec / dt); i < n; i++) { g.time += dt; g.update(dt); g.input.endFrame(); } };
  });

  // ------------------------------------------------------------------ movement numbers (aboard the ship: flat deck)
  if (!process.env.SKIP_MOVE) {
    const mv = await ev(() => {
      const g = window.__game, P = g.player, inp = g.input, W = g.weapons, C = g.world.collision, dt = 1 / 60, out = {};
      g.godMode = true; P.armed = true; W.refreshModel();
      // a clear 200 m deck far from the ship's boxes
      const y0 = P.pos.y, base = new P.pos.constructor(400, y0, 400);
      C.add([300, y0 - 1, 300, 500, y0, 500], 'runway');
      const reset = () => { P.pos.copy(base); P.vel.set(0, 0, 0); P.camYaw = Math.PI; P.yaw = 0; P.crouch = false; P.slideT = 0; P.slideCd = 0; P.tacT = 0; P.tacCd = 0;
        P.readyT = 0; P.adsK = 0; P.grounded = true; inp.down.clear(); for (let i = 0; i < 20; i++) P.update(dt, inp, C); };
      const run = (keys, sec, o = {}) => {
        inp.down.clear(); keys.forEach(k => inp.down.add(k)); inp.rmb = !!o.rmb;
        let vmax = 0, ymax = P.pos.y; const p0 = P.pos.clone(), tr = [];
        for (let f = 0; f * dt < sec; f++) {
          (o.hits && o.hits[f] || []).forEach(k => inp.hit.add(k));
          P.update(dt, inp, C); W.update(dt, inp); g.viewmodel.update(dt, inp); inp.hit.clear();
          const v = Math.hypot(P.vel.x, P.vel.z); vmax = Math.max(vmax, v); ymax = Math.max(ymax, P.pos.y); tr.push(v);
          o.each && o.each(f);
        }
        inp.down.clear(); inp.rmb = false;
        return { vmax: +vmax.toFixed(2), vend: +tr[tr.length - 1].toFixed(2), jump: +(ymax - p0.y).toFixed(2), tr };
      };
      out.mob = g.armor.mobility / 100;           // worn armour slows you a little (the simulation runs at parity: 1.0)
      reset(); out.walk = run(['KeyW'], 1.5).vend;
      reset(); out.walkAccel90 = +(run(['KeyW'], .5).tr.findIndex(v => v > out.walk * .9) * dt).toFixed(3);
      reset(); run(['KeyW'], 1.5); out.stop90 = +(run([], .5).tr.findIndex(v => v < out.walk * .1) * dt).toFixed(3);
      reset(); out.sprint = run(['KeyW', 'ShiftLeft'], 1.5).vend;
      reset(); out.ads = run(['KeyW'], 1.5, { rmb: true }).vend;
      reset(); run(['KeyW'], .1, { hits: { 1: ['KeyC'] } }); out.crouch = run(['KeyW'], 1.2).vend;
      // tactical sprint: double-tap sprint while running (release + press twice inside 0.3 s)
      reset(); run(['KeyW', 'ShiftLeft'], .8);
      const tac = run(['KeyW', 'ShiftLeft'], 1.2, { hits: { 2: ['ShiftLeft'], 8: ['ShiftLeft'] } });
      out.tac = tac.vend; out.tacOn = P.tacT > 0;
      run(['KeyW', 'ShiftLeft'], 4.5); out.tacAfter = +Math.hypot(P.vel.x, P.vel.z).toFixed(2); out.tacEnded = P.tacT <= 0;
      // slide from a sprint: distance until it ends
      reset(); run(['KeyW', 'ShiftLeft'], 1.2);
      const sp = P.pos.clone(); let slideT = 0;
      const sl = run(['KeyW', 'ShiftLeft'], 1.6, { hits: { 0: ['KeyC'] }, each: () => { if (P.slideT > 0) slideT += dt; } });
      out.slideDist = +Math.hypot(P.pos.x - sp.x, P.pos.z - sp.z).toFixed(2); out.slideTime = +slideT.toFixed(2); out.slideV = sl.vmax;
      // a slide distance measured only while sliding
      reset(); run(['KeyW', 'ShiftLeft'], 1.2); const s0 = P.pos.clone(); let s1 = null;
      run(['KeyW', 'ShiftLeft'], 1.6, { hits: { 0: ['KeyC'] }, each: () => { if (P.slideT <= 0 && !s1) s1 = P.pos.clone(); } });
      out.slideOnly = s1 ? +Math.hypot(s1.x - s0.x, s1.z - s0.z).toFixed(2) : null;
      // chaining: a second slide right after the first is refused (cooldown)
      reset(); run(['KeyW', 'ShiftLeft'], 1.2); run(['KeyW', 'ShiftLeft'], .95, { hits: { 0: ['KeyC'] } });
      let second = false; run(['KeyW', 'ShiftLeft'], .4, { hits: { 2: ['KeyC'] }, each: () => { if (P.slideT > .5) second = true; } });
      out.slideChain = second;
      // jump cancels a slide and keeps the momentum
      reset(); run(['KeyW', 'ShiftLeft'], 1.2); run(['KeyW', 'ShiftLeft'], .15, { hits: { 0: ['KeyC'] } });
      const sj = run(['KeyW', 'ShiftLeft'], .2, { hits: { 0: ['Space'] } }); out.slideJumpV = sj.vmax; out.slideCancelled = P.slideT <= 0;
      reset(); out.jump = run([], 1.2, { hits: { 1: ['Space'] } }).jump;
      // air control: release forward in a sprint jump -> speed is kept; strafe in air changes little
      reset(); run(['KeyW', 'ShiftLeft'], 1.0); run(['KeyW', 'ShiftLeft'], .05, { hits: { 0: ['Space'] } });
      run(['KeyD'], .4); out.airSide = +Math.abs(P.vel.x).toFixed(2); out.airFwd = +Math.abs(P.vel.z).toFixed(2);
      return out;
    });
    console.log('movement', JSON.stringify(mv));
    const bw = mv.walk / mv.mob, bs = mv.sprint / mv.mob;
    check(bw >= 4.5 && bw <= 5.0, 'walk speed 4.5-5 (before armour mobility ' + mv.mob + ')', bw.toFixed(2));
    check(bs >= 6.7 && bs <= 7.3, 'sprint ~7 (before armour mobility)', bs.toFixed(2));
    check(mv.ads / mv.walk >= .53 && mv.ads / mv.walk <= .62, 'ADS move 55-60% of walk', (mv.ads / mv.walk).toFixed(2));
    check(mv.walkAccel90 <= .15, 'reaches walk speed fast', mv.walkAccel90);
    check(mv.stop90 <= .12, 'stops fast', mv.stop90);
    check(mv.tacOn && mv.tac > mv.sprint + .8, 'tactical sprint on double-tap', mv.tac);
    check(mv.tacEnded && mv.tacAfter < mv.tac, 'tactical sprint runs out', mv.tacAfter);
    check(mv.slideOnly > 3.5 && mv.slideOnly < 8, 'slide carries momentum 3.5-8 m', mv.slideOnly);
    check(!mv.slideChain, 'slides cannot be chained back to back');
    check(mv.slideCancelled && mv.slideJumpV > mv.sprint, 'jump cancels a slide keeping momentum', mv.slideJumpV);
    check(mv.jump > .85 && mv.jump < 1.15, 'jump ~1 m', mv.jump);
    check(mv.airFwd > 5 && mv.airSide < 3, 'little air control, momentum kept', [mv.airFwd, mv.airSide]);
    // sprint-to-fire and ADS times per weapon class
    const hand = await ev(() => {
      const g = window.__game, P = g.player, inp = g.input, W = g.weapons, C = g.world.collision, dt = 1 / 60, out = {};
      const step = () => { P.update(dt, inp, C); W.update(dt, inp); g.viewmodel.update(dt, inp); inp.hit.clear(); inp.lmbHit = false; };
      for (const [arch, slot] of [['pistol', 1], ['rifle', 0], ['bolt', 1], ['rocket', 2]]) {
        const w = g.save.inventory.find(x => x.arch === arch);
        if (!w) { out[arch] = 'missing'; continue; }
        g.save.equipped[slot] = w.uid; W.slot = slot; W.refreshModel(); W.refill(); W.swap = 0; W.cool = 0; W.cancelReload();
        P.pos.set(400, P.pos.y, 400); P.vel.set(0, 0, 0); P.camYaw = Math.PI; P.crouch = false; P.slideT = 0; P.tacT = 0; P.adsK = 0;
        inp.down.clear(); inp.down.add('KeyW'); inp.down.add('ShiftLeft');
        for (let t = 0; t < 1.2; t += dt) step();
        inp.down.delete('ShiftLeft'); inp.lmb = true; inp.lmbHit = true;
        const s0 = g.save.stats.shots; let fireT = null;
        for (let f = 1; f < 60 && fireT === null; f++) { if (arch !== 'rifle') inp.lmbHit = f === 1; P.update(dt, inp, C); W.update(dt, inp); g.viewmodel.update(dt, inp); inp.hit.clear(); if (g.save.stats.shots > s0) fireT = f * dt; }
        inp.lmb = false; inp.down.clear();
        for (let k = 0; k < 90; k++) step();
        inp.rmb = true; let adsT = null;
        for (let f = 1; f < 90 && adsT === null; f++) { step(); P.finishCamera(dt, g.camera); if (P.adsK >= .999) adsT = f * dt; }
        inp.rmb = false; for (let k = 0; k < 40; k++) step();
        out[arch] = { sprintToFire: fireT === null ? null : +fireT.toFixed(3), ads: adsT === null ? null : +adsT.toFixed(3), fov: +g.camera.fov.toFixed(1) };
      }
      g.godMode = false;
      return out;
    });
    console.log('handling', JSON.stringify(hand));
    check(hand.pistol.sprintToFire >= .1 && hand.pistol.sprintToFire <= .2 && hand.bolt.sprintToFire >= .2 && hand.bolt.sprintToFire <= .3, 'sprint-to-fire per class (pistol fast, sniper slow)', hand);
    check(hand.pistol.ads < hand.rifle.ads && hand.rifle.ads < hand.bolt.ads, 'ADS-in per class', hand);
    await ev(() => { const g = window.__game, s = g.world.spawn(); g.player.spawn(s.pos, s.yaw); });
  }

  // ------------------------------------------------------------------ enter Shellbreak from the briefing table
  await ev(() => { const g = window.__game; g.station('briefing'); });
  await p.waitForTimeout(300);
  await p.click('[data-act="tab"][data-v="sim"]');
  await p.waitForTimeout(300);
  await p.click(`[data-act="simcfg"][data-k="difficulty"][data-v="${process.env.DIFF || 'normal'}"]`);
  await shot('00_briefing_sim');
  const t0 = Date.now();
  await p.click('[data-act="simgo"]');
  await waitPlay();
  console.log('arena load seconds', Math.round((Date.now() - t0) / 1000));
  const info = await ev(() => { const g = window.__game, w = g.world, m = w.match; return { kind: w.kind, bots: m.bots.length, team: m.playerTeam, navNodes: w.nav.n, navMs: +w.navMs.toFixed(1), colliders: w.collision.boxes.length, state: m.state,
    loadout: !document.querySelector('#arena .ar-load').classList.contains('hidden'), calls: g.renderer.r.info.render.calls }; });
  console.log('arena', JSON.stringify(info));
  check(info.kind === 'sim' && info.bots === 11 && info.loadout && info.state === 'loadout', 'arena loads with 11 bots and the loadout screen', info);
  await ev(() => window.__sim(1));
  await shot('01_loadout');
  // overview: a high orbit shot of the whole yard
  await ev(() => { const g = window.__game, w = g.world; w.ui.loadEl.classList.add('hidden'); const P = g.camera.position.constructor;
    const pos = new P(58, 62, 72), look = new P(0, 0, 4); g.camera.position.copy(pos); g.camera.lookAt(look); const q = g.camera.quaternion.clone();
    g.camFocus = { pos, look, q, p0: pos, q0: q, fov0: 55, t0: 0 }; w.flyover = () => {}; g.camera.fov = 55; g.camera.updateProjectionMatrix(); window.__sim(1 / 30); });
  await shot('02_overview');
  await ev(() => { const g = window.__game, w = g.world; delete w.flyover; w.ui.loadEl.classList.remove('hidden'); });

  // ------------------------------------------------------------------ deploy and play the match
  // the real Deploy button (a DOM click: software-rendered frames are too slow for Playwright's pointer actionability wait)
  await p.$eval('#arena .ar-load [data-a="deploy"]', b => b.click());
  await live();
  const st = await ev(() => { const g = window.__game, m = g.world.match; return { state: m.state, alive: m.bots.filter(b => b.alive).length, player: m.player.alive, eq: g.save.equipped.slice() }; });
  check(st.state === 'live' && st.alive === 11 && st.player, 'deploy starts the match, everyone spawned', st);
  // spawn sanity: every bot on its own squad's end, not inside a collider, on the nav
  const sp = await ev(() => { const g = window.__game, m = g.world.match, C = g.world.collision;
    return m.bots.map(b => ({ t: b.team, z: +b.pos.z.toFixed(1), inBox: [...C.near(b.pos.x, b.pos.z, .2)].some(x => b.pos.x > x.min.x + .05 && b.pos.x < x.max.x - .05 && b.pos.z > x.min.z + .05 && b.pos.z < x.max.z - .05 && b.pos.y + .5 > x.min.y && b.pos.y + .5 < x.max.y) })); });
  check(sp.every(s => (s.t === 'a' ? s.z < -30 : s.z > 30) && !s.inBox), 'bots spawn at their own end, clear of geometry', sp.filter(s => s.inBox || (s.t === 'a' ? s.z >= -30 : s.z <= 30)));

  if (!process.env.SKIP_MATCH) {
    // the player plays a little: stands at a lane mouth and fires at whatever is in front (god mode keeps the run going)
    const capMin = +(process.env.MATCH_MIN || 10);
    let firefight = false, board = false, last = null;
    const tStart = Date.now();
    for (let sec = 0; sec < capMin * 60; sec += 10) {
      const r = await ev(() => {
        const g = window.__game, m = g.world.match, t0 = performance.now();
        window.__sim(10);
        const ms = performance.now() - t0;
        const alive = m.bots.filter(b => b.alive);
        return { t: Math.round(m.t), state: m.state, a: m.score.a, b: m.score.b, alive: alive.length, ms: +(ms / 300).toFixed(2),
          ai: +(m.mgr.perf.ms / Math.max(1, m.mgr.perf.frames)).toFixed(3), aiMax: +m.mgr.perf.maxMs.toFixed(1), stuck: m.mgr.stats.stuck, shots: m.mgr.stats.shots, hits: m.mgr.stats.hits,
          fights: alive.filter(b => b.state === 'fight').length, deaths: m.all.reduce((s, c) => s + c.stats.deaths, 0), feed: m.feed.length,
          astar: m.mgr.nav.stats.searches, astarMs: +(m.mgr.nav.stats.ms / Math.max(1, m.mgr.nav.stats.searches)).toFixed(3) };
      });
      last = r;
      console.log('match', JSON.stringify(r));
      if (!firefight && r.state === 'live' && r.fights >= 2) {
        // a firefight from the player's view: stand next to a fighting ally, face its target
        const ok = await ev(() => { const g = window.__game, m = g.world.match, P = g.player;
          const b = m.bots.find(x => x.alive && x.ally && x.state === 'fight' && x.target && x.target.alive) || m.bots.find(x => x.alive && !x.ally && x.state === 'fight');
          if (!b) return false;
          const T = b.target, V = P.pos.constructor;
          if (P.dead) return false;
          const back = new V(b.pos.x - T.pos.x, 0, b.pos.z - T.pos.z).normalize();
          P.pos.copy(b.pos).addScaledVector(back, 2.2); P.pos.x += back.z * 1.2; P.pos.z -= back.x * 1.2; P.vel.set(0, 0, 0);
          P.camYaw = Math.atan2(-(T.pos.x - P.pos.x), -(T.pos.z - P.pos.z)); P.camPitch = -.02; P.snapCamera = true;
          g.godMode = true; window.__sim(.6, 1 / 60); return true; });
        if (ok) { await shot('03_firefight'); firefight = true; }
      }
      if (!board && r.t > 60 && r.state === 'live') {
        await ev(() => { const g = window.__game; g.world.ui.board(true); window.__sim(1 / 30); });
        await shot('04_scoreboard'); board = true;
        await ev(() => window.__game.world.ui.board(false));
      }
      if (r.state === 'over') break;
    }
    console.log('match wall seconds', Math.round((Date.now() - tStart) / 1000));
    const end = await ev(() => { const g = window.__game, m = g.world.match; return { state: m.state, result: m.result && { outcome: m.result.outcome, us: m.result.us, them: m.result.them, xp: m.result.xp, credits: m.result.credits, weapon: m.result.weapon.name },
      endShown: !document.querySelector('#arena .ar-end').classList.contains('hidden'), record: g.save.arena, inv: g.save.inventory.length,
      table: [...m.table('a'), ...m.table('b')].map(r => r.name + ' ' + r.elims + '/' + r.assists + '/' + r.deaths) }; });
    console.log('end', JSON.stringify(end));
    check(end.state === 'over' && end.result && end.endShown, 'match ends with a result screen', end.result);
    check(end.result && (end.result.us >= 50 || end.result.them >= 50 || end.result.outcome), 'a winner by score (or time)', end.result);
    check(end.record && end.record.matches === 1, 'service record saved', end.record);
    check(last && last.stuck <= 3, 'no stuck bots', last && last.stuck);
    check(last && last.ai < 3, 'AI cost per frame', last && last.ai + ' ms avg, ' + last.aiMax + ' ms max');
    await shot('05_end');
  }
  console.log('page errors:', errs.length, errs.slice(0, 5));
  check(errs.length === 0, 'no page errors');
  console.log(fails.length ? 'FAILED: ' + fails.join(', ') : 'ALL PASSED');
  await b.close();
  process.exit(fails.length ? 1 : 0);
})().catch(e => { console.error('ARENA TEST FAILED', e); process.exit(2); });
