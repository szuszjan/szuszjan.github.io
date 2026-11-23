// Wspólne helpery dla eksperymentów w /lab
const Lab = (() => {
  let toastEl, toastTimer;
  function toast(text, ms = 2200) {
    if (!toastEl) { toastEl = document.createElement('div'); toastEl.className = 'lab-toast'; document.body.appendChild(toastEl); }
    toastEl.textContent = text;
    toastEl.classList.add('show');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => toastEl.classList.remove('show'), ms);
  }

  function message(title, html, actions = []) {
    let el = document.querySelector('.lab-msg');
    if (!el) { el = document.createElement('div'); el.className = 'lab-msg'; document.body.appendChild(el); }
    el.innerHTML = `<div class="box"><h2></h2><p></p><div class="row" style="justify-content:center"></div></div>`;
    el.querySelector('h2').textContent = title;
    el.querySelector('p').innerHTML = html;
    const row = el.querySelector('.row');
    for (const a of actions) {
      const b = document.createElement(a.href ? 'a' : 'button');
      b.className = 'btn' + (a.primary ? ' primary' : '');
      b.textContent = a.label;
      if (a.href) { b.href = a.href; b.style.textDecoration = 'none'; }
      if (a.onClick) b.onclick = () => { el.classList.remove('show'); a.onClick(); };
      row.appendChild(b);
    }
    el.classList.add('show');
    return el;
  }

  // Zwijany panel z opisem
  function initPanel() {
    document.querySelectorAll('.lab-panel').forEach(p => {
      const t = p.querySelector('.toggle');
      if (!t) return;
      const key = 'lab-panel:' + location.pathname;
      let saved = null;
      try { saved = localStorage.getItem(key); } catch {}
      // na telefonie pełnoekranowe eksperymenty startują ze zwiniętym panelem
      const collapse = saved === '1' || (saved === null && innerWidth < 640 && document.body.classList.contains('fullscreen'));
      if (collapse) { p.classList.add('collapsed'); t.textContent = '+'; }
      t.addEventListener('click', () => {
        const c = p.classList.toggle('collapsed');
        t.textContent = c ? '+' : '–';
        try { localStorage.setItem(key, c ? '1' : '0'); } catch {}
      });
    });
  }

  // ---- czujniki orientacji ----
  // iOS wymaga jawnej zgody wywołanej gestem użytkownika.
  async function requestMotionPermission() {
    let ok = true;
    try {
      if (typeof DeviceOrientationEvent !== 'undefined' && typeof DeviceOrientationEvent.requestPermission === 'function') {
        ok = (await DeviceOrientationEvent.requestPermission()) === 'granted';
      }
      if (typeof DeviceMotionEvent !== 'undefined' && typeof DeviceMotionEvent.requestPermission === 'function') {
        ok = ((await DeviceMotionEvent.requestPermission()) === 'granted') && ok;
      }
    } catch { ok = false; }
    return ok;
  }
  const needsMotionPermission = () =>
    typeof DeviceOrientationEvent !== 'undefined' && typeof DeviceOrientationEvent.requestPermission === 'function';

  function screenAngle() {
    if (screen.orientation && typeof screen.orientation.angle === 'number') return screen.orientation.angle;
    return typeof window.orientation === 'number' ? window.orientation : 0;
  }

  // Wektor grawitacji w układzie ekranu (x w prawo, y w dół), długość ~1.
  // Liczony z beta/gamma (spójne między Androidem i iOS), skorygowany o obrót ekranu.
  function gravityFromOrientation(beta, gamma) {
    const b = beta * Math.PI / 180, g = gamma * Math.PI / 180;
    const gx = Math.cos(b) * Math.sin(g);
    const gy = Math.sin(b);
    const a = screenAngle() * Math.PI / 180;
    return { x: gx * Math.cos(a) - gy * Math.sin(a), y: gx * Math.sin(a) + gy * Math.cos(a) };
  }

  // Subskrypcja: cb({x,y}) z grawitacją, cbShake(magnitude) przy potrząśnięciu
  function onTilt(cb, cbShake) {
    let got = false;
    window.addEventListener('deviceorientation', e => {
      if (e.beta == null || e.gamma == null) return;
      got = true;
      cb(gravityFromOrientation(e.beta, e.gamma));
    });
    if (cbShake) {
      let last = 0;
      window.addEventListener('devicemotion', e => {
        const a = e.acceleration;
        if (!a || a.x == null) return;
        const m = Math.hypot(a.x, a.y, a.z);
        const now = performance.now();
        if (m > 14 && now - last > 350) { last = now; cbShake(m); }
      });
    }
    return () => got;
  }

  // ---- WebGPU ----
  async function gpu(canvas, opts = {}) {
    if (!('gpu' in navigator)) {
      message('Brak WebGPU', 'Ta przeglądarka nie obsługuje WebGPU. Spróbuj w aktualnym Chrome / Edge, Safari 26+ lub Firefox 141+.',
        [{ label: '← Wróć do Lab', href: '../', primary: true }]);
      return null;
    }
    const adapter = await navigator.gpu.requestAdapter({ powerPreference: 'high-performance' });
    if (!adapter) {
      message('Brak adaptera GPU', 'WebGPU jest dostępne, ale przeglądarka nie dała dostępu do karty graficznej (może być wyłączone lub zablokowane).',
        [{ label: '← Wróć do Lab', href: '../', primary: true }]);
      return null;
    }
    const device = await adapter.requestDevice(opts.device || {});
    device.lost.then(info => { if (info.reason !== 'destroyed') message('Utracono GPU', info.message || 'Urządzenie GPU zostało utracone.', [{ label: 'Odśwież', onClick: () => location.reload(), primary: true }]); });
    device.addEventListener?.('uncapturederror', e => console.error('WebGPU:', e.error.message));
    const context = canvas.getContext('webgpu');
    const format = navigator.gpu.getPreferredCanvasFormat();
    context.configure({ device, format, alphaMode: 'opaque' });
    return { adapter, device, context, format };
  }

  // Dopasowanie rozdzielczości canvasa do ekranu (z limitem pikseli dla wydajności)
  function fitCanvas(canvas, maxDpr = 2, maxPixels = 4.2e6) {
    let dpr = Math.min(devicePixelRatio || 1, maxDpr);
    const w = canvas.clientWidth, h = canvas.clientHeight;
    if (w * h * dpr * dpr > maxPixels) dpr = Math.sqrt(maxPixels / (w * h));
    const W = Math.max(1, Math.round(w * dpr)), H = Math.max(1, Math.round(h * dpr));
    const changed = canvas.width !== W || canvas.height !== H;
    if (changed) { canvas.width = W; canvas.height = H; }
    return { w: W, h: H, dpr, changed };
  }

  // Wake Lock – ekran nie gaśnie podczas eksperymentów z czujnikami
  let wakeLock = null;
  async function keepAwake(on = true) {
    try {
      if (on && 'wakeLock' in navigator) {
        wakeLock = await navigator.wakeLock.request('screen');
        document.addEventListener('visibilitychange', async () => {
          if (document.visibilityState === 'visible' && wakeLock && wakeLock.released) wakeLock = await navigator.wakeLock.request('screen');
        });
        return true;
      }
      if (!on && wakeLock) { await wakeLock.release(); wakeLock = null; }
    } catch {}
    return false;
  }

  document.addEventListener('DOMContentLoaded', initPanel);
  return { toast, message, requestMotionPermission, needsMotionPermission, gravityFromOrientation, onTilt, gpu, fitCanvas, keepAwake, screenAngle };
})();
