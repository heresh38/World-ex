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
    this.mats = {}; this.allMats = [];
    this.model.traverse(o => {
      if (o.isMesh) {
        o.material = o.material.clone();
        const m = o.material;
        this.mats[m.name] = m; this.allMats.push(m);
        m.userData.base = m.color.clone();
        if (m.emissive) m.userData.baseEmissive = m.emissive.clone();
        // strand cards: alpha tested, both faces, and they cast shadows like solid hair
        if (/hair_card/.test(m.name) || m.alphaTest > 0) { m.alphaTest = .5; m.transparent = false; m.depthWrite = true; m.side = THREE.DoubleSide; o.castShadow = true; }
      }
    });
    // player bodies (v3): body regions B_*, clothing/hair items C_<slot>__<item>, face morph targets, see players.py
    this.meta = null; this.regions = {}; this.items = {}; this.morphMeshes = []; this.parts = { O: {}, H: {} };
    this.model.traverse(o => {
      const lp = /^(O|H)_(.+)$/.exec(o.name);
      if (lp) this.parts[lp[1]][lp[2]] = o;
      if (o.userData && o.userData.worldex) { try { this.meta = JSON.parse(o.userData.worldex); } catch (e) { /* ignore */ } }
      let m = /^B_(.+)$/.exec(o.name);
      if (m) this.regions[m[1]] = o;
      m = /^C_([a-z]+)__(.+)$/.exec(o.name);
      if (m) (this.items[m[1]] = this.items[m[1]] || {})[m[2]] = o;
      if (o.isMesh && o.morphTargetDictionary && o.morphTargetInfluences) this.morphMeshes.push(o);
    });
    for (const mat of this.allMats) {
      if (/^(brow|lash)$/.test(mat.name)) {
        mat.alphaTest = mat.name === 'brow' ? .28 : .35; mat.transparent = false; mat.depthWrite = true; mat.side = THREE.DoubleSide;
        if (mat.map) { mat.map = mat.map.clone(); mat.map.needsUpdate = true; }
      }
    }
    this.wear = {};
    this.current = null; this.aimPitch = 0; this.aimYawOffset = 0;
    this.gun = null; this.gunOffset = null;
    this.play('IdleRelaxed', 0);
  }

  // civilians (civilians.py): outfits O_*, hair H_*; each outfit lists the body regions it covers
  get outfits() { return this.meta && this.meta.outfits ? Object.keys(this.meta.outfits) : []; }
  get hairStyles() { return this.meta && this.meta.hair ? this.meta.hair : []; }
  setLook(outfit, hair) {
    if (!this.meta || !this.meta.outfits) return;
    if (!this.meta.outfits[outfit]) outfit = this.outfits[0];
    if (!this.meta.hair.includes(hair)) hair = this.meta.hair[0];
    const hide = new Set(this.meta.outfits[outfit]);
    for (const [k, o] of Object.entries(this.parts.O)) o.visible = k === outfit;
    for (const [k, o] of Object.entries(this.parts.H)) o.visible = k === hair;
    for (const [k, o] of Object.entries(this.regions)) o.visible = !hide.has(k);
    this.outfit = outfit; this.hair = hair;
  }

  get isPlayerBody() { return !!(this.meta && this.meta.v === 3); }
  get wardrobe() { return (this.meta && this.meta.wardrobe) || {}; }
  get defaults() { return (this.meta && this.meta.defaults) || {}; }

  // One item (or 'none') per slot; hides the body regions the chosen items fully cover.
  setWear(wear) {
    if (!this.isPlayerBody) return {};
    const out = {};
    const hide = new Set(); let hideHair = false;
    for (const slot of Object.keys(this.items)) {
      let it = wear && wear[slot] !== undefined ? wear[slot] : this.defaults[slot];
      if (it !== 'none' && !this.items[slot][it]) it = this.defaults[slot] || 'none';
      out[slot] = it || 'none';
      const info = (this.wardrobe[slot] || {})[out[slot]];
      if (info) { info.hide.forEach(r => hide.add(r)); if (info.hideHair) hideHair = true; }
    }
    for (const [slot, list] of Object.entries(this.items)) {
      for (const [id, o] of Object.entries(list)) o.visible = out[slot] === id && !(slot === 'hair' && hideHair);
    }
    for (const [r, o] of Object.entries(this.regions)) o.visible = !hide.has(r);
    this.wear = out;
    return out;
  }

  setMorph(name, v) {
    for (const o of this.morphMeshes) {
      const i = o.morphTargetDictionary[name];
      if (i !== undefined) o.morphTargetInfluences[i] = v;
    }
  }

  // face: {group: presetName|null}, sliders: {name: -1..1}
  setFace(face = {}, sliders = {}) {
    if (!this.isPlayerBody) return;
    const M = this.meta.morphs;
    for (const [g, list] of Object.entries(M.groups)) for (const n of list) this.setMorph(n, face[g] === n ? 1 : 0);
    for (const n of M.sliders) this.setMorph(n, +(sliders[n] || 0));
  }

  // Skin, eyes, hair and brow colour, brow style, per-slot clothing tints and the glow colour.
  applyCharacter(c) {
    if (!this.isPlayerBody) { this.recolor(c); return; }
    c.wear = this.setWear(c.wear);
    this.setFace(c.face, c.sliders);
    const set = (name, hex) => { if (!hex) return; for (const m of this.allMats) if (m.name === name) m.color.set(hex); };
    set('skin', c.skin); set('eye_iris', c.eyes); set('hair', c.hairColor); set('brow', c.hairColor);
    for (const m of this.allMats) {
      if (m.name === 'brow' && m.map) m.map.offset.y = .25 * ((c.brow | 0) % 4);
      const t = /^(?:cloth_|armor_primary__)([a-z]+)$/.exec(m.name);
      if (t) { m.color.copy(m.userData.base); const hex = c.tints && c.tints[t[1]]; if (hex) m.color.multiply(new THREE.Color(hex)); }
    }
    this.recolor({ glow: c.glow });
  }

  // Tints multiply the original materials; null/undefined keeps the original look.
  recolor(c) {
    const tint = (prefix, hex, emissive = false) => {
      for (const m of this.allMats) {
        if (m.name !== prefix && !m.name.startsWith(prefix + '__')) continue;
        m.color.copy(m.userData.base);
        if (hex) m.color.multiply(new THREE.Color(hex));
        if (emissive && m.emissive) { m.emissive.copy(m.userData.baseEmissive || m.emissive); if (hex) m.emissive.set(hex); }
      }
    };
    if (!this.isPlayerBody) { tint('armor_primary', c.primary); tint('armor_secondary', c.secondary); }
    tint('glow', c.glow, true);
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
