// Player controller: WASD walk, Shift sprint (double-tap for a short tactical sprint), Space jump (coyote time and a jump
// buffer), C crouch / slide while sprinting, automatic mantling onto ledges up to ~2.4 m, sitting on seats, mouse look,
// and a third-person camera that never clips walls.
// Movement feel (fast modern military shooter): instant ground acceleration and stops, little air control, a slide that
// carries momentum (jump cancels it, a cooldown stops chaining), ADS-in time and sprint-to-fire delay per weapon class
// (data.js weaponHandling) that the viewmodel shows; the values are listed in CLAUDE.md.
import * as THREE from 'three';
import { Avatar } from './avatar.js';
import { weaponHandling, TAC_SPRINT_OUT } from './data.js';

const WALK = 4.8, RUN = 7.0, TAC = 8.6, AIMWALK = WALK * .58, CROUCH = 2.7, JUMP = 6.1, GRAV = 19;
const ACC = 55, DEC = 70, RUN_ACC = 24, AIR_ACC = 6;                      // m/s^2: ground start / stop, sprint build-up, air
const SLIDE_MIN = 6.0, SLIDE_BOOST = 2.4, SLIDE_MAX = 11, SLIDE_T = .9, SLIDE_FRIC = 1.35, SLIDE_CD = 1.0;
const TAC_TIME = 3.2, TAC_CD = 4.5, DOUBLE_TAP = .3;
export const MOVE = { WALK, RUN, TAC, AIMWALK, CROUCH, JUMP, GRAV, ACC, DEC, AIR_ACC, SLIDE_BOOST, SLIDE_T, SLIDE_CD, TAC_TIME, TAC_CD };
const R = .38, H = 1.8, HC = 1.15;
const COYOTE = .12, BUFFER = .15, CLIMB_MIN = .5, CLIMB_MAX = 2.45;
const _f = new THREE.Vector3(), _r = new THREE.Vector3(), _d = new THREE.Vector3(), _p = new THREE.Vector3(), _t = new THREE.Vector3();

export class Player {
  constructor(game) {
    this.g = game;
    this.pos = new THREE.Vector3(); this.vel = new THREE.Vector3();
    this.yaw = 0; this.camYaw = 0; this.camPitch = -.08;
    this.grounded = true; this.armed = false; this.aiming = false; this.running = false;
    this.camDist = 3.6; this.camCur = 3.6;
    this.maxHealth = 100; this.maxShield = 120; this.health = 100; this.shield = 120; this.sinceHit = 99;
    this.mode = 'foot'; this.dead = false;
    this.avatar = null; this.stepPhase = 0; this.airTime = 0;
    this.camera = game.camera;
    this.shake = 0; this.recoil = 0;
    this.lockYawToCam = 0;
    this.crouch = false; this.slideT = 0; this.coyote = 0; this.jumpBuf = 0; this.climb = null; this.dip = 0; this.eyeDrop = 0; this.seat = null;
    this.slideCd = 0; this.tacT = 0; this.tacCd = 0; this.tacK = 0; this.readyT = 0; this.readyMax = 0; this.runK = 0; this.adsK = 0; this.fovKick = 0; this.clock = 0;
  }

  setBody(body) {
    const model = body === 'male' ? 'player_male' : 'player_female';
    if (this.avatar && this.avatar.modelName === model) return;
    const old = this.avatar;
    this.avatar = new Avatar(this.g.assets, model);
    if (old) { old.dispose(); }
    this.g.scene && this.g.scene.add(this.avatar.root);
    this.applyLook();
    this.g.weapons && this.g.weapons.refreshModel();
    this.g.setAvatarLayer && this.g.setAvatarLayer();
  }

  // body, face, colours and clothing from the save
  applyLook() {
    const c = this.g.save.character;
    this.avatar.applyCharacter(c);
    this.g.viewmodel && this.g.viewmodel.recolor(c);
  }

