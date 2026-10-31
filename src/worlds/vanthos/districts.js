// VANTHOS districts as independent modules. Each one owns its building palette, enemy population, loot tier and
// story set pieces; `populate(ctx)` builds them through the world's context API, so a district can be reworked or a
// new one added without touching the rest of the city.
//
// ctx API (see world.js):
//   ctx.rnd()                                  seeded random for this district
//   ctx.takeLot(pred?) -> lot | null           claim a free lot {x, z, w, d}
//   ctx.building(kit, x, z, rot, scale?)       instanced building + collider, returns {h, top}
//   ctx.prop(kit, x, z, rot, {y, scale, solid}) set piece (clone), optional collider
//   ctx.pack(types, x, z, n, opts)             enemy spawn site (streamed with the district)
//   ctx.cache(x, z, tier, label?)               loot cache (tier 1..4)
//   ctx.lift(x, z, topY)                        rooftop lift (E to ride up / down)
//   ctx.metro(x, z)                             metro entrance (procedural dungeon below)
//   ctx.light(x, y, z, color, intensity, flicker)
//   ctx.trigger(x, z, r, fn)                    fires once when the player comes near
//   ctx.boss(type, x, y, z, name, hpMul, scale) unique boss
//   ctx.shard(x, z)                             hidden collectible
//   ctx.street(rnd?) -> {x, z}                  a point on a street of this district

const pickW = (rnd, table) => { const tot = Object.values(table).reduce((a, b) => a + b, 0); let r = rnd() * tot; for (const [k, w] of Object.entries(table)) { r -= w; if (r <= 0) return k; } return Object.keys(table)[0]; };

function fillLots(ctx, D, extra = () => {}) {
  let lot;
  while ((lot = ctx.takeLot())) {
    if (D.emptyLots && ctx.rnd() < D.emptyLots) { extra(lot); continue; }
    const kit = pickW(ctx.rnd, lot.big ? (D.bigKit || D.kit) : D.kit);
    const b = ctx.building(kit, lot.x, lot.z, Math.floor(ctx.rnd() * 4) * Math.PI / 2, Math.min(lot.w, lot.d));
    if (b && D.lifts && b.h > 40 && ctx.rnd() < .3) ctx.lift(lot.x + lot.w / 2 + 2, lot.z, b.h);
  }
}

function packs(ctx, D, n) {
  for (let i = 0; i < n; i++) {
    const p = ctx.street();
    const type = pickW(ctx.rnd, D.enemies);
    const [a, b] = D.pack;
    const n = a + Math.floor(ctx.rnd() * (b - a + 1));
    ctx.pack([type], p.x, p.z, type === 'mite' ? n * 2 + 2 : n, { ambush: D.ambush });     // mites come in swarms
  }
}

// a Writhe nest: hosts shambling over a carpet of mites, a bladder or two, a sickly glow
function nest(ctx, x, z, big = false) {
  ctx.pack(big ? ['host', 'mite', 'mite', 'host', 'mite', 'bladder', 'mite', 'host', 'mite', 'bladder'] : ['host', 'mite', 'mite', 'mite', 'host', 'bladder', 'mite'],
    x, z, big ? 12 : 7, {});
  ctx.light(x, 2.5, z, 0xb8ff40, big ? 3 : 2, true);
}

