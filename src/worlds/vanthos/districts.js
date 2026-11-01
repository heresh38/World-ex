// VANTHOS districts as independent modules. The city has been dead for years: most lots hold rubble mounds, broken
// foundations or wild growth; the few buildings still standing are ruins (src/worlds/vanthos/ruins.js, designs from
// tools/blender/ruins.py). Each district owns its ruin palette, its residents (creatures already living in the streets
// and halls: sleeping where they fell, feeding, perched on rubble, patrolling, roaming in packs), its loot tier and its
// story set pieces. `populate(ctx)` builds them through the world's context API (world.js).
//
// ctx API:
//   ctx.rnd()                                  seeded random for this district
//   ctx.takeLot(pred?) -> lot | null           claim a free lot {x, z, w, d, big, block}
//   ctx.building(kit, x, z, rot, fit?)         landmark from the old kit (instanced) + collider, returns {h, top}
//   ctx.ruin(name, x, z, rot, opts?)           a ruin design (VR_*), returns {meta, y, top} or null
//   ctx.prop(kit, x, z, rot, {y, scale, solid}) set piece from the old kit (clone), optional collider
//   ctx.tree(kind, x, z, scale?)               something growing: 'tree' | 'bush' | 'water' (willows) | a TR_ variant
//   ctx.resident(types, x, z, n, beh, opts)    creatures living here (streamed with the player): beh sleep | feed |
//                                              perch | patrol | roam | wander; opts.y stands them on a spot
//   ctx.cache(x, z, tier, label?)               loot cache (tier 1..4)
//   ctx.lift(x, z, topY) / ctx.metro(x, z) / ctx.light(...) / ctx.trigger(...) / ctx.boss(...) / ctx.shard(x, z)
//   ctx.street() -> {x, z, rot, along}         a point in the middle of a street of this district (rot: the street's yaw)
//   ctx.spots(kind) -> [Vector3]               ruin spots placed so far (inside / perch / tree / glow)

const pickW = (rnd, table) => { const tot = Object.values(table).reduce((a, b) => a + b, 0); let r = rnd() * tot; for (const [k, w] of Object.entries(table)) { r -= w; if (r <= 0) return k; } return Object.keys(table)[0]; };

// rotation that turns a design's front (+z) toward the lot's nearest street (lots sit in the corners of their block)
function facing(lot) {
  const b = lot.block; if (!b) return 0;
  const dx = lot.x - b.x, dz = lot.z - b.z;
  if (lot.big) return 0;
  return Math.abs(dx) / (b.w || 80) > Math.abs(dz) / (b.d || 100) ? (dx > 0 ? Math.PI / 2 : -Math.PI / 2) : (dz > 0 ? 0 : Math.PI);
}

// creatures that live in a ruin: sheltered in its ground floor (sleeping / feeding) or perched on its rubble
function inhabit(ctx, D, r, rnd) {
  const s = r.spots || {};
  if (s.inside && s.inside.length && rnd() < D.inside) {
    const p = s.inside[Math.floor(rnd() * s.inside.length)];
    const t = pickW(rnd, D.shelter || D.enemies);
    ctx.resident([t], p.x, p.z, t === 'mite' ? 5 : 1 + Math.floor(rnd() * 3), rnd() < .55 ? 'sleep' : 'feed', { y: p.y, spread: 3 });
  }
  if (s.perch && s.perch.length && rnd() < D.perch) {
    const p = s.perch[0];
    ctx.resident([D.percher || 'stalker'], p.x, p.z, 1, 'perch', { y: p.y });
  }
}