  addToScene(scene) { scene.add(this.avatar.root); }

  spawn(p, yaw = 0) {
    this.pos.copy(p); this.vel.set(0, 0, 0); this.yaw = yaw; this.camYaw = yaw + Math.PI; this.camPitch = -.12;
    this.mode = 'foot'; this.dead = false; this.health = this.maxHealth; this.shield = this.maxShield;
    this.crouch = false; this.slideT = 0; this.climb = null; this.seat = null; this.dip = 0; this.eyeDrop = 0;
    this.slideCd = 0; this.tacT = 0; this.tacCd = 0; this.readyT = 0; this.runK = 0; this.adsK = 0;
    if (this.avatar.rag) { this.avatar.rag = null; this.avatar.play('IdleRelaxed', 0); this.g.weapons && this.g.weapons.refreshModel(); }
    this.avatar.root.position.copy(p); this.avatar.root.rotation.set(0, yaw, 0);
    this.camCur = this.camDist;
    this.snapCamera = true;
  }

  get forwardYaw() { return this.camYaw + Math.PI; }

  // camera looks along (-sin camYaw, ., -cos camYaw)
  camForward(out) { return out.set(-Math.sin(this.camYaw) * Math.cos(this.camPitch), Math.sin(this.camPitch), -Math.cos(this.camYaw) * Math.cos(this.camPitch)); }

  // Camera look. No aim assist: the feel comes from three things —
  //  * zoom-matched sensitivity: while aiming, rotation scales with the visible field (tan of the half-FOV), so a
  //    hand movement sweeps the same share of the screen at 1.3x and at 8x (times the "Aiming sensitivity" setting);
  //  * smoothing: input goes into a pending turn that is paid out over a short time constant (Aim smoothing setting,
  //    0-60 ms), so jittery mice and touch steps glide without losing any of the movement;
  //  * touch response curve: slow drags are damped for fine corrections, fast swipes keep full speed.
  look(input, dt) {
    const S = this.g.save.settings, touch = !!input.touch;
    let k = (touch ? (S.touchSens ?? 1) : S.sens) * .0022;
    if (this.aiming) {
      const z = this.g.weapons ? Math.max(1, this.g.weapons.zoom()) : 1, half = (S.fov || 70) * Math.PI / 360;
      k *= (S.aimSens ?? 1) * Math.tan(half / z) / Math.tan(half);
    }
    let mx = input.mx, my = input.my;
    if (touch && (mx || my)) {
      const v = Math.hypot(mx, my) / Math.max(dt, 1 / 240);            // px per second
      const gain = .5 + .5 * Math.min(1, v / 1400);
      mx *= gain; my *= gain;
    }
    this.lookX = (this.lookX || 0) + mx * k;
    this.lookY = (this.lookY || 0) + my * k * (S.invertY ? -1 : 1);
    const tau = Math.max(0, Math.min(1, S.aimSmooth ?? (touch ? .5 : .3))) * .06;
    const a = tau > 0 ? 1 - Math.exp(-dt / tau) : 1;
    const dx = this.lookX * a, dy = this.lookY * a;
    this.lookX -= dx; this.lookY -= dy;
    if (Math.abs(this.lookX) < 1e-5) this.lookX = 0; if (Math.abs(this.lookY) < 1e-5) this.lookY = 0;
    this.camYaw -= dx;
    this.camPitch -= dy;
    this.camPitch = Math.max(-1.25, Math.min(1.2, this.camPitch));
  }

  // sit on a seat: {pos (floor point under the chair), yaw}; E or any movement key stands up
  sit(seat) {
    this.mode = 'sit'; this.seat = seat; this.vel.set(0, 0, 0);
    this.standFrom = this.pos.clone();
    this.pos.copy(seat.pos); this.yaw = seat.yaw;
    this.avatar.root.position.copy(this.pos); this.avatar.root.rotation.set(0, this.yaw, 0);
    this.avatar.play('Sit', .35); this.avatar.sitRelax = true;   // relaxed arms on a seat (avatar.relaxArms)
    this.g.weapons && this.g.weapons.refreshModel();
  }

