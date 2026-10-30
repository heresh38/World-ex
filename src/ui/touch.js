// Touch controls for phones (iPhone first): left stick to move (push to the rim to sprint), drag anywhere on the
// right to look, and thumb buttons for fire / aim / jump / reload / interact. Buttons feed the same Input state
// the keyboard and mouse use, so the game logic does not know the difference.
const ICON = {
  fire: '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="7" fill="none" stroke="currentColor" stroke-width="2"/><circle cx="12" cy="12" r="2" fill="currentColor"/><path d="M12 1v5M12 18v5M1 12h5M18 12h5" stroke="currentColor" stroke-width="2"/></svg>',
  aim: '<svg viewBox="0 0 24 24"><path d="M3 9V3h6M21 9V3h-6M3 15v6h6M21 15v6h-6" fill="none" stroke="currentColor" stroke-width="2"/><circle cx="12" cy="12" r="2" fill="currentColor"/></svg>',
  jump: '<svg viewBox="0 0 24 24"><path d="M12 4l7 8h-4v8H9v-8H5z" fill="currentColor"/></svg>',
  reload: '<svg viewBox="0 0 24 24"><path d="M20 12a8 8 0 1 1-2.3-5.7M20 4v5h-5" fill="none" stroke="currentColor" stroke-width="2.2"/></svg>',
  use: '<b>E</b>', swap: '<svg viewBox="0 0 24 24"><path d="M4 8h13l-3-3M20 16H7l3 3" fill="none" stroke="currentColor" stroke-width="2.2"/></svg>',
  car: '<svg viewBox="0 0 24 24"><path d="M4 15l2-6h12l2 6v3H4z M7 18v2M17 18v2" fill="none" stroke="currentColor" stroke-width="2"/></svg>',
  view: '<svg viewBox="0 0 24 24"><path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12z" fill="none" stroke="currentColor" stroke-width="2"/><circle cx="12" cy="12" r="3" fill="currentColor"/></svg>',
  menu: '<svg viewBox="0 0 24 24"><path d="M4 6h16M4 12h16M4 18h16" stroke="currentColor" stroke-width="2.2"/></svg>',
  sprint: '<svg viewBox="0 0 24 24"><path d="M13 3l-6 10h5l-1 8 6-10h-5z" fill="currentColor"/></svg>',
};

const cap = (el, id) => { try { el.setPointerCapture(id); } catch (e) { /* synthetic or ended pointer */ } };

export function isTouchDevice() {
  if (/[?&]touch=1/.test(location.search)) return true;
  if (/[?&]touch=0/.test(location.search)) return false;
  const coarse = window.matchMedia && matchMedia('(pointer: coarse)').matches;
  const fine = window.matchMedia && matchMedia('(any-pointer: fine)').matches;
  return ('ontouchstart' in window || navigator.maxTouchPoints > 0) && coarse && !fine;
}

export class TouchControls {
  constructor(game) {
    this.g = game; this.input = game.input;
    document.body.classList.add('touch');
    const el = this.el = document.createElement('div');
    el.id = 'touch'; el.className = 'hidden';
    el.innerHTML = `
      <div class="t-look"></div>
      <div class="t-stick"><div class="t-base"></div><div class="t-knob"></div></div>
      <div class="t-btns">
        <button class="tb fire" data-b="fire" aria-label="Fire">${ICON.fire}</button>
        <button class="tb aim" data-b="aim" aria-label="Aim">${ICON.aim}</button>
        <button class="tb jump" data-b="jump" aria-label="Jump">${ICON.jump}</button>
        <button class="tb reload" data-b="reload" aria-label="Reload">${ICON.reload}</button>
        <button class="tb use" data-b="use" aria-label="Interact">${ICON.use}</button>
        <button class="tb sprint" data-b="sprint" aria-label="Sprint">${ICON.sprint}</button>
      </div>
      <div class="t-top">
        <button class="ts" data-b="swap" aria-label="Switch weapon">${ICON.swap}</button>
        <button class="ts" data-b="car" aria-label="Summon car">${ICON.car}</button>
        <button class="ts" data-b="view" aria-label="Switch view">${ICON.view}</button>
        <button class="ts" data-b="menu" aria-label="Pause">${ICON.menu}</button>
      </div>
      <div class="t-rotate"><div>↻</div>Turn your phone sideways to play</div>`;
    document.getElementById('ui').appendChild(el);
    this.knob = el.querySelector('.t-knob'); this.base = el.querySelector('.t-base'); this.stickEl = el.querySelector('.t-stick');
    this.stick = null; this.look = new Map(); this.held = new Map();
    this.sprintLatch = false;
    this.bindStick(); this.bindLook(); this.bindButtons();
    // touch never uses pointer lock; treat the pointer as captured whenever the game runs
    this.input.touch = true; this.input.wantLock = false; this.input.locked = true;
    addEventListener('resize', () => this.layout());
    this.layout();
  }

  show(on) { this.el.classList.toggle('hidden', !on); }

  layout() {
    const portrait = innerHeight > innerWidth;
    this.el.classList.toggle('portrait', portrait);
  }

