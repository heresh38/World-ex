// Player controller: WASD walk, Shift run, Space jump, mouse look, third-person camera that never clips walls.
import * as THREE from 'three';
import { Avatar } from './avatar.js';

const WALK = 3.4, RUN = 7.2, AIMWALK = 2.6, JUMP = 5.6, GRAV = 18;
const R = .38, H = 1.8;
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

  update(dt, input, world) {
    const av = this.avatar;
    if (this.mode === 'seat' || this.mode === 'car') { av.update(dt); return; }
    if (this.dead) { av.update(dt); return; }
    const k = c => input.key(c);
    let mx = (k('KeyD') ? 1 : 0) - (k('KeyA') ? 1 : 0), mz = (k('KeyW') ? 1 : 0) - (k('KeyS') ? 1 : 0);
    if (input.axisX || input.axisY) { mx = input.axisX; mz = input.axisY; }
    if (!input.enabled) mx = mz = 0;
    const moving = mx || mz;
    this.aiming = this.armed && input.enabled && input.rmb;
    this.running = moving && (k('ShiftLeft') || input.axisRun) && !this.aiming && mz >= 0 || moving && k('ShiftRight');
    if (this.g.weapons && this.g.weapons.firingRecently()) this.running = false;
    const speed = this.aiming ? AIMWALK : this.running ? RUN : WALK;
    // camera-relative move direction
    _f.set(-Math.sin(this.camYaw), 0, -Math.cos(this.camYaw));
    _r.set(-_f.z, 0, _f.x);
    _d.set(0, 0, 0).addScaledVector(_f, mz).addScaledVector(_r, mx);
    if (_d.lengthSq() > 1) _d.normalize();
    else if (_d.lengthSq() > 0 && !(input.axisX || input.axisY)) _d.normalize();
    const accel = this.grounded ? 14 : 3;
    this.vel.x += (_d.x * speed - this.vel.x) * Math.min(1, accel * dt);
    this.vel.z += (_d.z * speed - this.vel.z) * Math.min(1, accel * dt);
    if (this.grounded && input.pressed('Space') && input.enabled) { this.vel.y = JUMP; this.grounded = false; this.g.audio.jump(); }
    this.vel.y -= GRAV * dt;
    const wasAir = !this.grounded;
    const res = world.moveCapsule(this.pos, this.vel, R, H, dt);
    this.grounded = res.grounded;
    if (this.grounded && wasAir && this.airTime > .25) this.g.audio.land();
    this.airTime = this.grounded ? 0 : this.airTime + dt;
    if (this.pos.y < -60) { this.pos.y = world.ground(this.pos.x, this.pos.z) + 2; this.vel.set(0, 0, 0); }
    // facing: strafe while aiming/firing, otherwise turn toward travel
    const fp = this.g.firstPerson();
    const faceCam = fp || this.aiming || (this.g.weapons && this.g.weapons.firingRecently());
    let target = this.yaw;
    if (moving) target = Math.atan2(_d.x, _d.z);
    if (faceCam) target = Math.atan2(_f.x, _f.z);
    let dy = target - this.yaw; dy = Math.atan2(Math.sin(dy), Math.cos(dy));
    if (fp) this.yaw = target; else this.yaw += dy * Math.min(1, (faceCam ? 20 : 11) * dt);
    av.root.position.copy(this.pos); av.root.rotation.y = this.yaw;
    // animation
    const hs = Math.hypot(this.vel.x, this.vel.z);
    const sfx = this.armed ? '' : 'Relaxed';
    if (!this.grounded && this.airTime > .12) av.play('Jump', .15);
    else if (hs > 4.6) av.play('Run' + sfx, .2, hs / RUN);
    else if (hs > .4) {
      // walking backward while strafing plays the walk cycle in reverse
      const back = faceCam && (this.vel.x * Math.sin(this.yaw) + this.vel.z * Math.cos(this.yaw)) < -.3;
      av.play('Walk' + sfx, .2, (back ? -1 : 1) * Math.max(.6, hs / WALK));
    } else av.play((this.armed ? 'Idle' : 'IdleRelaxed'), .3);
    av.aimPitch = this.armed ? this.camPitch * (faceCam ? 1 : .35) : 0;
    av.update(dt);
    // footsteps from the animation phase
    if (this.grounded && hs > .4) {
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
    this.sinceHit = 0;
    const hadShield = this.shield > 0;
    const s = Math.min(this.shield, n); this.shield -= s; n -= s;
    if (hadShield && this.shield <= 0) this.g.audio.shieldBreak();
    this.health -= n;
    this.g.audio.hurt();
    this.g.hud.damageFlash(this.shield > 0 ? .25 : .7, from);
    this.shake = Math.min(1, this.shake + .3);
    if (this.health <= 0) { this.health = 0; this.die(); }
  }

  die() {
    this.dead = true; this.avatar.play('Death', .15);
    this.g.save.stats.deaths++;
    this.g.onPlayerDeath();
  }

  // ------------------------------------------------------------- camera
  updateCamera(dt, world) {
    const cam = this.camera;
    let pivotH = 1.62, side = .62, dist = this.camDist;
    if (this.mode === 'car' && this.g.vehicles.current) {
      const c = this.g.vehicles.current;
      _p.copy(c.root.position).y += 1.6;
      dist = 7.5; side = 0;
    } else if (this.mode === 'seat') {
      _p.copy(this.pos).y += 1.3; dist = 2.6; side = .3;
    } else if (this.g.firstPerson()) {
      // first person: eye height from the body frame, a little head bob while moving
      const eye = this.avatar.modelName === 'player_male' ? 1.72 : 1.57;
      const hs = Math.hypot(this.vel.x, this.vel.z);
      this.headBob = (this.headBob || 0) + (this.grounded ? dt * hs * 1.15 : 0);
      const bob = this.aiming ? 0 : Math.abs(Math.sin(this.headBob)) * .035 * Math.min(1, hs / 7);
      cam.position.set(this.pos.x, this.pos.y + eye + bob, this.pos.z);
      this.camCur = 0; this.snapCamera = false;
      this.finishCamera(dt, cam);
      return;
    } else {
      if (this.aiming) { dist = 1.75; side = .58; pivotH = 1.58; }
      if (this.dead) { dist = 5; side = 0; pivotH = .8; }
      _p.copy(this.pos); _p.y += pivotH;
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
    const fov = this.g.save.settings.fov / (this.aiming && this.g.weapons ? this.g.weapons.zoom() : 1);
    if (Math.abs(cam.fov - fov) > .05) { cam.fov += (fov - cam.fov) * Math.min(1, dt * 14); cam.updateProjectionMatrix(); }
    this.g.audio.listener(cam.position, this.camYaw);
  }
}
