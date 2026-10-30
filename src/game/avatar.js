// Skinned character wrapper shared by the player, enemies and NPCs:
// clip cross-fading, gun attachment to the right hand, aim pitch on the spine, armour recolouring.
import * as THREE from 'three';

const _q = new THREE.Quaternion(), _q2 = new THREE.Quaternion(), _e = new THREE.Euler(), _v = new THREE.Vector3();

export class Avatar {
  constructor(assets, model) {
    this.assets = assets; this.modelName = model;
    this.root = new THREE.Group();          // feet origin, yaw on root
    this.model = assets.clone(model);
    this.root.add(this.model);
    this.mixer = new THREE.AnimationMixer(this.model);
    this.actions = {};
    for (const c of assets.clips(model)) {
      const a = this.mixer.clipAction(c);
      if (c.name === 'Death' || c.name === 'Jump') { a.setLoop(THREE.LoopOnce); a.clampWhenFinished = true; }
      this.actions[c.name] = a;
    }
    this.bones = {};
    this.model.traverse(o => {
      if (o.isBone) this.bones[o.name] = o;
      if (o.isMesh) { o.castShadow = true; o.receiveShadow = true; o.frustumCulled = false; }
    });
    this.handR = this.bones.handR || this.bones['hand.R'];
    this.spine = this.bones.spine; this.chest = this.bones.chest; this.head = this.bones.head;
    // own copies of materials so recolouring one avatar never affects another
    this.mats = {};
    this.model.traverse(o => {
      if (o.isMesh) {
        o.material = o.material.clone();
        this.mats[o.material.name] = o.material;
      }
    });
    this.current = null; this.aimPitch = 0; this.aimYawOffset = 0;
    this.gun = null; this.gunOffset = null;
    this.play('IdleRelaxed', 0);
  }

  recolor(c) {
    const set = (n, hex, emissive = false) => {
      const m = this.mats[n]; if (!m || !hex) return;
      m.color.set(hex);
      if (emissive) { m.emissive.set(hex); }
    };
    set('armor_primary', c.primary); set('armor_secondary', c.secondary);
    set('glow', c.glow, true);
    if (this.mats.visor && c.glow) this.mats.visor.emissive.set(c.glow).multiplyScalar(.6);
  }

  play(name, fade = .22, speed = 1) {
    const a = this.actions[name]; if (!a) return;
    if (this.current === a) { a.timeScale = speed; return; }
    a.reset(); a.timeScale = speed; a.enabled = true; a.setEffectiveWeight(1);
    if (this.current && fade > 0) a.crossFadeFrom(this.current, fade, false);
    else if (this.current) this.current.stop();
    a.play();
    this.current = a; this.currentName = name;
  }

  // phase 0..1 of the current looping clip (footsteps)
  phase() { const a = this.current; return a ? (a.time / a.getClip().duration) % 1 : 0; }

  attachGun(modelName, onMesh) {
    if (this.gunHolder) { this.gunHolder.removeFromParent(); this.gunHolder = null; this.gun = null; }
    if (!modelName || !this.handR) return null;
    const g = this.assets.clone(modelName);
    g.traverse(o => { if (o.isMesh) { o.castShadow = true; o.material = o.material.clone(); onMesh && onMesh(o); } });
    if (!this.gunOffset) this.computeGunOffset();
    // holder carries the solved hand offset; the gun itself stays free for reload/recoil motion
    const h = this.gunHolder = new THREE.Group();
    h.position.copy(this.gunOffset.p); h.quaternion.copy(this.gunOffset.q);
    h.add(g); this.handR.add(h);
    this.gun = g;
    this.muzzle = g.getObjectByName('muzzle');
    return g;
  }

  // Solve the hand->gun transform once from the armed idle pose so the barrel points straight ahead.
  computeGunOffset() {
    const prev = this.currentName;
    const a = this.actions.Idle;
    this.mixer.stopAllAction();
    a.reset().play(); this.mixer.update(0);
    const yaw = this.root.rotation.y; this.root.rotation.y = 0;
    this.root.updateMatrixWorld(true);
    this.handR.getWorldQuaternion(_q);
    this.root.getWorldQuaternion(_q2);
    const local = _q.clone().invert().multiply(_q2);
    this.gunOffset = { q: local, p: new THREE.Vector3(0, .075, .0) };
    this.root.rotation.y = yaw;
    a.stop(); this.current = null;
    if (prev) this.play(prev, 0);
  }

  update(dt) {
    this.mixer.update(dt);
    // additive aim: spread pitch across spine/chest, a little yaw
    if (this.spine && (this.aimPitch || this.aimYawOffset)) {
      _e.set(-this.aimPitch * .45, this.aimYawOffset * .5, 0, 'XYZ');
      // bone local X = character right axis after export -> pitch about X
      _q.setFromEuler(_e); this.spine.quaternion.multiply(_q);
      _e.set(-this.aimPitch * .55, this.aimYawOffset * .5, 0, 'XYZ');
      _q.setFromEuler(_e); this.chest.quaternion.multiply(_q);
    }
  }

  muzzleWorld(out) {
    if (this.muzzle) return this.muzzle.getWorldPosition(out);
    return this.root.getWorldPosition(out).add(_v.set(0, 1.4, 0));
  }

  dispose() { this.root.removeFromParent(); this.mixer.stopAllAction(); }
}
