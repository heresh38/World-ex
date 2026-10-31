// Vehicles check on Earth: fixed traffic population, gravity (drop + drive off a slope, lands on the ground),
// first-person car interior, hover board summon + ride, shooting a traffic driver (car rolls to a stop), bullet
// damage on a car, and car collisions with the player and pedestrians.
// Usage: python3 -m http.server 8765 &  then  NODE_PATH=$(npm root -g) node tools/test/vehicles.js  (shots in test-out/vehicles)
const { chromium } = require('playwright');
const fs = require('fs');
const BASE = process.env.BASE || 'http://localhost:8765';
const OUT = process.env.OUT || 'test-out/vehicles';
fs.mkdirSync(OUT, { recursive: true });

(async () => {
  const b = await chromium.launch({ args: ['--ignore-gpu-blocklist', '--enable-unsafe-swiftshader', '--use-angle=swiftshader'] });
  const p = await b.newPage({ viewport: { width: +(process.env.VW || 1100), height: +(process.env.VH || 620) } });
  const errs = [];
  p.on('pageerror', e => { errs.push(e.message); console.log('PAGE ERROR', e.message.slice(0, 300), (e.stack || '').split('\n').slice(0, 4).join(' | ')); });
  p.on('console', m => { if (m.type() === 'error') { errs.push(m.text()); console.log('CONSOLE ERROR', m.text().slice(0, 300)); } });
  await p.addInitScript(() => { localStorage.clear(); });
  // crowd LOD bodies may not be built yet in a fresh checkout: stand in the full player bodies for this test only
  for (const sex of ['female', 'male']) {
    if (!fs.existsSync(`assets/models/player_${sex}_npc.glb`)) await p.route(`**/player_${sex}_npc.glb`, r => r.fulfill({ path: `assets/models/player_${sex}.glb`, contentType: 'model/gltf-binary' }));
  }
  const ev = (fn, a) => p.evaluate(fn, a);
  const wait = ms => p.waitForTimeout(ms);
  const shot = async n => { await p.screenshot({ path: `${OUT}/${n}.jpg`, type: 'jpeg', quality: 82, timeout: 600000 }); console.log('shot', n); };
  const waitPlay = async () => {
    await p.waitForFunction(() => window.__game && window.__game.state === 'play', null, { timeout: 1200000, polling: 1000 });
    await ev(() => { const g = window.__game; g.paused = false; g.menus.hidePause(); g.input.locked = true; g.input.enabled = true; });
  };
  const keep = () => ev(() => { const g = window.__game; g.paused = false; g.menus.hidePause(); g.input.locked = true; g.input.enabled = true; });
  // run game frames for a while (keeps the game unpaused while waiting)
  const run = async ms => { const t0 = Date.now(); while (Date.now() - t0 < ms) { await keep(); await wait(Math.min(1000, ms)); } };
  const results = {};
  const check = (name, ok, info) => { results[name] = ok; console.log(ok ? 'PASS' : 'FAIL', name, info !== undefined ? JSON.stringify(info) : ''); };

  await p.goto(BASE + '/index.html');
  await p.waitForFunction(() => window.__game && window.__game.state === 'title', null, { timeout: 600000, polling: 500 });
  await ev(q => { const g = window.__game; g.save.settings.quality = q; g.save.settings.dynamicRes = false; g.renderer.settings = g.save.settings; g.renderer.applyQuality(); g.startGame(true); }, process.env.QUALITY || 'low');
  await waitPlay();
  const t0 = Date.now();
  await ev(() => window.__game.travel('earth'));
  await waitPlay();
  console.log('earth load seconds', Math.round((Date.now() - t0) / 1000));
  await run(3000);
  const pop = await ev(() => { const g = window.__game, w = g.world; return { traffic: w.traffic.cars.length, drivers: w.traffic.cars.filter(t => t.car.driver && t.car.driver.alive).length, cars: g.vehicles.cars.length, parked: g.vehicles.cars.filter(c => c.parked).length, save: g.save.car }; });
  console.log('population', JSON.stringify(pop));
  check('fixed traffic population with drivers', pop.traffic >= 80 && pop.drivers === pop.traffic, pop);
  const n0 = pop.traffic;

  // ---- gravity: a car dropped from 6 m lands and settles on the ground
  const drop = await ev(async () => {
    const g = window.__game, V = g.player.pos.constructor;
    const x = -150, z = 92;
    const c = g.vehicles.spawn('car_sedan', '#2a4f7a', new V(x, g.world.collision.ground(x, z) + 6, z), 0);
    c.pos.y = g.world.collision.ground(x, z) + 6; c.wake();
    let minAir = 99, maxH = 0;
    for (let i = 0; i < 40; i++) { await new Promise(r => setTimeout(r, 100)); const h = c.pos.y - g.world.collision.support(c.pos.x, c.pos.z, c.pos.y + 1); maxH = Math.max(maxH, h); }
    const gy = g.world.collision.support(c.pos.x, c.pos.z, c.pos.y + 1);
    window.__dropCar = c;
    return { y: +c.pos.y.toFixed(2), ground: +gy.toFixed(2), contacts: c.contacts, pitch: +c.pitch.toFixed(3), roll: +c.roll.toFixed(3) };
  });
  check('dropped car lands on the ground', Math.abs(drop.y - drop.ground) < .2 && drop.contacts === 4, drop);

  // ---- drive off a slope: find the steepest drop in the countryside and drive over it
  const slope = await ev(async () => {
    const g = window.__game, w = g.world, m = w.map, V = g.player.pos.constructor;
    let best = null;
    for (let x = 560; x < 1100; x += 12) for (let z = -1000; z < 1000; z += 12) {
      const h0 = m.height(x, z); if (h0 < 2) continue;
      for (const [dx, dz] of [[1, 0], [-1, 0], [0, 1], [0, -1]]) {
        const h1 = m.height(x + dx * 25, z + dz * 25), h2 = m.height(x + dx * 8, z + dz * 8);
        const drop = h0 - h1; if (h2 > h0 + .5) continue;
        if (!best || drop > best.drop) best = { x, z, dx, dz, drop };
      }
    }
    const yaw = Math.atan2(best.dx, best.dz);
    const sx = best.x - best.dx * 18, sz = best.z - best.dz * 18;
    const c = g.vehicles.spawn('car_suv', '#a3121f', new V(sx, m.height(sx, sz), sz), yaw);
    g.player.pos.set(sx + 3, m.height(sx + 3, sz), sz); g.player.avatar.root.position.copy(g.player.pos);
    g.vehicles.enter(c);
    g.input.down.add('KeyW');
    let air = 0, maxAirH = 0;
    const hist = [];
    for (let i = 0; i < 70; i++) {
      await new Promise(r => setTimeout(r, 100));
      g.paused = false; g.input.locked = true; g.input.enabled = true;
      const gy = g.world.collision.support(c.pos.x, c.pos.z, c.pos.y + 1), h = c.pos.y - gy;
      if (c.contacts === 0) air++;
      maxAirH = Math.max(maxAirH, h);
      if (i % 10 === 0) hist.push([+c.pos.y.toFixed(1), +gy.toFixed(1), c.contacts, +c.speed.toFixed(1)]);
      if (i === 45) g.input.down.delete('KeyW');
    }
    g.input.down.delete('KeyW');
    const gy = g.world.collision.support(c.pos.x, c.pos.z, c.pos.y + 1);
    return { drop: +best.drop.toFixed(1), airFrames: air, maxAirH: +maxAirH.toFixed(2), y: +c.pos.y.toFixed(2), ground: +gy.toFixed(2), contacts: c.contacts, hist };
  });
  check('car follows a hill down and ends on the ground', Math.abs(slope.y - slope.ground) < .3 && slope.contacts >= 3, slope);
  await ev(() => { const g = window.__game; g.save.settings.view = 'third'; g.setAvatarLayer(); g.player.camPitch = -.2; });
  await run(2500); await shot('01_suv_hill_third');

  // ---- first person interior (parked sedan in the city)
  const fp = await ev(async () => {
    const g = window.__game, V = g.player.pos.constructor;
    if (g.vehicles.current) g.vehicles.exit();
    const c = window.__dropCar;
    c.yaw = Math.PI / 2; c.pos.y += .3; c.wake();
    g.player.pos.set(c.pos.x, c.pos.y, c.pos.z + 3); g.player.avatar.root.position.copy(g.player.pos);
    g.vehicles.enter(c);
    g.save.settings.view = 'first'; g.setAvatarLayer();
    g.player.camYaw = c.yaw + Math.PI; g.player.camPitch = -.15;
    await new Promise(r => setTimeout(r, 1500));
    return { fp: g.carFirstPerson(), cam: g.camera.position.toArray().map(v => +v.toFixed(2)), car: c.pos.toArray().map(v => +v.toFixed(2)), layer: g._fpLayer };
  });
  check('first-person car camera inside the cabin', fp.fp && Math.abs(fp.cam[1] - fp.car[1] - 1.15) < .35, fp);
  await run(3000); await shot('02_interior_forward');
  await ev(() => { const g = window.__game, c = g.vehicles.current; g.player.camYaw = c.yaw + Math.PI + 1.2; g.player.camPitch = -.25; });
  await run(2500); await shot('03_interior_left');
  await ev(() => { const g = window.__game, c = g.vehicles.current; g.player.camYaw = c.yaw + Math.PI - .9; g.player.camPitch = -.45; });
  await run(2500); await shot('04_interior_console');
  // drive a little in first person: needles + steering wheel move
  const drive = await ev(async () => {
    const g = window.__game, c = g.vehicles.current;
    g.player.camYaw = c.yaw + Math.PI; g.player.camPitch = -.1;
    g.input.down.add('KeyW'); g.input.down.add('KeyA');
    await new Promise(r => setTimeout(r, 2500));
    const st = c.steerWheel ? c.steerWheel.quaternion.angleTo(c.steerWheel.userData.q0) : 0;
    const nd = c.needleS ? c.needleS.quaternion.angleTo(c.needleS.userData.q0) : 0;
    g.input.down.delete('KeyA');
    return { speed: +c.speed.toFixed(1), steerWheelRot: +st.toFixed(2), needleRot: +nd.toFixed(2) };
  });
  check('steering wheel and speedometer animate', drive.steerWheelRot > .3 && drive.needleRot > .3, drive);
  await shot('05_interior_driving');
  await ev(() => { const g = window.__game; g.input.down.delete('KeyW'); g.input.down.add('Space'); });
  await run(1500);
  await ev(() => { const g = window.__game; g.input.down.delete('Space'); g.vehicles.exit(); });

  // ---- hover board: V summons it under the player, ride it
  const board = await ev(async () => {
    const g = window.__game;
    g.player.pos.set(-150, 0, 60); g.player.avatar.root.position.copy(g.player.pos); g.player.yaw = Math.PI / 2;
    g.save.settings.view = 'third'; g.setAvatarLayer();
    g.vehicles.summon();
    const b = g.vehicles.current;
    if (!b || !b.board) return 'no board';
    g.input.down.add('KeyW');
    let jumpH = 0;
    for (let i = 0; i < 30; i++) {
      await new Promise(r => setTimeout(r, 100)); g.paused = false; g.input.locked = true;
      if (i === 15) g.input.pressed = (k => c => c === 'Space' || k(c))(g.input.pressed.bind(g.input));
      if (i === 16) delete g.input.pressed;
      jumpH = Math.max(jumpH, b.pos.y - g.world.collision.ground(b.pos.x, b.pos.z));
    }
    const h = b.pos.y - g.world.collision.support(b.pos.x, b.pos.z, b.pos.y + 1);
    return { model: b.model, speed: +b.speed.toFixed(1), hover: +h.toFixed(2), jumpH: +jumpH.toFixed(2), mode: g.player.mode, save: g.save.car.model };
  });
  check('hover board summoned and ridden', board.mode === 'car' && board.speed > 5 && board.hover > .15 && board.hover < 1.2, board);
  await shot('06_board_third');
  await ev(() => { const g = window.__game; g.save.settings.view = 'first'; g.setAvatarLayer(); g.player.camPitch = -.5; });
  await run(2500); await shot('07_board_first');
  await ev(() => { const g = window.__game; g.input.down.delete('KeyW'); g.save.settings.view = 'third'; g.setAvatarLayer(); });
  await run(1500);
  await ev(() => { const g = window.__game; if (g.vehicles.current) g.vehicles.exit(); });

  // ---- shoot a traffic driver through the windscreen: the car rolls to a stop
  const kill = await ev(async () => {
    const g = window.__game, w = g.world, V = g.player.pos.constructor;
    // a moving city car on a straight
    const cand = w.traffic.cars.filter(t => t.mode === 'lane' && t.lane.city && t.s > 150 && t.s < t.lane.total - 250);
    const t = cand[0]; if (!t) return 'no car';
    const c = t.car; t.v = t.want = 12; t.stopT = 0;
    // stand beside the road ahead of the car, a few metres off its lane
    const f = new V(Math.sin(c.yaw), 0, Math.cos(c.yaw)), side = new V(Math.cos(c.yaw), 0, -Math.sin(c.yaw));
    const pp = c.pos.clone().addScaledVector(f, 14).addScaledVector(side, 6);
    g.player.pos.set(pp.x, g.world.collision.support(pp.x, pp.z, 5), pp.z); g.player.avatar.root.position.copy(g.player.pos);
    t.ignoreT = 999;
    await new Promise(r => setTimeout(r, 400));
    c.root.updateMatrixWorld(true);
    const d = c.driver; d.av.root.updateMatrixWorld(true);
    const head = new V(); d.av.head.getWorldPosition(head); head.y += .07;
    const eye = g.player.pos.clone(); eye.y += 1.6;
    const dir = head.clone().sub(eye).normalize();
    const res = g.combat.trace(eye, dir, 80, 'player');
    const hitDriver = res.target === d;
    const speed0 = c.speed;
    if (res.target) res.target.takeDamage(500, true, res.point, dir, 'player');
    await new Promise(r => setTimeout(r, 300));
    const sp = [];
    for (let i = 0; i < 16; i++) { await new Promise(r => setTimeout(r, 500)); g.paused = false; g.input.locked = true; sp.push(+c.speed.toFixed(1)); }
    window.__deadCar = c;
    return { hitDriver, target: res.target ? res.target.T.name : null, alive: d.alive, speed0: +speed0.toFixed(1), speeds: sp, mode: t.mode, holes: c.holes.length, horn: c.hornT > 0 || sp.length > 0 };
  });
  check('driver headshot through glass stops the car', kill.hitDriver && !kill.alive && kill.mode === 'dyn' && kill.speeds[kill.speeds.length - 1] < .6, kill);
  await ev(() => { const g = window.__game, c = window.__deadCar; const V = c.pos.constructor;
    const side = new V(Math.cos(c.yaw), 0, -Math.sin(c.yaw));
    g.player.pos.copy(c.pos).addScaledVector(side, 4.5); g.player.pos.y = g.world.collision.support(g.player.pos.x, g.player.pos.z, c.pos.y + 2); g.player.avatar.root.position.copy(g.player.pos);
    g.player.camYaw = Math.atan2(side.x, side.z); g.player.camPitch = -.12; g.save.settings.view = 'first'; g.setAvatarLayer(); });
  await run(2500); await shot('08_dead_driver');

  // ---- bullet damage on the body: holes, then smoke
  const dmg = await ev(async () => {
    const g = window.__game, c = window.__deadCar, V = c.pos.constructor;
    const eye = g.camera.position.clone();
    let hits = 0;
    for (let i = 0; i < 18; i++) {
      const tgt = c.pos.clone().add(new V((Math.random() - .5) * 2, .6 + Math.random() * .3, (Math.random() - .5) * 2));
      const dir = tgt.sub(eye).normalize();
      const res = g.combat.trace(eye, dir, 60, 'player');
      if (res.target === c) { c.takeDamage(30, false, res.point, dir, 'player'); hits++; }
    }
    c.hp = c.S.hp * .3;
    await new Promise(r => setTimeout(r, 2500));
    return { hits, holes: c.holes.length, hp: Math.round(c.hp), alive: c.alive };
  });
  check('bullets leave holes in the car', dmg.hits > 5 && dmg.holes > 3, dmg);
  await run(1500); await shot('09_car_damage_smoke');

  // ---- collisions: player pushed out of a parked car, knocked by a moving car
  const col = await ev(async () => {
    const g = window.__game, V = g.player.pos.constructor;
    g.save.settings.view = 'third'; g.setAvatarLayer();
    const x = -260, z = 92;
    const c = g.vehicles.spawn('car_van', '#e8e6e2', new V(x, g.world.collision.ground(x, z), z), 0);
    await new Promise(r => setTimeout(r, 300));
    g.player.pos.set(x + .2, c.pos.y, z + .5); g.player.vel.set(0, 0, 0); g.player.avatar.root.position.copy(g.player.pos);
    await new Promise(r => setTimeout(r, 400));
    const lx = g.player.pos.x - x, lz = g.player.pos.z - z;
    const outside = Math.abs(lx) > c.hw || Math.abs(lz - c.cz) > c.hl;
    // walk into it: stays outside
    g.player.pos.set(x + 2.5, c.pos.y, z); g.player.camYaw = Math.PI / 2; g.input.down.add('KeyW');
    await new Promise(r => setTimeout(r, 1500)); g.input.down.delete('KeyW');
    const walkX = g.player.pos.x - x;
    // a car rolling into the player at 10 m/s
    g.player.godMode = false; g.player.health = 100; g.player.shield = 0; g.player.sinceHit = 0;
    const hp0 = g.player.health;
    const m = g.vehicles.spawn('car_hatch', '#a3121f', new V(x + 14, g.world.collision.ground(x + 14, z - 12), z - 12), 0);
    g.player.pos.set(x + 14, g.world.collision.ground(x + 14, z - 4), z - 4);
    m.wake(); m.vel.set(0, 0, 11);
    await new Promise(r => setTimeout(r, 1500));
    return { outside, walkX: +walkX.toFixed(2), halfW: +c.hw.toFixed(2), hp0, hp: Math.round(g.player.health), shield: Math.round(g.player.shield) };
  });
  check('car pushes the player out', col.outside && col.walkX > col.halfW, col);
  check('moving car knocks the player', col.hp < col.hp0 || col.shield < 0, col);
  await g_restoreHealth();
  async function g_restoreHealth() { await ev(() => { const g = window.__game; g.player.health = g.player.maxHealth; }); }

  // ---- pedestrians: a fast car runs one over, a slow one pushes
  const ped = await ev(async () => {
    const g = window.__game, V = g.player.pos.constructor, pop = g.world.population;
    const q = pop.peds.find(q => q.alive && q.pos.distanceTo(g.player.pos) < 200) || pop.peds.find(q => q.alive);
    g.player.pos.copy(q.pos).add(new V(8, 0, 8)); g.player.avatar.root.position.copy(g.player.pos);
    const yaw = 0;
    const c = g.vehicles.spawn('car_sedan', '#1a1b1e', new V(q.pos.x, q.pos.y, q.pos.z - 9), yaw);
    q.state = 'idle'; q.idleT = 99;
    c.wake(); c.vel.set(0, 0, 13); c.parked = false;
    await new Promise(r => setTimeout(r, 2000));
    return { pedAlive: q.alive, carSpeed: +c.speed.toFixed(1) };
  });
  check('fast car runs a pedestrian over', !ped.pedAlive, ped);

  const fin = await ev(() => { const g = window.__game, w = g.world; return { traffic: w.traffic.cars.length, cars: g.vehicles.cars.length, fps: Math.round(g.fps) }; });
  check('traffic never despawns', fin.traffic >= n0 - 2, { before: n0, after: fin.traffic });
  console.log('final', JSON.stringify(fin));
  await ev(() => { const g = window.__game; g.player.pos.set(-150, 0, 60); g.player.avatar.root.position.copy(g.player.pos); g.player.camYaw = Math.PI * .75; g.player.camPitch = .02; g.save.settings.view = 'third'; g.setAvatarLayer(); });
  await run(4000); await shot('10_street_traffic');
  console.log('page errors:', errs.length);
  const failed = Object.entries(results).filter(([, v]) => !v).map(([k]) => k);
  console.log('failed:', failed.length ? failed.join(', ') : 'none');
  await b.close();
  process.exit(errs.length || failed.length ? 1 : 0);
})().catch(e => { console.error('VEHICLES TEST FAILED', e); process.exit(2); });
