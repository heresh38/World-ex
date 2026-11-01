// VANTHOS soundscape (src/core/soundscape.js): wind moaning through the blown-out towers, steel and concrete groaning
// as they settle, water dripping in the halls and the drowned district, mites skittering around their nests, hosts
// moaning where they lie, and, following the listener, a low dread drone and the city far off (a shriek between the
// towers, a roar, something collapsing). Only the nearest few emitters play (4 voices on touch, 6 otherwise).
import { Soundscape } from '../../core/soundscape.js';

export class VanthosAmbience {
  constructor(world) {
    this.w = world; this.g = world.g;
    const S = this.s = new Soundscape(this.g.audio, { voices: this.g.renderer.touch ? 4 : 6 });
    const R = world.ruins;
    let k = 0;
    for (const D of R.designs.values()) {
      const kind = D.meta.kind;
      if (!/^(tower|mid|hall|low)$/.test(kind)) continue;
      for (const m of D.list) {
        const x = m.elements[12], y = m.elements[13], z = m.elements[14];
        if (kind === 'tower' || kind === 'mid') S.add({ kind: 'ruinwind', pos: { x, y: y + Math.min(30, (D.meta.h || 20) * .6), z }, r: 120, gain: kind === 'tower' ? .6 : .45 });
        if ((kind === 'tower' || kind === 'hall') && k++ % 2 === 0) S.add({ kind: 'creak', pos: { x, y: y + 8, z }, r: 75, gain: .55 });
        if (kind === 'hall' || kind === 'low') S.add({ kind: 'drip', pos: { x, y: y + 2, z }, r: 32, gain: .6 });
      }
    }
    for (const st of world.sites) {
      if (st.types.includes('mite')) S.add({ kind: 'skitter', pos: { x: st.pos.x, y: st.pos.y + .3, z: st.pos.z }, r: 42, gain: .6, site: st, active: () => st.cleared ? 0 : 1 });
      else if (st.types.includes('host') && st.o.res) S.add({ kind: 'groan', pos: { x: st.pos.x, y: st.pos.y + 1, z: st.pos.z }, r: 55, gain: .5, active: () => st.cleared ? 0 : 1 });
    }
    // the drowned streets drip and lap
    const map = world.map;
    for (let x = -1500; x <= 1500; x += 90) for (let z = -1500; z <= 1500; z += 90) if (map.flooded(x, z) > .6 && ((x + z) / 90) % 2 === 0) S.add({ kind: 'drip', pos: { x, y: -1, z }, r: 45, gain: .45 });
    // with the listener: the dread bed and the far city
    const cam = this.g.camera.position;
    S.add({ kind: 'dread', pos: p => { p.x = cam.x; p.y = cam.y - 4; p.z = cam.z + 2; return p; }, r: 400, gain: .35 });
    S.add({ kind: 'distant', pos: p => { const t = this.g.time * .03; p.x = cam.x + Math.cos(t) * 40; p.y = cam.y + 10; p.z = cam.z + Math.sin(t) * 40; return p; }, r: 600, gain: .7 });
  }

  update(dt) {
    const g = this.g, cam = g.camera.position, e = g.camera.matrixWorld.elements, yaw = Math.atan2(e[8], e[10]);
    this.s.update(dt, cam, yaw, 18);
  }

  stats() { return this.s.stats(); }
  dispose() { this.s.dispose(); }
}