  stand(world) {
    if (this.mode !== 'sit') return;
    this.mode = 'foot';
    // step out in front of the seat (or back where we came from if that is blocked)
    const f = _p.set(Math.sin(this.yaw), 0, Math.cos(this.yaw));
    const out = this.pos.clone().addScaledVector(f, .75); out.y = world.support(out.x, out.z, this.pos.y + .5);
    const blocked = world.raycast(_t.copy(this.pos).setY(this.pos.y + .9), f, .9);
    this.pos.copy(blocked && this.standFrom ? this.standFrom : out);
    this.seat = null; this.avatar.sitRelax = false; this.avatar.play(this.armed ? 'Idle' : 'IdleRelaxed', .3);
    this.g.weapons && this.g.weapons.refreshModel();
  }

  // ledge in front of the player that can be climbed: returns the stand point on top, or null
  findLedge(world, fwd) {
    this.ledgeWhy = 'no hit';
    for (const hgt of [.35, .9, 1.5]) {
      const o = _t.set(this.pos.x, this.pos.y + hgt, this.pos.z);
      const hit = world.raycast(o, fwd, R + .55);
      if (!hit || !hit.box) continue;
      const top = hit.box.max.y, rise = top - this.pos.y;
      if (rise < CLIMB_MIN || rise > CLIMB_MAX) { this.ledgeWhy = 'rise ' + rise.toFixed(2); continue; }
      // stand point a little past the edge, must be on a surface at that height with head room above
      const tx = hit.point.x + fwd.x * (R + .12), tz = hit.point.z + fwd.z * (R + .12);
      const sy = world.support(tx, tz, top + .05);
      if (Math.abs(sy - top) > .3) { this.ledgeWhy = 'support ' + sy.toFixed(2) + ' vs ' + top.toFixed(2); continue; }
      let clear = true;
      for (const b of world.near(tx, tz, R)) {
        if (b.max.y <= sy + .05 || b.min.y >= sy + HC) continue;
        if (tx + R * .8 > b.min.x && tx - R * .8 < b.max.x && tz + R * .8 > b.min.z && tz - R * .8 < b.max.z) { clear = false; break; }
      }
      if (!clear) { this.ledgeWhy = 'no room on top'; continue; }
      // nothing overhead on the way up
      const up = world.raycast(_t.set(this.pos.x, this.pos.y + H - .1, this.pos.z), _d.set(0, 1, 0), rise + .2);
      if (up && up.box && up.box !== hit.box) { this.ledgeWhy = 'overhead ' + (up.box.tag || '') + ' at ' + up.dist.toFixed(2); continue; }
      this.ledgeWhy = 'ok';
      return new THREE.Vector3(tx, sy, tz);
    }
    return null;
  }