function fillLots(ctx, D, extra = null) {
  let lot;
  const W = D.lots;          // {stand, collapse, stub, wild}
  while ((lot = ctx.takeLot())) {
    const rnd = ctx.rnd, r = rnd(), rot = facing(lot);
    const n = lot.big ? 2 : 1;
    for (let k = 0; k < n; k++) {
      const ox = lot.big ? (k ? 1 : -1) * lot.w * .22 : 0, oz = lot.big ? (k ? -1 : 1) * lot.d * .18 : 0;
      const x = lot.x + ox + (rnd() - .5) * 4, z = lot.z + oz + (rnd() - .5) * 4;
      const q = k ? rnd() : r;
      if (q < W.stand) {
        const name = pickW(rnd, D.stand);
        const [hw, hd] = ctx.half(name, rot);
        if (hw * 2 <= lot.w + 6 && hd * 2 <= lot.d + 6) { const R = ctx.ruin(name, x, z, rot); if (R) { inhabit(ctx, D, R, rnd); continue; } }
      }
      if (q < W.stand + W.collapse) {
        const R = ctx.ruin(rnd() < .55 ? 'VR_mound_l' : 'VR_mound_m', x, z, rnd() * 6.28);
        if (rnd() < .6) ctx.ruin(rnd() < .5 ? 'VR_debris' : 'VR_slabs', x + (rnd() - .5) * lot.w * .7, z + (rnd() - .5) * lot.d * .7, rnd() * 6.28);
        if (R) inhabit(ctx, D, R, rnd);
        continue;
      }
      if (q < W.stand + W.collapse + W.stub) { const R = ctx.ruin('VR_stub', x, z, rot + (rnd() < .5 ? 0 : Math.PI)); if (R) inhabit(ctx, D, R, rnd); continue; }
      // wild: the lot has gone back to scrub and young trees; sometimes remains, and something eating them
      if (extra && extra(lot)) continue;
      const nt = 2 + Math.floor(rnd() * 5);
      for (let t = 0; t < nt; t++) ctx.tree(rnd() < .7 ? 'tree' : 'bush', lot.x + (rnd() - .5) * lot.w * .8, lot.z + (rnd() - .5) * lot.d * .8);
      if (rnd() < .35) { const px = lot.x + (rnd() - .5) * 10, pz = lot.z + (rnd() - .5) * 10; ctx.ruin('VR_remains', px, pz, rnd() * 6.28);
        if (rnd() < D.feed) ctx.resident([pickW(rnd, D.enemies)], px + 1.5, pz, 1 + Math.floor(rnd() * 2), 'feed', { spread: 1.5 }); }
    }
  }
}

// the streets: wrecks, toppled lamps, fallen signs, old barricades, remains, debris; then the street residents
function streets(ctx, D, n) {
  const rnd = ctx.rnd;
  for (let i = 0; i < n; i++) {
    const s = ctx.street(), side = (rnd() < .5 ? -1 : 1) * (3 + rnd() * 2.5), c = Math.cos(s.rot), sn = Math.sin(s.rot);
    const x = s.x + c * side, z = s.z - sn * side, r = rnd();
    if (r < .38) ctx.ruin(rnd() < .55 ? 'VR_car_burnt' : 'VR_car_rust', x, z, s.rot + (rnd() - .5) * .6 + (rnd() < .5 ? Math.PI : 0));
    else if (r < .44) ctx.ruin('VR_bus_burnt', s.x + c * side * .6, s.z - sn * side * .6, s.rot + (rnd() - .5) * .3);
    else if (r < .55) ctx.ruin('VR_lamp_down', x, z, s.rot + (rnd() < .5 ? 1.5 : -1.5) + (rnd() - .5) * .4, { collide: false });
    else if (r < .64) ctx.ruin(rnd() < .5 ? 'VR_sign_a' : 'VR_sign_b', x, z, rnd() * 6.28, { collide: false });
    else if (r < .7) ctx.ruin('VR_barricade', s.x, s.z, s.rot + Math.PI / 2 + (rnd() - .5) * .2);
    else if (r < .8) ctx.ruin('VR_remains', x, z, rnd() * 6.28, { collide: false });
    else ctx.ruin('VR_debris', s.x + (rnd() - .5) * 6, s.z + (rnd() - .5) * 6, rnd() * 6.28, { collide: false });
    if (rnd() < .22) ctx.tree(rnd() < .5 ? 'tree' : 'bush', x + (rnd() - .5) * 4, z + (rnd() - .5) * 4, .6 + rnd() * .4);
  }
}

// creatures in the streets: sleepers among the wrecks, feeders, patrols and roaming packs
function residents(ctx, D, n) {
  const rnd = ctx.rnd;
  for (let i = 0; i < n; i++) {
    const p = ctx.street(), type = pickW(rnd, D.enemies), [a, b] = D.pack;
    let k = a + Math.floor(rnd() * (b - a + 1));
    if (type === 'mite') k = k * 2 + 2;
    const beh = pickW(rnd, D.beh);
    ctx.resident([type], p.x, p.z, k, beh, {});
  }
}

// a Writhe nest: hosts lying over a carpet of mites, a bladder or two, a sickly glow
function nest(ctx, x, z, big = false) {
  ctx.resident(['mite'], x, z, big ? 9 : 6, 'wander', { spread: 5 });
  ctx.resident(['host'], x + 4, z - 3, big ? 3 : 2, 'sleep', { spread: 4 });
  ctx.resident(['bladder'], x - 3, z + 3, big ? 2 : 1, 'wander', {});
  ctx.ruin('VR_remains', x + 1, z + 1, ctx.rnd() * 6); ctx.ruin('VR_remains', x - 2, z - 1, ctx.rnd() * 6);
  ctx.prop(big ? 'VX_growth_l' : 'VX_growth_s', x, z, ctx.rnd() * 6);
  ctx.light(x, 2.5, z, 0xb8ff40, big ? 1.1 : .8, true);
}

