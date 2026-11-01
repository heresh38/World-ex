// The Writhe infestation + reworked aliens: spawn each creature near the player, screenshot it, then check the
// behaviours: mite swarm leaps, bladder rupture releasing brood, a mite raising a corpse as a host, the Writhe fighting
// the other factions, and 0 page errors.
// Usage: python3 -m http.server 8765 &  then  NODE_PATH=$(npm root -g) node tools/test/horror.js   (screenshots in test-out/)
// WORLD=vanthos_metro (default, the research-sector metro), vanthos, ares (a frontier planet) or ship (the hub).
// Software rendering runs at a few fps, so behaviour checks advance the game with fixed 1/30 s update steps (no
// rendering) instead of waiting in real time; screenshots render normally.
const { chromium } = require('playwright');
const fs = require('fs');
const BASE = process.env.BASE || 'http://localhost:8765';
const OUT = process.env.OUT || 'test-out';
const WORLD = process.env.WORLD || 'vanthos_metro';
fs.mkdirSync(OUT, { recursive: true });

(async () => {
  const b = await chromium.launch({ args: ['--ignore-gpu-blocklist', '--enable-unsafe-swiftshader', '--use-angle=swiftshader'] });
  const p = await b.newPage({ viewport: { width: 960, height: 540 } });
  const errs = [];
  p.on('pageerror', e => { errs.push(e.message); console.log('PAGE ERROR', e.message.slice(0, 400)); });
  p.on('console', m => { if (m.type() === 'error') { errs.push(m.text()); console.log('CONSOLE ERROR', m.text().slice(0, 400)); } });
  await p.addInitScript(() => { localStorage.clear(); window.__TEST_QUALITY = 'low'; });
  // other work in progress may list models that are not built yet: serve a stand-in so the game can boot
  await p.route('**/assets/models/*.glb', async route => {
    const r = await route.fetch();
    if (r.status() !== 404) return route.fulfill({ response: r });
    const u = route.request().url(), f = u.split('/').pop();
    console.log('fallback for', f);
    return route.continue({ url: /_npc\.glb$/.test(f) ? u.replace('_npc.glb', '.glb') : u.replace(f, 'writhe_mite.glb') });
  });
  const ev = (fn, arg) => p.evaluate(fn, arg);
  const wait = ms => p.waitForTimeout(ms);
  const shot = async n => { await p.screenshot({ path: `${OUT}/${n}.jpg`, type: 'jpeg', quality: 85, timeout: 300000 }); console.log('shot', n); };
  const live = () => ev(() => { const g = window.__game; g.paused = false; g.menus.hidePause && g.menus.hidePause(); g.input.locked = true; g.input.enabled = true; });
  const waitPlay = async () => { await p.waitForFunction(() => window.__game && window.__game.state === 'play', null, { timeout: 900000, polling: 1000 }); await live(); };
  await p.goto(BASE + '/index.html');
  await p.waitForFunction(() => window.__game && window.__game.state === 'title', null, { timeout: 300000, polling: 500 });
  await ev(() => { const g = window.__game; g.save.settings.quality = 'low'; g.save.settings.dynamicRes = false; g.renderer.settings = g.save.settings; g.renderer.applyQuality(); });
  await p.click('[data-act="title-play"]');
  await waitPlay();
  if (WORLD !== 'ship') {
    await ev(w => { const g = window.__game; if (w === 'vanthos_metro') g.metroEntry = { x: 0, y: 0, z: 0, district: 'research', seed: 7, level: 8 }; g.travel(w); }, WORLD);
    await waitPlay();
  }
  await wait(1500);
  // freeze the world's own spawning, clear it, make the player invulnerable; __sim(sec) steps the game without rendering
  const base = await ev(() => {
    const g = window.__game, w = g.world;
    w.stream = () => {}; w.wanted = () => []; w.droneT = 1e9; if (w.packs) w.packs.forEach(pk => pk.live = true);
    g.enemies.clear(); g.godMode = true;
    window.__sim = sec => { for (let i = 0, n = Math.round(sec * 30); i < n; i++) { g.time += 1 / 30; g.update(1 / 30); } };
    window.__dmg = 0; const pd = g.player.damage.bind(g.player); g.player.damage = (n, f) => { window.__dmg += n; pd(n, f); };
    const c = w.startPos ? w.startPos.clone() : w.sites ? (w.sites.find(s => s.D.id === 'old') || w.sites[0]).pos.clone() : g.player.pos.clone();
    return { x: c.x, y: c.y, z: c.z, kind: w.kind, models: ['writhe_mite', 'writhe_host', 'writhe_bladder', 'writhe_amalgam'].map(m => !!g.assets.models[m]) };
  });
  console.log('base', JSON.stringify(base));
  // ---- portraits: the creature at the base point facing a free camera, AI frozen
  const portrait = async (type, name, dist = 4, h = 1.2, clip = null, frame = 0) => {
    await ev(([type, bx, bz, dist, h, clip, frame]) => {
      const g = window.__game, w = g.world, Vc = g.camera.position.constructor;
      g.enemies.clear();
      const x = bx, z = bz, y = w.collision.ground(x, z);
      const e = g.enemies.spawn(type, new Vc(x, y, z), 10);
      e.update = function (dt) { this.av.update(dt); return true; };
      e.yaw = .35; e.obj.rotation.y = e.yaw;
      if (clip) { e.av.play(clip, 0); e.av.current.time = frame; e.av.current.paused = true; }
      e.av.update(0);
      const c = g.camera, cp = new Vc(x + Math.sin(e.yaw) * dist, y + h + .25, z + Math.cos(e.yaw) * dist), look = new Vc(x, y + h * .78, z);
      g.player.pos.set(x, y, z + dist + 3); g.player.avatar.root.position.copy(g.player.pos);
      g.stationId = 'test'; c.position.copy(cp); c.lookAt(look);
      g.camFocus = { pos: cp, look, orbit: false, q: c.quaternion.clone(), p0: c.position.clone(), q0: c.quaternion.clone(), fov0: 55, t0: 0 };
      if (w.torch) { w.torch.intensity = 140; }
    }, [type, base.x, base.z, dist, h, clip, frame]);
    await wait(2500); await shot(name);
  };
  await portrait('host', 'h01_host', 3.2, 1.3);
  await portrait('host', 'h02_host_attack', 3.4, 1.3, 'Attack', .45);
  await portrait('mite', 'h03_mite', 1.4, .3);
  await portrait('bladder', 'h04_bladder', 3.6, 1.2);
  await portrait('amalgam', 'h05_amalgam', 4.6, 1.9);
  for (const a of ['stalker', 'hulk', 'mutant', 'swimmer', 'elite']) await portrait(a, 'h06_alien_' + a, a === 'hulk' || a === 'elite' ? 4.4 : 3.4, a === 'hulk' ? 1.7 : 1.4);
  await ev(() => { const g = window.__game; g.stationId = null; g.camFocus = null; g.enemies.clear(); });
  await live();
  // behaviour arena: in the metro and the ship, the open floor beyond the walls; elsewhere the base point
  const A = WORLD === 'vanthos_metro' || WORLD === 'ship' ? { x: base.x + 300, z: base.z } : { x: base.x, z: base.z };
  // ---- swarm: mites skitter in, leap and burst on the player
  const swarm = await ev(([ax, az]) => {
    const g = window.__game, w = g.world, Vc = g.player.pos.constructor;
    g.player.pos.set(ax, w.collision.ground(ax, az), az); g.player.avatar.root.position.copy(g.player.pos);
    if (g.save.settings.view !== 'third') g.toggleView();
    window.__dmg = 0;
    const ms = [];
    for (let k = 0; k < 7; k++) { const x = ax + 14 + Math.random() * 3, z = az - 4 + k * 1.3; ms.push(g.enemies.spawn('mite', new Vc(x, w.collision.ground(x, z), z), 8)); }
    ms.forEach(m => m.alert());
    let leapt = 0;
    for (let i = 0; i < 6 * 30; i++) { window.__sim(1 / 30); leapt = Math.max(leapt, ms.filter(m => m.leaping).length); }
    return { leaptAtOnce: leapt, dmg: Math.round(window.__dmg), burst: ms.filter(m => !m.alive).length };
  }, [A.x, A.z]);
  console.log('swarm', JSON.stringify(swarm));
  // a rendered look at a fresh swarm
  await ev(([ax, az]) => { const g = window.__game, w = g.world, Vc = g.player.pos.constructor; g.enemies.clear();
    for (let k = 0; k < 6; k++) { const x = ax + 5 + Math.random() * 2, z = az - 3 + k; const m = g.enemies.spawn('mite', new Vc(x, w.collision.ground(x, z), z), 8); m.alert(); }
    g.player.yaw = -Math.PI / 2; window.__sim(.8); }, [A.x, A.z]);
  await wait(800); await shot('h07_swarm');
  // ---- bladder: waddles in, swells and ruptures, the brood spills out
  const bladder = await ev(([ax, az]) => {
    const g = window.__game, w = g.world, Vc = g.player.pos.constructor;
    g.enemies.clear(); window.__dmg = 0;
    const x = ax + 8, z = az; const bl = g.enemies.spawn('bladder', new Vc(x, w.collision.ground(x, z), z), 8); bl.alert();
    let t = 0, swelled = false;
    while (bl.alive && t < 20) { window.__sim(.1); t += .1; swelled = swelled || bl.swellT > 0; }
    return { burst: !bl.alive, swelled, seconds: +t.toFixed(1), brood: g.enemies.list.filter(e => e.type === 'mite' && e.alive).length, dmg: Math.round(window.__dmg) };
  }, [A.x, A.z]);
  console.log('bladder', JSON.stringify(bladder));
  await wait(600); await shot('h08_bladder_burst');
  // shooting a bladder from range also ruptures it
  const shotBladder = await ev(([ax, az]) => {
    const g = window.__game, w = g.world, Vc = g.player.pos.constructor;
    g.enemies.clear();
    const x = ax + 20, z = az + 5; const bl = g.enemies.spawn('bladder', new Vc(x, w.collision.ground(x, z), z), 8);
    bl.takeDamage(9999, false, bl.center(new Vc()), new Vc(1, 0, 0), 'player');
    return { burst: !bl.alive, brood: g.enemies.list.filter(e => e.type === 'mite' && e.alive).length };
  }, [A.x, A.z]);
  console.log('bladder shot', JSON.stringify(shotBladder));
  // ---- hosts lurch in, lunge and club
  const lurch = await ev(([ax, az]) => {
    const g = window.__game, w = g.world, Vc = g.player.pos.constructor;
    g.enemies.clear(); window.__dmg = 0;
    g.player.pos.set(ax, w.collision.ground(ax, az), az);
    const h = g.enemies.spawn('host', new Vc(ax + 14, w.collision.ground(ax + 14, az), az), 8, { gun: null }); h.alert();
    let lunged = false, t = 0;
    while (t < 10 && window.__dmg <= 0) { window.__sim(.1); t += .1; lunged = lunged || h.lungeT > 0; }
    return { lunged, hit: window.__dmg > 0, seconds: +t.toFixed(1) };
  }, [A.x, A.z]);
  console.log('lurch', JSON.stringify(lurch));
  // ---- reanimation: a dead raider, a mite finds it, the corpse rises as a host
  const rean = await ev(([ax, az]) => {
    const g = window.__game, w = g.world, Vc = g.player.pos.constructor;
    g.enemies.clear();
    g.player.pos.set(ax - 45, w.collision.ground(ax - 45, az), az); g.player.avatar.root.position.copy(g.player.pos);
    const tx = ax + 10, tz = az + 2;
    const tr = g.enemies.spawn('trooper', new Vc(tx, w.collision.ground(tx, tz), tz), 8);
    tr.takeDamage(9999, false, tr.center(new Vc()), new Vc(1, 0, 0), 'rival');
    const mx = tx + 6, mz = tz + 4; const m = g.enemies.spawn('mite', new Vc(mx, w.collision.ground(mx, mz), mz), 8);
    let host = null, t = 0;
    while (!host && t < 15) { window.__sim(.1); t += .1; host = g.enemies.list.find(e => e.type === 'host' && e.alive); }
    const rising = host && host.riseT > 0;
    window.__sim(2.2);
    return { risen: !!host, seconds: +t.toFixed(1), rising, stoodUp: !!host && !(host.riseT > 0), armed: !!(host && host.armed), corpseGone: !g.enemies.list.includes(tr), miteConsumed: !m.alive,
      at: host && [host.pos.x, host.pos.z] };
  }, [A.x, A.z]);
  console.log('reanimate', JSON.stringify(rean));
  if (rean.at) {
    await ev(([x, z]) => { const g = window.__game, w = g.world; g.player.pos.set(x - 5, w.collision.ground(x - 5, z), z); g.player.avatar.root.position.copy(g.player.pos); g.player.yaw = -Math.PI / 2; }, rean.at);
    await wait(1200); await shot('h09_risen_host');
  }
  // ---- faction war: the Writhe against raiders and aliens with the player far away (no faction-war district needed)
  const war = await ev(([ax, az]) => {
    const g = window.__game, w = g.world, Vc = g.player.pos.constructor;
    g.enemies.clear();
    g.player.pos.set(ax - 90, w.collision.ground(ax - 90, az), az); g.player.avatar.root.position.copy(g.player.pos);
    const at = (dx, dz) => new Vc(ax + dx, w.collision.ground(ax + dx, az + dz), az + dz);
    const h = g.enemies.spawn('host', at(0, 0), 8, { gun: null }), tr = g.enemies.spawn('trooper', at(12, 0), 8);
    const am = g.enemies.spawn('amalgam', at(0, 30), 8), st = g.enemies.spawn('stalker', at(10, 30), 8);
    const ms = [0, 1, 2].map(k => g.enemies.spawn('mite', at(4 + k, 60), 8)), br = g.enemies.spawn('brute', at(12, 60), 8);
    const hp0 = [h.hp, tr.hp, am.hp, st.hp, br.hp];
    window.__sim(10);
    const hurt = (e, i) => e.hp < hp0[i] || !e.alive;
    return { factionWar: !!w.factionWar, hostHurt: hurt(h, 0), trooperHurt: hurt(tr, 1), amalgamHurt: hurt(am, 2), stalkerHurt: hurt(st, 3), bruteHurt: hurt(br, 4),
      mitesLeft: ms.filter(m => m.alive).length, enemies: g.enemies.list.filter(e => e.alive).map(e => e.type).join(',') };
  }, [A.x, A.z]);
  console.log('war', JSON.stringify(war));
  await ev(([ax, az]) => { const g = window.__game, w = g.world; g.player.pos.set(ax - 10, w.collision.ground(ax - 10, az), az + 15); g.player.avatar.root.position.copy(g.player.pos); g.player.yaw = -Math.PI * .75; }, [A.x, A.z]);
  await wait(1200); await shot('h10_war');
  console.log('fps', await ev(() => Math.round(window.__game.fps)));
  const ok = swarm.dmg > 0 && bladder.burst && bladder.brood > 0 && shotBladder.brood > 0 && lurch.hit && rean.risen && rean.stoodUp &&
    (war.hostHurt || war.trooperHurt) && (war.amalgamHurt || war.stalkerHurt) && (war.bruteHurt || war.mitesLeft < 3);
  console.log('checks', ok ? 'PASS' : 'FAIL', 'page errors:', errs.length);
  await b.close();
  process.exit(errs.length || !ok ? 1 : 0);
})().catch(e => { console.error('HORROR TEST FAILED', e); process.exit(2); });
