// Weapons check: every new kinetic and horror gun is given to the player, equipped, shown in first person (hip and
// aimed through its sight), then fired at a spawned enemy. Logs damage, rounds/goo in flight, slime stains and acid
// damage-over-time; also mounts each optic on the carbine. 0 page errors expected.
// Usage: python3 -m http.server 8765 &  then  NODE_PATH=$(npm root -g) node tools/test/weapons.js   (screenshots in test-out/)
// Env: ARCHS (comma list), WORLD (default ares)
const { chromium } = require('playwright');
const fs = require('fs');
const BASE = process.env.BASE || 'http://localhost:8765';
const OUT = process.env.OUT || 'test-out';
const ARCHS = (process.env.ARCHS || 'rifle,carbine,dmr,ksmg,bolt,pistol,revolver,pump,spitter,bile,brood').split(',');
fs.mkdirSync(OUT, { recursive: true });

(async () => {
  const b = await chromium.launch({ args: ['--ignore-gpu-blocklist', '--enable-unsafe-swiftshader', '--use-angle=swiftshader'] });
  const p = await b.newPage({ viewport: { width: +(process.env.VW || 960), height: +(process.env.VH || 540) } });
  const errs = [];
  p.on('pageerror', e => { errs.push(e.message); console.log('PAGE ERROR', e.message.slice(0, 400)); });
  p.on('crash', () => console.log('PAGE CRASHED'));
  p.on('console', m => { if (process.env.VERBOSE && m.type() === 'log') console.log('LOG', m.text().slice(0, 200)); if (m.type() === 'error') { errs.push(m.text()); console.log('CONSOLE ERROR', m.text().slice(0, 400)); } });
  await p.addInitScript(() => { localStorage.clear(); window.__TEST_QUALITY = 'low'; });
  const ev = (fn, arg) => p.evaluate(fn, arg);
  const wait = ms => p.waitForTimeout(ms);
  const shot = async n => { await p.screenshot({ path: `${OUT}/${n}.jpg`, type: 'jpeg', quality: 82, timeout: 300000 }); console.log('shot', n); };
  const waitPlay = async () => { await p.waitForFunction(() => window.__game && window.__game.state === 'play', null, { timeout: 900000, polling: 1000 });
    await ev(() => { const g = window.__game; g.paused = false; g.menus.hidePause(); g.input.locked = true; g.input.enabled = true; }); };
  // models other people are still building: stand in the base model so the run is not blocked by a missing file
  await p.route(/assets\/models\/[^/]+\.glb$/, (route, req) => {
    const f = 'assets/models/' + req.url().split('/').pop();
    // this run only visits the ship and a frontier planet: big city / other-body models are swapped for a small one to
    // keep the headless renderer's memory down (STUB=0 loads everything)
    const heavy = process.env.STUB !== '0' && /\/(vanthos|city_buildings|rural|civ_male|player_male|player_female_npc|player_male_npc)\.glb$/.test(f);
    if (fs.existsSync(f) && !heavy) return route.continue();
    const alt = 'assets/models/npc_vendor.glb';   // small skinned stand-in
    console.log('stand-in for', f, '->', alt);
    return route.fulfill({ status: 200, contentType: 'model/gltf-binary', body: fs.readFileSync(alt) });
  });
  await p.goto(BASE + '/index.html');
  await p.waitForFunction(() => window.__game && window.__game.state === 'title', null, { timeout: 300000, polling: 500 });
  await ev(() => { window.__game.save.settings.dynamicRes = false; });
  await p.click('[data-act="title-play"]');
  await waitPlay();
  const WORLD = process.env.WORLD || 'ship';   // the ship is the lightest world (headless renderers get OOM-killed under load)
  if (WORLD !== 'ship') { await ev(w => window.__game.travel(w), WORLD); await waitPlay(); }
  await wait(2500);
  // keep the run deterministic: no wandering hostiles, the player cannot die
  await ev(() => {
    const g = window.__game, pl = g.player; g.enemies.clear(); if (g.save.settings.view !== 'first') g.toggleView();
    if (g.world.constructor.name !== 'ShipWorld') {
      // turn away from the dropship and walk out into the open
      pl.camYaw += Math.PI; const fx = -Math.sin(pl.camYaw), fz = -Math.cos(pl.camYaw);
      pl.pos.x += fx * 25; pl.pos.z += fz * 25; pl.pos.y = g.world.collision.ground(pl.pos.x, pl.pos.z) + .1; pl.avatar.root.position.copy(pl.pos);
    }
  });

  const results = {};
  for (const arch of ARCHS) {
    const info = await ev(async arch => {
      const g = window.__game, st = await import('/src/game/state.js'), data = await import('/src/game/data.js');
      const w = st.makeWeapon(arch, 3, 30); g.addWeapon(w);
      const A = data.ARCHETYPES[arch];
      g.save.equipped[A.slot] = w.uid; g.weapons.slot = A.slot; g.weapons.ammo[w.uid] = null; delete g.weapons.ammo[w.uid];
      g.player.armed = true; g.weapons.refreshModel(); g.weapons.swap = 0; g.weapons.reloading = 0;
      g.enemies.clear(); g.paused = false; g.input.locked = true; g.input.enabled = true;
      const vm = g.viewmodel;
      return { uid: w.uid, name: w.name, label: data.archLabel(arch), sight: data.weaponSight(w), scoped: !!vm.scoped, model: A.model,
        meshes: (() => { let n = 0, mats = new Set(); vm.gun && vm.gun.traverse(o => { if (o.isMesh && o.visible) { n++; mats.add(o.material.name); } }); return { n, mats: [...mats] }; })() };
    }, arch);
    await wait(3500);
    await shot(`w_${arch}_hip`);
    // aim down sights
    await ev(() => { window.__game.input.rmb = true; window.__game.player.armed = true; });
    await wait(3000);
    await shot(`w_${arch}_ads`);
    await ev(() => { window.__game.input.rmb = false; });
    // spawn a target ahead and fire a few times at its chest
    const fire = await ev(async arch => {
      const g = window.__game, pl = g.player, V = pl.pos.constructor;
      const data = await import('/src/game/data.js'), st = await import('/src/game/state.js');
      const ship = g.world.constructor.name === 'ShipWorld';
      let dist = ship ? (arch === 'bile' || arch === 'pump' ? 5 : 9) : arch === 'bolt' ? 40 : arch === 'bile' || arch === 'pump' ? 8 : 16;
      pl.armed = true;
      // face the most open direction so the target is not behind a console
      let yaw = pl.camYaw, free = 0;
      for (let k = 0; k < 16; k++) {
        const y = pl.camYaw + k * Math.PI / 8, d = new V(-Math.sin(y), 0, -Math.cos(y)), o = pl.pos.clone(); o.y += 1.2;
        const h = g.world.collision.raycast(o, d, 60), f = h ? h.dist : 60;
        if (f > free + .5) { free = f; yaw = y; }
      }
      const want = dist; dist = Math.max(3, Math.min(want, free - 2.5));
      const fx = -Math.sin(yaw), fz = -Math.cos(yaw);
      const at = new V(pl.pos.x + fx * dist, 0, pl.pos.z + fz * dist); at.y = g.world.collision.ground(at.x, at.z);
      const e = g.enemies.spawn('brute', at, 30); e.state = 'idle'; e.fireT = 999;
      await new Promise(r => setTimeout(r, 300));
      const hp0 = e.hp;
      const w = g.weapons.equipped(), A = data.ARCHETYPES[w.arch], S = st.weaponStats(w), a = g.weapons.ammoOf(w);
      let maxRounds = 0, maxGoo = 0;
      console.log('target spawned', hp0);
      for (let k = 0; k < 4; k++) {
        console.log('fire', k);
        // aim at the target's centre from the camera
        const c = e.center(new V()), cam = g.camera.position;
        const d = c.clone().sub(cam); pl.camYaw = Math.atan2(-d.x, -d.z); pl.camPitch = Math.atan2(d.y, Math.hypot(d.x, d.z));
        pl.health = pl.maxHealth; pl.shield = pl.maxShield || pl.shield;
        a.mag = Math.max(a.mag, 2); g.weapons.fire(w, A, S, a);
        maxRounds = Math.max(maxRounds, g.weapons.rounds.length); maxGoo = Math.max(maxGoo, g.weapons.goo.length);
        await new Promise(r => setTimeout(r, 450));
        maxRounds = Math.max(maxRounds, g.weapons.rounds.length); maxGoo = Math.max(maxGoo, g.weapons.goo.length);
      }
      await new Promise(r => setTimeout(r, 2500));
      const fxo = g.fx, stains = fxo.slimeLife ? Array.from(fxo.slimeLife).filter(v => v > 0).length : 0;
      return { dist, hp0: Math.round(hp0), hp1: Math.round(e.hp), alive: e.alive, damage: Math.round(hp0 - e.hp), maxRounds, maxGoo,
        stains, afflicted: g.weapons.afflicted.size, drop: A.grav ? 'gravity' : 'straight', vel: A.vel };
    }, arch);
    await shot(`w_${arch}_fire`);
    results[arch] = { ...info, ...fire };
    console.log(arch, JSON.stringify(results[arch]));
    await ev(() => window.__game.enemies.clear());
  }

  // bullet drop: a level round fired high above the world, kinetic (gravity) vs energy (straight)
  const drop = await ev(async () => {
    const g = window.__game, V = g.player.pos.constructor, data = await import('/src/game/data.js'), st = await import('/src/game/state.js');
    const out = {};
    for (const arch of ['bolt', 'auto']) {
      const w = st.makeWeapon(arch, 1, 10), A = data.ARCHETYPES[arch], S = st.weaponStats(w);
      const o = g.player.pos.clone().add(new V(0, 400, 0)), d = new V(1, 0, 0);
      g.weapons.spawnRound(o, o, d, S, w, A, { hit: false });
      const r = g.weapons.rounds[g.weapons.rounds.length - 1], t0 = performance.now();
      await new Promise(res => setTimeout(res, 400));
      const t = (performance.now() - t0) / 1000;
      out[arch] = { vel: A.vel, dist: Math.round(r.dist), dropM: +(o.y - r.p.y).toFixed(3), expectedAtDist: +(.5 * 9.81 * (r.dist / A.vel) ** 2 * (A.grav ?? 1)).toFixed(3) };
    }
    return out;
  });
  console.log('drop', JSON.stringify(drop));

  // optics on the carbine: each sight mounts and changes ADS zoom / scope overlay
  const optics = [];
  for (const sight of ['default', 'reflex', 'holo', 'x2', 'x4', 'x8']) {
    const o = await ev(async sight => {
      const g = window.__game, st = await import('/src/game/state.js');
      let w = g.save.inventory.find(x => x.arch === 'carbine');
      w.sight = sight; g.save.equipped[0] = w.uid; g.weapons.slot = 0; g.weapons.refreshModel();
      const vm = g.viewmodel, att = vm.gun.getObjectByName('att_' + sight);
      return { sight, mounted: !!att, scoped: vm.scoped, zoom: g.weapons.zoom(), eye: vm.sight.toArray().map(v => +v.toFixed(3)) };
    }, sight);
    optics.push(o); console.log('optic', JSON.stringify(o));
    if (sight === 'holo' || sight === 'x4') {
      await ev(() => { window.__game.input.rmb = true; }); await wait(1600); await shot(`w_optic_${sight}_ads`);
      await ev(() => { window.__game.input.rmb = false; }); await wait(600);
    }
  }
  await ev(() => { const g = window.__game; g.input.rmb = false; g.player.armed = true; if (g.save.settings.view !== 'third') g.toggleView(); });
  await wait(1500); await shot('w_third_person');
  const fps = await ev(() => Math.round(window.__game.fps || 0));
  console.log('fps', fps);
  console.log('page errors', errs.length);
  fs.writeFileSync(`${OUT}/weapons.json`, JSON.stringify({ results, drop, optics, errs }, null, 1));
  await b.close();
})();
