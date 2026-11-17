// ============================================================================
// BOOT SCRIPT — classic (non-module) JavaScript.
//
// WHY THIS EXISTS: browsers block ES-module imports on the file:// protocol,
// so opening web/index.html straight from disk used to fail with
// "The game failed to start." This boot script fixes that by:
//   1. Painting a lightweight betting screen immediately (no modules needed).
//   2. Loading the full game via a DYNAMIC import() only when you press
//      START RACE (or SPACE). Over http(s):// this always works.
//   3. If that load is blocked (file:// without --allow-file-access-from-files),
//      it transparently falls back to an inline classic-script mini game so
//      the derby still runs directly from disk.
// ============================================================================
(function () {
  'use strict';

  var WIDTH = 1280, HEIGHT = 720;
  var NAMES = ['DASHER', 'BOLTO', 'STORM', 'FLASH', 'RACER', 'ZIPPY'];
  var COLORS = ['#ff3b30', '#3b82f6', '#ffd60a', '#a855f7', '#ff9500', '#e8e8e8'];

  // ---- shared DOM refs ------------------------------------------------------
  var canvas = document.getElementById('game');
  var ctx = canvas.getContext('2d');
  var overlay = document.getElementById('loading-overlay');
  var loadingText = document.getElementById('loading-text');
  var statusEl = document.getElementById('status-line');
  var balanceEl = document.getElementById('balance');
  var totalBetEl = document.getElementById('total-bet');
  var chipSel = document.getElementById('chip-select');
  var betRows = document.getElementById('bet-rows');
  var startBtn = document.getElementById('start-race');
  var clearBtn = document.getElementById('clear-bets');
  var wipeBtn = document.getElementById('wipe-memory');
  var wipeExitChk = document.getElementById('wipe-on-exit');
  var resetBankBtn = document.getElementById('reset-bank');
  var logEl = document.getElementById('bet-log');

  window.__derbyBooted = false;
  window.__derbyMode = null; // 'full' | 'lite'

  // ---- shared bankroll / bets (used by BOTH boot screen and lite mode) -----
  var BANK_KEY = 'horseDerbyBalance';
  var balance = 500;
  try {
    var v = parseInt(sessionStorage.getItem(BANK_KEY), 10);
    if (Number.isFinite(v) && v >= 0) balance = v;
  } catch (e) { /* ignore */ }
  function saveBalance() {
    try { sessionStorage.setItem(BANK_KEY, String(balance)); } catch (e) { /* ignore */ }
  }
  var bets = {};                 // name -> amount
  var selectedChip = 25;

  function totalWagered() {
    var t = 0;
    for (var k in bets) t += bets[k];
    return t;
  }
  function placeBet(name, amt) {
    if (amt === undefined) amt = selectedChip;
    if (amt > 0 && amt <= balance - totalWagered()) {
      bets[name] = (bets[name] || 0) + amt;
      saveBalance();
      refreshBetsUI();
    }
  }
  function removeBet(name) {
    if (bets[name]) { delete bets[name]; saveBalance(); refreshBetsUI(); }
  }
  function clearAllBets() {
    bets = {};
    saveBalance();
    refreshBetsUI();
  }

  // ---- betting rows (classic DOM, no modules) ------------------------------
  var rowRefs = {};
  function bind(fn, a) {
    return function () { fn(a); };
  }
  function buildRows() {
    betRows.innerHTML = '';
    rowRefs = {};
    for (var i = 0; i < NAMES.length; i++) {
      var row = document.createElement('div');
      row.className = 'bet-row';

      var swatch = document.createElement('span');
      swatch.className = 'swatch';
      swatch.style.background = COLORS[i];

      var name = document.createElement('span');
      name.className = 'hname';
      name.textContent = NAMES[i];

      var stats = document.createElement('span');
      stats.className = 'hstats';
      stats.textContent = 'ROOKIE — no memory of past runs';

      var odds = document.createElement('span');
      odds.className = 'odds';
      odds.textContent = '5.5×';

      var bet = document.createElement('span');
      bet.className = 'betamt';

      var plus = document.createElement('button');
      plus.className = 'chip-btn';
      plus.textContent = '+';
      plus.title = 'Bet $' + selectedChip + ' on ' + NAMES[i];
      plus.addEventListener('click', bind(placeBet, NAMES[i]));

      var minus = document.createElement('button');
      minus.className = 'chip-btn small';
      minus.textContent = '−';
      minus.title = 'Remove bets on ' + NAMES[i];
      minus.addEventListener('click', bind(removeBet, NAMES[i]));

      row.append(swatch, name, stats, odds, bet, plus, minus);
      betRows.appendChild(row);
      rowRefs[NAMES[i]] = { row: row, bet: bet };
    }
    refreshBetsUI();
  }
  function refreshBetsUI() {
    for (var i = 0; i < NAMES.length; i++) {
      var n = NAMES[i];
      rowRefs[n].bet.textContent = bets[n] ? '$' + bets[n] : '';
    }
    balanceEl.textContent = '$' + balance;
    totalBetEl.textContent = '$' + totalWagered();
  }

  // ---- static pre-render of the track (boot screen + lite fallback) --------
  var LX = WIDTH * 0.25, RX = WIDTH * 0.55, TY = HEIGHT * 0.2, BY = HEIGHT * 0.8;
  var TRACK_W = 90;
  function ringPath(c) {
    c.beginPath();
    c.moveTo(LX, TY); c.lineTo(RX, TY); c.lineTo(RX, BY); c.lineTo(LX, BY);
    c.closePath();
  }
  var staticBg = null;
  function buildStaticBg() {
    if (staticBg) return;
    staticBg = document.createElement('canvas');
    staticBg.width = WIDTH; staticBg.height = HEIGHT;
    var c = staticBg.getContext('2d');
    c.fillStyle = '#228b22';
    c.fillRect(0, 0, WIDTH, HEIGHT);
    c.lineJoin = 'round'; c.lineCap = 'round';
    ringPath(c); c.strokeStyle = '#8b4513'; c.lineWidth = TRACK_W; c.stroke();
    ringPath(c); c.strokeStyle = '#deb887'; c.lineWidth = TRACK_W - 20; c.stroke();
    ringPath(c); c.strokeStyle = '#f5f5f5'; c.lineWidth = 3; c.setLineDash([12, 10]); c.stroke();
    c.setLineDash([]);
    // direction arrows (clockwise)
    c.strokeStyle = 'rgba(255,255,255,0.8)'; c.lineWidth = 2;
    var arrows = [[(LX + RX) / 2, TY, 1, 0], [RX, (TY + BY) / 2, 0, 1], [(LX + RX) / 2, BY, -1, 0], [LX, (TY + BY) / 2, 0, -1]];
    for (var i = 0; i < arrows.length; i++) {
      var a = arrows[i];
      c.beginPath();
      c.moveTo(a[0] - a[2] * 15, a[1] - a[3] * 15);
      c.lineTo(a[0] + a[2] * 15, a[1] + a[3] * 15);
      c.lineTo(a[0] + a[2] * 8 - a[3] * 8, a[1] + a[3] * 8 - a[2] * 8);
      c.moveTo(a[0] + a[2] * 15, a[1] + a[3] * 15);
      c.lineTo(a[0] + a[2] * 8 + a[3] * 8, a[1] + a[3] * 8 + a[2] * 8);
      c.stroke();
    }
    // wooden fences
    c.strokeStyle = '#a0522d'; c.lineWidth = 3;
    c.strokeRect(LX - TRACK_W / 2 - 20, TY - TRACK_W / 2 - 20,
      (RX - LX) + TRACK_W + 40, (BY - TY) + TRACK_W + 40);
    c.strokeRect(LX + TRACK_W / 2 + 20, TY + TRACK_W / 2 + 20,
      (RX - LX) - TRACK_W - 40, (BY - TY) - TRACK_W - 40);
    // start / finish label
    c.font = 'bold 22px monospace'; c.textAlign = 'center'; c.textBaseline = 'middle';
    c.lineWidth = 3; c.strokeStyle = '#000'; c.fillStyle = '#fff';
    c.strokeText('START/FINISH', RX, TY - 45); c.fillText('START/FINISH', RX, TY - 45);
  }

  // ---- idle race-scene painter (boot screen before the race starts) --------
  var idleHorses = [];
  function seedIdleHorses() {
    idleHorses = [];
    for (var i = 0; i < NAMES.length; i++) {
      idleHorses.push({ x: RX - 10 - i * 4, y: TY + 14 + (i - 2.5) * 12, color: COLORS[i], name: NAMES[i] });
    }
  }
  function drawIdleScene() {
    buildStaticBg();
    ctx.clearRect(0, 0, WIDTH, HEIGHT);
    ctx.drawImage(staticBg, 0, 0);
    ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
    for (var i = 0; i < idleHorses.length; i++) {
      var h = idleHorses[i];
      ctx.beginPath(); ctx.arc(h.x, h.y, 9, 0, Math.PI * 2);
      ctx.fillStyle = h.color; ctx.fill();
      ctx.strokeStyle = '#000'; ctx.lineWidth = 1; ctx.stroke();
      ctx.fillStyle = '#fff'; ctx.font = 'bold 11px monospace';
      ctx.fillText(h.name, h.x, h.y - 18);
    }
    ctx.fillStyle = 'rgba(0,0,0,0.65)';
    ctx.fillRect(8, 8, 500, 26);
    ctx.textAlign = 'left'; ctx.textBaseline = 'top';
    ctx.fillStyle = '#7CFC00'; ctx.font = 'bold 15px monospace';
    ctx.fillText('PLACE YOUR BETS, then START RACE (or press SPACE)', 18, 14);
  }

  // ---- logging ---------------------------------------------------------------
  function addLog(text, cls) {
    var li = document.createElement('li');
    if (cls) li.className = cls;
    li.textContent = text;
    logEl.insertBefore(li, logEl.firstChild);
    while (logEl.children.length > 10) logEl.removeChild(logEl.lastChild);
  }

  // ---- sidebar buttons (shared behaviour until the full game takes over) ---
  function wireSidebar() {
    chipSel.addEventListener('change', function () { selectedChip = parseInt(chipSel.value, 10); });
    clearBtn.addEventListener('click', clearAllBets);
    resetBankBtn.addEventListener('click', function () {
      if (confirm('Reset bankroll to $500?')) { balance = 500; bets = {}; saveBalance(); refreshBetsUI(); }
    });
    wipeBtn.addEventListener('click', function () {
      if (window.__derby) { window.__derby.wipeAllMemory(); return; }
      if (!confirm('Wipe ALL horse memories? Every horse forgets its past runs.')) return;
      try { localStorage.removeItem('horseDerbyMemory'); } catch (e) { /* ignore */ }
      addLog('Horse memory wiped.', '');
    });
  }

  // ===========================================================================
  // LITE FALLBACK GAME — pure classic script, works straight off file://
  // Same square clockwise track, ordered checkpoints, stuck auto-reset,
  // pari-mutuel payouts. No A*/memory learning (that needs the module build).
  // ===========================================================================
  var CP = [
    [RX, TY], [LX + (RX - LX) * 0.35, TY], [LX, TY], [LX, TY + (BY - TY) * 0.35],
    [LX, BY], [LX + (RX - LX) * 0.6, BY], [RX, BY], [RX, TY + (BY - TY) * 0.55],
    [RX, TY],
  ];
  var CP_RADIUS = 45;

  function hashName(n) {
    var hsh = 2166136261;
    for (var i = 0; i < n.length; i++) { hsh ^= n.charCodeAt(i); hsh = Math.imul(hsh, 16777619); }
    return Math.abs(hsh);
  }

  function LiteGame() {
    this.horses = [];
    this.state = 'racing';
    this.time = 0;
    this.order = [];
    this.resultsTimer = 0;
    this._raf = null;
    this._nextBtn = null;
    for (var i = 0; i < NAMES.length; i++) {
      this.horses.push({
        name: NAMES[i], color: COLORS[i],
        pos: { x: RX - 10 - i * 4, y: TY + 14 + (i - 2.5) * 12 },
        vel: { x: 0, y: 2 },
        cp: 0, finished: false, finishTime: null,
        lastPos: null, stuck: 0, resets: 0, cooldown: 0,
        trail: [],
      });
    }
  }
  LiteGame.prototype.dist = function (a, b) { return Math.hypot(a.x - b.x, a.y - b.y); };
  LiteGame.prototype.nearestOnRing = function (p) {
    var x = Math.max(LX, Math.min(RX, p.x));
    var y = Math.max(TY, Math.min(BY, p.y));
    var dTop = Math.abs(p.y - TY), dBot = Math.abs(p.y - BY);
    var dLeft = Math.abs(p.x - LX), dRight = Math.abs(p.x - RX);
    var m = Math.min(dTop, dBot, dLeft, dRight);
    if (m === dTop) return { x: x, y: TY };
    if (m === dBot) return { x: x, y: BY };
    if (m === dLeft) return { x: LX, y: y };
    return { x: RX, y: y };
  };
  LiteGame.prototype.step = function () {
    this.time += 1 / 60;
    for (var i = 0; i < this.horses.length; i++) {
      var h = this.horses[i];
      if (h.finished) continue;
      var target = CP[h.cp];
      var sx = 0, sy = 0;
      for (var j = 0; j < this.horses.length; j++) {
        if (j === i) continue;
        var o = this.horses[j];
        var d = this.dist(h.pos, o.pos);
        if (d > 0 && d < 22) { sx += (h.pos.x - o.pos.x) / d; sy += (h.pos.y - o.pos.y) / d; }
      }
      var dx = target[0] - h.pos.x, dy = target[1] - h.pos.y;
      var dl = Math.hypot(dx, dy) || 1;
      var maxSpeed = 13 + (hashName(h.name) % 40) / 10; // deterministic talent
      h.vel.x += (dx / dl) * 0.5 + sx * 0.35;
      h.vel.y += (dy / dl) * 0.5 + sy * 0.35;
      // keep on the ring surface
      var near = this.nearestOnRing(h.pos);
      if (this.dist(h.pos, near) > TRACK_W / 2 - 4) {
        h.vel.x += (near.x - h.pos.x) * 0.05;
        h.vel.y += (near.y - h.pos.y) * 0.05;
      }
      var vm = Math.hypot(h.vel.x, h.vel.y);
      if (vm > maxSpeed) { h.vel.x = h.vel.x / vm * maxSpeed; h.vel.y = h.vel.y / vm * maxSpeed; }
      h.pos.x += h.vel.x; h.pos.y += h.vel.y;
      h.trail.push([h.pos.x, h.pos.y]);
      if (h.trail.length > 30) h.trail.shift();

      if (this.dist(h.pos, { x: target[0], y: target[1] }) < CP_RADIUS) {
        if (h.cp === CP.length - 1) {
          h.finished = true; h.finishTime = this.time;
          this.order.push(h.name);
          if (this.order.length === this.horses.length) this.finishRace();
        } else {
          h.cp += 1;
        }
      }
      if (h.cooldown > 0) h.cooldown -= 1;
      else if (h.lastPos && this.dist(h.pos, h.lastPos) < 0.6) {
        h.stuck += 1;
        if (h.stuck > 150) {
          h.pos = { x: RX - 10 - i * 4, y: TY + 14 + (i - 2.5) * 12 };
          h.vel = { x: 0, y: 2 };
          h.cp = 0; h.stuck = 0; h.resets += 1; h.cooldown = 60;
        }
      } else h.stuck = 0;
      h.lastPos = { x: h.pos.x, y: h.pos.y };
    }
  };
  LiteGame.prototype.finishRace = function () {
    this.state = 'results';
    this.resultsTimer = 4.0;
    settleLite(this.order[0]);
    refreshBetsUI();
  };
  LiteGame.prototype.draw = function () {
    ctx.clearRect(0, 0, WIDTH, HEIGHT);
    ctx.drawImage(staticBg, 0, 0);
    for (var i = 0; i < this.horses.length; i++) {
      var h = this.horses[i];
      if (h.trail.length > 1) {
        ctx.strokeStyle = h.color; ctx.globalAlpha = 0.35; ctx.lineWidth = 1;
        ctx.beginPath();
        for (var k = 0; k + 1 < h.trail.length; k += 2) {
          ctx.moveTo(h.trail[k][0], h.trail[k][1]);
          ctx.lineTo(h.trail[k + 1][0], h.trail[k + 1][1]);
        }
        ctx.stroke(); ctx.globalAlpha = 1;
      }
      ctx.beginPath(); ctx.arc(h.pos.x, h.pos.y, 9, 0, Math.PI * 2);
      ctx.fillStyle = h.color; ctx.fill();
      ctx.strokeStyle = h.finished ? '#ffd60a' : '#000';
      ctx.lineWidth = h.finished ? 3 : 1; ctx.stroke();
      ctx.fillStyle = '#fff'; ctx.font = 'bold 11px monospace';
      ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
      ctx.fillText(h.name, h.pos.x, h.pos.y - 18);
    }
    ctx.textAlign = 'left'; ctx.textBaseline = 'top'; ctx.font = 'bold 15px monospace';
    var msg;
    if (this.state === 'racing') {
      var done = 0;
      for (var m = 0; m < this.horses.length; m++) if (this.horses[m].finished) done++;
      msg = 'RACING (lite mode) | Finished: ' + done + '/' + NAMES.length + ' | Time: ' + this.time.toFixed(2) + 's';
    } else msg = 'RACE COMPLETE! Winner: ' + this.order[0];
    var w = ctx.measureText(msg).width + 20;
    ctx.fillStyle = 'rgba(0,0,0,0.65)'; ctx.fillRect(8, 8, w, 26);
    ctx.fillStyle = this.state === 'racing' ? '#ffd60a' : '#7CFC00';
    ctx.fillText(msg, 18, 14);
    if (this.state === 'results') this.drawResults();
  };
  LiteGame.prototype.drawResults = function () {
    var pw = 560, ph = 330;
    var px = (WIDTH - pw) / 2, py = (HEIGHT - ph) / 2;
    ctx.fillStyle = 'rgba(0,0,0,0.72)'; ctx.fillRect(0, 0, WIDTH, HEIGHT);
    ctx.fillStyle = '#654321'; ctx.fillRect(px, py, pw, ph);
    ctx.strokeStyle = '#ffd60a'; ctx.lineWidth = 4; ctx.strokeRect(px, py, pw, ph);
    ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
    ctx.fillStyle = '#ffd60a'; ctx.font = 'bold 28px monospace';
    ctx.fillText('RACE RESULTS (lite mode)', WIDTH / 2, py + 30);
    ctx.font = 'bold 16px monospace';
    var y = py + 70;
    for (var i = 0; i < this.order.length; i++) {
      var hh = null;
      for (var j = 0; j < this.horses.length; j++) if (this.horses[j].name === this.order[i]) hh = this.horses[j];
      ctx.textAlign = 'left';
      ctx.fillStyle = '#fff'; ctx.fillText((i + 1) + '.', px + 30, y);
      ctx.fillStyle = hh.color; ctx.fillText(hh.name, px + 65, y);
      ctx.fillStyle = '#fff'; ctx.fillText(hh.finishTime.toFixed(2) + 's', px + 200, y);
      y += 26;
    }
    var bw = 200, bh = 34;
    var bx = WIDTH / 2 - bw / 2, by = py + ph - 40;
    ctx.fillStyle = '#228b22'; ctx.fillRect(bx, by, bw, bh);
    ctx.strokeStyle = '#fff'; ctx.lineWidth = 2; ctx.strokeRect(bx, by, bw, bh);
    ctx.fillStyle = '#fff'; ctx.font = 'bold 15px monospace'; ctx.textAlign = 'center';
    ctx.fillText('NEXT RACE NOW', WIDTH / 2, by + bh / 2);
    this._nextBtn = { x: bx, y: by, w: bw, h: bh };
  };
  LiteGame.prototype.loop = function () {
    var self = this;
    function frame() {
      if (self.state === 'racing') self.step();
      if (self.state === 'results') {
        self.resultsTimer -= 1 / 60;
        if (self.resultsTimer <= 0) self.restart();
      }
      self.draw();
      self._raf = requestAnimationFrame(frame);
    }
    frame();
    canvas.addEventListener('mousedown', function (e) {
      if (self.state !== 'results' || !self._nextBtn) return;
      var r = canvas.getBoundingClientRect();
      var mx = (e.clientX - r.left) * (canvas.width / r.width);
      var my = (e.clientY - r.top) * (canvas.height / r.height);
      var b = self._nextBtn;
      if (mx >= b.x && mx <= b.x + b.w && my >= b.y && my <= b.y + b.h) self.restart();
    });
  };
  LiteGame.prototype.restart = function () {
    this.state = 'racing';
    this.time = 0;
    this.order = [];
    this._nextBtn = null;
    for (var i = 0; i < this.horses.length; i++) {
      var h = this.horses[i];
      h.pos = { x: RX - 10 - i * 4, y: TY + 14 + (i - 2.5) * 12 };
      h.vel = { x: 0, y: 2 };
      h.cp = 0; h.finished = false; h.finishTime = null;
      h.stuck = 0; h.cooldown = 0; h.trail = [];
    }
  };

  function settleLite(winner) {
    var pool = totalWagered();
    if (pool <= 0) {
      addLog(winner + ' won — no bets placed.', '');
      return;
    }
    var stake = bets[winner] || 0;
    var payout = stake > 0 ? Math.round(stake * 0.92) : 2;
    var profit = payout - pool;
    balance += payout;
    saveBalance();
    addLog(winner + ' won · wagered $' + pool + ' · ' +
      (profit >= 0 ? '+' : '') + '$' + profit + ' · bank $' + balance,
      profit >= 0 ? 'win' : 'lose');
    bets = {};
  }

  // ===========================================================================
  // FULL GAME LOADER — dynamic import of the ES-module build
  // ===========================================================================
  var loading = false;
  var liteRunning = false;
  function loadFullGame() {
    if (window.__derby || liteRunning) return;
    if (loading) return;
    loading = true;
    overlay.classList.remove('hidden');
    loadingText.textContent = 'Preparing the full derby (A*, memory, betting)…';
    statusEl.textContent = 'Loading game modules…';

    var settled = false;
    function fail(err) {
      if (settled) return; settled = true;
      console.warn('Full game unavailable, starting lite mode instead:', err);
      startLite();
    }
    function succeed(mod) {
      if (settled) return; settled = true;
      try {
        var game = new mod.DerbyGame(canvas, bets, balance, selectedChip, addLog);
        game.enableAutoWipeOnExit(wipeExitChk.checked);
        window.__derby = game;
        window.__derbyMode = 'full';
        window.__derbyBooted = true;
        game.start();
      } catch (err) { fail(err); }
    }
    try {
      Promise.resolve(import('./main.js')).then(succeed, fail);
      setTimeout(function () { fail(new Error('module load timeout')); }, 8000);
    } catch (err) { fail(err); }
  }

  function startLite() {
    liteRunning = true;
    window.__derbyMode = 'lite';
    window.__derbyBooted = true;
    overlay.classList.add('hidden');
    statusEl.textContent = 'Lite mode running (opened from disk — serve over HTTP for the full A* game).';
    addLog('Started in lite mode (file:// fallback). Serve web/ over HTTP for the full game.', '');
    var g = new LiteGame();
    window.__derbyLite = g;
    g.loop();
  }

  function beginRace() {
    if (liteRunning || window.__derby) return; // already started
    loadFullGame();
  }

  // ===========================================================================
  // INIT
  // ===========================================================================
  function init() {
    buildRows();
    wireSidebar();
    seedIdleHorses();
    buildStaticBg();
    drawIdleScene();
    statusEl.textContent = 'Place bets, then press START RACE.';

    startBtn.addEventListener('click', beginRace);
    window.addEventListener('keydown', function (e) {
      if (e.code === 'Space') { e.preventDefault(); beginRace(); }
    });

    // Clicking a horse on the idle scene places a bet on it.
    canvas.addEventListener('mousedown', function (e) {
      if (window.__derby || liteRunning) return; // real handlers take over
      var r = canvas.getBoundingClientRect();
      var mx = (e.clientX - r.left) * (canvas.width / r.width);
      var my = (e.clientY - r.top) * (canvas.height / r.height);
      for (var i = 0; i < idleHorses.length; i++) {
        if (Math.hypot(idleHorses[i].x - mx, idleHorses[i].y - my) < 26) {
          placeBet(idleHorses[i].name, selectedChip);
          return;
        }
      }
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else init();
})();