  update(dt, input, world) {
    const av = this.avatar;
    this.clock += dt;
    if (this.mode !== 'foot' || this.dead) { this.adsK = 0; this.runK = 0; this.readyT = 0; this.tacT = 0; this.aiming = false; this.running = false; }
    if (this.mode === 'seat' || this.mode === 'car') { av.update(dt); return; }
    if (this.dead) { av.update(dt); return; }
    const k = c => input.key(c);
    if (this.mode === 'sit') {
      av.root.position.copy(this.pos); av.root.rotation.set(0, this.yaw, 0); av.aimPitch = 0; av.update(dt);
      if (input.enabled && (input.pressed('KeyW') || input.pressed('KeyS') || input.pressed('Space') || input.pressed('KeyE'))) { input.consume('KeyE'); this.stand(world); }
      return;
    }
    // ---- climbing: ease up and over the ledge, then hand control back
    if (this.climb) {
      const c = this.climb; c.t += dt / c.dur;
      const t = Math.min(1, c.t), up = Math.min(1, t / .62), fw = Math.max(0, (t - .45) / .55);
      const eu = 1 - Math.pow(1 - up, 3), ef = fw * fw * (3 - 2 * fw);
      this.pos.set(c.from.x + (c.to.x - c.from.x) * ef, c.from.y + (c.to.y + .05 - c.from.y) * eu, c.from.z + (c.to.z - c.from.z) * ef);
      av.root.position.copy(this.pos); av.root.rotation.set(0, this.yaw, 0);   // full set: a quaternion copied in a vehicle can leave x/z at ±π (mirrored facing)
      av.play('Jump', .1); av.update(dt);
      this.eyeDrop = Math.sin(t * Math.PI) * .25;
      if (t >= 1) { this.climb = null; this.pos.copy(c.to); this.vel.set(c.dir.x * 2, 0, c.dir.z * 2); this.grounded = true; this.g.audio.land(); }
      return;
    }
    let mx = (k('KeyD') ? 1 : 0) - (k('KeyA') ? 1 : 0), mz = (k('KeyW') ? 1 : 0) - (k('KeyS') ? 1 : 0);
    if (input.axisX || input.axisY) { mx = input.axisX; mz = input.axisY; }
    if (!input.enabled) mx = mz = 0;
    const moving = mx || mz;
    const W = this.g.weapons, gun = this.armed && W ? W.equipped() : null, hd = weaponHandling(gun ? gun.arch : null);
    this.aiming = this.armed && input.enabled && input.rmb;
    const fireHeld = this.armed && input.enabled && input.lmb;
    // ---- sprint: forward only, not while aiming or holding the trigger; double-tap for a tactical sprint
    let tacReq = false;
    if (input.enabled && (input.pressed('ShiftLeft') || input.pressed('ShiftRight'))) { if (this.clock - (this.shiftT ?? -9) < DOUBLE_TAP) tacReq = true; this.shiftT = this.clock; }
    if (input.tacHit) { input.tacHit = false; tacReq = true; }          // touch: double-tap the sprint button (touch.js)
    this.running = !!(moving && mz > 0 && (k('ShiftLeft') || input.axisRun) && !this.aiming && !fireHeld || moving && k('ShiftRight') && !this.aiming && !fireHeld);
    if (W && W.lastFire < .15) this.running = false;
    this.tacCd = Math.max(0, this.tacCd - dt);
    if (tacReq && this.running && this.tacCd <= 0 && this.tacT <= 0 && this.slideT <= 0) this.tacT = TAC_TIME;
    if (this.tacT > 0) {
      if (!this.running || mz <= 0) { this.tacT = 0; this.tacCd = TAC_CD * .6; }
      else { this.tacT -= dt; if (this.tacT <= 0) { this.tacT = 0; this.tacCd = TAC_CD; } }
    }
    const tac = this.tacT > 0;
    this.tacK += ((tac ? 1 : 0) - this.tacK) * Math.min(1, dt * 10);
    // ---- sprint-to-fire: the gun is down while sprinting and comes back up over the class delay (weapons.js waits)
    if (this.running) { this.readyMax = this.readyT = hd.sprintOut + (tac ? TAC_SPRINT_OUT : 0); }
    else this.readyT = Math.max(0, this.readyT - dt);
    this.runK = this.running ? 1 : this.readyMax ? this.readyT / this.readyMax : 0;
    // ---- ADS: in over the class time (out a little faster), only once the gun is up and not reloading
    const adsOn = this.aiming && this.readyT <= 0 && !(W && W.reloading > 0);
    this.adsK = Math.max(0, Math.min(1, this.adsK + (adsOn ? dt / hd.ads : -dt / (hd.ads * .8))));
    const hs0 = Math.hypot(this.vel.x, this.vel.z);
    this.slideCd = Math.max(0, this.slideCd - dt);
    // ---- crouch / slide (C): sprinting into C slides (not again until the cooldown is over)
    if (input.enabled && input.pressed('KeyC')) {
      if (this.grounded && this.running && hs0 > SLIDE_MIN && this.slideT <= 0 && this.slideCd <= 0) {
        this.slideT = SLIDE_T; this.crouch = true; this.running = false; this.tacT = 0;
        const boost = Math.min(SLIDE_MAX, Math.max(hs0, RUN) + SLIDE_BOOST); this.vel.x *= boost / hs0; this.vel.z *= boost / hs0;
        this.g.audio.step && this.g.audio.step(true, 'gravel');
      } else if (this.slideT > 0) { this.slideT = 0; this.slideCd = SLIDE_CD; }
      else this.crouch = !this.crouch;
    }
    if (this.running && this.crouch && this.slideT <= 0) this.crouch = false;     // sprinting stands you up
    if (!this.crouch && this.slideT <= 0 && this.wasCrouch) {
      // only stand up if there is head room
      const up = world.raycast(_t.set(this.pos.x, this.pos.y + HC - .05, this.pos.z), _d.set(0, 1, 0), H - HC + .1);
      if (up) { this.crouch = true; this.running = false; }
    }
    this.wasCrouch = this.crouch;
    const mob = this.g.armor ? this.g.armor.mobility / 100 : 1;
    const base = this.crouch ? CROUCH : this.running ? (tac ? TAC : RUN) : WALK;
    const speed = (base + (Math.min(base, this.crouch ? CROUCH * .8 : AIMWALK) - base) * (this.aiming ? Math.max(this.adsK, .5) : this.adsK)) * mob;
    // camera-relative move direction
    _f.set(-Math.sin(this.camYaw), 0, -Math.cos(this.camYaw));
    _r.set(-_f.z, 0, _f.x);
    _d.set(0, 0, 0).addScaledVector(_f, mz).addScaledVector(_r, mx);
    if (_d.lengthSq() > 1) _d.normalize();
    else if (_d.lengthSq() > 0 && !(input.axisX || input.axisY)) _d.normalize();
    if (this.slideT > 0) {
      // sliding: momentum carries, friction bleeds it off, slight steering
      this.slideT -= dt;
      const f = Math.max(0, 1 - dt * SLIDE_FRIC); this.vel.x *= f; this.vel.z *= f;
      this.vel.x += _d.x * dt * 2.5; this.vel.z += _d.z * dt * 2.5;
      if (this.slideT <= 0 || Math.hypot(this.vel.x, this.vel.z) < 3.2) { this.slideT = 0; this.slideCd = SLIDE_CD; }
    } else if (this.grounded) {
      // ground: a fixed-rate approach to the wanted velocity (instant feel: walk speed in ~0.09 s, a stop in ~0.07 s);
      // building up to a sprint takes a moment, reversing brakes hard
      const tx = _d.x * speed, tz = _d.z * speed, ex = tx - this.vel.x, ez = tz - this.vel.z, el = Math.hypot(ex, ez);
      let a = ACC;
      if (_d.lengthSq() === 0 || tx * this.vel.x + tz * this.vel.z < 0) a = DEC;
      else if (speed > WALK * mob + .2 && hs0 > WALK * mob - .4) a = RUN_ACC;
      const st = a * dt;
      if (el <= st) { this.vel.x = tx; this.vel.z = tz; } else { this.vel.x += ex / el * st; this.vel.z += ez / el * st; }
    } else if (_d.lengthSq() > 0) {
      // air: a little steering, momentum is kept (no drag, never pushed past the faster of target and current speed)
      const cap = Math.max(speed, hs0);
      this.vel.x += _d.x * AIR_ACC * dt; this.vel.z += _d.z * AIR_ACC * dt;
      const h = Math.hypot(this.vel.x, this.vel.z); if (h > cap) { this.vel.x *= cap / h; this.vel.z *= cap / h; }
    }
    // ---- jump: coyote time + buffered presses; mantle when a ledge is in front
    this.coyote = this.grounded ? COYOTE : Math.max(0, this.coyote - dt);
    if (input.enabled && input.pressed('Space')) this.jumpBuf = BUFFER; else this.jumpBuf = Math.max(0, this.jumpBuf - dt);
    const fwd = _p.set(Math.sin(this.yaw), 0, Math.cos(this.yaw));
    if (moving && mz > 0) fwd.set(_d.x, 0, _d.z).normalize();
    const wantClimb = (this.jumpBuf > 0 || (!this.grounded && mz > 0 && this.vel.y < 2)) && input.enabled;
    const ledge = wantClimb && (mz > 0 || this.jumpBuf > 0) ? this.findLedge(world, fwd) : null;
    if (ledge && (this.jumpBuf > 0 && ledge.y - this.pos.y > 1.0 || !this.grounded)) {
      const rise = ledge.y - this.pos.y;
      this.climb = { from: this.pos.clone(), to: ledge, t: 0, dur: .32 + rise * .16, dir: fwd.clone() };
      this.jumpBuf = 0; this.crouch = false; this.slideT = 0; this.vel.set(0, 0, 0);
      this.yaw = Math.atan2(fwd.x, fwd.z); this.g.audio.jump();
      return;
    }
    if (this.jumpBuf > 0 && this.coyote > 0) {
      this.vel.y = JUMP; this.grounded = false; this.coyote = 0; this.jumpBuf = 0; this.g.audio.jump();
      if (this.slideT > 0) { this.slideT = 0; this.slideCd = SLIDE_CD; }       // jump cancels the slide, keeping the momentum
      this.crouch = false;
    }
    this.vel.y -= GRAV * dt;
    const wasAir = !this.grounded;
    const res = world.moveCapsule(this.pos, this.vel, R, this.crouch ? HC : H, dt);
    this.grounded = res.grounded;
    if (this.grounded && wasAir && this.airTime > .25) { this.g.audio.land(); this.dip = Math.min(.22, this.airTime * .18); }
    this.airTime = this.grounded ? 0 : this.airTime + dt;
    if (this.pos.y < -60) { this.pos.y = world.ground(this.pos.x, this.pos.z) + 2; this.vel.set(0, 0, 0); }
    // facing: strafe while aiming/firing, otherwise turn toward travel
    const fp = this.g.firstPerson();
    const faceCam = fp || this.aiming || (this.g.weapons && this.g.weapons.firingRecently());
    let target = this.yaw;
    if (moving) target = Math.atan2(_d.x, _d.z);
    if (this.slideT > 0) target = Math.atan2(this.vel.x, this.vel.z);
    if (faceCam) target = Math.atan2(_f.x, _f.z);
    let dy = target - this.yaw; dy = Math.atan2(Math.sin(dy), Math.cos(dy));
    if (fp) this.yaw = target; else this.yaw += dy * Math.min(1, (faceCam ? 20 : 12) * dt);
    av.root.position.copy(this.pos); av.root.rotation.set(0, this.yaw, 0);   // full set: a quaternion copied in a vehicle can leave x/z at ±π (mirrored facing)
    // camera height: slide / crouch drop the eye, landings dip it briefly
    const drop = this.slideT > 0 ? .75 : this.crouch ? .55 : 0;
    this.eyeDrop += (drop - this.eyeDrop) * Math.min(1, dt * 12);
    this.dip = Math.max(0, this.dip - dt * .9);
    // animation
    const hs = Math.hypot(this.vel.x, this.vel.z);
    const sfx = this.armed ? '' : 'Relaxed';
    if (this.slideT > 0) av.play(av.actions.Slide ? 'Slide' : 'Sit', .12);
    else if (!this.grounded && this.airTime > .12) av.play('Jump', .15);
    else if (this.crouch) av.play(av.actions.CrouchWalk && hs > .4 ? 'CrouchWalk' : av.actions.CrouchIdle ? 'CrouchIdle' : hs > .4 ? 'Walk' + sfx : (this.armed ? 'Idle' : 'IdleRelaxed'), .2, hs > .4 ? Math.max(.6, hs / CROUCH) * .6 : 1);
    else if (hs > 5.2) av.play('Run' + sfx, .2, hs / RUN);
    else if (hs > .4) {
      // walking backward while strafing plays the walk cycle in reverse
      const back = faceCam && (this.vel.x * Math.sin(this.yaw) + this.vel.z * Math.cos(this.yaw)) < -.3;
      av.play('Walk' + sfx, .2, (back ? -1 : 1) * Math.max(.6, hs / WALK) * 1.1);
    } else av.play((this.armed ? 'Idle' : 'IdleRelaxed'), .3);
    av.aimPitch = this.armed && this.slideT <= 0 ? this.camPitch * (faceCam ? 1 : .35) : 0;
    av.update(dt);
    // footsteps from the animation phase
    if (this.grounded && hs > .4 && this.slideT <= 0) {
      const ph = av.phase();
      const half = ph < .5 ? 0 : 1;
      if (half !== this.stepPhase) { this.stepPhase = half; this.g.audio.step(this.running, this.g.world.surface || 'metal'); }
    }
    this.g.save.stats.distance += hs * dt;
    // shields
    this.sinceHit += dt;
    if (this.sinceHit > 4 && this.shield < this.maxShield) {
      if (this.shield <= 0) this.g.audio.shieldUp();
      this.shield = Math.min(this.maxShield, this.shield + 60 * dt);
    }
    if (this.sinceHit > 8 && this.health < this.maxHealth) this.health = Math.min(this.maxHealth, this.health + 20 * dt);
  }

