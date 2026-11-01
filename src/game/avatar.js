// Skinned character wrapper shared by the player, enemies and NPCs:
// clip cross-fading, gun attachment to the right hand, aim pitch on the spine, armour recolouring.
import * as THREE from 'three';
import { Ragdoll } from './ragdoll.js';

const _q = new THREE.Quaternion(), _q2 = new THREE.Quaternion(), _q2b = new THREE.Quaternion(), _e = new THREE.Euler(), _v = new THREE.Vector3();

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
    // rest pose of every bone: additive tweaks (aim lean, board crouch, slumps) are undone before each animation step,
    // because clips exported with constant tracks stripped would otherwise never reset those bones and they would spin
    this.restQ = new Map(); this.touched = new Set();
    this.model.traverse(o => {
      if (o.isBone) { this.bones[o.name] = o; this.restQ.set(o, o.quaternion.clone()); }
      if (o.isMesh) { o.castShadow = true; o.receiveShadow = true; o.frustumCulled = false; }
    });
    // SkeletonUtils.clone gives every skinned mesh its own Skeleton (and bone texture, updated each frame);
    // the body, hair and garments all use the same bones, so bind them to one shared skeleton.
    const skels = [];
    this.model.traverse(o => {
      if (!o.isSkinnedMesh) return;
      const s = o.skeleton, sh = skels.find(k => k.bones.length === s.bones.length && k.bones.every((b, i) => b === s.bones[i])
        && k.boneInverses.every((m, i) => m.equals(s.boneInverses[i])));
      if (sh) { if (sh !== s) { o.skeleton = sh; s.dispose(); } } else skels.push(s);
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
    if (this.meta && this.meta.v === 3) this.setupPlayerMaterials();
    this.wear = {};
    this.current = null; this.aimPitch = 0; this.aimYawOffset = 0;
    this.gun = null; this.gunOffset = null;
    this.play('IdleRelaxed', 0);
  }

  // Player bodies: strand-card hair (alpha tested, two-sided, anisotropic sheen along the strands) and the skin
  // cover mask (skin under worn garments is pulled a few mm inwards so animated skin never pierces cloth).
  setupPlayerMaterials() {
    this.coverU = { value: 0 };
    const coverU = this.coverU;
    this.model.traverse(o => {
      if (!o.isMesh) return;
      const m = o.material;
      if (m.name === 'hair') {
        // crowd LOD (player_*_npc): plain standard material, same alpha setup
        const h = this.modelName.endsWith('_npc')
          ? new THREE.MeshStandardMaterial({ name: 'hair', map: m.map, color: m.color.clone(), roughness: .55, metalness: 0,
            alphaTest: .42, transparent: false, depthWrite: true, side: THREE.DoubleSide })
          : new THREE.MeshPhysicalMaterial({
            name: 'hair', map: m.map, color: m.color.clone(), roughness: .48, metalness: 0,
            alphaTest: .42, transparent: false, depthWrite: true, side: THREE.DoubleSide,
            anisotropy: .65, anisotropyRotation: Math.PI / 2, specularIntensity: .7,
          });
        h.userData.base = m.userData.base;
        o.material = h; o.castShadow = true;
        this.allMats[this.allMats.indexOf(m)] = h; this.mats.hair = h;
      } else if (m.name === 'hair__cap') {
        // strand atlas: solid inside, the hairline fades out in strand tips
        m.roughness = .62; m.transparent = false; m.depthWrite = true; m.alphaTest = .42; m.side = THREE.FrontSide;
      } else if (m.name === 'skin' && o.geometry.attributes._covermask) {
        m.onBeforeCompile = sh => {
          sh.uniforms.coverMask = coverU;
          sh.vertexShader = sh.vertexShader
            .replace('#include <common>', '#include <common>\nattribute float _covermask;\nuniform float coverMask;')
            .replace('#include <begin_vertex>', '#include <begin_vertex>\nif ((int(_covermask + .5) & int(coverMask + .5)) != 0) transformed -= normal * .006;');
        };
        m.customProgramCacheKey = () => 'skin-cover';
      }
    });
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
      if (it === 'none' && this.isLocked(slot)) it = this.defaults[slot] || Object.keys(this.items[slot])[0];
      out[slot] = it || 'none';
    }
    // a dress replaces the top and the legs pieces (they stay selected, just not shown)
    const replaced = new Set();
    for (const slot of Object.keys(this.items)) { const info = (this.wardrobe[slot] || {})[out[slot]]; if (info && info.replaces) info.replaces.forEach(s => replaced.add(s)); }
    for (const slot of Object.keys(this.items)) {
      const info = (this.wardrobe[slot] || {})[out[slot]];
      if (info && !replaced.has(slot)) { info.hide.forEach(r => hide.add(r)); if (info.hideHair) hideHair = true; }
    }
    for (const [slot, list] of Object.entries(this.items)) {
      const info = (this.wardrobe[slot] || {})[out[slot]] || {};
      // the base layer is always worn; it only disappears under clothing that covers it
      const covered = (info.coveredBy || []).some(s => out[s] && out[s] !== 'none' && !replaced.has(s)) || replaced.has(slot);
      for (const [id, o] of Object.entries(list)) o.visible = out[slot] === id && !(slot === 'hair' && hideHair) && !covered;
    }
    for (const [r, o] of Object.entries(this.regions)) o.visible = !hide.has(r);
    // skin cover mask: one bit per visible garment (players.py cover_masks)
    let mask = 0;
    for (const [slot, list] of Object.entries(this.items)) {
      const info = (this.wardrobe[slot] || {})[out[slot]];
      if (info && info.cover !== undefined && list[out[slot]] && list[out[slot]].visible) mask |= 1 << info.cover;
    }
    if (this.coverU) this.coverU.value = mask;
    this.wear = out; this.wearKey = JSON.stringify(out);
    return out;
  }

  isLocked(slot) { return Object.values(this.wardrobe[slot] || {}).some(d => d.locked); }

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
    set('skin', c.skin); set('eye_iris', c.eyes); set('hair', c.hairColor); set('hair__cap', c.hairColor); set('brow', c.hairColor);
    for (const m of this.allMats) {
      if (m.name === 'brow' && m.map) m.map.offset.y = .25 * ((c.brow | 0) % 4);
      const t = /^(?:cloth_|armor_primary__)([a-z]+)(?:__[a-z0-9_]+)?$/.exec(m.name);
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

  // physical death: the animation hands over to a verlet ragdoll pushed by the killing blow
  ragdoll(impulse, ground) {
    if (this.rag) return;
    this.attachGun(null);
    this.mixer.stopAllAction(); this.current = null;
    const r = new Ragdoll(this, impulse, ground);
    if (r.ok) this.rag = r; else this.play('Death', .1);
  }

  update(dt) {
    if (this.rag) { this.rag.step(Math.min(dt, .05)); return; }
    for (const b of this.touched) { const r = this.restQ.get(b); if (r) b.quaternion.copy(r); }
    this.touched.clear();
    this.mixer.update(dt);
    // additive aim: pitch the spine and chest about the character's own right axis (converted into each bone's
    // parent space), so the torso bends forward/back instead of twisting around its centre
    if (this.spine && (this.aimPitch || this.aimYawOffset)) {
      this.root.updateMatrixWorld(true);
      this.root.getWorldQuaternion(_q2);
      const right = _v.set(1, 0, 0).applyQuaternion(_q2), up = new THREE.Vector3(0, 1, 0);
      for (const [bone, k] of [[this.spine, .45], [this.chest, .55]]) {
        if (!bone || !bone.parent) continue;
        bone.parent.getWorldQuaternion(_q);
        const inv = _q.invert();
        const ax = right.clone().applyQuaternion(inv).normalize(), ay = up.clone().applyQuaternion(inv).normalize();
        this.touched.add(bone);
        bone.quaternion.premultiply(_q2b.setFromAxisAngle(ax, -this.aimPitch * k));
        if (this.aimYawOffset) bone.quaternion.premultiply(_q2b.setFromAxisAngle(ay, this.aimYawOffset * .5));
        bone.updateMatrixWorld(true);
      }
    }
  }

  muzzleWorld(out) {
    if (this.muzzle) return this.muzzle.getWorldPosition(out);
    return this.root.getWorldPosition(out).add(_v.set(0, 1.4, 0));
  }

  dispose() {
    this.root.removeFromParent(); this.mixer.stopAllAction();
    // free the per-character GPU state: bone textures and the cloned materials (textures stay with the shared model)
    const skels = new Set();
    this.root.traverse(o => { if (o.isSkinnedMesh) skels.add(o.skeleton); });
    skels.forEach(k => k.dispose());
    for (const m of this.allMats || []) m.dispose();
  }
}
