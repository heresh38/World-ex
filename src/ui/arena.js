// Shellbreak UI (src/worlds/arena/): squad score bar and clock, a compact elimination feed, the elimination / assist
// confirm under the crosshair, squadmate name tags, the death card with the re-sleeve timer, the scoreboard (hold Tab,
// I toggles, a touch button), the loadout screen (primary / special / heavy from the inventory) and the end screen with
// the result, the player's numbers and the rewards. Own DOM + styles; pointer events only on the panels and buttons.
import * as THREE from 'three';
import { ARCHETYPES, RARITY, SLOT_NAMES, PERKS } from '../game/data.js';
import { TEAM_COL, DIFFICULTY } from '../game/bots.js';
import { MODE_NAME } from '../worlds/arena/match.js';

const esc = s => String(s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const mmss = t => { t = Math.max(0, Math.ceil(t)); return Math.floor(t / 60) + ':' + String(t % 60).padStart(2, '0'); };
const _v = new THREE.Vector3();

const CSS = `
#arena{position:fixed;inset:0;pointer-events:none;z-index:3;font-family:var(--font);color:var(--bone)}
#arena .hidden{display:none!important}
.ar-top{position:absolute;left:50%;top:50px;transform:translateX(-50%);display:flex;align-items:stretch;gap:10px;text-shadow:0 1px 3px #000}
.ar-sq{width:150px;display:flex;flex-direction:column;gap:3px}
.ar-sq b{font:700 30px/1 var(--font);letter-spacing:.04em}
.ar-sq small{font-size:10px;letter-spacing:.32em;opacity:.75}
.ar-sq .ab{height:4px;background:rgba(255,255,255,.12);position:relative;overflow:hidden}.ar-sq .ab i{position:absolute;top:0;bottom:0;transition:width .3s}
.ar-sq.ally{text-align:right;align-items:flex-end}.ar-sq.ally b{color:${TEAM_COL.ally}}.ar-sq.ally .ab i{right:0;background:${TEAM_COL.ally}}.ar-sq.ally .ab{width:100%}
.ar-sq.enemy b{color:${TEAM_COL.enemy}}.ar-sq.enemy .ab i{left:0;background:${TEAM_COL.enemy}}.ar-sq.enemy .ab{width:100%}
.ar-clock{min-width:96px;text-align:center;font:700 22px/1 var(--font);letter-spacing:.08em;padding:4px 10px;background:rgba(5,7,12,.55);border:1px solid rgba(236,230,216,.14)}
.ar-clock small{display:block;font-size:9px;letter-spacing:.3em;color:var(--gold);margin-top:5px;font-weight:600}
.ar-clock.low{color:var(--red)}
.ar-feed{position:absolute;right:30px;top:238px;width:330px;display:flex;flex-direction:column;align-items:flex-end;gap:3px}
.ar-feed div{font-size:13px;letter-spacing:.05em;padding:3px 10px;background:linear-gradient(270deg,rgba(5,7,12,.7),rgba(5,7,12,.15));white-space:nowrap;animation:arfeed .2s ease-out}
.ar-feed div.me{background:linear-gradient(270deg,rgba(227,194,108,.35),rgba(5,7,12,.15))}
.ar-feed em{font-style:normal;font-size:11px;opacity:.6;margin:0 7px;letter-spacing:.08em}
.ar-feed .a{color:${TEAM_COL.ally}}.ar-feed .e{color:${TEAM_COL.enemy}}
@keyframes arfeed{from{opacity:0;transform:translateX(16px)}}
.ar-confirm{position:absolute;left:50%;top:58%;transform:translateX(-50%);text-align:center;text-shadow:0 1px 4px #000}
.ar-confirm div{font:700 15px var(--font);letter-spacing:.3em;text-transform:uppercase;animation:arpop .9s ease-out forwards}
.ar-confirm div small{display:block;font-size:11px;letter-spacing:.24em;color:var(--gold);margin-top:2px}
.ar-confirm div.as{font-size:12px;opacity:.85}
@keyframes arpop{0%{opacity:0;transform:scale(1.25)}12%{opacity:1;transform:scale(1)}75%{opacity:1}100%{opacity:0}}
.ar-tags span{position:absolute;transform:translate(-50%,-100%);font:600 11px var(--font);letter-spacing:.14em;color:${TEAM_COL.ally};text-shadow:0 1px 2px #000;white-space:nowrap;text-transform:uppercase;text-align:center}
.ar-tags span:after{content:'';display:block;margin:2px auto 0;width:0;height:0;border-left:5px solid transparent;border-right:5px solid transparent;border-top:6px solid ${TEAM_COL.ally}}
.ar-death{position:absolute;left:50%;top:30%;transform:translateX(-50%);text-align:center;text-shadow:0 1px 4px #000}
.ar-death b{display:block;font:700 30px var(--font);letter-spacing:.32em;color:var(--red)}
.ar-death span{display:block;font-size:14px;letter-spacing:.2em;margin-top:6px}
.ar-death i{display:block;font-style:normal;font-size:12px;letter-spacing:.3em;color:var(--gold);margin-top:14px}
.ar-death button,.ar-tb{pointer-events:auto}
.ar-panel{position:absolute;inset:0;pointer-events:auto;background:linear-gradient(180deg,rgba(2,3,8,.78),rgba(2,3,8,.9));display:flex;flex-direction:column;align-items:center;padding:34px 4vw 24px;overflow:auto}
.ar-panel.clear{background:rgba(2,3,8,.62);backdrop-filter:blur(3px)}
.ar-k{font-size:12px;letter-spacing:.5em;color:var(--gold);text-transform:uppercase}
.ar-h{font:700 44px/1 var(--font);letter-spacing:.14em;text-transform:uppercase;margin:6px 0 4px}
.ar-d{font-family:var(--body);font-size:13px;color:var(--dim);max-width:720px;text-align:center;margin-bottom:16px}
.ar-cols{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:16px;width:min(1100px,100%)}
.ar-col h4{margin:0 0 8px;font-size:12px;letter-spacing:.4em;color:var(--dim);font-weight:600}
.ar-list{display:flex;flex-direction:column;gap:6px;max-height:46vh;overflow:auto;padding-right:4px}
.ar-w{border:1px solid rgba(236,230,216,.14);border-left:3px solid var(--rc);padding:7px 10px;background:rgba(10,14,22,.6);cursor:pointer;position:relative}
.ar-w:hover{background:rgba(30,36,48,.7)}.ar-w.on{border-color:var(--gold);background:rgba(227,194,108,.14)}
.ar-w .n{font:700 15px var(--font);letter-spacing:.06em}.ar-w .t{font-size:11px;letter-spacing:.16em;color:var(--dim);text-transform:uppercase}
.ar-w .p{position:absolute;right:10px;top:7px;font:700 15px var(--font);color:var(--gold)}
.ar-row{display:flex;gap:10px;margin-top:18px;align-items:center;flex-wrap:wrap;justify-content:center}
.ar-btn{font:700 15px var(--font);letter-spacing:.24em;text-transform:uppercase;padding:11px 26px;border:1px solid rgba(236,230,216,.4);background:rgba(10,14,22,.7);color:var(--bone);cursor:pointer}
.ar-btn.pri{background:var(--gold);color:#120d02;border-color:var(--gold)}
.ar-btn:hover{filter:brightness(1.15)}
.ar-meta{font-size:12px;letter-spacing:.24em;color:var(--dim);text-transform:uppercase}
.ar-meta b{color:var(--bone);margin:0 4px}
.ar-board{position:absolute;left:50%;top:90px;transform:translateX(-50%);display:grid;grid-template-columns:1fr 1fr;gap:18px;padding:16px 18px;background:rgba(3,5,10,.82);border:1px solid rgba(236,230,216,.14);backdrop-filter:blur(4px);min-width:min(860px,96vw)}
.ar-board h5{margin:0 0 6px;font-size:13px;letter-spacing:.4em;display:flex;justify-content:space-between}
.ar-board table{width:100%;border-collapse:collapse;font-size:14px;letter-spacing:.06em}
.ar-board th{font-size:10px;letter-spacing:.24em;color:var(--dim);font-weight:600;text-align:right;padding:2px 6px}
.ar-board th:first-child,.ar-board td:first-child{text-align:left}
.ar-board td{text-align:right;padding:4px 6px;border-top:1px solid rgba(236,230,216,.07)}
.ar-board tr.me td{background:rgba(227,194,108,.16);color:var(--gold)}
.ar-board tr.dead td{opacity:.45}
.ar-board .foot{grid-column:1/3;text-align:center;font-size:11px;letter-spacing:.3em;color:var(--dim)}
.ar-end .big{font:700 74px/1 var(--font);letter-spacing:.24em;text-transform:uppercase}
.ar-end .big.win{color:${TEAM_COL.ally}}.ar-end .big.loss{color:${TEAM_COL.enemy}}.ar-end .big.draw{color:var(--gold)}
.ar-end .sc{font:700 30px var(--font);letter-spacing:.16em;margin:4px 0 16px}
.ar-stats{display:flex;gap:26px;flex-wrap:wrap;justify-content:center;margin:6px 0 14px}
.ar-stats div{text-align:center}.ar-stats b{display:block;font:700 30px var(--font)}.ar-stats small{font-size:10px;letter-spacing:.3em;color:var(--dim)}
.ar-rew{display:flex;gap:14px;flex-wrap:wrap;justify-content:center;align-items:stretch}
.ar-rew .r{border:1px solid rgba(236,230,216,.16);padding:10px 16px;background:rgba(10,14,22,.6);text-align:center;min-width:120px}
.ar-rew .r b{display:block;font:700 22px var(--font);color:var(--gold)}.ar-rew .r small{font-size:10px;letter-spacing:.3em;color:var(--dim)}
.ar-rew .wpn{border-left:3px solid var(--rc);text-align:left;min-width:240px}.ar-rew .wpn b{color:var(--rc);font-size:18px}
.ar-tb{position:absolute;left:calc(14px + env(safe-area-inset-left,0px));top:calc(62px + env(safe-area-inset-top,0px));width:40px;height:40px;border-radius:50%;border:1.5px solid rgba(236,230,216,.32);background:rgba(5,7,12,.42);color:var(--bone);display:none;place-items:center;font:700 13px var(--font)}
body.touch .ar-tb{display:grid}
@media (max-height:500px){
  .ar-top{top:30px}.ar-sq{width:96px}.ar-sq b{font-size:20px}.ar-sq small{display:none}.ar-clock{font-size:15px;min-width:70px}.ar-clock small{display:none}
  .ar-feed{top:auto;bottom:40%;right:calc(12px + env(safe-area-inset-right,0px));width:260px}.ar-feed div{font-size:10px}
  .ar-h{font-size:28px}.ar-panel{padding:14px 3vw}.ar-list{max-height:52vh}.ar-end .big{font-size:42px}.ar-end .sc{font-size:20px;margin:2px 0 8px}
  .ar-stats b{font-size:20px}.ar-board{top:40px;font-size:12px;padding:10px}
}`;

export class ArenaUI {
  constructor(game, world) {
    this.g = game; this.w = world; this.m = world.match;
    if (!document.getElementById('arena-css')) { const st = document.createElement('style'); st.id = 'arena-css'; st.textContent = CSS; document.head.appendChild(st); }
    const el = this.el = document.createElement('div'); el.id = 'arena';
    el.innerHTML = `
      <div class="ar-top hidden"><div class="ar-sq ally"><b>0</b><div class="ab"><i></i></div><small>Your squad</small></div>
        <div class="ar-clock">0:00<small>${MODE_NAME}</small></div>
        <div class="ar-sq enemy"><b>0</b><div class="ab"><i></i></div><small>Opposing squad</small></div></div>
      <div class="ar-feed"></div><div class="ar-confirm"></div><div class="ar-tags"></div>
      <div class="ar-death hidden"><b>Shell broken</b><span class="by"></span><span class="tm"></span><i>L / tap · change loadout</i></div>
      <div class="ar-board hidden"></div>
      <button class="ar-tb" data-a="board">TAB</button>
      <div class="ar-panel ar-load hidden"></div>
      <div class="ar-panel ar-end hidden"></div>`;
    document.getElementById('ui').appendChild(el);
    const q = s => el.querySelector(s);
    this.topEl = q('.ar-top'); this.feedEl = q('.ar-feed'); this.confEl = q('.ar-confirm'); this.tagsEl = q('.ar-tags');
    this.deathEl = q('.ar-death'); this.boardEl = q('.ar-board'); this.loadEl = q('.ar-load'); this.endEl = q('.ar-end');
    this.clockEl = q('.ar-clock'); this.allyEl = q('.ar-sq.ally'); this.enemyEl = q('.ar-sq.enemy');
    this.tags = []; this.modal = false; this.boardOn = false; this.boardHold = false;
    el.addEventListener('click', e => this.onClick(e));
    this.deathEl.addEventListener('click', () => { if (this.g.player.dead) this.showLoadout(true); });
    this.deathEl.style.pointerEvents = 'auto';
    this.keyUp = e => { if (e.code === 'Tab' && this.boardHold) { this.boardHold = false; this.board(false); } };
    this.keyDown = e => {
      if (e.code === 'KeyL' && !this.modal && this.m.state === 'live' && this.g.player.dead) this.showLoadout(true);
      if (e.code === 'Enter' && this.loadEl && !this.loadEl.classList.contains('hidden')) this.w.deploy();
    };
    addEventListener('keyup', this.keyUp); addEventListener('keydown', this.keyDown);
    this.pick = [0, 1, 2].map(i => this.g.save.equipped[i]);
    this.showLoadout(false);
  }

  // ---------------------------------------------------------------- loadout
  showLoadout(mid) {
    const g = this.g, sv = g.save, cfg = this.w.cfg;
    this.modal = true; this.loadMid = mid;
    g.input.enabled = false; g.input.unlock();
    if (mid) this.w.menuMode(true);
    const col = slot => {
      const list = sv.inventory.filter(w => ARCHETYPES[w.arch].slot === slot).sort((a, b) => (b.uid === this.pick[slot]) - (a.uid === this.pick[slot]) || b.power - a.power || b.rarity - a.rarity);
      const cards = list.slice(0, 40).map(w => {
        const A = ARCHETYPES[w.arch], R = RARITY[w.rarity];
        return `<div class="ar-w ${w.uid === this.pick[slot] ? 'on' : ''}" style="--rc:${R.color}" data-a="pick" data-s="${slot}" data-v="${w.uid}">
          <div class="n" style="color:${R.color}">${esc(w.name)}</div><div class="t">${esc((A.cls ? A.cls + ' · ' : '') + A.name)}${w.perks.length ? ' · ' + esc(w.perks.map(p => PERKS[p].name).join(', ')) : ''}</div><div class="p">${w.power}</div></div>`;
      }).join('');
      return `<div class="ar-col"><h4>${SLOT_NAMES[slot].toUpperCase()}</h4><div class="ar-list">${cards || '<div class="ar-meta">Nothing for this slot</div>'}</div></div>`;
    };
    const D = DIFFICULTY[cfg.difficulty] || DIFFICULTY.normal;
    this.loadEl.innerHTML = `<div class="ar-k">${MODE_NAME} · Wayfarer combat simulation</div><div class="ar-h">${mid ? 'Change loadout' : 'Choose your loadout'}</div>
      <div class="ar-d">Two squads of ghost-shells on <b>${esc(this.w.name)}</b>, a ruined foundry yard. First squad to <b>${cfg.limit}</b> eliminations, or ahead after <b>${cfg.minutes}</b> minutes.
        Weapon power is at parity in the simulation; every shell holds 100 integrity and 50 shield. ${mid ? 'The new loadout is issued at your next re-sleeve.' : ''}</div>
      <div class="ar-cols">${[0, 1, 2].map(col).join('')}</div>
      <div class="ar-row"><span class="ar-meta">Opposition<b>${esc(D.label)}</b>· Squads<b>${cfg.size} v ${cfg.size}</b>· You are<b style="color:${TEAM_COL.ally}">${this.m.playerTeam === 'a' ? 'South' : 'North'} squad</b></span></div>
      <div class="ar-row"><button class="ar-btn pri" data-a="deploy">${mid ? 'Confirm' : 'Deploy'}</button><button class="ar-btn" data-a="leave">Leave simulation</button></div>`;
    this.loadEl.classList.remove('hidden');
    this.loadEl.classList.toggle('clear', !!mid);
  }

  hideLoadout() {
    const sv = this.g.save;
    for (let i = 0; i < 3; i++) if (this.pick[i] && sv.inventory.some(w => w.uid === this.pick[i])) sv.equipped[i] = this.pick[i];
    this.loadEl.classList.add('hidden'); this.modal = false;
    this.g.persist();
  }

  onClick(e) {
    const t = e.target.closest('[data-a]'); if (!t) return;
    const a = t.dataset.a, g = this.g;
    g.audio.ui('click');
    if (a === 'pick') { this.pick[+t.dataset.s] = t.dataset.v; const w = g.save.inventory.find(x => x.uid === t.dataset.v); if (w) w.isNew = false; this.showLoadout(this.loadMid); }
    else if (a === 'deploy') this.w.deploy();
    else if (a === 'leave') this.w.leave();
    else if (a === 'again') this.w.again();
    else if (a === 'board') { this.board(!this.boardOn); }
  }

  // ---------------------------------------------------------------- scoreboard
  scoreKey(e, down) {
    if (this.modal) return;
    if (e.code === 'Tab') { if (e.repeat) return; this.boardHold = true; this.board(true); }
    else this.board(!this.boardOn);
  }

  board(on) {
    this.boardOn = on; this.boardEl.classList.toggle('hidden', !on);
    if (on) this.renderBoard();
  }

  renderBoard() {
    const m = this.m;
    const tbl = (team, ally) => {
      const rows = m.table(team).map(r => `<tr class="${r.me ? 'me' : ''} ${r.alive ? '' : 'dead'}"><td>${esc(r.name)}</td><td>${r.elims}</td><td>${r.assists}</td><td>${r.deaths}</td><td>${r.score}</td></tr>`).join('');
      return `<div><h5 style="color:${ally ? TEAM_COL.ally : TEAM_COL.enemy}"><span>${ally ? 'YOUR SQUAD' : 'OPPOSING SQUAD'}</span><span>${m.score[team]}</span></h5>
        <table><tr><th>Shell</th><th>Elims</th><th>Assists</th><th>Deaths</th><th>Score</th></tr>${rows}</table></div>`;
    };
    this.boardEl.innerHTML = tbl(m.playerTeam, true) + tbl(m.enemyTeam, false) +
      `<div class="foot">${MODE_NAME} · first to ${m.cfg.limit} · ${mmss(m.timeLeft)} left · ${esc((DIFFICULTY[m.cfg.difficulty] || DIFFICULTY.normal).label)} opposition</div>`;
    this.boardT = 0;
  }

  // ---------------------------------------------------------------- feed + confirms
  onFeed() {
    const m = this.m;
    const nm = c => c ? `<span class="${c.team === m.playerTeam ? 'a' : 'e'}">${esc(c.name)}</span>` : '';
    this.feedEl.innerHTML = m.feed.slice(-5).map(f => `<div class="${f.k && f.k.isPlayer || f.v.isPlayer ? 'me' : ''}">${f.k ? nm(f.k) + `<em>${esc(f.weapon)}${f.crit ? ' ◎' : ''}</em>` : '<em>shell failure</em>'}${nm(f.v)}</div>`).join('');
    this.feedT = 0;
    if (this.boardOn) this.renderBoard();
  }

  confirm(victim, crit) {
    const d = document.createElement('div');
    d.innerHTML = `Eliminated · ${esc(victim.name)}<small>+${crit ? 125 : 100}${crit ? ' · precision' : ''}${this.m.player.stats.streak >= 3 ? ' · streak ' + this.m.player.stats.streak : ''}</small>`;
    this.confEl.appendChild(d); setTimeout(() => d.remove(), 950);
    while (this.confEl.children.length > 2) this.confEl.firstChild.remove();
  }

  assist(victim) {
    const d = document.createElement('div'); d.className = 'as';
    d.innerHTML = `Assist · ${esc(victim.name)}<small>+50</small>`;
    this.confEl.appendChild(d); setTimeout(() => d.remove(), 950);
  }

  // ---------------------------------------------------------------- end
  showEnd(r) {
    const g = this.g, W = r.weapon, A = ARCHETYPES[W.arch], R = RARITY[W.rarity], s = r.stats;
    this.board(false); this.modal = true; this.endShown = true;
    const title = r.outcome === 'win' ? 'Victory' : r.outcome === 'loss' ? 'Defeat' : 'Draw';
    const kd = s.deaths ? (s.elims / s.deaths).toFixed(2) : s.elims.toFixed(2);
    const acc = '';
    this.endEl.innerHTML = `<div class="ar-k">${MODE_NAME} · ${r.reason === 'time' ? 'Time limit reached' : 'Score limit reached'} · ${mmss(r.time)}</div>
      <div class="big ${r.outcome}">${title}</div>
      <div class="sc"><span style="color:${TEAM_COL.ally}">${r.us}</span> <span style="color:var(--dim)">—</span> <span style="color:${TEAM_COL.enemy}">${r.them}</span></div>
      <div class="ar-stats">${[[s.elims, 'Eliminations'], [s.assists, 'Assists'], [s.deaths, 'Deaths'], [kd, 'E / D'], [s.best, 'Best streak'], [s.score, 'Score']].map(([v, l]) => `<div><b>${v}</b><small>${l.toUpperCase()}</small></div>`).join('')}</div>${acc}
      <div class="ar-k" style="margin:4px 0 10px">Rewards</div>
      <div class="ar-rew"><div class="r"><b>+${r.xp}</b><small>XP</small></div><div class="r"><b>+${r.credits}</b><small>CREDITS</small></div>
        <div class="r wpn" style="--rc:${R.color}"><small>${R.name.toUpperCase()} · ${esc((A.cls || '').toUpperCase())} ${esc(A.name.toUpperCase())}</small><b>${esc(W.name)}</b><small>POWER ${W.power}${W.perks.length ? ' · ' + esc(W.perks.map(p => PERKS[p].name).join(', ')) : ''}</small></div></div>
      <div class="ar-board" style="position:static;transform:none;margin-top:18px">${this.boardHtml()}</div>
      <div class="ar-row"><button class="ar-btn pri" data-a="again">Run it back</button><button class="ar-btn" data-a="leave">Return to ship</button></div>`;
    this.endEl.classList.remove('hidden');
    this.deathEl.classList.add('hidden');
    g.audio.levelUp && r.outcome === 'win' && g.audio.levelUp();
  }

  boardHtml() { this.renderBoard(); const h = this.boardEl.innerHTML; this.boardEl.innerHTML = ''; return h; }

  hideEnd() { this.endEl.classList.add('hidden'); this.modal = false; this.endShown = false; }

  // ---------------------------------------------------------------- per frame
  update(dt) {
    const m = this.m, g = this.g, live = m.state === 'live';
    this.topEl.classList.toggle('hidden', m.state === 'loadout' || (m.state === 'over'));
    if (live) {
      const us = m.score[m.playerTeam], them = m.score[m.enemyTeam];
      const key = us + ':' + them + ':' + Math.ceil(m.timeLeft);
      if (key !== this.key) {
        this.key = key;
        this.allyEl.querySelector('b').textContent = us; this.enemyEl.querySelector('b').textContent = them;
        this.allyEl.querySelector('i').style.width = Math.min(100, us / m.cfg.limit * 100) + '%';
        this.enemyEl.querySelector('i').style.width = Math.min(100, them / m.cfg.limit * 100) + '%';
        this.clockEl.firstChild.textContent = mmss(m.timeLeft);
        this.clockEl.classList.toggle('low', m.timeLeft < 60);
        this.clockEl.querySelector('small').textContent = MODE_NAME + ' · to ' + m.cfg.limit;
      }
    }
    // feed lines fade after a while
    this.feedT = (this.feedT || 0) + dt;
    this.feedEl.style.opacity = this.feedT > 7 ? Math.max(0, 1 - (this.feedT - 7)) : 1;
    // death card
    const dead = live && g.player.dead && !this.modal;
    this.deathEl.classList.toggle('hidden', !dead);
    if (dead) {
      const k = m.killedBy;
      this.deathEl.querySelector('.by').textContent = k ? 'by ' + k.name + (k.weapon ? ' · ' + k.weapon : '') : '';
      this.deathEl.querySelector('.tm').textContent = 'Re-sleeving in ' + m.respawnIn(m.player).toFixed(1);
    }
    if (this.boardOn && (this.boardT = (this.boardT || 0) + dt) > .5) this.renderBoard();
    this.updateTags(live && !this.modal);
  }

  // squadmate tags over their heads
  updateTags(on) {
    const m = this.m, cam = this.g.camera, W = innerWidth, H = innerHeight;
    const list = on ? m.bots.filter(b => b.ally && b.alive) : [];
    while (this.tags.length < list.length) { const s = document.createElement('span'); this.tagsEl.appendChild(s); this.tags.push(s); }
    this.tags.forEach((el, i) => {
      const b = list[i];
      if (!b) { el.style.display = 'none'; return; }
      _v.set(b.pos.x, b.pos.y + 2.05 - b.crouch * .45, b.pos.z);
      const d = _v.distanceTo(cam.position);
      _v.project(cam);
      if (_v.z > 1 || Math.abs(_v.x) > 1.1 || Math.abs(_v.y) > 1.1 || d > 70) { el.style.display = 'none'; return; }
      el.style.display = ''; el.style.left = ((_v.x + 1) / 2 * W) + 'px'; el.style.top = ((1 - _v.y) / 2 * H) + 'px';
      el.style.opacity = d < 30 ? 1 : Math.max(.35, 1 - (d - 30) / 50);
      if (el.textContent !== b.name) el.textContent = b.name;
    });
  }

  dispose() {
    removeEventListener('keyup', this.keyUp); removeEventListener('keydown', this.keyDown);
    this.el.remove();
  }
}