  damage(n, from) {
    if (this.dead || this.g.godMode) return;
    this.sinceHit = 0; if (from) this.lastHitFrom = from.clone ? from.clone() : null;
    const hadShield = this.shield > 0;
    if (this.g.armor) n *= 1 - this.g.armor.resist;
    if (this.shield <= 0 && from) this.g.fx.blood(this.pos.clone().setY(this.pos.y + 1.2), this.pos.clone().sub(from).setY(.3).normalize(), .6);
    const s = Math.min(this.shield, n); this.shield -= s; n -= s;
    if (hadShield && this.shield <= 0) this.g.audio.shieldBreak();
    this.health -= n;
    this.g.audio.hurt();
    this.g.hud.damageFlash(this.shield > 0 ? .25 : .7, from);
    this.shake = Math.min(1, this.shake + .3);
    if (this.health <= 0) { this.health = 0; this.die(); }
  }

  die() {
    this.dead = true;
    this.avatar.ragdoll(this.lastHitFrom ? this.pos.clone().sub(this.lastHitFrom).setY(1.5).normalize().multiplyScalar(4) : new THREE.Vector3(0, 1, 0), (x, z) => this.g.world.collision.ground(x, z));
    this.g.fx.bloodPool(this.pos.clone(), 1);
    this.g.save.stats.deaths++;
    this.g.onPlayerDeath();
  }