export const DISTRICTS = [
  {
    id: 'crown', name: 'The Crown', blurb: 'Corporate towers, holographic adverts and suspended bridges around the Spire',
    kit: { VX_com_a: 3, VX_com_b: 2, VX_com_c: 2, VX_com_ruin: 3, VX_res_b: 1 }, bigLots: .45, lifts: true,
    enemies: { elite: 1, stalker: 4, trooper: 2 }, pack: [2, 4], factionWar: true, loot: 3, danger: 3, packs: 14,
    populate(ctx) {
      fillLots(ctx, this);
      packs(ctx, this, this.packs);
      for (let i = 0; i < 8; i++) { const p = ctx.street(); ctx.prop(i % 2 ? 'VX_holo_a' : 'VX_holo_b', p.x, p.z, ctx.rnd() * 6); }
      for (let i = 0; i < 4; i++) { const p = ctx.street(); ctx.prop('VX_apc', p.x, p.z, ctx.rnd() * 6, { solid: true }); }
      for (let i = 0; i < 3; i++) { const p = ctx.street(); ctx.prop('VX_roadblock', p.x, p.z, ctx.rnd() * 6, { solid: true }); }
      for (let i = 0; i < 4; i++) { const p = ctx.street(); ctx.cache(p.x, p.z, 3, 'Executive vault'); }
    },
  },
  {
    id: 'old', name: 'Old Quarter', a0: 15, a1: 75, blurb: 'Dense apartments, markets and narrow streets',
    kit: { VX_res_a: 3, VX_res_b: 2, VX_res_c: 3, VX_res_ruin: 2, VX_res_market: 2 },
    enemies: { stalker: 1, host: .3 }, pack: [3, 5], loot: 1, danger: 1, packs: 12,
    populate(ctx) {
      fillLots(ctx, this);
      packs(ctx, this, this.packs);
      const n0 = ctx.street(); nest(ctx, n0.x, n0.z);
      // survivors' camp by a metro entrance (the underground mall they moved into)
      const c = ctx.street(); ctx.prop('VX_camp', c.x, c.z, 0); ctx.metro(c.x + 14, c.z);
      ctx.light(c.x, 3, c.z, 0xffae2f, 2.5, true);
      for (let i = 0; i < 6; i++) { const p = ctx.street(); ctx.prop('VX_car_wreck', p.x, p.z, ctx.rnd() * 6, { solid: true }); }
      for (let i = 0; i < 5; i++) { const p = ctx.street(); ctx.cache(p.x, p.z, 1); }
      const m = ctx.street(); ctx.metro(m.x, m.z);
    },
  },
  {
    id: 'commercial', name: 'Commercial District', a0: 75, a1: 135, blurb: 'Malls, hotels and financial towers. Predators wait inside',
    kit: { VX_com_a: 2, VX_com_c: 2, VX_com_ruin: 2, VX_res_market: 2, VX_res_a: 1 }, lifts: true, bigLots: .25,
    enemies: { stalker: 1 }, pack: [2, 4], ambush: true, loot: 2, danger: 2, packs: 12,
    populate(ctx) {
      // the shopping centre: a big round atrium with rare loot, ambush inside
      const mall = ctx.takeLot(l => l.big) || ctx.takeLot();
      if (mall) { ctx.building('VX_com_c', mall.x, mall.z, 0, Math.min(mall.w, mall.d)); ctx.cache(mall.x + mall.w / 2 + 4, mall.z, 4, 'Shopping centre strongroom');
        ctx.pack(['stalker'], mall.x + mall.w / 2 + 8, mall.z + 10, 5, { ambush: true }); }
      // the alien organism bursting through a skyscraper
      const org = ctx.takeLot(l => l.big) || ctx.takeLot();
      if (org) { ctx.building('VX_organism', org.x, org.z, 0); ctx.light(org.x, 60, org.z, 0xb46cff, 6, false); }
      fillLots(ctx, this);
      packs(ctx, this, this.packs);
      // crashed evacuation shuttle and the luggage around it
      const s = ctx.street(); ctx.prop('VX_shuttle', s.x, s.z, ctx.rnd() * 6, { solid: true }); ctx.cache(s.x + 6, s.z + 6, 2, 'Evacuee luggage');
      for (let i = 0; i < 6; i++) { const p = ctx.street(); ctx.prop(i % 2 ? 'VX_holo_a' : 'VX_holo_b', p.x, p.z, ctx.rnd() * 6); }
      const m = ctx.street(); ctx.metro(m.x, m.z);
    },
  },
  {
    id: 'flooded', name: 'Flooded District', a0: 135, a1: 195, blurb: 'Half-sunken streets, flooded metro entrances, things moving under the water',
    kit: { VX_res_ruin: 3, VX_com_ruin: 2, VX_res_c: 1, VX_ind_warehouse: 1 }, emptyLots: .2,
    enemies: { swimmer: 1, host: .5, mite: .4 }, pack: [2, 4], loot: 1, danger: 2, packs: 11,
    populate(ctx) {
      fillLots(ctx, this, lot => ctx.prop('VX_rubble', lot.x, lot.z, ctx.rnd() * 6));
      packs(ctx, this, this.packs);
      // the Writhe breeds in the drowned streets
      for (let i = 0; i < 3; i++) { const p = ctx.street(); nest(ctx, p.x, p.z, i === 0); }
      for (let i = 0; i < 12; i++) { const p = ctx.street(); ctx.shard(p.x, p.z); }
      for (let i = 0; i < 3; i++) { const p = ctx.street(); ctx.metro(p.x, p.z); }
      for (let i = 0; i < 6; i++) { const p = ctx.street(); ctx.prop('VX_car_wreck', p.x, p.z, ctx.rnd() * 6); }
    },
  },
  {
    id: 'research', name: 'Research Sector', a0: 195, a1: 255, blurb: 'Laboratories, containment sites and a hospital whose lights never went out',
    kit: { VX_lab_a: 3, VX_lab_containment: 2, VX_com_c: 1, VX_res_c: 1 },
    enemies: { mutant: 1, host: .6 }, pack: [2, 3], loot: 2, danger: 2, packs: 11,
    populate(ctx) {
      // abandoned hospital: emergency lights, fog closes in, the dead walk out
      const h = ctx.takeLot(l => l.big) || ctx.takeLot();
      if (h) {
        ctx.building('VX_hospital', h.x, h.z, 0);
        for (let i = 0; i < 4; i++) ctx.light(h.x - 20 + i * 12, 4, h.z - 14, 0xff3326, 3, true);
        ctx.trigger(h.x, h.z, 45, () => {
          ctx.horror(h.x, h.z); ctx.pack(['mutant'], h.x, h.z - 18, 3, { awake: true });
          // the patients the parasite took first pour out of the wards
          ctx.pack(['host', 'mite', 'mite', 'host', 'mite', 'mite'], h.x + 8, h.z - 22, 10, { awake: true });
          ctx.pack(['bladder'], h.x - 10, h.z - 24, 2, { awake: true });
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
      fillLots(ctx, this);
      packs(ctx, this, this.packs);
      const m = ctx.street(); ctx.metro(m.x, m.z);
    },
  },
  {
    id: 'military', name: 'Military Zone', a0: 255, a1: 315, blurb: 'Bunkers, checkpoints and walls, still held by armed raiders',
    kit: { VX_mil_bunker: 3, VX_mil_depot: 1, VX_mil_tower: 2, VX_ind_warehouse: 1 }, emptyLots: .15,
    enemies: { trooper: 3, brute: 1 }, pack: [3, 5], loot: 3, danger: 2, packs: 14,
    populate(ctx) {
      // the weapons depot: the best loot outside the Spire
      const d = ctx.takeLot(l => l.big) || ctx.takeLot();
      if (d) { ctx.building('VX_mil_depot', d.x, d.z, 0); ctx.cache(d.x - 12, d.z - 18, 4, 'Weapons depot'); ctx.cache(d.x + 12, d.z - 18, 4, 'Weapons depot');
        ctx.pack(['brute', 'trooper'], d.x, d.z - 26, 5, {}); ctx.pack(['turret'], d.x - 18, d.z - 22, 1, {}); ctx.pack(['turret'], d.x + 18, d.z - 22, 1, {}); }
      fillLots(ctx, this, lot => { ctx.prop('VX_mil_wall', lot.x, lot.z, 0, { solid: true }); ctx.prop('VX_mil_gate', lot.x, lot.z + 14, 0, { solid: true }); });
      packs(ctx, this, this.packs);
      for (let i = 0; i < 6; i++) { const p = ctx.street(); ctx.prop('VX_apc', p.x, p.z, ctx.rnd() * 6, { solid: true }); }
      for (let i = 0; i < 4; i++) { const p = ctx.street(); ctx.prop('VX_roadblock', p.x, p.z, ctx.rnd() * 6, { solid: true }); ctx.pack(['turret'], p.x + 4, p.z + 4, 1, {}); }
      const m = ctx.street(); ctx.metro(m.x, m.z);
    },
  },
  {
    id: 'industrial', name: 'Industrial Spine', a0: 315, a1: 375, blurb: 'Factories, refineries and the heavy things that nest in them',
    kit: { VX_ind_factory: 3, VX_ind_refinery: 2, VX_ind_warehouse: 3, VX_ind_power: 1 }, bigLots: .35,
    enemies: { hulk: 1, stalker: 2, trooper: 2 }, pack: [2, 4], factionWar: true, loot: 2, danger: 2, packs: 12,
    populate(ctx) {
      fillLots(ctx, this);
      packs(ctx, this, this.packs);
      // the frozen train, half out of a collapsed tunnel
      const t = ctx.street(); ctx.prop('VX_train', t.x, t.z, ctx.rnd() * 6, { solid: true }); ctx.prop('VX_bridge_broken', t.x + 30, t.z, 0, { solid: true });
      ctx.cache(t.x, t.z + 6, 2, 'Freight car');
      for (let i = 0; i < 3; i++) { const p = ctx.street(); ctx.pack(['hulk'], p.x, p.z, 1, {}); }
      for (let i = 0; i < 2; i++) { const p = ctx.street(); nest(ctx, p.x, p.z); }
      const m = ctx.street(); ctx.metro(m.x, m.z);
    },
  },
  {
    id: 'outskirts', name: 'The Outskirts', blurb: 'Abandoned settlements, scrapyards and the highways out', sparse: .4, emptyLots: .25,
    kit: { VX_res_c: 2, VX_res_ruin: 1, VX_ind_warehouse: 1 },
    enemies: { trooper: 2, stalker: 2, brute: 1, host: .8 }, pack: [2, 4], factionWar: true, loot: 1, danger: 1, packs: 12,
    populate(ctx) {
      fillLots(ctx, this, lot => { for (let k = 0; k < 6; k++) ctx.prop('VX_car_wreck', lot.x + (ctx.rnd() - .5) * lot.w, lot.z + (ctx.rnd() - .5) * lot.d, ctx.rnd() * 6, { solid: true }); });
      packs(ctx, this, this.packs);
      for (let i = 0; i < 3; i++) { const p = ctx.street(); ctx.prop('VX_camp', p.x, p.z, ctx.rnd() * 6); ctx.cache(p.x + 5, p.z, 1, 'Settlers’ stash'); }
      // a settlement the Writhe has already taken
      const o = ctx.street(); ctx.prop('VX_camp', o.x, o.z, ctx.rnd() * 6); nest(ctx, o.x + 4, o.z + 4, true); ctx.cache(o.x - 5, o.z, 2, 'Overrun stash');
    },
  },
];