const BEH = { sleep: 3, feed: 2, perch: 0, patrol: 2, roam: 1.5, wander: 1.5 };

export const DISTRICTS = [
  {
    id: 'crown', name: 'The Crown', blurb: 'The broken towers around the Spire. Nothing up here sleeps for long',
    lots: { stand: .5, collapse: .36, stub: .1 }, stand: { VR_tower_a: 3, VR_tower_b: 3, VR_tower_c: 2, VR_mid_c: 2, VR_mid_a: 1 },
    enemies: { stalker: 4, elite: .4, host: 1.5, mite: 1 }, shelter: { stalker: 2, host: 2, mite: 1 }, percher: 'stalker',
    beh: { ...BEH, perch: 0, roam: 2.5 }, pack: [2, 3], inside: .55, perch: .45, feed: .4, factionWar: true, loot: 3, danger: 3,
    populate(ctx) {
      fillLots(ctx, this);
      streets(ctx, this, 70);
      residents(ctx, this, 16);
      for (let i = 0; i < 2; i++) { const p = ctx.street(); nest(ctx, p.x, p.z, i === 0); }
      for (let i = 0; i < 4; i++) { const p = ctx.street(); ctx.cache(p.x, p.z, 3, 'Executive vault'); }
    },
  },
  {
    id: 'old', name: 'Old Quarter', a0: 15, a1: 75, blurb: 'Collapsed apartments and the market hall. The dead lie where they fell, mostly',
    lots: { stand: .48, collapse: .34, stub: .14 }, stand: { VR_mid_a: 3, VR_mid_b: 3, VR_mid_c: 2, VR_low_a: 3, VR_low_b: 3, VR_hall: 2 },
    enemies: { host: 3, mite: 1.2, stalker: 1.2, bladder: .4 }, shelter: { host: 3, stalker: 1, mite: 1 },
    beh: { ...BEH, sleep: 4 }, pack: [2, 4], inside: .42, perch: .3, feed: .5, loot: 1, danger: 1,
    populate(ctx) {
      fillLots(ctx, this);
      streets(ctx, this, 80);
      residents(ctx, this, 13);
      for (let i = 0; i < 2; i++) { const n0 = ctx.street(); nest(ctx, n0.x, n0.z, i === 0); }
      for (let i = 0; i < 5; i++) { const p = ctx.street(); ctx.cache(p.x, p.z, 1); }
      for (let i = 0; i < 2; i++) { const m = ctx.street(); ctx.metro(m.x, m.z); }
    },
  },
  {
    id: 'commercial', name: 'Commercial District', a0: 75, a1: 135, blurb: 'Gutted towers and malls. Predators wait inside',
    lots: { stand: .48, collapse: .36, stub: .1 }, stand: { VR_tower_a: 2, VR_tower_b: 3, VR_tower_c: 1, VR_mid_c: 2, VR_hall: 1 },
    enemies: { stalker: 3, host: 1, mite: .6 }, shelter: { stalker: 3, host: 1 }, percher: 'stalker',
    beh: { ...BEH, sleep: 2, perch: 0, patrol: 3 }, pack: [2, 3], inside: .65, perch: .5, feed: .5, loot: 2, danger: 2,
    populate(ctx) {
      // the alien organism bursting through a skyscraper
      const org = ctx.takeLot(l => l.big) || ctx.takeLot();
      if (org) { ctx.building('VX_organism', org.x, org.z, 0); ctx.light(org.x, 60, org.z, 0xb46cff, 4, false);
        ctx.resident(['stalker'], org.x + 18, org.z + 6, 3, 'feed', {}); ctx.ruin('VR_mound_l', org.x - 22, org.z + 20, 1.2); }
      fillLots(ctx, this);
      streets(ctx, this, 70);
      residents(ctx, this, 15);
      for (let i = 0; i < 3; i++) { const p = ctx.street(); ctx.cache(p.x, p.z, 2, 'Shop strongroom'); }
      const m = ctx.street(); ctx.metro(m.x, m.z);
    },
  },
  {
    id: 'flooded', name: 'Flooded District', a0: 135, a1: 195, blurb: 'Drowned streets, sunken ruins, things moving under the water',
    lots: { stand: .26, collapse: .44, stub: .18 }, stand: { VR_low_b: 2, VR_mid_b: 2, VR_low_a: 1, VR_mid_a: 1 },
    enemies: { swimmer: 2, host: 1.4, mite: .8 }, shelter: { host: 2, swimmer: 1 },
    beh: { ...BEH, sleep: 2, wander: 3 }, pack: [2, 4], inside: .5, perch: .2, feed: .5, loot: 1, danger: 2, water: true,
    populate(ctx) {
      fillLots(ctx, this);
      streets(ctx, this, 50);
      residents(ctx, this, 14);
      for (let i = 0; i < 3; i++) { const p = ctx.street(); nest(ctx, p.x, p.z, i === 0); }
      for (let i = 0; i < 12; i++) { const p = ctx.street(); ctx.shard(p.x, p.z); }
      for (let i = 0; i < 3; i++) { const p = ctx.street(); ctx.metro(p.x, p.z); }
    },
  },
  {
    id: 'research', name: 'Research Sector', a0: 195, a1: 255, blurb: 'Laboratories, containment sites and a hospital whose emergency lights never went out',
    lots: { stand: .42, collapse: .36, stub: .14 }, stand: { VR_mid_c: 2, VR_mid_a: 1, VR_low_b: 2, VR_hall: 1, VR_tower_c: 1 },
    enemies: { mutant: 2, host: 2, mite: 1 }, shelter: { mutant: 1, host: 2 },
    beh: { ...BEH, wander: 3 }, pack: [2, 3], inside: .6, perch: .2, feed: .6, loot: 2, danger: 2,
    populate(ctx) {
      // abandoned hospital: emergency lights, fog closes in, the dead walk out
      const h = ctx.takeLot(l => l.big) || ctx.takeLot();
      if (h) {
        ctx.building('VX_hospital', h.x, h.z, 0);
        for (let i = 0; i < 4; i++) ctx.light(h.x - 20 + i * 12, 4, h.z - 14, 0xff3326, 2.4, true);
        // the patients the parasite took first lie in front of the doors
        ctx.resident(['host'], h.x + 6, h.z - 20, 4, 'sleep', { spread: 6 });
        ctx.trigger(h.x, h.z, 45, () => {
          ctx.horror(h.x, h.z); ctx.pack(['mutant'], h.x, h.z - 18, 2, { awake: true });
          ctx.pack(['host', 'mite', 'mite', 'host', 'mite'], h.x + 8, h.z - 22, 6, { awake: true });
          ctx.pack(['bladder'], h.x - 10, h.z - 24, 1, { awake: true });
        });
        ctx.cache(h.x, h.z - 16, 2, 'Pharmacy stores');
        // what was left of the staff, fused into one thing, guards the morgue
        ctx.boss('amalgam', h.x + 18, 0, h.z + 20, 'The Ward Matron', 3, 1);
        nest(ctx, h.x - 20, h.z + 16, true);
      }
      // the lab boss among containment chambers
      const b = ctx.takeLot(l => l.big) || ctx.takeLot();
      if (b) { ctx.building('VX_lab_containment', b.x - 12, b.z, 0); ctx.building('VX_lab_containment', b.x + 12, b.z, 0);
        ctx.boss('mutant', b.x, 0, b.z + 18, 'Specimen Prime', 7, 1.9); ctx.cache(b.x, b.z - 14, 3, 'Specimen vault'); }
      for (let i = 0; i < 2; i++) { const l = ctx.takeLot(); if (l) { ctx.building('VX_lab_a', l.x, l.z, facing(l)); ctx.resident(['mutant'], l.x, l.z + l.d * .4, 2, 'wander', {}); } }
      fillLots(ctx, this);
      streets(ctx, this, 60);
      residents(ctx, this, 13);
      const m = ctx.street(); ctx.metro(m.x, m.z);
    },
  },
  {
    id: 'military', name: 'Military Zone', a0: 255, a1: 315, blurb: 'Bunkers and checkpoints. The garrison never left; its sentries still fire',
    lots: { stand: .32, collapse: .36, stub: .24 }, stand: { VR_low_b: 2, VR_hall: 1, VR_mid_b: 1 },
    enemies: { host: 3, mite: 1, stalker: .6 }, shelter: { host: 3 },
    beh: { ...BEH, patrol: 3, sleep: 3 }, pack: [2, 4], inside: .6, perch: .2, feed: .4, loot: 3, danger: 2,
    populate(ctx) {
      // the weapons depot: the best loot outside the Spire, still covered by its automated sentries
      const d = ctx.takeLot(l => l.big) || ctx.takeLot();
      if (d) { ctx.building('VX_mil_depot', d.x, d.z, 0); ctx.cache(d.x - 12, d.z - 18, 4, 'Weapons depot'); ctx.cache(d.x + 12, d.z - 18, 4, 'Weapons depot');
        ctx.resident(['host'], d.x, d.z - 26, 4, 'patrol', { armed: true });
        ctx.pack(['turret'], d.x - 18, d.z - 22, 1, {}); ctx.pack(['turret'], d.x + 18, d.z - 22, 1, {}); }
      for (let i = 0; i < 3; i++) { const l = ctx.takeLot(); if (l) { ctx.building(i ? 'VX_mil_bunker' : 'VX_mil_tower', l.x, l.z, facing(l)); ctx.prop('VX_mil_wall', l.x, l.z + l.d * .45, 0, { solid: true }); } }
      fillLots(ctx, this);
      streets(ctx, this, 60);
      residents(ctx, this, 14);
      for (let i = 0; i < 4; i++) { const p = ctx.street(); ctx.ruin('VR_barricade', p.x, p.z, p.rot + Math.PI / 2); ctx.pack(['turret'], p.x + 4, p.z + 4, 1, {}); }
      const m = ctx.street(); ctx.metro(m.x, m.z);
    },
  },
  {
    id: 'industrial', name: 'Industrial Spine', a0: 315, a1: 375, blurb: 'Gutted factories and halls, and the heavy things that sleep in them',
    lots: { stand: .45, collapse: .34, stub: .14 }, stand: { VR_hall: 4, VR_low_a: 1, VR_mid_b: 1, VR_low_b: 1 },
    enemies: { stalker: 2, hulk: .6, host: 1.5, mite: 1 }, shelter: { hulk: 1.5, stalker: 1.5, host: 1 },
    beh: { ...BEH }, pack: [2, 3], inside: .65, perch: .3, feed: .5, factionWar: true, loot: 2, danger: 2,
    populate(ctx) {
      for (const k of ['VX_ind_power', 'VX_ind_refinery', 'VX_ind_factory']) { const l = ctx.takeLot(q => q.big) || ctx.takeLot(); if (l) ctx.building(k, l.x, l.z, facing(l)); }
      fillLots(ctx, this);
      streets(ctx, this, 60);
      residents(ctx, this, 13);
      // the frozen train, half out of a collapsed tunnel
      const t = ctx.street(); ctx.prop('VX_train', t.x, t.z, ctx.rnd() * 6, { solid: true }); ctx.prop('VX_bridge_broken', t.x + 30, t.z, 0, { solid: true });
      ctx.cache(t.x, t.z + 6, 2, 'Freight car');
      for (let i = 0; i < 2; i++) { const p = ctx.street(); ctx.resident(['hulk'], p.x, p.z, 1, 'sleep', {}); }
      for (let i = 0; i < 2; i++) { const p = ctx.street(); nest(ctx, p.x, p.z); }
      const m = ctx.street(); ctx.metro(m.x, m.z);
    },
  },
  {
    id: 'outskirts', name: 'The Outskirts', blurb: 'Fallen settlements, scrub and the dead highways out', sparse: .4,
    lots: { stand: .26, collapse: .34, stub: .26 }, stand: { VR_low_a: 2, VR_low_b: 2, VR_mid_b: 1 },
    enemies: { host: 2.5, stalker: 1.5, mite: 1 }, shelter: { host: 2, stalker: 1 },
    beh: { ...BEH, roam: 3 }, pack: [2, 4], inside: .5, perch: .3, feed: .6, factionWar: true, loot: 1, danger: 1,
    populate(ctx) {
      fillLots(ctx, this, lot => { if (ctx.rnd() < .35) { for (let k = 0; k < 4; k++) ctx.ruin(ctx.rnd() < .5 ? 'VR_car_rust' : 'VR_car_burnt', lot.x + (ctx.rnd() - .5) * lot.w * .7, lot.z + (ctx.rnd() - .5) * lot.d * .7, ctx.rnd() * 6); return true; } return false; });
      streets(ctx, this, 50);
      residents(ctx, this, 14);
      for (let i = 0; i < 3; i++) { const p = ctx.street(); ctx.cache(p.x + 5, p.z, 1, 'Settlers’ stash'); }
      // a settlement the Writhe took
      const o = ctx.street(); nest(ctx, o.x + 4, o.z + 4, true); ctx.cache(o.x - 5, o.z, 2, 'Overrun stash');
    },
  },
];
