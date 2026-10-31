// Title screen, loading screen, pause menu and every ship-station panel (the old main menu, moved aboard).
import { DESTINATIONS, ARCHETYPES, RARITY, PERKS, SLOT_NAMES, SHADERS, ARMOR_COLORS, GLOW_COLORS, PAINTS, TIPS,
  SKIN_TONES, EYE_COLORS, HAIR_COLORS, SLOT_ORDER, SLOT_LABELS, FACE_LABELS, SLIDER_LABELS, BROW_LABELS, ARMOR_SLOT, armorPiece } from '../game/data.js';
import { weaponStats, makeWeapon, randomArch, rollRarity, xpForLevel, defaultCharacter } from '../game/state.js';

const cap = s => s.charAt(0).toUpperCase() + s.slice(1);
const presetName = id => cap(id.split('_').slice(1).join(' '));

const esc = s => String(s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const $ = id => document.getElementById(id);

export class Menus {
  constructor(game) {
    this.g = game;
    this.panel = $('panel'); this.pauseEl = $('pause'); this.titleEl = $('title'); this.loadEl = $('loading');
    this.open = null; this.tab = null; this.sel = null;
    for (const el of [this.panel, this.pauseEl, this.titleEl]) {
      el.addEventListener('click', e => this.onClick(e));
      el.addEventListener('input', e => this.onInput(e));
      el.addEventListener('change', e => this.onInput(e));
      el.addEventListener('mouseover', e => { if (e.target.closest('button,.card')) this.g.audio.ui('hover'); });
    }
  }

  // ------------------------------------------------------------------ title
  showTitle(hasSave) {
    const el = this.titleEl; el.classList.remove('hidden');
    el.innerHTML = `
      <div class="t-brand">WORLD <b>EX</b></div>
      <div class="t-sub">Frontier Protocol</div>
      <div class="t-menu">
        <button class="t-btn sel" data-act="title-play">${hasSave ? 'Continue' : 'Launch'}</button>
        ${hasSave ? '<button class="t-btn" data-act="title-new">New Game</button>' : ''}
        <button class="t-btn" data-act="title-settings">Settings</button>
        <button class="t-btn" data-act="title-credits">Credits</button>
      </div>
      <div class="t-press">${document.body.classList.contains('touch') ? 'Tap to begin' : 'Click to begin'}</div>
      <div class="t-foot">Build 1.0 · All models made in Blender<br>Three.js r${this.g.THREE_REV}</div>
      <div class="t-overlay"></div>`;
  }
  hideTitle() { this.titleEl.classList.add('hidden'); }

  // ------------------------------------------------------------------ loading
  showLoading(dest, kind) {
    const el = this.loadEl; el.classList.remove('hidden');
    const tip = TIPS[Math.floor(Math.random() * TIPS.length)];
    el.innerHTML = `<div class="l-glyph"></div>
      <div class="l-kind">${esc(kind)}</div><div class="l-dest">${esc(dest.name)}</div>
      <div class="l-desc">${esc(dest.desc || '')}</div>
      <div class="l-bar"><i style="width:0%"></i></div>
      <div class="l-row"><span class="l-step">Initialising</span><span class="l-pct">0%</span></div>
      <div class="l-tip"><b>Field note</b>${esc(tip)}</div>`;
    this.lBar = el.querySelector('.l-bar i'); this.lStep = el.querySelector('.l-step'); this.lPct = el.querySelector('.l-pct');
  }
  loading(p, label) {
    if (!this.lBar) return;
    const pc = Math.round(Math.max(0, Math.min(1, p)) * 100);
    this.lBar.style.width = pc + '%'; this.lPct.textContent = pc + '%';
    if (label) this.lStep.textContent = label;
  }
  hideLoading() { this.loadEl.classList.add('hidden'); this.lBar = null; }

  // ------------------------------------------------------------------ pause
  showPause() {
    const g = this.g, el = this.pauseEl;
    el.classList.remove('hidden');
    const inShip = g.world && g.world.kind === 'ship';
    el.innerHTML = `<div class="ps"><h2>Paused</h2>
      <button class="btn pri" data-act="resume">Resume</button>
      <button class="btn" data-act="pause-inventory">Inventory</button>
      <button class="btn" data-act="pause-settings">Settings</button>
      ${!inShip ? '<button class="btn gold" data-act="orbit">Return to orbit</button>' : ''}
      <button class="btn" data-act="quit">Save &amp; quit to title</button></div>`;
  }
  hidePause() { this.pauseEl.classList.add('hidden'); }

  // ------------------------------------------------------------------ stations
  openStation(id) {
    this.open = id; this.tab = null; this.sel = null;
    this.panel.classList.remove('hidden');
    this.render();
  }
  close() { this.open = null; this.panel.classList.add('hidden'); this.panel.innerHTML = ''; }

  frame(kicker, title, desc, body, tabs = null, foot = '') {
    const g = this.g;
    const t = tabs ? `<div class="pn-tabs">${tabs.map(([k, l]) => `<button class="${this.tab === k ? 'on' : ''}" data-act="tab" data-v="${k}">${l}</button>`).join('')}</div>` : '';
    return `<div class="pn"><div class="pn-k">${esc(kicker)}</div><div class="pn-h">${esc(title)}</div><div class="pn-d">${desc}</div>${t}
      <div class="pn-body">${body}</div><div class="pn-foot"><button class="btn" data-act="leave">Leave station</button><span class="kbd-hint"><kbd>Esc</kbd></span> ${foot}</div></div>
      <div class="wallet">CREDITS<b>${g.save.credits.toLocaleString()}</b><br>ALLOY<b>${g.save.alloy}</b><br>POWER<b>${g.power()}</b></div>`;
  }

  render() {
    const id = this.open; if (!id) return;
    const fn = this['st_' + id]; if (!fn) return;
    const top = this.panel.querySelector('.pn-body') ? this.panel.querySelector('.pn-body').scrollTop : 0;
    this.panel.innerHTML = fn.call(this);
    const b = this.panel.querySelector('.pn-body'); if (b) b.scrollTop = top;
  }

  weaponCard(w, on = false, extra = '') {
    const A = ARCHETYPES[w.arch], R = RARITY[w.rarity];
    return `<div class="card ${on ? 'on' : ''}" style="--rc:${R.color}" data-act="pick" data-v="${w.uid}">
      <div class="pw">${w.power}</div><div class="nm" style="color:${R.color}">${esc(w.name)}</div>
      <div class="ty">${R.name} · ${A.cls ? cap(A.cls) + ' ' : ''}${A.name}</div>
      <div class="pk">${w.perks.map(p => PERKS[p].name).join(' · ') || 'No perks'}</div>${extra}</div>`;
  }

  statBars(w) {
    const S = weaponStats(w), A = ARCHETYPES[w.arch];
    const rows = [['Impact', Math.min(1, S.dmg * (A.pellets || 1) / 250), Math.round(S.dmg * (A.pellets || 1))],
      ['Rate of fire', Math.min(1, S.rpm / 900), Math.round(S.rpm)], ['Range', Math.min(1, S.range / 140), Math.round(S.range)],
      ['Stability', Math.min(1, 1 / (S.spread + .4)), Math.round(100 / (S.spread + 1))], ['Magazine', Math.min(1, S.mag / 50), S.mag],
      ['Reload', Math.min(1, 1.2 / S.reload), S.reload.toFixed(1) + 's']];
    return rows.map(([n, f, v]) => `<div class="stat"><span>${n}</span><div class="sb"><i style="width:${f * 100}%"></i></div><b>${v}</b></div>`).join('') +
      w.perks.map(p => `<div style="margin-top:8px;font-family:var(--body);font-size:13px"><b style="color:var(--gold);font-family:var(--font);letter-spacing:.12em">${PERKS[p].name.toUpperCase()}</b> — ${PERKS[p].desc}</div>`).join('');
  }

  // Captain's chair: navigation (old Play / Teleport / World map)
  st_captain() {
    const g = this.g, pw = g.power();
    const cur = g.save.lastDest || 'earth';
    const cards = DESTINATIONS.filter(d => !d.hidden).map(d => {
      const visited = g.save.stats.visited.includes(d.id);
      const warn = pw < d.power ? `<span style="color:var(--red)"> · recommended power ${d.power}</span>` : '';
      return `<div class="card ${this.sel === d.id ? 'on' : ''}" data-act="dest" data-v="${d.id}">
        <div class="orb" style="background:${d.orb}"></div>
        <div class="info"><div class="ty">${esc(d.kind === 'city' ? 'Home world · city' : d.kind === 'metropolis' ? 'Open world · fallen city' : 'Frontier · endless')}${d.id === cur ? ' · in orbit' : ''}</div>
        <div class="nm" style="font-size:22px">${esc(d.name)}</div><div class="lvl">${esc(d.region)} · Level ${d.level}${warn}</div></div>
        <div style="font-size:11px;letter-spacing:.2em;color:var(--dim)">${visited ? 'CHARTED' : 'UNCHARTED'}</div></div>`;
    }).join('');
    const d = DESTINATIONS.find(x => x.id === this.sel);
    const launch = d ? `<div style="margin-top:16px;border-top:1px solid var(--line);padding-top:14px"><p class="guide">${esc(d.desc)}</p>
      <button class="btn pri" data-act="launch" data-v="${d.id}">Set course · ${esc(d.name)}</button></div>` : '<p class="guide" style="margin-top:14px">Select a destination.</p>';
    return this.frame('Captain’s chair', 'Navigation', 'Plot a jump. Earth is home; every frontier world is generated endlessly in all directions.', `<div class="dest">${cards}</div>${launch}`);
  }

  // Briefing table: contracts + field guide (old Help / About / Home)
  st_briefing() {
    const g = this.g; this.tab = this.tab || 'contracts';
    let body = '';
    if (this.tab === 'contracts') {
      body = g.save.contracts.map((c, i) => `<div class="contract ${c.done ? 'done' : ''}"><div class="row" style="justify-content:space-between">
        <b style="font-size:17px;letter-spacing:.06em">${esc(c.text)}</b><span style="color:var(--gold)">${c.reward} CR</span></div>
        <div style="font-size:12px;letter-spacing:.2em;color:var(--dim);margin-top:4px">${Math.min(c.p, c.n)} / ${c.n}</div>
        <div class="pb"><i style="width:${Math.min(100, c.p / c.n * 100)}%"></i></div>
        ${c.done ? `<button class="btn gold" style="margin-top:10px" data-act="claim" data-v="${i}">Claim reward</button>` : ''}</div>`).join('') +
        `<p class="guide" style="margin-top:12px">Contracts completed: <b>${g.save.contractsDone}</b>. New contracts are posted when you claim one.</p>`;
    } else if (this.tab === 'guide') {
      body = `<p class="guide"><b>Your ship is home.</b> Walk the decks: the <b>captain’s chair</b> on the bridge plots jumps, the <b>armory</b> and <b>gunsmith bench</b> in the hangar manage weapons, the <b>wardrobe pod</b> restyles your armour, the <b>engineering terminal</b> holds settings and the <b>service record</b> keeps your stats.</p>
        <p class="guide"><b>Earth</b> is New Meridian City: the spaceport Quartermaster sells weapons and raiders hold a district to the north-east.</p>
        <p class="guide"><b>Frontier worlds</b> never end. Push out from your landing zone to find raider outposts. Destroy each <b>generator</b> to unlock its supply cache. Outposts further from the landing zone hit harder and pay better.</p>
        <p class="guide"><b>Loot</b> drops as data cores coloured by rarity: <span style="color:var(--r-common)">Common</span>, <span style="color:var(--r-uncommon)">Uncommon</span>, <span style="color:var(--r-rare)">Rare</span>, <span style="color:var(--r-legendary)">Legendary</span>, <span style="color:var(--r-exotic)">Exotic</span>. Your <b>power</b> is the average of your equipped weapons.</p>
        <p class="guide"><b>Shields</b> recharge a few seconds after you stop taking fire. Precision hits on heads and glowing weak points deal bonus damage.</p>`;
    } else body = this.controlsHtml();
    return this.frame('Briefing table', 'Contracts', 'Bounties posted by the city council and the frontier relays.', body, [['contracts', 'Contracts'], ['guide', 'Field guide'], ['controls', 'Controls']]);
  }

  controlsHtml() {
    const K = [['W A S D', 'Move'], ['Shift', 'Run / boost in car'], ['T', 'Switch first / third person'], ['Mouse', 'Look / aim'], ['Space', 'Jump / handbrake'], ['E', 'Interact, enter / exit car'], ['Left mouse', 'Fire'], ['Right mouse', 'Aim down sights'], ['R', 'Reload'], ['1 2 3 / Wheel', 'Switch weapon'], ['V', 'Summon hover car'], ['I / Tab', 'Inventory'], ['Esc', 'Pause / leave station'], ['F3', 'FPS counter']];
    return `<div class="keys">${K.map(([k, v]) => `<b>${k}</b><span>${v}</span>`).join('')}</div>`;
  }

  // Wardrobe pod: character creator (body, face, hair) and clothing slots
  st_wardrobe() {
    const c = this.g.save.character, av = this.g.player.avatar;
    if (!['body', 'face', 'hair', 'wear', 'lights'].includes(this.tab)) this.tab = 'face';
    const label = s => `<div class="ty" style="letter-spacing:.3em;color:var(--dim);font-size:12px;margin-top:6px">${s}</div>`;
    const swatches = (act, list, cur, k = '', orig = false) => `<div class="swatches">${orig ? `<div class="sw ${!cur ? 'on' : ''}" title="Original" style="background:linear-gradient(135deg,#fff 45%,#c33 46%,#c33 54%,#fff 55%)" data-act="${act}" data-k="${k}" data-v=""></div>` : ''}${list.map(h => `<div class="sw ${cur === h ? 'on' : ''}" style="background:${h}" data-act="${act}" data-k="${k}" data-v="${h}"></div>`).join('')}</div>`;
    const btns = (act, list, cur, k = '') => `<div class="row" style="margin:8px 0 14px;flex-wrap:wrap">${list.map(([id, name]) => `<button class="btn ${cur === id ? 'pri' : ''}" data-act="${act}" data-k="${k}" data-v="${id}">${esc(name)}</button>`).join('')}</div>`;
    const meta = av.meta || {}, M = meta.morphs || { groups: {}, sliders: [] };
    let body = '';
    if (this.tab === 'body') {
      body = `${label('FRAME')}${btns('body', [['female', 'Female'], ['male', 'Male']], c.body)}
        ${label('SKIN TONE')}${swatches('skin', SKIN_TONES, c.skin)}
        <div class="row" style="margin-top:16px"><button class="btn" data-act="charreset">Reset look to default</button></div>`;
    } else if (this.tab === 'face') {
      for (const [g, list] of Object.entries(M.groups)) {
        body += label((FACE_LABELS[g] || g).toUpperCase()) + btns('face', [['', 'Default'], ...list.map(n => [n, presetName(n)])], (c.face && c.face[g]) || '', g);
      }
      body += label('EYE COLOUR') + swatches('eyecol', EYE_COLORS, c.eyes);
      body += label('BROWS') + btns('brow', BROW_LABELS.map((n, i) => [String(i), n]), String(c.brow | 0));
      body += label('FINE TUNING') + M.sliders.map(n => `<div class="set"><span>${SLIDER_LABELS[n] || n}</span><input type="range" min="-1" max="1" step=".05" value="${(c.sliders && c.sliders[n]) || 0}" data-slider="${n}"><span class="v">${(+((c.sliders && c.sliders[n]) || 0)).toFixed(2)}</span></div>`).join('');
    } else if (this.tab === 'hair') {
      const hair = Object.entries(av.wardrobe.hair || {}).map(([id, d]) => [id, d.label]);
      body = `${label('STYLE')}${btns('wear', [['none', 'Shaved'], ...hair], (c.wear || {}).hair, 'hair')}
        ${label('COLOUR')}${swatches('haircol', HAIR_COLORS, c.hairColor)}`;
    } else if (this.tab === 'wear') {
      for (const slot of SLOT_ORDER) {
        const items = Object.entries(av.wardrobe[slot] || {}).map(([id, d]) => [id, d.label]);
        const cur = (c.wear || {})[slot] || 'none';
        if (!items.length && slot.startsWith('under')) continue;
        body += label((SLOT_LABELS[slot] || slot).toUpperCase());
        if (!items.length) { if (!slot.startsWith('under')) body += `<p class="guide" style="margin:6px 0 12px">No ${(SLOT_LABELS[slot] || slot).toLowerCase()} yet — more pieces are coming.</p>`; continue; }
        if (av.isLocked(slot)) { body += `<p class="guide" style="margin:6px 0 4px">Always worn — pick a colour.</p>`; body += swatches('tint', ARMOR_COLORS, (c.tints || {})[slot], slot, true); continue; }
        body += btns('wear', [['none', 'None'], ...items], cur, slot);
        if (cur !== 'none') body += swatches('tint', ARMOR_COLORS, (c.tints || {})[slot], slot, true);
      }
    } else {
      body = `${label('ARMOUR LIGHTS')}${swatches('color', GLOW_COLORS, c.glow, 'glow', true)}`;
    }
    const tabs = [['body', 'Body'], ['face', 'Face'], ['hair', 'Hair'], ['wear', 'Clothing'], ['lights', 'Lights']];
    return this.frame('Wardrobe pod', 'Appearance', 'Shape your face, pick hair and clothing piece by piece. Drag to turn around.', body, tabs);
  }

  // Engineering terminal (old Settings + Controls)
  st_engineering() {
    const s = this.g.save.settings; this.tab = this.tab || 'graphics';
    let body = '';
    const range = (k, min, max, step, fmt) => `<div class="set"><span>${k[1]}</span><input type="range" min="${min}" max="${max}" step="${step}" value="${s[k[0]]}" data-set="${k[0]}"><span class="v">${fmt(s[k[0]])}</span></div>`;
    const tog = (k, l) => `<div class="set"><span>${l}</span><button class="btn ${s[k] ? 'pri' : ''}" data-act="toggle" data-v="${k}" style="justify-self:start">${s[k] ? 'On' : 'Off'}</button><span></span></div>`;
    if (this.tab === 'graphics') {
      body = `<div class="set"><span>Quality preset</span><select data-set="quality">${['low', 'medium', 'high'].map(q => `<option ${s.quality === q ? 'selected' : ''} value="${q}">${q}</option>`).join('')}</select><span></span></div>
        ${range(['resScale', 'Render scale'], .5, 1, .05, v => Math.round(v * 100) + '%')}
        ${tog('dynamicRes', 'Hold 60 fps (dynamic res)')}
        <div class="set"><span>Camera</span><div class="row"><button class="btn ${s.view !== 'third' ? 'pri' : ''}" data-act="view" data-v="first">First person</button><button class="btn ${s.view === 'third' ? 'pri' : ''}" data-act="view" data-v="third">Third person</button></div><span></span></div>
        ${range(['fov', 'Field of view'], 55, 95, 1, v => v)}
        ${tog('showFps', 'Show FPS')}
        <p class="guide" style="margin-top:12px">Low: no bloom, 1K shadows. Medium: bloom, FXAA, 2K shadows. High: 4K shadows and 1.5× pixel density.</p>`;
    } else if (this.tab === 'audio') {
      body = range(['master', 'Master'], 0, 1, .05, v => Math.round(v * 100)) + range(['music', 'Music'], 0, 1, .05, v => Math.round(v * 100)) + range(['sfx', 'Effects'], 0, 1, .05, v => Math.round(v * 100)) + tog('muted', 'Mute all');
    } else if (this.tab === 'controls') {
      body = range(['sens', 'Mouse sensitivity'], .2, 3, .05, v => v.toFixed(2)) + tog('invertY', 'Invert look') + '<div style="height:12px"></div>' + this.controlsHtml();
    } else {
      body = `<p class="guide">Erase your service record, inventory and progress and begin again.</p><button class="btn" data-act="wipe" style="border-color:var(--red);color:var(--red)">Reset save data</button>`;
    }
    return this.frame('Engineering terminal', 'Ship systems', 'Graphics, audio and control settings. Changes are saved automatically.', body, [['graphics', 'Graphics'], ['audio', 'Audio'], ['controls', 'Controls'], ['data', 'Data']]);
  }

  // Service record (old Stats)
  st_record() {
    const g = this.g, s = g.save.stats;
    const acc = s.shots ? Math.round(s.hits / s.shots * 100) : 0;
    const t = Math.floor(s.time / 60);
    const cell = (v, l) => `<div><b>${v}</b><small>${l}</small></div>`;
    const body = `<div class="big-stat">${cell(g.save.level, 'Level')}${cell(g.power(), 'Power')}${cell(g.save.inventory.length, 'Weapons owned')}
      ${cell(s.kills, 'Hostiles defeated')}${cell(s.precision, 'Precision kills')}${cell(s.deaths, 'Times fallen')}
      ${cell(acc + '%', 'Accuracy')}${cell(s.generators, 'Generators destroyed')}${cell(s.caches, 'Caches opened')}
      ${cell(s.brutes, 'Brutes defeated')}${cell(s.drones, 'Drones downed')}${cell((s.distance / 1000).toFixed(1) + ' km', 'Walked')}
      ${cell((s.carDistance / 1000).toFixed(1) + ' km', 'Driven')}${cell(Math.floor(t / 60) + 'h ' + (t % 60) + 'm', 'Time in service')}${cell(s.visited.filter(v => v !== 'vanthos_metro').length + ' / ' + DESTINATIONS.filter(d => !d.hidden).length, 'Worlds charted')}</div>
      <div class="bar xp" style="margin-top:18px;height:4px;transform:none"><i style="width:${g.save.xp / xpForLevel(g.save.level) * 100}%"></i></div>
      <div style="font-size:12px;letter-spacing:.2em;color:var(--dim);margin-top:6px">${g.save.xp} / ${xpForLevel(g.save.level)} XP TO LEVEL ${g.save.level + 1}</div>`;
    return this.frame('Service record', 'Statistics', 'Everything you have done since you took command.', body);
  }

  // Armory rack (old Arsenal)
  st_armory() {
    const g = this.g, sv = g.save;
    this.tab = this.tab || '0';
    const slot = +this.tab;
    const cur = g.weapons.equipped(slot);
    const list = sv.inventory.filter(w => ARCHETYPES[w.arch].slot === slot).sort((a, b) => b.power - a.power || b.rarity - a.rarity);
    const sel = sv.inventory.find(w => w.uid === this.sel) || cur;
    const body = `<div class="grid">${list.map(w => this.weaponCard(w, sv.equipped.includes(w.uid), sv.equipped.includes(w.uid) ? '<div style="position:absolute;right:12px;bottom:10px;font-size:10px;letter-spacing:.3em;color:var(--gold)">EQUIPPED</div>' : '')).join('') || '<p class="guide">No weapons for this slot yet.</p>'}</div>
      ${sel ? `<div style="margin-top:18px;border-top:1px solid var(--line);padding-top:14px"><div class="nm" style="font:700 24px var(--font);color:${RARITY[sel.rarity].color}">${esc(sel.name)}</div>
        <div class="ty" style="letter-spacing:.24em;color:var(--dim);font-size:12px;margin-bottom:10px">${RARITY[sel.rarity].name} ${ARCHETYPES[sel.arch].name} · Power ${sel.power}</div>
        ${this.statBars(sel)}
        <div class="row" style="margin-top:14px">${sv.equipped.includes(sel.uid) ? '<button class="btn" disabled>Equipped</button>' : `<button class="btn pri" data-act="equip" data-v="${sel.uid}">Equip to ${SLOT_NAMES[slot]}</button>`}</div></div>` : ''}`;
    return this.frame('Armory', 'Loadout', 'Primary: rifles. Special: hand cannons, shotguns, snipers. Heavy: rockets.', body, [['0', 'Primary'], ['1', 'Special'], ['2', 'Heavy']]);
  }

  // Inventory (I / Tab, anywhere): everything you carry and wear. Changing the loadout happens aboard the ship.
  st_inventory() {
    const g = this.g, sv = g.save, aboard = g.world && g.world.kind === 'ship';
    if (!['weapons', 'armor', 'missions', 'overview'].includes(this.tab)) this.tab = 'weapons';
    const label = s => `<div class="ty" style="letter-spacing:.3em;color:var(--dim);font-size:12px;margin:14px 0 8px">${s}</div>`;
    let body = '';
    if (this.tab === 'weapons') {
      const f = this.filter == null ? -1 : this.filter;
      const cf = this.clsFilter || 'all';
      const list = sv.inventory.filter(w => (f < 0 || ARCHETYPES[w.arch].slot === f) && (cf === 'all' || (ARCHETYPES[w.arch].cls || 'energy') === cf))
        .sort((a, b) => (sv.equipped.includes(b.uid) - sv.equipped.includes(a.uid)) || b.power - a.power || b.rarity - a.rarity);
      const sel = sv.inventory.find(w => w.uid === this.sel) || g.weapons.equipped(g.weapons.slot) || list[0];
      if (sel) this.sel = sel.uid;
      g.inspect && g.inspect.setWeapon(sel);
      const chips = [[-1, 'All'], [0, 'Primary'], [1, 'Special'], [2, 'Heavy']].map(([k, n]) =>
        `<button class="btn ${f === k ? 'pri' : ''}" data-act="invfilter" data-v="${k}">${n} · ${k < 0 ? sv.inventory.length : sv.inventory.filter(w => ARCHETYPES[w.arch].slot === k).length}</button>`).join('');
      const classes = [...new Set(Object.values(ARCHETYPES).map(a => a.cls).filter(Boolean))];
      const cchips = classes.length > 1 ? ['all', ...classes].map(k => `<button class="btn ${cf === k ? 'pri' : ''}" data-act="invcls" data-v="${k}">${k === 'all' ? 'Every class' : cap(k)}</button>`).join('') : '';
      body = `<div class="row" style="flex-wrap:wrap;margin-bottom:8px">${chips}</div>${cchips ? `<div class="row" style="flex-wrap:wrap;margin-bottom:10px">${cchips}</div>` : ''}`;
      if (sel) {
        const A = ARCHETYPES[sel.arch], R = RARITY[sel.rarity], eq = sv.equipped.includes(sel.uid), am = g.weapons.ammoOf(sel);
        const sh = SHADERS.find(x => x.id === sel.shader) || SHADERS[0];
        body += `<div class="inv-sel"><div class="nm" style="font:700 26px var(--font);color:${R.color}">${esc(sel.name)}</div>
          <div class="ty" style="letter-spacing:.24em;color:var(--dim);font-size:12px;margin-bottom:10px">${R.name} ${A.cls ? cap(A.cls) + ' ' : ''}${A.name} · ${SLOT_NAMES[A.slot]} slot · Power ${sel.power}${eq ? ' · <span style="color:var(--gold)">EQUIPPED</span>' : ''}</div>
          ${this.statBars(sel)}
          <div class="inv-facts"><span>Ammo<b>${am.mag} / ${am.reserve}</b></span><span>Precision<b>×${A.crit}</b></span><span>Fire mode<b>${A.burst ? A.burst + '-round burst' : A.auto ? 'Automatic' : 'Semi-auto'}</b></span><span>Finish<b>${esc(sh.name)}</b></span></div>
          <div class="row" style="margin-top:12px">${eq ? '<button class="btn" disabled>Equipped</button>' : aboard
            ? `<button class="btn pri" data-act="equip" data-v="${sel.uid}">Equip to ${SLOT_NAMES[A.slot]}</button>`
            : '<button class="btn" disabled>Equip aboard the ship</button>'}</div></div>`;
      }
      body += label('CARRIED (' + list.length + ')') + `<div class="grid">${list.map(w => this.weaponCard(w, w.uid === this.sel, sv.equipped.includes(w.uid) ? '<div style="position:absolute;right:12px;bottom:10px;font-size:10px;letter-spacing:.3em;color:var(--gold)">EQUIPPED</div>' : '')).join('') || '<p class="guide">Nothing here yet.</p>'}</div>`;
    } else if (this.tab === 'armor') {
      g.inspect && g.inspect.setCharacter();
      const A = g.armor, wr = g.player.avatar.wardrobe || {};
      body = `<div class="big-stat">${[[A.armor, 'Armour rating'], [Math.round(A.resist * 100) + '%', 'Damage resisted'], [Math.round(A.mobility) + '%', 'Mobility'],
        [g.player.maxShield, 'Shield capacity'], [g.player.maxHealth, 'Health']].map(([v, l]) => `<div><b>${v}</b><small>${l}</small></div>`).join('')}</div>`;
      body += label('WORN');
      for (const slot of Object.keys(ARMOR_SLOT)) {
        if (!wr[slot] || !Object.keys(wr[slot]).length) continue;
        const id = (sv.character.wear || {})[slot], d = id && id !== 'none' ? wr[slot][id] : null;
        const a = d ? armorPiece(slot, id, d.label) : null;
        body += `<div class="inv-row"><span>${esc(SLOT_LABELS[slot] || slot)}</span><b>${d ? esc(d.label) : '<i style="color:var(--dim)">Nothing</i>'}</b>
          <em>${a ? (a.heavy ? 'Armoured · ' : 'Light · ') + '+' + a.armor : ''}</em></div>`;
      }
      body += `<p class="guide" style="margin-top:14px">${aboard ? 'Change armour and clothing at the <b>Wardrobe pod</b> in the commons.' : 'Armour is changed at the <b>Wardrobe pod</b> aboard the ship.'} Armoured pieces resist more damage but slow you slightly. Drag the picture to turn around.</p>`;
    } else if (this.tab === 'missions') {
      g.inspect && g.inspect.clear();
      const obj = (g.world && g.world.objectives ? g.world.objectives() : []) || [];
      body = label('CURRENT · ' + esc((g.world && g.world.name) || '')) + (obj.map(o => `<div class="contract"><b style="font-size:16px;letter-spacing:.06em">${esc(o.text)}</b>
        ${o.sub ? `<div style="font-size:13px;color:var(--dim);margin-top:4px;font-family:var(--body)">${esc(o.sub)}</div>` : ''}</div>`).join('') || '<p class="guide">Nothing pressing here. Explore.</p>');
      body += label('CONTRACTS') + sv.contracts.map(c => `<div class="contract ${c.done ? 'done' : ''}"><div class="row" style="justify-content:space-between">
        <b style="font-size:16px;letter-spacing:.06em">${esc(c.text)}</b><span style="color:var(--gold)">${c.reward} CR</span></div>
        <div style="font-size:12px;letter-spacing:.2em;color:var(--dim);margin-top:4px">${Math.min(c.p, c.n)} / ${c.n}${c.done ? ' · READY — CLAIM AT THE BRIEFING TABLE' : ''}</div>
        <div class="pb"><i style="width:${Math.min(100, c.p / c.n * 100)}%"></i></div></div>`).join('');
      const vs = sv.vanthos;
      if (vs) body += label('VANTHOS') + `<div class="inv-row"><span>Memory shards</span><b>${(vs.shards || []).length}</b><em></em></div><div class="inv-row"><span>Guardians defeated</span><b>${(vs.bosses || []).length}</b><em></em></div>`;
      body += label('WORLDS') + DESTINATIONS.filter(d => !d.hidden).map(d => `<div class="inv-row"><span>${esc(d.region)}</span><b>${esc(d.name)}</b><em>${sv.stats.visited.includes(d.id) ? 'Charted · level ' + d.level : 'Uncharted'}</em></div>`).join('');
    } else {
      g.inspect && g.inspect.clear();
      const S = sv.stats;
      body = `<div class="big-stat">${[[sv.level, 'Level'], [g.power(), 'Power'], [sv.credits.toLocaleString(), 'Credits'], [sv.alloy, 'Alloy'],
        [sv.inventory.length, 'Weapons'], [g.armor.armor, 'Armour'], [S.kills, 'Hostiles defeated'], [S.caches, 'Caches opened']].map(([v, l]) => `<div><b>${v}</b><small>${l}</small></div>`).join('')}</div>
        ${label('LOADOUT')}${[0, 1, 2].map(i => { const w = g.weapons.equipped(i); return `<div class="inv-row"><span>${SLOT_NAMES[i]}</span><b style="color:${w ? RARITY[w.rarity].color : 'var(--dim)'}">${w ? esc(w.name) : 'Empty'}</b><em>${w ? ARCHETYPES[w.arch].name + ' · ' + w.power : ''}</em></div>`; }).join('')}
        <p class="guide" style="margin-top:14px">Weapons are swapped at the <b>Armory</b> and upgraded at the <b>Gunsmith bench</b> in the ship's hangar.</p>`;
    }
    const stage = this.tab === 'overview' || this.tab === 'missions' ? '' : '<div class="inv-stage"><i></i></div>';
    return this.frame('Inventory', aboard ? 'Aboard the Wayfarer' : 'Field inventory', 'Your weapons, armour and gear. <kbd>I</kbd> or <kbd>Tab</kbd> to close.', body,
      [['weapons', 'Weapons'], ['armor', 'Armour'], ['missions', 'Missions'], ['overview', 'Overview']]) + stage;
  }

  // Gunsmith bench (old Gunsmith)
  st_gunsmith() {
    const g = this.g, sv = g.save;
    const list = [...sv.inventory].sort((a, b) => b.power - a.power);
    const sel = sv.inventory.find(w => w.uid === this.sel) || g.weapons.equipped(0) || list[0];
    if (sel) this.sel = sel.uid;
    const cost = sel ? { cr: 150 + sel.power * 6, al: 4 + Math.floor(sel.power / 15) } : null;
    const cap = g.power() + 20 + sv.level * 2;
    const eq = sel && sv.equipped.includes(sel.uid);
    const body = sel ? `<div class="nm" style="font:700 26px var(--font);color:${RARITY[sel.rarity].color}">${esc(sel.name)}</div>
      <div class="ty" style="letter-spacing:.24em;color:var(--dim);font-size:12px;margin-bottom:12px">${RARITY[sel.rarity].name} ${ARCHETYPES[sel.arch].name} · Power ${sel.power}</div>
      ${this.statBars(sel)}
      <div class="row" style="margin:16px 0">
        <button class="btn pri" data-act="upgrade" ${sv.credits < cost.cr || sv.alloy < cost.al || sel.power >= cap ? 'disabled' : ''}>Infuse +5 power · ${cost.cr} CR · ${cost.al} alloy</button>
        <button class="btn" data-act="dismantle" ${eq ? 'disabled' : ''}>Dismantle (+${2 + sel.rarity * 3} alloy)</button></div>
      ${sel.power >= cap ? `<p class="guide">Infusion cap reached (${cap}). Raise your level or power to push further.</p>` : ''}
      <div class="ty" style="letter-spacing:.3em;color:var(--dim);font-size:12px">SHADER</div>
      <div class="swatches">${SHADERS.map(s => `<div class="sw ${sel.shader === s.id ? 'on' : ''}" title="${s.name}" style="background:${s.body}" data-act="shader" data-v="${s.id}"></div>`).join('')}</div>
      <div class="ty" style="letter-spacing:.3em;color:var(--dim);font-size:12px;margin:10px 0">INVENTORY (${sv.inventory.length})</div>
      <div class="grid">${list.map(w => this.weaponCard(w, w.uid === sel.uid)).join('')}</div>` : '<p class="guide">No weapons.</p>';
    return this.frame('Gunsmith bench', 'Weapon foundry', 'Infuse power with credits and alloy, apply shaders, or break down spares for alloy.', body);
  }

  // Hangar car (garage)
  st_garage() {
    const sv = this.g.save;
    const body = `<div class="ty" style="letter-spacing:.3em;color:var(--dim);font-size:12px">CHASSIS</div>
      <div class="row" style="margin:8px 0 16px"><button class="btn ${sv.car.model === 'car_sport' ? 'pri' : ''}" data-act="carmodel" data-v="car_sport">Vanta GT · sport</button>
      <button class="btn ${sv.car.model === 'car_utility' ? 'pri' : ''}" data-act="carmodel" data-v="car_utility">Mule Hauler · armoured</button></div>
      <div class="ty" style="letter-spacing:.3em;color:var(--dim);font-size:12px">PAINT</div>
      <div class="swatches">${PAINTS.map(h => `<div class="sw ${sv.car.paint === h ? 'on' : ''}" style="background:${h}" data-act="paint" data-v="${h}"></div>`).join('')}</div>
      <p class="guide">Press <b>V</b> on Earth or any frontier world to have the ship drop your car beside you.</p>`;
    return this.frame('Hangar bay', 'Garage', 'Your hover car rides down with every drop.', body);
  }

  // Earth spaceport vendor
  st_vendor() {
    const g = this.g;
    if (!this.stock || this.stockLevel !== g.save.level) {
      this.stockLevel = g.save.level;
      this.stock = [0, 0, 1, 1, 2].map((slot, i) => { const w = makeWeapon(randomArch(Math.random, slot), Math.max(1, rollRarity(.12)), g.power() + 2 + Math.floor(Math.random() * 4)); w.price = 300 + w.rarity * 350 + w.power * 4; return w; });
    }
    const body = `<div class="grid">${this.stock.map(w => this.weaponCard(w, this.sel === w.uid, `<div style="margin-top:8px;color:var(--gold);font-weight:700">${w.sold ? 'SOLD' : w.price + ' CR'}</div>`)).join('')}</div>
      ${(() => { const w = this.stock.find(x => x.uid === this.sel); return w ? `<div style="margin-top:16px">${this.statBars(w)}<div class="row" style="margin-top:12px"><button class="btn pri" data-act="buy" ${w.sold || g.save.credits < w.price ? 'disabled' : ''}>Buy · ${w.price} CR</button></div></div>` : ''; })()}
      <div class="row" style="margin-top:16px"><button class="btn" data-act="buyammo" ${g.save.credits < 100 ? 'disabled' : ''}>Ammo synthesis · 100 CR</button><button class="btn" data-act="buyalloy" ${g.save.credits < 250 ? 'disabled' : ''}>10 alloy · 250 CR</button></div>`;
    return this.frame('Spaceport', 'Quartermaster Okafor', '“Everything on this rack fires straight. Mostly.”', body);
  }

  // ------------------------------------------------------------------ events
  onInput(e) {
    const sl = e.target.dataset.slider;
    if (sl) {
      const c = this.g.save.character; (c.sliders = c.sliders || {})[sl] = +e.target.value;
      this.g.player.avatar.setFace(c.face, c.sliders);
      const v = e.target.parentElement.querySelector('.v'); if (v) v.textContent = (+e.target.value).toFixed(2);
      return;
    }
    const k = e.target.dataset.set; if (!k) return;
    const s = this.g.save.settings;
    s[k] = e.target.type === 'range' ? +e.target.value : e.target.value;
    this.g.applySettings(k);
    if (e.type === 'change') this.render();
    else { const v = e.target.parentElement.querySelector('.v'); if (v && e.target.type === 'range') v.textContent = (+e.target.value).toFixed(e.target.step < 1 ? 2 : 0); }
  }

  onClick(e) {
    const t = e.target.closest('[data-act]'); if (!t) return;
    const g = this.g, sv = g.save, act = t.dataset.act, v = t.dataset.v;
    g.audio.ui('click');
    switch (act) {
      case 'title-play': g.startGame(false); return;
      case 'title-new':
        // two-step confirm inside the page (browser dialogs are not available everywhere)
        if (t.dataset.armed) { g.startGame(true); return; }
        t.dataset.armed = '1'; t.textContent = 'Click again to erase progress'; return;
      case 'title-settings': g.titleSettings(); return;
      case 'title-credits': g.titleCredits(); return;
      case 'resume': g.resume(); return;
      case 'leave': g.closeStation(); return;
      case 'pause-inventory': this.hidePause(); g.paused = false; g.openInventory(); return;
      case 'pause-settings': this.hidePause(); g.paused = false; g.openStationPanelOnly('engineering'); return;
      case 'orbit': this.hidePause(); g.paused = false; g.travel('ship'); return;
      case 'quit': g.quitToTitle(); return;
      case 'tab': this.tab = v; this.sel = null; if (this.open === 'wardrobe') g.wardrobeFocus(v); break;
      case 'dest': this.sel = v; break;
      case 'launch': g.audio.ui('confirm'); g.closeStation(); g.travel(v); return;
      case 'claim': g.claimContract(+v); break;
      case 'body':
        if (sv.character.body !== v) sv.character = defaultCharacter(v);
        g.player.setBody(v); g.player.avatar.play('IdleRelaxed', 0); g.placeInWardrobe(); g.setAvatarLayer(); g.weapons.refreshModel(); break;
      case 'charreset': sv.character = defaultCharacter(sv.character.body); g.player.applyLook(); break;
      case 'skin': sv.character.skin = v; g.player.applyLook(); break;
      case 'eyecol': sv.character.eyes = v; g.player.applyLook(); break;
      case 'haircol': sv.character.hairColor = v; g.player.applyLook(); break;
      case 'brow': sv.character.brow = +v; g.player.applyLook(); break;
      case 'face': (sv.character.face = sv.character.face || {})[t.dataset.k] = v || null; g.player.applyLook(); break;
      case 'wear': if (v === 'none' && g.player.avatar.isLocked(t.dataset.k)) break; (sv.character.wear = sv.character.wear || {})[t.dataset.k] = v; g.player.applyLook(); g.weapons.refreshModel(); break;
      case 'tint': (sv.character.tints = sv.character.tints || {})[t.dataset.k] = v || null; g.player.applyLook(); break;
      case 'color': sv.character[t.dataset.k] = v || null; g.player.applyLook(); break;
      case 'toggle': sv.settings[v] = !sv.settings[v]; g.applySettings(v); break;
      case 'view': if ((sv.settings.view === 'third') !== (v === 'third')) g.toggleView(); break;
      case 'wipe':
        if (t.dataset.armed) { g.wipe(); return; }
        t.dataset.armed = '1'; t.textContent = 'Click again to erase everything'; return;
      case 'pick': this.sel = v; break;
      case 'invfilter': this.filter = +v; this.sel = null; break;
      case 'invcls': this.clsFilter = v; this.sel = null; break;
      case 'equip': {
        if (!g.world || g.world.kind !== 'ship') break;
        const w = sv.inventory.find(x => x.uid === v); const slot = ARCHETYPES[w.arch].slot;
        sv.equipped[slot] = w.uid; g.weapons.refreshModel(); g.audio.ui('confirm'); g.onLoadoutChanged(); break;
      }
      case 'upgrade': {
        const w = sv.inventory.find(x => x.uid === this.sel); const cost = { cr: 150 + w.power * 6, al: 4 + Math.floor(w.power / 15) };
        if (sv.credits >= cost.cr && sv.alloy >= cost.al) { sv.credits -= cost.cr; sv.alloy -= cost.al; w.power += 5; g.audio.ui('confirm'); g.onLoadoutChanged(); }
        break;
      }
      case 'dismantle': {
        const i = sv.inventory.findIndex(x => x.uid === this.sel); if (i < 0 || sv.equipped.includes(this.sel)) break;
        sv.alloy += 2 + sv.inventory[i].rarity * 3; sv.inventory.splice(i, 1); this.sel = null; g.audio.ui('back'); g.onLoadoutChanged(); break;
      }
      case 'shader': { const w = sv.inventory.find(x => x.uid === this.sel); if (w) { w.shader = v; g.weapons.refreshModel(); g.onLoadoutChanged(); } break; }
      case 'carmodel': sv.car.model = v; g.world.refreshCar && g.world.refreshCar(); break;
      case 'paint': sv.car.paint = v; g.world.refreshCar && g.world.refreshCar(); break;
      case 'buy': {
        const w = this.stock.find(x => x.uid === this.sel);
        if (w && !w.sold && sv.credits >= w.price) { sv.credits -= w.price; w.sold = true; const c = { ...w }; delete c.price; delete c.sold; g.addWeapon(c); g.audio.pickup(w.rarity); g.hud.feed('Purchased ' + w.name, RARITY[w.rarity].color); }
        break;
      }
      case 'buyammo': if (sv.credits >= 100) { sv.credits -= 100; g.weapons.refill(); g.audio.ammo(); g.hud.feed('Ammunition restocked'); } break;
      case 'buyalloy': if (sv.credits >= 250) { sv.credits -= 250; sv.alloy += 10; g.audio.ui('confirm'); } break;
    }
    g.persist();
    this.render();
  }
}
