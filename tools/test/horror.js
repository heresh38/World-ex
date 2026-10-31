// The Writhe infestation + reworked aliens: spawn each creature near the player in VANTHOS, screenshot it, then check
// the behaviours: mite swarm leaps, bladder rupture releasing brood, mites raising a corpse as a host, Writhe vs other
// factions, and 0 page errors.
// Usage: python3 -m http.server 8765 &  then  NODE_PATH=$(npm root -g) node tools/test/horror.js   (screenshots in test-out/)
// WORLD=ares (or another frontier planet id) runs the same checks on a lighter world: VANTHOS needs a renderer with ~5 GB.
const { chromium } = require('playwright');
const fs = require('fs');
const BASE = process.env.BASE || 'http://localhost:8765';
const OUT = process.env.OUT || 'test-out';
const WORLD = process.env.WORLD || 'vanthos';
fs.mkdirSync(OUT, { recursive: true });

(async () => {
  const b = await chromium.launch({ args: ['--ignore-gpu-blocklist', '--enable-unsafe-swiftshader', '--use-angle=swiftshader'] });
  const p = await b.newPage({ viewport: { width: 960, height: 540 } });
  const errs = [];
  p.on('pageerror', e => { errs.push(e.message); console.log('PAGE ERROR', e.message.slice(0, 400)); });
  p.on('console', m => { if (m.type() === 'error') { errs.push(m.text()); console.log('CONSOLE ERROR', m.text().slice(0, 400)); } });
  await p.addInitScript(() => { localStorage.clear(); window.__TEST_QUALITY = 'low'; });
  // other work in progress may list models that are not built yet (player *_npc): fall back to the base model for this test
  await p.route('**/assets/models/*_npc.glb', async route => {
    const r = await route.fetch();
    if (r.status() === 404) { console.log('fallback for', route.request().url().split('/').pop()); return route.continue({ url: route.request().url().replace('_npc.glb', '.glb') }); }
    return route.fulfill({ response: r });
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
  await ev(w => window.__game.travel(w), WORLD);
  await waitPlay();
  await wait(2000);
  // a quiet street: stop the district streaming and clear what is around, the player is invulnerable for the shots
  const base = await ev(() => {
    const g = window.__game, w = g.world;
    w.stream = () => {}; w.wanted = () => []; w.droneT = 1e9;           // no streaming packs, chunks or drone patrols
    g.enemies.clear(); g.godMode = true;
    const st = w.sites ? (w.sites.find(s => s.D.id === 'old') || w.sites[0]) : { pos: g.player.pos.clone() };
    const x = st.pos.x, z = st.pos.z;
    g.player.pos.set(x, w.collision.ground(x, z), z); g.player.avatar.root.position.copy(g.player.pos);
    window.__dmg = 0; const pd = g.player.damage.bind(g.player); g.player.damage = (n, f) => { window.__dmg += n; pd(n, f); };
    return { x, z, models: ['writhe_mite', 'writhe_host', 'writhe_bladder', 'writhe_amalgam'].map(m => !!g.assets.models[m]) };
  });
  console.log('base', JSON.stringify(base));
  const V = (x, y, z) => [x, y, z];
  // ---- portraits: each creature 4 m in front of a free camera, AI frozen
  const portrait = async (type, name, dist = 4, h = 1.2, clip = null) => {
    await ev(([type, bx, bz, dist, h, clip]) => {
      const g = window.__game, w = g.world, Vc = g.camera.position.constructor;
      g.enemies.clear();
      const x = bx + 6, z = bz + 6, y = w.collision.ground(x, z);
      const e = g.enemies.spawn(type, new Vc(x, y, z), 10);
      e.thinkT = 1e9; e.update = function (dt) { this.av.update(dt); if (this.glowMats) for (const o of this.glowMats) o.m.emissiveIntensity = o.base; return true; };
      e.yaw = Math.PI * .8; e.obj.rotation.y = e.yaw;
      if (clip) e.av.play(clip, 0);
      const c = g.camera, cp = new Vc(x + Math.sin(e.yaw) * dist, y + h + .3, z + Math.cos(e.yaw) * dist), look = new Vc(x, y + h * .75, z);
      g.stationId = 'test'; c.position.copy(cp); c.lookAt(look);
      g.camFocus = { pos: cp, look, orbit: false, q: c.quaternion.clone(), p0: c.position.clone(), q0: c.quaternion.clone(), fov0: 55, t0: 0 };
    }, [type, base.x, base.z, dist, h, clip]);
    await wait(3500); await shot(name);
  };
  await portrait('host', 'h01_host', 3.4, 1.3);
  await portrait('host', 'h02_host_attack', 3.6, 1.3, 'Attack');
  await portrait('mite', 'h03_mite', 1.6, .35);
  await portrait('bladder', 'h04_bladder', 4.2, 1.2);
  await portrait('amalgam', 'h05_amalgam', 6, 1.9);
  for (const a of ['stalker', 'hulk', 'mutant', 'swimmer', 'elite']) await portrait(a, 'h06_alien_' + a, a === 'hulk' || a === 'elite' ? 5 : 3.8, a === 'hulk' ? 1.7 : 1.4);
  await ev(() => { const g = window.__game; g.stationId = null; g.camFocus = null; g.enemies.clear(); });
  await live();
  // ---- swarm: mites skitter in, leap and burst on the player
  const swarm = await ev(async ([bx, bz]) => {
    const g = window.__game, w = g.world, Vc = g.player.pos.constructor;
    if (g.save.settings.view !== 'third') g.toggleView();
    window.__dmg = 0;
    const ms = [];
    for (let k = 0; k < 7; k++) { const x = bx + 12 + Math.random() * 3, z = bz - 4 + k * 1.3; ms.push(g.enemies.spawn('mite', new Vc(x, w.collision.ground(x, z), z), 8)); }
    ms.forEach(m => m.alert());
    await new Promise(r => setTimeout(r, 2200));
    return { leapt: ms.filter(m => m.leapCd > 0 || m.leaping || !m.alive).length };
  }, [base.x, base.z]);
  await shot('h07_swarm');
  await wait(4000);
  const swarm2 = await ev(() => ({ dmg: Math.round(window.__dmg), mitesLeft: window.__game.enemies.list.filter(e => e.type === 'mite' && e.alive).length }));
  console.log('swarm', JSON.stringify({ ...swarm, ...swarm2 }));
  // ---- bladder: waddles in, swells and ruptures, the brood spills out
  const bladder = await ev(async ([bx, bz]) => {
    const g = window.__game, w = g.world, Vc = g.player.pos.constructor;
    g.enemies.clear(); window.__dmg = 0;
    const x = bx + 7, z = bz; const bl = g.enemies.spawn('bladder', new Vc(x, w.collision.ground(x, z), z), 8); bl.alert();
    const t0 = performance.now();
    while (bl.alive && performance.now() - t0 < 25000) await new Promise(r => setTimeout(r, 250));
    await new Promise(r => setTimeout(r, 300));
    return { burst: !bl.alive, seconds: Math.round((performance.now() - t0) / 100) / 10, brood: g.enemies.list.filter(e => e.type === 'mite' && e.alive).length, dmg: Math.round(window.__dmg) };
  }, [base.x, base.z]);
  await shot('h08_bladder_burst');
  console.log('bladder', JSON.stringify(bladder));
  // shooting a bladder from range also ruptures it
  const shotBladder = await ev(([bx, bz]) => {
    const g = window.__game, w = g.world, Vc = g.player.pos.constructor;
    g.enemies.clear();
    const x = bx + 20, z = bz + 5; const bl = g.enemies.spawn('bladder', new Vc(x, w.collision.ground(x, z), z), 8);
    bl.takeDamage(9999, false, bl.center(new Vc()), new Vc(1, 0, 0), 'player');
    return { burst: !bl.alive, brood: g.enemies.list.filter(e => e.type === 'mite' && e.alive).length };
  }, [base.x, base.z]);
  console.log('bladder shot', JSON.stringify(shotBladder));
  // ---- reanimation: a dead raider, a mite finds it, the corpse rises as a host
  const rean = await ev(async ([bx, bz]) => {
    const g = window.__game, w = g.world, Vc = g.player.pos.constructor;
    g.enemies.clear();
    const px = bx - 40; g.player.pos.set(px, w.collision.ground(px, bz), bz); g.player.avatar.root.position.copy(g.player.pos);
    const tx = bx + 10, tz = bz + 2;
    const tr = g.enemies.spawn('trooper', new Vc(tx, w.collision.ground(tx, tz), tz), 8);
    tr.takeDamage(9999, false, tr.center(new Vc()), new Vc(1, 0, 0), 'rival');
    const mx = tx + 5, mz = tz + 3; const m = g.enemies.spawn('mite', new Vc(mx, w.collision.ground(mx, mz), mz), 8);
    const t0 = performance.now(); let host = null;
    while (!host && performance.now() - t0 < 20000) { await new Promise(r => setTimeout(r, 250)); host = g.enemies.list.find(e => e.type === 'host' && e.alive); }
    return { risen: !!host, seconds: Math.round((performance.now() - t0) / 100) / 10, armed: !!(host && host.armed), corpseGone: !g.enemies.list.includes(tr), mite: m.alive, at: host && [Math.round(host.pos.x), Math.round(host.pos.z)] };
  }, [base.x, base.z]);
  console.log('reanimate', JSON.stringify(rean));
  if (rean.at) {
    await ev(([x, z]) => { const g = window.__game, w = g.world; g.player.pos.set(x - 5, w.collision.ground(x - 5, z), z); g.player.avatar.root.position.copy(g.player.pos); g.player.yaw = -Math.PI / 2; }, rean.at);
    await wait(1500); await shot('h09_risen_host');
  }
  // ---- faction war: the Writhe against raiders and aliens, far from the player (no faction-war district needed)
  const war = await ev(async ([bx, bz]) => {
    const g = window.__game, w = g.world, Vc = g.player.pos.constructor;
    g.enemies.clear();
    g.player.pos.set(bx - 80, w.collision.ground(bx - 80, bz), bz); g.player.avatar.root.position.copy(g.player.pos);
    const at = (dx, dz) => new Vc(bx + dx, w.collision.ground(bx + dx, bz + dz), bz + dz);
    const h = g.enemies.spawn('host', at(0, 0), 8), tr = g.enemies.spawn('trooper', at(12, 0), 8);
    const am = g.enemies.spawn('amalgam', at(0, 30), 8), st = g.enemies.spawn('stalker', at(10, 30), 8);
    const hp0 = [h.hp, tr.hp, am.hp, st.hp];
    await new Promise(r => setTimeout(r, 9000));
    return { factionWar: !!w.factionWar, hostHurt: h.hp < hp0[0] || !h.alive, trooperHurt: tr.hp < hp0[1] || !tr.alive, amalgamHurt: am.hp < hp0[2] || !am.alive, stalkerHurt: st.hp < hp0[3] || !st.alive };
  }, [base.x, base.z]);
  console.log('war', JSON.stringify(war));
  await ev(([bx, bz]) => { const g = window.__game, w = g.world; g.player.pos.set(bx - 12, w.collision.ground(bx - 12, bz), bz + 15); g.player.avatar.root.position.copy(g.player.pos); }, [base.x, base.z]);
  await wait(1500); await shot('h10_war');
  console.log('fps', await ev(() => Math.round(window.__game.fps)));
  const ok = swarm2.dmg > 0 && bladder.burst && bladder.brood > 0 && shotBladder.brood > 0 && rean.risen && (war.hostHurt || war.trooperHurt) && (war.amalgamHurt || war.stalkerHurt);
  console.log('checks', ok ? 'PASS' : 'FAIL', 'page errors:', errs.length);
  await b.close();
  process.exit(errs.length || !ok ? 1 : 0);
})().catch(e => { console.error('HORROR TEST FAILED', e); process.exit(2); });
