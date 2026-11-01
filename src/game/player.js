// Player controller: WASD walk, Shift sprint, Space jump (with coyote time and a jump buffer), C crouch / slide
// while sprinting, automatic mantling onto ledges up to ~2.4 m, sitting on seats, mouse look, and a third-person
// camera that never clips walls.
import * as THREE from 'three';
import { Avatar } from './avatar.js';

const WALK = 4.4, RUN = 8.6, AIMWALK = 3.0, CROUCH = 2.4, JUMP = 6.1, GRAV = 19;
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
    if (this.avatar.rag) { this.avatar.rag = null; this.avatar.play('IdleRelaxed', 0); this.g.weapons && this.g.weapons.refreshModel(); }
    this.avatar.root.position.copy(p); this.avatar.root.rotation.y = yaw;
    this.camCur = this.camDist;
    this.snapCamera = true;
  }

  get forwardYaw() { return this.camYaw + Math.PI; }

  // camera looks along (-sin camYaw, ., -cos camYaw)
  camForward(out) { return out.set(-Math.sin(this.camYaw) * Math.cos(this.camPitch), Math.sin(this.camPitch), -Math.cos(this.camYaw) * Math.cos(this.camPitch)); }

  look(input, dt) {
    const s = this.g.save.settings.sens * .0022 * (this.aiming ? .6 : 1);
    this.camYaw -= input.mx * s;
    this.camPitch -= input.my * s * (this.g.save.settings.invertY ? -1 : 1);
    this.camPitch = Math.max(-1.25, Math.min(1.2, this.camPitch));
  }

  // sit on a seat: {pos (floor point under the chair), yaw}; E or any movement key stands up
  sit(seat) {
    this.mode = 'sit'; this.seat = seat; this.vel.set(0, 0, 0);
    this.standFrom = this.pos.clone();
    this.pos.copy(seat.pos); this.yaw = seat.yaw;
    this.avatar.root.position.copy(this.pos); this.avatar.root.rotation.set(0, this.yaw, 0);
    this.avatar.play('Sit', .35);
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
    this.seat = null; this.avatar.play(this.armed ? 'Idle' : 'IdleRelaxed', .3);
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
    if (this.mode === 'seat' || this.mode === 'car') { av.update(dt); return; }
    if (this.dead) { av.update(dt); return; }
    const k = c => input.key(c);
    if (this.mode === 'sit') {
      av.root.position.copy(this.pos); av.root.rotation.y = this.yaw; av.aimPitch = 0; av.update(dt);
      if (input.enabled && (input.pressed('KeyW') || input.pressed('KeyS') || input.pressed('Space') || input.pressed('KeyE'))) { input.consume('KeyE'); this.stand(world); }
      return;
    }
    // ---- climbing: ease up and over the ledge, then hand control back
    if (this.climb) {
      const c = this.climb; c.t += dt / c.dur;
      const t = Math.min(1, c.t), up = Math.min(1, t / .62), fw = Math.max(0, (t - .45) / .55);
      const eu = 1 - Math.pow(1 - up, 3), ef = fw * fw * (3 - 2 * fw);
      this.pos.set(c.from.x + (c.to.x - c.from.x) * ef, c.from.y + (c.to.y + .05 - c.from.y) * eu, c.from.z + (c.to.z - c.from.z) * ef);
      av.root.position.copy(this.pos); av.root.rotation.y = this.yaw;
      av.play('Jump', .1); av.update(dt);
      this.eyeDrop = Math.sin(t * Math.PI) * .25;
      if (t >= 1) { this.climb = null; this.pos.copy(c.to); this.vel.set(c.dir.x * 2, 0, c.dir.z * 2); this.grounded = true; this.g.audio.land(); }
      return;
    }
    let mx = (k('KeyD') ? 1 : 0) - (k('KeyA') ? 1 : 0), mz = (k('KeyW') ? 1 : 0) - (k('KeyS') ? 1 : 0);
    if (input.axisX || input.axisY) { mx = input.axisX; mz = input.axisY; }
    if (!input.enabled) mx = mz = 0;
    const moving = mx || mz;
    this.aiming = this.armed && input.enabled && input.rmb;
    this.running = moving && (k('ShiftLeft') || input.axisRun) && !this.aiming && mz > 0 && !this.crouch || moving && k('ShiftRight');
    if (this.g.weapons && this.g.weapons.firingRecently()) this.running = false;
    const hs0 = Math.hypot(this.vel.x, this.vel.z);
    // ---- crouch / slide (C)
    if (input.enabled && input.pressed('KeyC')) {
      if (this.grounded && this.running && hs0 > 6 && this.slideT <= 0) {
        this.slideT = .85; this.crouch = true; this.running = false;
        const boost = Math.max(hs0, RUN) + 2.8; this.vel.x *= boost / hs0; this.vel.z *= boost / hs0;
        this.g.audio.step && this.g.audio.step(true, 'gravel');
      } else this.crouch = !this.crouch;
    }
    if (this.running && this.crouch && this.slideT <= 0) this.crouch = false;     // sprinting stands you up
    if (!this.crouch && this.slideT <= 0 && this.wasCrouch) {
      // only stand up if there is head room
      const up = world.raycast(_t.set(this.pos.x, this.pos.y + HC - .05, this.pos.z), _d.set(0, 1, 0), H - HC + .1);
      if (up) this.crouch = true;
    }
    this.wasCrouch = this.crouch;
    const mob = this.g.armor ? this.g.armor.mobility / 100 : 1;
    const speed = (this.aiming ? AIMWALK : this.crouch ? CROUCH : this.running ? RUN : WALK) * mob;
    // camera-relative move direction
    _f.set(-Math.sin(this.camYaw), 0, -Math.cos(this.camYaw));
    _r.set(-_f.z, 0, _f.x);
    _d.set(0, 0, 0).addScaledVector(_f, mz).addScaledVector(_r, mx);
    if (_d.lengthSq() > 1) _d.normalize();
    else if (_d.lengthSq() > 0 && !(input.axisX || input.axisY)) _d.normalize();
    if (this.slideT > 0) {
      // sliding: momentum carries, friction bleeds it off, slight steering
      this.slideT -= dt;
      const f = Math.max(0, 1 - dt * 1.6); this.vel.x *= f; this.vel.z *= f;
      this.vel.x += _d.x * dt * 3; this.vel.z += _d.z * dt * 3;
      if (this.slideT <= 0 || Math.hypot(this.vel.x, this.vel.z) < 3) { this.slideT = 0; }
    } else {
      // snappy on the ground (quick to speed, quicker to stop), light air control
      const want = _d.lengthSq() > 0;
      const accel = this.grounded ? (want ? 16 : 20) : 3.5;
      this.vel.x += (_d.x * speed - this.vel.x) * Math.min(1, accel * dt);
      this.vel.z += (_d.z * speed - this.vel.z) * Math.min(1, accel * dt);
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
      if (this.slideT > 0) { this.slideT = 0; }              // slide-jump keeps the momentum
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
    av.root.position.copy(this.pos); av.root.rotation.y = this.yaw;
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
    // zoom when aiming
    // sprinting and sliding widen the view a touch
    const kick = this.mode === 'foot' && !this.aiming ? (this.slideT > 0 ? 10 : this.running && Math.hypot(this.vel.x, this.vel.z) > 6 ? 7 : 0) : 0;
    const fov = (this.g.save.settings.fov + kick) / (this.aiming && this.g.weapons ? this.g.weapons.zoom() : 1);
    if (Math.abs(cam.fov - fov) > .05) { cam.fov += (fov - cam.fov) * Math.min(1, dt * (kick ? 6 : 14)); cam.updateProjectionMatrix(); }
    this.g.audio.listener(cam.position, this.camYaw);
  }
}