  // ------------------------------------------------------------- camera
  updateCamera(dt, world) {
    const cam = this.camera;
    let pivotH = 1.62, side = .62, dist = this.camDist;
    if (this.mode === 'car' && this.g.vehicles.current) {
      if (this.g.vehicles.camera(cam, dt)) return;      // first-person seat / board camera (vehicles.js)
      const c = this.g.vehicles.current;
      _p.copy(c.root.position).y += c.board ? 1.5 : 1.8;
      dist = c.board ? 4.2 : 7.5; side = 0;
    } else if (this.mode === 'seat' || (this.mode === 'sit' && this.g.save.settings.view === 'third')) {
      _p.copy(this.pos).y += 1.3; dist = 2.6; side = .3;
    } else if (this.mode === 'sit') {
      // seated first person: eyes at seated head height, free look
      const eye = (this.avatar.modelName === 'player_male' ? 1.72 : 1.57) * .72;
      cam.position.set(this.pos.x + Math.sin(this.yaw) * .12, this.pos.y + eye, this.pos.z + Math.cos(this.yaw) * .12);
      this.finishCamera(dt, cam);
      return;
    } else if (this.g.firstPerson()) {
      // first person: eye height from the body frame, a little head bob while moving
      const eye = this.avatar.modelName === 'player_male' ? 1.72 : 1.57;
      const hs = Math.hypot(this.vel.x, this.vel.z);
      this.headBob = (this.headBob || 0) + (this.grounded ? dt * hs * 1.15 : 0);
      const bob = this.aiming ? 0 : Math.abs(Math.sin(this.headBob)) * .035 * Math.min(1, hs / 7);
      cam.position.set(this.pos.x, this.pos.y + eye + bob - this.eyeDrop - this.dip, this.pos.z);
      this.camCur = 0; this.snapCamera = false;
      this.finishCamera(dt, cam);
      return;
    } else {
      if (this.aiming) { dist = 1.75; side = .58; pivotH = 1.58; }
      if (this.dead) { dist = 5; side = 0; pivotH = .8; }
      _p.copy(this.pos); _p.y += pivotH - this.eyeDrop * .8 - this.dip;
      _r.set(Math.cos(this.camYaw), 0, -Math.sin(this.camYaw)); // camera right
      // keep the shoulder pivot itself out of walls
      _t.copy(_r).multiplyScalar(side);
      const sh = world.raycast(_p, _r, side + .25);
      if (sh) _t.copy(_r).multiplyScalar(Math.max(0, sh.dist - .25));
      _p.add(_t);
    }
    this.camForward(_f);
    _d.copy(_f).negate();
    // collision: cast from pivot to the desired camera spot, pull in on hit
    const hit = world.raycast(_p, _d, dist + .3);
    let want = dist;
    if (hit) want = Math.max(.35, hit.dist - .3);
    if (this.snapCamera || want < this.camCur) this.camCur = want;
    else this.camCur += (want - this.camCur) * Math.min(1, dt * 4);
    this.snapCamera = false;
    cam.position.copy(_p).addScaledVector(_d, this.camCur);
    const gy = world.ground(cam.position.x, cam.position.z) + .3;
    if (cam.position.y < gy) cam.position.y = gy;
    this.finishCamera(dt, cam);
  }