  // ---------------------------------------------------------------- move stick (floating: appears where you touch)
  bindStick() {
    const z = this.stickEl, R = 52;
    z.addEventListener('pointerdown', e => {
      if (this.stick) return;
      e.preventDefault(); cap(z, e.pointerId);
      const r = z.getBoundingClientRect();
      this.stick = { id: e.pointerId, x: e.clientX, y: e.clientY };
      this.base.style.left = this.knob.style.left = (e.clientX - r.left) + 'px';
      this.base.style.top = this.knob.style.top = (e.clientY - r.top) + 'px';
      z.classList.add('on');
    });
    z.addEventListener('pointermove', e => {
      const s = this.stick; if (!s || s.id !== e.pointerId) return;
      let dx = e.clientX - s.x, dy = e.clientY - s.y; const d = Math.hypot(dx, dy);
      if (d > R) { dx *= R / d; dy *= R / d; }
      const r = z.getBoundingClientRect();
      this.knob.style.left = (s.x - r.left + dx) + 'px'; this.knob.style.top = (s.y - r.top + dy) + 'px';
      this.input.axisX = dx / R; this.input.axisY = -dy / R;
      this.input.axisRun = this.sprintLatch || d > R * 1.15 && -dy > R * .6;
    });
    const end = e => {
      const s = this.stick; if (!s || s.id !== e.pointerId) return;
      this.stick = null; this.input.axisX = this.input.axisY = 0; this.input.axisRun = false;
      z.classList.remove('on');
    };
    z.addEventListener('pointerup', end); z.addEventListener('pointercancel', end);
  }

  // ---------------------------------------------------------------- look: drag on the right half (and on the fire button)
  addLook(e) {
    const prev = this.look.get(e.pointerId); if (!prev) return;
    const k = 2.4;   // touch pixels are coarser than mouse counts
    this.input.mx += (e.clientX - prev.x) * k; this.input.my += (e.clientY - prev.y) * k;
    prev.x = e.clientX; prev.y = e.clientY;
  }

  bindLook() {
    const z = this.el.querySelector('.t-look');
    z.addEventListener('pointerdown', e => { e.preventDefault(); cap(z, e.pointerId); this.look.set(e.pointerId, { x: e.clientX, y: e.clientY }); });
    z.addEventListener('pointermove', e => this.addLook(e));
    const end = e => this.look.delete(e.pointerId);
    z.addEventListener('pointerup', end); z.addEventListener('pointercancel', end);
  }

  // ---------------------------------------------------------------- buttons
  bindButtons() {
    const inp = this.input, g = this.g;
    const key = (code, down) => { if (down) { if (!inp.down.has(code)) inp.hit.add(code); inp.down.add(code); } else inp.down.delete(code); };
    const press = (b, down, e) => {
      switch (b) {
        case 'fire':
          inp.lmb = down; if (down) inp.lmbHit = true;
          if (down) this.look.set(e.pointerId, { x: e.clientX, y: e.clientY }); else this.look.delete(e.pointerId);
          break;
        case 'aim': if (down) inp.rmb = !inp.rmb; break;
        case 'jump': key('Space', down); break;
        case 'reload': key('KeyR', down); break;
        case 'use': key('KeyE', down); break;
        case 'sprint':
          if (g.player && g.player.mode === 'car') key('ShiftLeft', down);
          else if (down) { this.sprintLatch = !this.sprintLatch; inp.axisRun = this.sprintLatch; }
          break;
        case 'swap': if (down) inp.wheel += 1; break;
        case 'car': key('KeyV', down); break;
        case 'view': key('KeyT', down); break;
        case 'menu': if (down) g.pause(); break;
      }
    };
    this.el.querySelectorAll('[data-b]').forEach(btn => {
      const b = btn.dataset.b;
      btn.addEventListener('pointerdown', e => { e.preventDefault(); e.stopPropagation(); cap(btn, e.pointerId); btn.classList.add('on'); this.held.set(e.pointerId, b); press(b, true, e); g.audio.start(); });
      btn.addEventListener('pointermove', e => { if (b === 'fire') this.addLook(e); });
      const up = e => { if (!this.held.has(e.pointerId)) return; this.held.delete(e.pointerId); btn.classList.remove('on'); press(b, false, e); };
      btn.addEventListener('pointerup', up); btn.addEventListener('pointercancel', up);
      btn.addEventListener('contextmenu', e => e.preventDefault());
    });
  }

  // per-frame: context-sensitive button states
  update() {
    const g = this.g, p = g.player; if (!p) return;
    const car = p.mode === 'car', armed = p.armed && !car;
    const cls = this.el.classList;
    cls.toggle('car', car); cls.toggle('unarmed', !armed);
    cls.toggle('can-use', !!g.hud.lastPrompt || car);
    cls.toggle('aiming', !!this.input.rmb);
    cls.toggle('sprinting', !!this.sprintLatch);
    cls.toggle('cars', !!(g.world && g.world.allowCars));
    if (!armed && this.input.rmb) this.input.rmb = false;
  }
}
