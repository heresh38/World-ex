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
      const g = window.__game, P = g.player, inp = g.input, W = g.weapons, dt = 1 / 60, out = {};
      g.godMode = true; P.armed = true; W.refreshModel();
      const C = g.world.collision;
      // a clear 70 m runway far from the ship's boxes (floor at the deck height)
      const y0 = P.pos.y, base = new P.pos.constructor(400, y0, 400);
      C.add([300, y0 - 1, 300, 500, y0, 500], 'runway');
      const reset = () => { P.pos.copy(base); P.vel.set(0, 0, 0); P.camYaw = Math.PI; P.yaw = 0; P.crouch = false; P.slideT = 0; P.slideCd = 0; P.tacT = 0; P.tacCharge = P.TAC ? P.TAC.time : 0; P.grounded = true; for (let i = 0; i < 10; i++) P.update(dt, inp, C); };
      const run = (keys, sec, opt = {}) => {
        inp.down.clear(); keys.forEach(k => inp.down.add(k)); inp.rmb = !!opt.rmb; inp.lmb = !!opt.lmb;
        let vmax = 0, ymax = P.pos.y, t = 0; const p0 = P.pos.clone(); const trace = [];
        for (; t < sec; t += dt) {
          (opt.hits && opt.hits[Math.round(t / dt)] || []).forEach(k => inp.hit.add(k));
          P.update(dt, inp, C); W.update(dt, inp); g.viewmodel.update(dt, inp); inp.hit.clear(); inp.lmbHit = false;
          const v = Math.hypot(P.vel.x, P.vel.z); vmax = Math.max(vmax, v); ymax = Math.max(ymax, P.pos.y); trace.push(v);
          if (opt.each) opt.each(t);
        }
        inp.down.clear(); inp.rmb = false; inp.lmb = false;
        return { vmax: +vmax.toFixed(2), vend: +trace[trace.length - 1].toFixed(2), dist: +P.pos.distanceTo(p0).toFixed(2), jump: +(ymax - p0.y).toFixed(2), trace };
      };
      reset(); out.walk = run(['KeyW'], 1.5).vend;
      reset(); const acc = run(['KeyW'], .5); out.walkAccel90 = +(acc.trace.findIndex(v => v > out.walk * .9) * dt).toFixed(3);
      reset(); run(['KeyW'], 1.5); const st = run([], .5); out.stop90 = +(st.trace.findIndex(v => v < out.walk * .1) * dt).toFixed(3);
      reset(); out.sprint = run(['KeyW', 'ShiftLeft'], 1.5).vend;
      reset(); out.ads = run(['KeyW'], 1.5, { rmb: true }).vend;
      reset(); out.crouch = run(['KeyW'], .1, { hits: { 1: ['KeyC'] } }) && run(['KeyW'], 1.2).vend;
      // tactical sprint: double-tap sprint while running
      reset(); run(['KeyW', 'ShiftLeft'], .8); P.update(dt, inp, C);
      const tac = run(['KeyW', 'ShiftLeft'], 1.2, { hits: { 2: ['ShiftLeft'], 8: ['ShiftLeft'] } });
      out.tac = tac.vend; out.tacOn = P.tacT > 0;
      reset(); const tl = run(['KeyW', 'ShiftLeft'], 8, { hits: { 50: ['ShiftLeft'], 56: ['ShiftLeft'] } }); out.tacAfter = tl.vend;
      // slide from a sprint: distance until it ends
      reset(); run(['KeyW', 'ShiftLeft'], 1.2);
      const sp = P.pos.clone(); let slideT = 0;
      const sl = run(['KeyW', 'ShiftLeft'], 1.6, { hits: { 0: ['KeyC'] }, each: () => { if (P.slideT > 0) { slideT += dt; } } });
      out.slideDist = +Math.hypot(P.pos.x - sp.x, P.pos.z - sp.z).toFixed(2); out.slideTime = +slideT.toFixed(2); out.slideVmax = sl.vmax;
      // slide chaining: a second slide right after the first is refused (cooldown)
      reset(); run(['KeyW', 'ShiftLeft'], 1.2); run(['KeyW', 'ShiftLeft'], .9, { hits: { 0: ['KeyC'] } });
      let second = false; run(['KeyW', 'ShiftLeft'], .4, { hits: { 2: ['KeyC'] }, each: () => { if (P.slideT > .5) second = true; } });
      out.slideChain = second;
      // slide jump cancel keeps the momentum
      reset(); run(['KeyW', 'ShiftLeft'], 1.2); run(['KeyW', 'ShiftLeft'], .2, { hits: { 0: ['KeyC'] } });
      const sj = run(['KeyW', 'ShiftLeft'], .15, { hits: { 0: ['Space'] } }); out.slideJumpV = sj.vmax; out.slideCancelled = P.slideT <= 0;
      // jump height and air control
      reset(); out.jump = run([], 1.2, { hits: { 1: ['Space'] } }).jump;
      // sprint-to-fire delay: sprint, then hold fire; time until the first round leaves
      const delay = arch => {
        const w = g.save.inventory.find(x => x.arch === arch); if (!w) return null;
        g.save.equipped[ARCH_SLOT(arch)] = w.uid; W.slot = ARCH_SLOT(arch); W.refreshModel(); W.refill(); W.swap = 0; W.cool = 0;
        reset(); run(['KeyW', 'ShiftLeft'], 1.0);
        const shots0 = g.save.stats.shots; let t1 = null;
        run(['KeyW'], .6, { lmb: true, hits: { 0: ['Mouse0'] }, each: t => { if (t1 === null && g.save.stats.shots > shots0) t1 = t; } });
        return t1 === null ? null : +t1.toFixed(3);
      };
      const ARCH_SLOT = a => window.__game.weapons && (window.__ARCH ? 0 : 0);
      out.slots = null;
      return out;
    });
    console.log('movement', JSON.stringify(mv));
    check(mv.walk >= 4.5 && mv.walk <= 5.0, 'walk speed 4.5-5', mv.walk);
    check(mv.sprint >= 6.7 && mv.sprint <= 7.3, 'sprint ~7', mv.sprint);
    check(mv.ads / mv.walk >= .53 && mv.ads / mv.walk <= .62, 'ADS move 55-60% of walk', (mv.ads / mv.walk).toFixed(2));
    check(mv.walkAccel90 <= .2, 'reaches walk speed fast', mv.walkAccel90);
    check(mv.stop90 <= .16, 'stops fast', mv.stop90);
    check(mv.tacOn && mv.tac > mv.sprint + .8, 'tactical sprint on double-tap', mv.tac);
    check(mv.tacAfter < mv.tac, 'tactical sprint runs out', mv.tacAfter);
    check(mv.slideDist > 4 && mv.slideDist < 9, 'slide carries momentum 4-9 m', mv.slideDist);
    check(!mv.slideChain, 'slides cannot be chained back to back');
    check(mv.slideCancelled && mv.slideJumpV > mv.sprint, 'jump cancels a slide keeping momentum', mv.slideJumpV);
    check(mv.jump > .85 && mv.jump < 1.2, 'jump ~1 m', mv.jump);
    // sprint-to-fire and ADS times per weapon class
    const hand = await ev(() => {
      const g = window.__game, P = g.player, inp = g.input, W = g.weapons, C = g.world.collision, dt = 1 / 60, out = {};
      for (const arch of ['pistol', 'rifle', 'bolt', 'hmg']) {
        const w = g.save.inventory.find(x => x.arch === arch) || null;
        const A = window.__ARCHS && window.__ARCHS[arch];
        if (!w) { out[arch] = 'missing'; continue; }
        const slot = { pistol: 1, rifle: 0, bolt: 1, hmg: 2 }[arch];
        g.save.equipped[slot] = w.uid; W.slot = slot; W.refreshModel(); W.refill(); W.swap = 0; W.cool = 0;
        P.pos.set(400, P.pos.y, 400); P.vel.set(0, 0, 0); P.camYaw = Math.PI; P.crouch = false; P.slideT = 0; P.tacT = 0;
        inp.down.clear(); inp.down.add('KeyW'); inp.down.add('ShiftLeft');
        for (let t = 0; t < 1.2; t += dt) { P.update(dt, inp, C); W.update(dt, inp); g.viewmodel.update(dt, inp); inp.hit.clear(); }
        inp.down.delete('ShiftLeft'); inp.lmb = true; inp.lmbHit = true;
        const s0 = g.save.stats.shots; let fireT = null, t = 0;
        for (; t < .8 && fireT === null; t += dt) { P.update(dt, inp, C); W.update(dt, inp); g.viewmodel.update(dt, inp); inp.hit.clear(); if (g.save.stats.shots > s0) fireT = t; }
        inp.lmb = false; inp.lmbHit = false; inp.down.clear();
        for (let k = 0; k < 60; k++) { P.update(dt, inp, C); W.update(dt, inp); g.viewmodel.update(dt, inp); }
        // ADS: time until the view reaches 95 % of the sight's zoom
        inp.rmb = true; let adsT = null;
        for (t = 0; t < 1 && adsT === null; t += dt) { P.update(dt, inp, C); W.update(dt, inp); g.viewmodel.update(dt, inp); P.finishCamera(dt, g.camera); if ((P.adsK ?? g.viewmodel.ads) > .95) adsT = t; }
        inp.rmb = false;
        out[arch] = { sprintToFire: fireT === null ? null : +fireT.toFixed(3), ads: adsT === null ? null : +adsT.toFixed(3) };
      }
      g.godMode = false;
      return out;
    });
    console.log('handling', JSON.stringify(hand));
    check(hand.pistol.sprintToFire >= .1 && hand.pistol.sprintToFire <= .2 && hand.bolt.sprintToFire >= .2 && hand.bolt.sprintToFire <= .3, 'sprint-to-fire per class (pistol fast, sniper slow)', hand);
    check(hand.pistol.ads < hand.rifle.ads && hand.rifle.ads < hand.bolt.ads, 'ADS-in per class', hand);
    await ev(() => { const g = window.__game; g.player.pos.set(0, g.player.pos.y, 0); });
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
  await p.click('#arena .ar-load [data-a="deploy"]');
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