  finishCamera(dt, cam) {
    // shake + recoil kick
    this.shake = Math.max(0, this.shake - dt * 2.5); this.recoil = Math.max(0, this.recoil - dt * 6);
    const sk = this.shake * this.shake * .06;
    cam.rotation.order = 'YXZ';
    cam.rotation.set(this.camPitch + this.recoil * .03 + (Math.random() - .5) * sk, this.camYaw + (Math.random() - .5) * sk, 0);
    // zoom follows the ADS progress (per-class ADS time, eased); sprinting, the tactical sprint and slides widen the view
    const kick = this.mode === 'foot' && !this.aiming ? (this.slideT > 0 ? 10 : this.running && Math.hypot(this.vel.x, this.vel.z) > 6 ? (this.tacT > 0 ? 11 : 7) : 0) : 0;
    this.fovKick += (kick - this.fovKick) * Math.min(1, dt * 6);
    const e = this.adsK * this.adsK * (3 - 2 * this.adsK), z = this.g.weapons && this.adsK > 0 ? this.g.weapons.zoom() : 1;
    const fov = (this.g.save.settings.fov + this.fovKick) / (1 + (z - 1) * e);
    if (Math.abs(cam.fov - fov) > .02) { cam.fov = fov; cam.updateProjectionMatrix(); }
    this.g.audio.listener(cam.position, this.camYaw);
  }
}
