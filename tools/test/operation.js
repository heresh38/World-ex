// Operation Heartline (src/worlds/vanthos/operation.js) end to end: land on VANTHOS, run every stage (relay uplink hold,
// Flight Nine recorder, Brood Road purge, Spire lift hold + ride), fight the Spire Warden through both shield phases
// (immune at 50 % until the conduits fall, again at 20 %), open the reliquary and check the randomized loot, duplicate
// copies of one archetype in the inventory, the vault cap, the run record, and a replay. Screenshots in test-out/operation/.
// Usage: python3 -m http.server 8765 &  then  NODE_PATH=$(npm root -g) node tools/test/operation.js
// Software rendering runs at a few fps, so the game is advanced with fixed 1/30 s update steps (__sim) between shots.
const { chromium } = require('playwright');
const fs = require('fs');
const BASE = process.env.BASE || 'http://localhost:8765';
const OUT = (process.env.OUT || 'test-out') + '/operation';
fs.mkdirSync(OUT, { recursive: true });

(async () => {
  const b = await chromium.launch({ args: ['--ignore-gpu-blocklist', '--enable-unsafe-swiftshader', '--use-angle=swiftshader'] });
  const p = await b.newPage({ viewport: { width: 960, height: 540 } });
  const errs = [], fails = [];
  p.on('pageerror', e => { errs.push(e.message); console.log('PAGE ERROR', e.message.slice(0, 400)); });
  p.on('console', m => { if (m.type() === 'error') { errs.push(m.text()); console.log('CONSOLE ERROR', m.text().slice(0, 400)); } });
  await p.addInitScript(() => { localStorage.clear(); window.__TEST_QUALITY = 'low'; window.__MAXTEX = 1024; });
  const ev = (fn, arg) => p.evaluate(fn, arg);
  const wait = ms => p.waitForTimeout(ms);
  // the last rendered frame stays on the canvas while the capture runs: swiftshader frames that pile up behind a slow
  // capture otherwise balloon the browser's memory (the 14 GB box OOM-kills it)
  const shot = async n => {
    await mem(n);
    await ev(() => { const r = window.__game.renderer; if (!r.__render) { r.__render = r.render; r.render = () => {}; } });
    try { await p.screenshot({ path: `${OUT}/${n}.jpg`, type: 'jpeg', quality: 85, timeout: 300000 }); }
    finally { await ev(() => { const r = window.__game.renderer; if (r.__render) { r.render = r.__render; r.__render = null; } }).catch(() => {}); }
    console.log('shot', n);
  };
  const { execSync } = require('child_process');
  const rss = () => { try { const out = execSync('ps -eo pid,ppid,rss').toString().trim().split('\n').slice(1).map(l => l.trim().split(/\s+/).map(Number));
    const kids = new Set([process.pid]); let ch = true; while (ch) { ch = false; for (const [a, pp] of out) if (kids.has(pp) && !kids.has(a)) { kids.add(a); ch = true; } }
    return Math.round(out.filter(r => kids.has(r[0])).reduce((s, r) => s + r[2], 0) / 1024); } catch (e) { return -1; } };
  const mem = async tag => { const m = await p.evaluate(() => { const g = window.__game, r = g.renderer.r.info; return { geo: r.memory.geometries, tex: r.memory.textures, prog: r.programs.length, heap: Math.round(performance.memory.usedJSHeapSize / 1e6), enemies: g.enemies.list.length, scene: g.scene.children.length }; }).catch(() => null);
    console.log('mem', tag, rss() + ' MB', JSON.stringify(m)); };
  const check = (ok, what, info = '') => { console.log((ok ? 'PASS ' : 'FAIL ') + what + (info !== '' ? ' · ' + (typeof info === 'string' ? info : JSON.stringify(info)) : '')); if (!ok) fails.push(what); };
  const live = () => ev(() => { const g = window.__game; g.paused = false; g.menus.hidePause && g.menus.hidePause(); g.input.locked = true; g.input.enabled = true; });
  const waitPlay = async () => { await p.waitForFunction(() => window.__game && window.__game.state === 'play', null, { timeout: 900000, polling: 1000 }); await live(); };
  await p.goto(BASE + '/index.html');
  await p.waitForFunction(() => window.__game && window.__game.state === 'title', null, { timeout: 300000, polling: 500 });
  await ev(() => { const g = window.__game; g.save.settings.quality = 'low'; g.save.settings.dynamicRes = false; g.renderer.settings = g.save.settings; g.renderer.applyQuality(); });
  await p.click('[data-act="title-play"]');
  await waitPlay();
  const t0 = Date.now();
  await ev(() => window.__game.travel('vanthos'));
  await waitPlay();
  console.log('load seconds', Math.round((Date.now() - t0) / 1000));
  // helpers: fixed-step simulation, teleport, look at, E press, kill the operation's live enemies
  const setup = () => ev(() => {
    const g = window.__game;
    g.godMode = true;
    window.__sim = sec => { for (let i = 0, n = Math.round(sec * 30); i < n; i++) { g.time += 1 / 30; g.update(1 / 30); } };
    window.__op = () => g.world.op;
    window.__tp = (x, y, z) => { const P = g.player; P.pos.set(x, y, z); P.vel.set(0, 0, 0); P.avatar.root.position.copy(P.pos); P.snapCamera = true; };
    window.__look = (x, y, z, pitch = -.08) => { const P = g.player; P.camYaw = Math.atan2(-(x - P.pos.x), -(z - P.pos.z)); P.yaw = P.camYaw + Math.PI; P.camPitch = pitch; P.snapCamera = true; };
    window.__press = () => { const f = g.world.focus(g.player); g.input.hit.add('KeyE'); window.__sim(1 / 30); return f ? f.label + ' · ' + f.verb : null; };
    window.__killOp = () => { const V = g.player.pos.constructor; let n = 0; for (const e of g.enemies.list) if (e.alive && e.op && !e.boss) { e.takeDamage(1e7, false, e.center(new V()).clone(), null, 'player'); n++; } return n; };
    window.__state = () => { const o = g.world.op; return { i: o.i, stage: o.S.id, phase: o.phase, hold: +(o.hold.p || 0).toFixed(2), alive: o.reqAlive(), obj: (o.objectives()[0] || {}).text, radio: g.hud.radioCur ? g.hud.radioCur.who + ': ' + g.hud.radioCur.text : null }; };
  });
  await setup();
  const S = () => ev(() => window.__state());
  const info = await ev(() => { const o = window.__op(); return { stages: o.stages.map(s => [s.id, Math.round(s.pos.x), Math.round(s.pos.y), Math.round(s.pos.z)]), off: o.offSites, sites: window.__game.world.sites.length, landing: window.__game.world.landing.toArray().map(Math.round) }; });
  console.log('operation', JSON.stringify(info));
  check(info.stages.length === 5, 'five stages');
  // ---------------------------------------------------------------- landing: intro radio + first objective
  await ev(() => { window.__sim(2.2); const o = window.__op(), s = o.stages[0]; window.__look(s.pos.x, 10, s.pos.z, .02); });
  let st = await S(); console.log('landing', JSON.stringify(st));
  check(st.stage === 'relay' && st.phase === 'travel' && /relay/i.test(st.obj || ''), 'stage 1 objective with distance', st.obj);
  check(!!st.radio, 'intro radio subtitle', st.radio);
  await wait(5000); await shot('op01_landing_radio'); await mem('after op01');
  // ---------------------------------------------------------------- 1: the relay (start the uplink, hold while raiders come)
  await ev(() => { const s = window.__op().stages[0]; window.__tp(s.cp.x, s.cp.y, s.cp.z); window.__sim(.6); });
  st = await S(); check(st.phase === 'ready', 'relay arrival beat', st);
  let pr = await ev(() => { const s = window.__op().stages[0]; window.__tp(s.console.x, s.console.y, s.console.z); window.__look(s.pos.x, s.pos.y + 6, s.pos.z, .25); return window.__press(); });
  st = await S(); check(st.phase === 'hold', 'E starts the uplink', pr);
  let shotHold = false;
  for (let k = 0; k < 40; k++) {
    st = await ev(() => { window.__sim(2); if (Math.random() < .7) window.__killOp(); return window.__state(); });
    if (process.env.MEMLOG) await mem('hold ' + st.hold);
    if (!shotHold && st.hold > .35) { shotHold = true; await ev(() => { const o = window.__op(), s = o.stages[0], L = window.__game.world.landing, d = L.clone().sub(s.pos).setY(0).normalize(); window.__tp(s.pos.x + d.x * 15, s.pos.y, s.pos.z + d.z * 15); window.__look(s.pos.x, s.pos.y + 9, s.pos.z, .32); window.__sim(.1); }); await wait(1500); await shot('op02_relay_hold'); await setup(); }
    if (st.i > 0 || st.phase === 'done') break;
  }
  check(st.phase === 'done' || st.i === 1, 'uplink held to 100 %', st);
  await ev(() => window.__sim(3));
  // ---------------------------------------------------------------- 2: Flight Nine (ambush, pull the recorder, second wave)
  st = await S(); check(st.i === 1 && st.stage === 'shuttle', 'stage 2 next', st);
  await ev(() => { const s = window.__op().stages[1]; window.__tp(s.cp.x, s.cp.y, s.cp.z); window.__sim(3); window.__look(s.pos.x, s.pos.y + 2, s.pos.z, .0); });
  st = await S(); check(st.phase === 'fight1' && st.alive > 0, 'stalker ambush in the wreck', st);
  await wait(1500); await shot('op03_shuttle_ambush');
  await ev(() => { window.__killOp(); window.__sim(1.5); });
  st = await S(); check(st.phase === 'recorder', 'recorder unlocked after the ambush', st);
  pr = await ev(() => { const s = window.__op().stages[1]; window.__tp(s.recorder.x, s.recorder.y - .7, s.recorder.z); return window.__press(); });
  st = await S(); check(st.phase === 'log', 'E pulls the recorder', pr);
  await ev(() => window.__sim(6));
  st = await S(); check(st.phase === 'fight2' && st.alive > 0, 'second wave after the recorder', st);
  for (let k = 0; k < 10 && st.phase === 'fight2'; k++) st = await ev(() => { window.__killOp(); window.__sim(1.5); return window.__state(); });
  await ev(() => window.__sim(3));
  // ---------------------------------------------------------------- 3: the Brood Road (three Writhe waves, then light the gas main)
  st = await S(); check(st.i === 2 && st.stage === 'nest', 'stage 3 next', st);
  await ev(() => { const s = window.__op().stages[2]; window.__tp(s.cp.x, s.cp.y, s.cp.z); window.__sim(1.2); const q = s.cp.clone().lerp(s.pos, .7); window.__tp(q.x, window.__op().ground(q.x, q.z), q.z); window.__look(s.pos.x, s.pos.y + .5, s.pos.z, -.12); window.__sim(.3); });
  st = await S(); check(st.phase === 'w1' && st.alive > 0, 'Writhe nest wakes', st);
  await wait(1500); await shot('op04_nest');
  const seen = new Set();
  for (let k = 0; k < 20 && st.phase !== 'valve'; k++) { st = await ev(() => { window.__killOp(); window.__sim(1); return window.__state(); }); seen.add(st.phase); }
  check(seen.has('w2') || seen.has('w3'), 'nest waves escalate to the amalgam', [...seen]);
  check(st.phase === 'valve', 'valve unlocked', st);
  pr = await ev(() => { const s = window.__op().stages[2]; window.__tp(s.valve.x, s.valve.y, s.valve.z); const P = window.__game.player; window.__look(s.pos.x, s.pos.y, s.pos.z, -.05); return window.__press(); });
  st = await S(); check(st.phase === 'purge', 'E opens the gas main', pr);
  await ev(() => window.__sim(1.6)); await wait(1200); await shot('op05_purge');
  await ev(() => window.__sim(5));
  // ---------------------------------------------------------------- 4: the Spire lift (restore power under attack, ride up)
  st = await S(); check(st.i === 3 && st.stage === 'lift', 'stage 4 next', st);
  const denied = await ev(() => { const g = window.__game, w = g.world, b = w.spireLiftBase; window.__tp(b.pos.x, b.pos.y, b.pos.z + 1); const v = b.verb; window.__press(); return { verb: v, y: g.player.pos.y }; });
  check(denied.y < 20 && /no power/i.test(denied.verb), 'lift refuses without power', denied);
  await ev(() => { const s = window.__op().stages[3]; window.__tp(s.cp.x, s.cp.y, s.cp.z); window.__sim(.6); });
  st = await S(); check(st.phase === 'ready', 'lift arrival beat', st);
  pr = await ev(() => { const s = window.__op().stages[3]; window.__tp(s.console.x, s.console.y, s.console.z + 1.2); return window.__press(); });
  st = await S(); check(st.phase === 'hold', 'E starts rerouting power', pr);
  shotHold = false;
  for (let k = 0; k < 50 && st.phase === 'hold'; k++) {
    st = await ev(() => { window.__sim(2); if (Math.random() < .6) window.__killOp(); return window.__state(); });
    if (!shotHold && st.hold > .5) { shotHold = true; await ev(() => { if (window.__game.save.settings.view !== 'third') window.__game.toggleView(); const P = window.__game.player; window.__look(P.pos.x, 30, P.pos.z - 60, .12); }); await wait(1800); await shot('op06_lift_defend'); await setup(); }
  }
  check(st.phase === 'ride', 'lift powered', st);
  pr = await ev(() => { const b = window.__game.world.spireLiftBase; window.__killOp(); window.__tp(b.pos.x, b.pos.y, b.pos.z + 1); return window.__press(); });
  const up = await ev(() => window.__game.player.pos.y);
  check(up > 25, 'lift rides to the foundation', { pr, y: up });
  await ev(() => window.__sim(3.2));
  // ---------------------------------------------------------------- 5: the Spire Warden
  st = await S(); check(st.i === 4 && st.phase === 'intro', 'the Warden wakes on the foundation', st);
  await ev(() => window.__sim(4));
  const boss0 = await ev(() => { const B = window.__op().boss; return { alive: B.alive, hp: B.hp, max: B.maxHp, name: B.T.name, state: B.state }; });
  check(boss0.alive && boss0.state === 'combat', 'boss fight starts', boss0);
  await ev(() => { const B = window.__op().boss; window.__tp(B.pos.x + 4, 28, B.pos.z + 16); window.__look(B.pos.x, B.pos.y + 2.5, B.pos.z, .1); window.__sim(.2); });
  await wait(1500); await shot('op07_warden');
  // to 50 %: the floor holds, the shield rises, damage is blocked
  const half = await ev(() => { const g = window.__game, B = window.__op().boss, V = g.player.pos.constructor;
    B.takeDamage(B.maxHp * .3, false, B.center(new V()).clone(), null, 'player'); B.takeDamage(B.maxHp * .3, false, B.center(new V()).clone(), null, 'player');
    const hp = B.hp, r = B.takeDamage(5000, false, B.center(new V()).clone(), null, 'player');
    return { frac: +(hp / B.maxHp).toFixed(3), immune: B.immune, blocked: r.immune === true && B.hp === hp, phase: window.__op().phase, active: window.__op().conduits.filter(c => c.alive).length }; });
  check(half.frac === .5 && half.immune && half.blocked, 'at 50 % the Warden is immune (damage blocked)', half);
  check(half.phase === 'shield' && half.active === 3, 'three shield conduits online', half);
  // a real weapon round through the hit pipeline: the trace finds the Warden and the HUD shows IMMUNE
  const real = await ev(() => { const g = window.__game, B = window.__op().boss, V = g.player.pos.constructor;
    const o = g.camera.position.clone(), c = B.center(new V()).clone(), d = c.clone().sub(o).normalize();
    const res = g.combat.trace(o, d, 300, 'player'); const hp = B.hp;
    const w = g.weapons.equipped(g.weapons.slot);
    if (res.target) g.weapons.roundHit({ w, S: { dmg: 80, range: 50, crit: 2 }, dist: 0, shot: {} }, res, d);
    window.__sim(1 / 30);
    const nums = [...document.querySelectorAll('.h-num')].filter(e => e.style.display !== 'none').map(e => e.textContent);
    return { hitBoss: res.target === B, hpSame: B.hp === hp, nums, bar: document.querySelector('.h-boss .bs').textContent, shield: document.querySelector('.h-boss').classList.contains('shield') }; });
  check(real.hitBoss && real.hpSame && real.nums.includes('IMMUNE'), 'weapon hit on the shield shows IMMUNE', real);
  check(real.shield && /immune/i.test(real.bar), 'boss bar shows the shield state', real.bar);
  await ev(() => { window.__sim(2); const B = window.__op().boss; const P = window.__game.player; window.__look(B.pos.x, B.pos.y + 3, B.pos.z, .12); });
  await wait(1800); await shot('op08_shield_phase');
  // the same moment on a landscape phone (iPhone-size viewport, touch layout)
  await p.setViewportSize({ width: 932, height: 430 });
  await ev(() => { document.body.classList.add('touch'); window.__game.hud.radio('Wren Asheby · Wayfarer', 'It’s pulling power through those pylons. The shield is fed from the core. Break the conduits!', { color: '#1ad8ff' }); window.__sim(.5); });
  await wait(1800); await shot('op08b_shield_phone');
  await ev(() => document.body.classList.remove('touch'));
  await p.setViewportSize({ width: 960, height: 540 });
  // a conduit: a ray finds it, its bar shows, shots wear it down
  const cd = await ev(() => { const g = window.__game, op = window.__op(), c = op.conduits[0], V = g.player.pos.constructor;
    window.__tp(c.pos.x - 10, 28, c.pos.z + 10); window.__look(c.pos.x, c.pos.y + 3, c.pos.z, .15); window.__sim(.1);
    const o = g.camera.position.clone(), d = c.center(new V()).clone().sub(o).normalize(), res = g.combat.trace(o, d, 200, 'player');
    const hp0 = c.hp; c.takeDamage(c.maxHp * .4, false, c.center(new V()).clone(), d, 'player');
    return { traced: res.target === c, hp0, hp: c.hp, bars: op.barTargets().length }; });
  check(cd.traced && cd.hp < cd.hp0 && cd.bars >= 1, 'conduits are shootable targets with health bars', cd);
  await wait(1500); await shot('op09_conduit');
  const drop = await ev(() => { const g = window.__game, op = window.__op(), V = g.player.pos.constructor;
    for (const c of op.conduits) if (c.alive) c.takeDamage(1e7, false, c.center(new V()).clone(), null, 'player');
    const B = op.boss, hp = B.hp; const r = B.takeDamage(1000, false, B.center(new V()).clone(), null, 'player');
    return { immune: B.immune, phase: op.phase, stun: B.stunT > 0, dealt: Math.round(r.dealt || 0), dropped: Math.round(hp - B.hp) }; });
  check(!drop.immune && drop.phase === 'stagger' && drop.stun && drop.dropped > 0, 'conduits down: shield drops, the Warden staggers, damage lands', drop);
  await ev(() => { const B = window.__op().boss; window.__tp(B.pos.x + 3, 28, B.pos.z + 12); window.__look(B.pos.x, B.pos.y + 2.5, B.pos.z, .1); window.__sim(.3); });
  await wait(1200); await shot('op10_stagger');
  const p2 = await ev(() => { const g = window.__game, op = window.__op(), B = op.boss, V = g.player.pos.constructor;
    window.__sim(5);
    B.takeDamage(B.maxHp, false, B.center(new V()).clone(), null, 'player');
    const r = { frac: +(B.hp / B.maxHp).toFixed(3), immune: B.immune, active: op.conduits.filter(c => c.alive).length, phase: op.phase };
    for (const c of op.conduits) if (c.alive) c.takeDamage(1e7, false, c.center(new V()).clone(), null, 'player');
    r.after = op.phase; window.__sim(5);
    B.takeDamage(1e8, false, B.center(new V()).clone(), null, 'player'); window.__sim(2);
    r.dead = !B.alive; r.loot = op.phase; r.sealed = op.reliq.sealed; r.runs = g.save.vanthos.runs; r.best = g.save.vanthos.best;
    return r; });
  check(p2.frac === .2 && p2.immune && p2.active === 2, 'second shield phase at 20 % with two conduits', p2);
  check(p2.after === 'stagger' && p2.dead && p2.loot === 'loot' && !p2.sealed, 'Warden dies, reliquary unseals', p2);
  check(p2.runs === 1 && p2.best > 0, 'run recorded (runs, best time)', { runs: p2.runs, best: p2.best });
  // ---------------------------------------------------------------- loot: the reliquary
  const loot = await ev(() => { const g = window.__game, op = window.__op(), sv = g.save;
    const n0 = sv.inventory.length, it = op.its.find(x => x.label === 'The Warden’s reliquary');
    window.__tp(it.pos.x, it.pos.y, it.pos.z); window.__look(op.reliq.pos.x, op.reliq.pos.y + .8, op.reliq.pos.z, -.35);
    const pr = window.__press(); window.__sim(.5);
    const ws = (op.rewards && op.rewards.weapons) || [];
    const ok = ws.every(w => sv.inventory.includes(w) && w.isNew && w.source === 'Spire reliquary');
    return { pr, n: ws.length, added: sv.inventory.length - n0, ok, complete: op.complete, ws: ws.map(w => ({ uid: w.uid, arch: w.arch, rarity: w.rarity, power: w.power, perks: w.perks, sight: w.sight })),
      signal: !!op.its.find(x => x.label === 'Signal the Wayfarer' && x.enabled()) }; });
  console.log('loot', JSON.stringify(loot));
  check(loot.n >= 2 && loot.n <= 3 && loot.added === loot.n && loot.ok && loot.complete, 'reliquary grants 2-3 rolled weapons', { n: loot.n, added: loot.added });
  check(new Set(loot.ws.map(w => w.uid)).size === loot.n, 'every reward has its own uid');
  check(loot.signal, 'return-to-orbit signal offered');
  await wait(1800); await shot('op11_reliquary_summary');
  // duplicates: the same archetype many times, every copy its own roll
  const dup = await ev(async () => { const g = window.__game, op = window.__op(), sv = g.save;
    const { sightOptions } = await import('/src/game/data.js');
    const ws = op.rollRewards(4, { arch: 'rifle' }); ws.forEach(w => g.addWeapon(w));
    const rifles = sv.inventory.filter(w => w.arch === 'rifle');
    const sig = w => w.perks.join('+') + '|' + w.sight + '|' + Object.values(w.stats).map(v => v.toFixed(3)).join(',');
    return { copies: rifles.length, uids: new Set(rifles.map(w => w.uid)).size, distinct: new Set(ws.map(sig)).size, perkSets: ws.map(w => w.perks.join('+')),
      sightsOk: ws.every(w => sightOptions('rifle').includes(w.sight)), sights: ws.map(w => w.sight) }; });
  console.log('duplicates', JSON.stringify(dup));
  check(dup.copies >= 4 && dup.uids === dup.copies, 'duplicate archetypes coexist (unique uids)', dup);
  check(dup.distinct === 4 && dup.sightsOk && new Set(dup.perkSets).size >= 2, 'duplicates differ in perks / sight / stat rolls', dup.perkSets);
  // the inventory shows what sets the copies apart (NEW tags, sight, roll %), and Lock protects one
  const inv = await ev(() => { const g = window.__game, m = g.menus;
    g.openInventory(); m.tab = 'weapons'; m.filter = 0; m.clsFilter = 'kinetic'; m.render();
    const cards = [...document.querySelectorAll('#panel .card')];
    const rifle = cards.filter(c => /Assault Rifle/.test(c.textContent));
    return { cards: cards.length, rifleCards: rifle.length, news: document.querySelectorAll('#panel .card .tag:not(.lock)').length,
      sg: rifle.slice(0, 4).map(c => (c.querySelector('.sg') || {}).textContent), pk: rifle.slice(0, 4).map(c => (c.querySelector('.pk') || {}).textContent),
      facts: [...document.querySelectorAll('#panel .inv-facts span')].map(s => s.textContent).slice(4) }; });
  console.log('inventory', JSON.stringify(inv));
  check(inv.rifleCards >= 4 && inv.news >= 4 && inv.sg.every(Boolean), 'inventory lists every copy with NEW tag, sight and rolls', { rifleCards: inv.rifleCards, news: inv.news });
  await wait(1200); await shot('op12_inventory_duplicates');
  const vault = await ev(() => { const g = window.__game, sv = g.save, m = g.menus;
    // pick a reward card: the NEW tag clears; lock it
    const w = g.world.op.rewards.weapons[0]; m.sel = null;
    document.querySelector(`#panel .card[data-v="${w.uid}"]`) || (m.filter = -1, m.clsFilter = 'all', m.render());
    const card = document.querySelector(`#panel .card[data-v="${w.uid}"]`); card && card.click();
    const seenNew = w.isNew; document.querySelector('#panel [data-act="keep"]').click();
    g.closeStation();
    // flood the vault far past the cap with plain spares: locked, new and equipped weapons survive, nothing silent
    const locked = sv.inventory.filter(x => x.keep).map(x => x.uid), fresh = sv.inventory.filter(x => x.isNew).map(x => x.uid), eq = [...sv.equipped];
    for (let k = 0; k < 230; k++) { const x = g.world.op.rollRewards(1)[0]; x.isNew = false; g.addWeapon(x); }
    const has = id => sv.inventory.some(x => x.uid === id);
    return { len: sv.inventory.length, keptLocked: locked.every(has), keptNew: fresh.every(has), keptEq: eq.filter(Boolean).every(has), lockedReward: w.keep, seenNew,
      feed: [...document.querySelectorAll('.h-feed div')].map(d => d.textContent).filter(t => /Vault full/.test(t)).length }; });
  console.log('vault', JSON.stringify(vault));
  check(vault.len <= 200 && vault.keptLocked && vault.keptNew && vault.keptEq && vault.lockedReward && vault.seenNew === false, 'vault cap 200: never scraps locked / new / equipped, and says so', vault);
  check(vault.feed > 0, 'vault overflow is reported in the feed');
  // ---------------------------------------------------------------- HUD state at the end, then a replay
  const fin = await ev(() => { const g = window.__game; return { obj: g.world.objectives().slice(0, 2).map(o => o.text), runs: g.save.vanthos.runs }; });
  console.log('final', JSON.stringify(fin));
  check(/complete/i.test(fin.obj[0]), 'objectives show the completed operation', fin.obj);
  await ev(() => window.__game.travel('vanthos'));
  await waitPlay(); await setup();
  const again = await ev(() => { window.__sim(1); const g = window.__game, o = g.world.op; return { i: o.i, phase: o.phase, complete: o.complete, runs: g.save.vanthos.runs, boss: !!o.boss }; });
  check(again.i === 0 && again.phase === 'travel' && !again.complete && again.runs === 1, 'replay: a new visit restarts the operation, the run count stays', again);
  check(errs.length === 0, '0 page errors', errs.length);
  console.log(fails.length ? 'FAILED: ' + fails.join(' | ') : 'ALL PASSED');
  await b.close();
  process.exit(fails.length || errs.length ? 1 : 0);
})().catch(e => { console.error(e); process.exit(1); });
