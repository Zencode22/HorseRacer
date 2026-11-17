// ============================================================================
// HORSE RACE DERBY - browser port of game/horse_race_game.py + main.py
//  * Race simulation on a canvas (60 FPS)
//  * Betting phase between races (fake money, pari-mutuel payout)
//  * Horse memory: past runs improve each horse; wipeable by user or on exit
// ============================================================================

import {
  WIDTH, HEIGHT, NUM_HORSES, HORSE_NAMES, COLORS, STARTING_BALANCE,
  MEMORY_KEY, BALANCE_KEY,
} from './config.js';
import { Vector2 } from './vector2.js';
import { RaceTrack } from './track.js';
import { Horse } from './horse.js';
import {
  loadMemory, saveMemory, flushMemory, getRecord, recordFinish, wipeMemory,
  winProbability, oddsFromProb, predictedTime, computeSkill,
} from './memory.js';
import { BettingSystem } from './betting.js';

const HORSE_COLORS = [COLORS.RED, COLORS.BLUE, COLORS.YELLOW, COLORS.PURPLE, COLORS.ORANGE, '#e8e8e8'];

export class DerbyGame {
  // bootState comes from js/boot.js: the player places bets on the classic
  // script betting screen BEFORE this module is even loaded (dynamic
  // import), so we adopt balance + wagers here and carry them straight
  // into the first race.
  constructor(canvas, bootState = null) {
    const boot = bootState || {};
    this.canvas = canvas;
    this.ctx = canvas.getContext('2d');
    this.track = new RaceTrack(WIDTH, HEIGHT);

    this.memory = loadMemory();
    this.betting = new BettingSystem(boot.balance);

    // Bets placed on the classic-script boot screen (js/boot.js) before this
    // module was dynamically imported. NOTE: placeBet() checks affordability
    // against balance MINUS what is already wagered, so we must deduct each
    // adopted bet from the spendable balance ourselves as we go — otherwise
    // only the first carried-over bet would ever be accepted.
    if (boot.bets && Object.keys(boot.bets).length) {
      for (const [k, v] of Object.entries(boot.bets)) {
        if (this.betting.placeBet(k, v)) this.betting.balance -= v;
      }
      this._adoptedBootBets = Object.keys(this.betting.bets).length > 0;
    } else {
      this._adoptedBootBets = false;
    }

    this.horses = [];
    const starts = this.track.getSpreadStartPositions(NUM_HORSES);
    for (let i = 0; i < NUM_HORSES; i++) {
      const h = new Horse(starts[i].x, starts[i].y, HORSE_COLORS[i % HORSE_COLORS.length]);
      h.track = this.track;
      h.setName(HORSE_NAMES[i], i);
      this._restoreHorseMemory(h);
      this.horses.push(h);
    }

    // state machine: 'betting' | 'racing' | 'results'
    this.state = 'betting';
    this.selectedChip = boot.chip || 25;
    this.raceFinishedCount = 0;
    this.order = [];          // finish order (horse names)
    this.settlement = null;   // last payout info
    this.odds = {};           // name -> decimal odds
    this.resultsTimer = 0;

    this.lastFrame = performance.now();
    this.fps = 60;
    this.raf = null;

    // LOAD PERFORMANCE: heavy setup (path requests, static track render) is
    // deferred to after the first paint so the page becomes interactive
    // immediately instead of blocking on computation for minutes.
    this._ready = false;

    this.recomputeOdds();
    this.resetHorsesToStart();

    this._bindUI();
    this.updateUI();
  }

  _finishDeferredSetup() {
    if (this._ready) return;
    this._ready = true;
    // Pre-render the static track surface and prime pathfinding caches now
    // that the browser has already painted the loading screen.
    this.track.prepare();
    for (const h of this.horses) h.requestNewPath(this.track.pathfinder);
  }

  // ---------------------------------------------------------------- horses --

  _restoreHorseMemory(h) {
    const rec = getRecord(this.memory, h.name);
    h.skill = rec.skill;
    h.attempts = rec.races;
    h.preferredLine = {};
    if (rec.lines) {
      for (const [k, v] of Object.entries(rec.lines)) h.preferredLine[k] = v;
    }
    h.applySkill(rec.skill);
  }

  _saveHorseLines(h) {
    const rec = getRecord(this.memory, h.name);
    rec.lines = h.preferredLine;
  }

  resetHorsesToStart() {
    const starts = this.track.getSpreadStartPositions(NUM_HORSES);
    for (let i = 0; i < this.horses.length; i++) {
      const h = this.horses[i];
      const sp = starts[i];
      h.position = sp.copy();
      h.velocity = this.track.getForwardDirection(sp).mult(2.0);
      h.acceleration = new Vector2(0, 0);
      h.hasFinished = false;
      h.finishTime = null;
      h.currentCheckpointIndex = 0;
      h.checkpointReachedTime = 0;
      h.segmentTimes.fill(null);
      h.lastCheckpointStamp = null;
      h.barrierMemory.clear();
      h.consecutiveBarrierHits = 0;
      h.stuckTimer = 0;
      h.resetCooldown = 0;
      h.resetsThisRace = 0;
      h.wrongDirectionPenalty = 0;
      h.pathHistory = [];
      h.lastPosition = sp.copy();
      h.target = this.track.checkpointPositions[0];
      // NOTE: no path request here anymore. Paths are requested lazily on the
      // first race frame (see tick()), which keeps page load instantaneous.
    }
    this.order = [];
    this.settlement = null;
  }

  // One simulation step. Guarded so a heavy frame can never lock up the tab:
  // at most one path search per horse per interval, and if a single update
  // would exceed the frame budget we skip the rest of the batch (the browser
  // stays responsive; the sim simply continues next frame).
  tick() {
    const t0 = performance.now();
    for (const h of this.horses) {
      if (h.hasFinished) continue;
      h.flock(this.horses);
      h.update([WIDTH, HEIGHT]);
      if (h.hasFinished) {
        this.raceFinishedCount += 1;
        this.order.push(h.name);
        const rec = getRecord(this.memory, h.name);
        recordFinish(rec, h.finishTime, h.resetsThisRace, h.segmentTimes);
        if (this.order.length === 1) rec.wins += 1;
        this._saveHorseLines(h);
        saveMemory(this.memory);
      }
      if (performance.now() - t0 > 12) break; // frame budget guard
    }
    if (this.raceFinishedCount >= NUM_HORSES) {
      this.finishRace();
    }
  }

  // ----------------------------------------------------------------- race --

  startRace() {
    if (this.state === 'racing') return;
    // The player pressed START on the boot screen: skip the betting phase,
    // jump straight into the race with the adopted bets.
    const hadBootBets = this._adoptedBootBets && Object.keys(this.betting.bets).length > 0;
    this._adoptedBootBets = false;
    this._finishDeferredSetup(); // idempotent safety net
    this.resetHorsesToStart();
    // Fresh race clock: horses measure finish times against track.simTime,
    // so stamp every racer's start time AFTER resetting them to the line.
    for (const h of this.horses) h.raceStartTime = null;
    for (const h of this.horses) {
      h.raceStartTime = this.track.simTime;
      h.requestNewPath(this.track.pathfinder); // lazy first path, now racing
    }
    this.state = 'racing';
    this.raceFinishedCount = 0;
    this.recomputeOdds();
    this.updateUI();
    if (hadBootBets) {
      const parts = [];
      for (const [k, v] of Object.entries(this.betting.bets)) parts.push(`${k} $${v}`);
      this.setStatus('Race started — your bets: ' + parts.join(', '));
    } else {
      this.setStatus('Race started — no bets placed.');
    }
  }

  setStatus(msg) {
    if (this.el && this.el.status) this.el.status.textContent = msg;
  }

  recomputeOdds() {
    const records = this.horses.map((h) => getRecord(this.memory, h.name));
    const probs = winProbability(records);
    this.odds = {};
    this.horses.forEach((h, i) => { this.odds[h.name] = oddsFromProb(probs[i]); });
  }

  update(dt) {
    if (this.state !== 'racing') return;
    // Guard: a horse stuck mid-circuit can stall the whole race forever.
    // If no new finisher has appeared for a long stretch, force-close the
    // race with whatever order we have (the rest are marked finished) so
    // the game always returns to the betting window instead of hanging on
    // "RACING" with an empty loading screen.
    if (this.raceFinishedCount < this.order.length) this._noProgressTimer = 0;
    else this._noProgressTimer += dt;
    if (this.order.length > 0 && this.raceFinishedCount < NUM_HORSES &&
        this._noProgressTimer > 45) {
      for (const h of this.horses) {
        if (!h.hasFinished) {
          h.markFinished();
          // A DNF horse must not poison the learning data with a bogus
          // (huge) finish time — record it as a reset-heavy run instead.
          h.finishTime = null;
          this.order.push(h.name);
          this.raceFinishedCount += 1;
        }
      }
    }

    this.track.simTime += 1 / 60; // fixed timestep keeps physics stable
    this.tick();
  }

  finishRace() {
    this.state = 'results';
    flushMemory(); // persist the whole race's learning in ONE debounced write
    const winner = this.order[0];
    if (this.betting.totalWagered > 0) {
      this.settlement = this.betting.settle(winner);
    } else {
      this.settlement = { winner, staked: 0, payout: 0, profit: 0, details: [] };
    }
    for (const h of this.horses) this._restoreHorseMemory(h); // apply new skill levels
    this.resultsTimer = 4.0; // auto-return to betting after 4s
    this.updateUI();
  }

  backToBetting() {
    this.state = 'betting';
    this.resetHorsesToStart();
    this.recomputeOdds();
    this.updateUI();
  }

  // ------------------------------------------------------------- memory UI --

  wipeAllMemory() {
    if (!confirm('Wipe ALL horse memories? Every horse forgets its past runs and resets to rookie form.')) return;
    wipeMemory(this.memory, HORSE_NAMES);
    flushMemory(); // user action: persist immediately, don't wait for debounce
    for (const h of this.horses) {
      h.preferredLine = {};
      h.applySkill(0);
      h.skill = 0;
      h.attempts = 0;
    }
    this.recomputeOdds();
    this.updateUI();
  }

  // Wipe memory when the program is exited out (tab closed / page unloaded).
  wipeOnExit() {
    try {
      localStorage.removeItem(MEMORY_KEY);
      sessionStorage.removeItem(BALANCE_KEY);
    } catch (e) { /* ignore */ }
  }

  enableAutoWipeOnExit() {
    window.addEventListener('beforeunload', () => this.wipeOnExit());
    window.addEventListener('pagehide', () => this.wipeOnExit());
  }

  // ------------------------------------------------------------------ loop --

  start() {
    // LOAD PERFORMANCE: never let a slow/failed module evaluation leave the
    // loading overlay up forever. If no first frame has painted within 5s we
    // surface a clear message + recovery action instead of an endless spinner.
    this._firstFrameDone = false;
    setTimeout(() => {
      if (this._firstFrameDone) return;
      const overlay = document.getElementById('loading-overlay');
      const text = document.getElementById('loading-text');
      if (overlay && !overlay.classList.contains('hidden') && text) {
        text.innerHTML = 'Still loading after 5 seconds? <br>' +
          '<button id="force-start" style="margin-top:10px">Retry now</button>';
        const btn = document.getElementById('force-start');
        if (btn) btn.addEventListener('click', () => {
          try { this._finishDeferredSetup(); this.draw(); } catch (e) { console.error(e); }
          overlay.classList.add('hidden');
        });
      }
    }, 5000);

    const step = (now) => {
      const dt = Math.min(0.05, (now - this.lastFrame) / 1000);
      this.lastFrame = now;
      this.fps = this.fps * 0.95 + (1 / Math.max(dt, 1e-4)) * 0.05;

      if (!this._ready) this._finishDeferredSetup(); // after first paint

      this.update(dt);

      if (this.state === 'results') {
        this.resultsTimer -= dt;
        if (this.resultsTimer <= 0) this.backToBetting();
      }

      this.draw();
      this.updateLiveUI();
      if (!this._firstFrameDone) {
        this._firstFrameDone = true;
        const overlay = document.getElementById('loading-overlay');
        if (overlay) overlay.classList.add('hidden');
        const statusEl = document.getElementById('status-line');
        if (statusEl) statusEl.textContent = 'Ready.';
      }
      this.raf = requestAnimationFrame(step);
    };
    this.raf = requestAnimationFrame(step);
  }

  stop() { if (this.raf) cancelAnimationFrame(this.raf); }

  // ----------------------------------------------------------------- draw --

  draw() {
    const ctx = this.ctx;
    this.track.draw(ctx);

    for (const h of this.horses) h.draw(ctx);

    // HUD top-left
    ctx.textAlign = 'left';
    ctx.textBaseline = 'top';
    ctx.font = 'bold 15px monospace';
    let hud = '';
    if (this.state === 'betting') hud = 'PLACE YOUR BETS, then START RACE (or press SPACE)';
    else if (this.state === 'racing') {
      const done = this.horses.filter((h) => h.hasFinished).length;
      hud = `RACING  |  Finished: ${done}/${NUM_HORSES}  |  Time: ${this.raceTime().toFixed(2)}s`;
    } else hud = 'RACE COMPLETE!';

    const w = ctx.measureText(hud).width + 20;
    ctx.fillStyle = 'rgba(0,0,0,0.65)';
    ctx.fillRect(8, 8, w, 26);
    ctx.fillStyle = this.state === 'racing' ? COLORS.YELLOW : '#7CFC00';
    ctx.fillText(hud, 18, 14);

    if (this.state === 'results') this.drawResultsBoard(ctx);
  }

  raceTime() {
    if (!this.horses.length) return 0;
    const first = this.horses.find((h) => h.raceStartTime != null);
    if (!first) return 0;
    if (this.state !== 'racing') {
      const times = this.horses.map((h) => h.finishTime).filter((t) => t != null);
      return times.length ? Math.max(...times) : 0;
    }
    return this.track.simTime - first.raceStartTime;
  }

  drawResultsBoard(ctx) {
    const pw = 560, ph = 330;
    const px = (WIDTH - pw) / 2, py = (HEIGHT - ph) / 2;
    ctx.fillStyle = 'rgba(0,0,0,0.72)';
    ctx.fillRect(0, 0, WIDTH, HEIGHT);
    ctx.fillStyle = COLORS.DARK_BROWN;
    ctx.fillRect(px, py, pw, ph);
    ctx.strokeStyle = COLORS.YELLOW;
    ctx.lineWidth = 4;
    ctx.strokeRect(px, py, pw, ph);

    ctx.textAlign = 'center';
    ctx.fillStyle = COLORS.YELLOW;
    ctx.font = 'bold 28px monospace';
    ctx.fillText('RACE RESULTS', WIDTH / 2, py + 18);

    ctx.font = 'bold 16px monospace';
    let y = py + 58;
    this.order.forEach((name, i) => {
      const h = this.horses.find((x) => x.name === name);
      const rec = getRecord(this.memory, name);
      ctx.textAlign = 'left';
      ctx.fillStyle = COLORS.WHITE;
      ctx.fillText(`${i + 1}.`, px + 30, y - 4);
      ctx.fillStyle = h.color;
      ctx.fillText(name, px + 65, y - 4);
      ctx.fillStyle = COLORS.WHITE;
      ctx.fillText(`${(h.finishTime ?? 0).toFixed(2)}s`, px + 200, y - 4);
      ctx.fillStyle = '#bbb';
      ctx.fillText(`tries ${rec.races}  best ${rec.bestTime ? rec.bestTime.toFixed(2) + 's' : '--'}`, px + 300, y - 4);
      y += 26;
    });

    y += 8;
    ctx.textAlign = 'center';
    if (this.settlement && this.settlement.staked > 0) {
      const s = this.settlement;
      ctx.font = 'bold 18px monospace';
      ctx.fillStyle = s.profit >= 0 ? '#7CFC00' : '#ff6b6b';
      ctx.fillText(
        `Wagered $${s.staked}  →  Paid $${s.payout}   (${s.profit >= 0 ? '+' : ''}$${s.profit})`,
        WIDTH / 2, y,
      );
      y += 26;
    } else {
      ctx.font = '14px monospace';
      ctx.fillStyle = '#ccc';
      ctx.fillText('No bets were placed this race.', WIDTH / 2, y);
      y += 26;
    }

    ctx.font = '14px monospace';
    ctx.fillStyle = '#aaa';
    ctx.fillText(`Returning to betting window in ${Math.max(0, this.resultsTimer).toFixed(1)}s…`, WIDTH / 2, py + ph - 44);

    // Next race button
    const bw = 200, bh = 34;
    const bx = WIDTH / 2 - bw / 2, by = py + ph - 34;
    ctx.fillStyle = COLORS.GREEN;
    ctx.fillRect(bx, by, bw, bh);
    ctx.strokeStyle = '#fff'; ctx.lineWidth = 2; ctx.strokeRect(bx, by, bw, bh);
    ctx.fillStyle = '#fff';
    ctx.font = 'bold 15px monospace';
    ctx.fillText('NEXT RACE NOW', WIDTH / 2, by + 9);
    this._nextBtn = { x: bx, y: by, w: bw, h: bh };
  }

  // -------------------------------------------------------------- click map --

  handleCanvasClick(mx, my) {
    if (this.state === 'results' && this._nextBtn) {
      const b = this._nextBtn;
      if (mx >= b.x && mx <= b.x + b.w && my >= b.y && my <= b.y + b.h) {
        this.backToBetting();
      }
      return;
    }
    if (this.state === 'betting') {
      for (const h of this.horses) {
        const d = Math.hypot(h.position.x - mx, h.position.y - my);
        if (d < 26) { this.addBet(h.name); return; }
      }
    }
  }

  // -------------------------------------------------------------------- UI --

  _bindUI() {
    this.el = {
      balance: document.getElementById('balance'),
      totalBet: document.getElementById('total-bet'),
      chipSel: document.getElementById('chip-select'),
      betRows: document.getElementById('bet-rows'),
      startBtn: document.getElementById('start-race'),
      clearBtn: document.getElementById('clear-bets'),
      wipeBtn: document.getElementById('wipe-memory'),
      wipeExitChk: document.getElementById('wipe-on-exit'),
      resetBank: document.getElementById('reset-bank'),
      status: document.getElementById('status-line'),
      log: document.getElementById('bet-log'),
    };

    for (const opt of this.el.chipSel.querySelectorAll('option')) {
      opt.textContent = `$${opt.value}`;
    }
    this.el.chipSel.addEventListener('change', () => {
      this.selectedChip = parseInt(this.el.chipSel.value, 10);
    });

    this.el.startBtn.addEventListener('click', () => this.startRace());
    this.el.clearBtn.addEventListener('click', () => { this.betting.clearBets(); this.updateUI(); });
    this.el.wipeBtn.addEventListener('click', () => this.wipeAllMemory());
    this.el.resetBank.addEventListener('click', () => {
      if (confirm('Reset bankroll to $' + STARTING_BALANCE + '?')) { this.betting.resetBankroll(); this.updateUI(); }
    });
    this.el.wipeExitChk.addEventListener('change', () => {
      if (this.el.wipeExitChk.checked) this.enableAutoWipeOnExit();
    });

    this.canvas.addEventListener('mousedown', (e) => {
      const r = this.canvas.getBoundingClientRect();
      const sx = this.canvas.width / r.width, sy = this.canvas.height / r.height;
      this.handleCanvasClick((e.clientX - r.left) * sx, (e.clientY - r.top) * sy);
    });

    window.addEventListener('keydown', (e) => {
      if (e.code === 'Space') { e.preventDefault(); if (this.state !== 'racing') this.startRace(); }
      if (e.key === 'r' || e.key === 'R') { if (this.state === 'racing') { this.resetHorsesToStart(); } }
    });

    this.buildBetRows();
  }

  buildBetRows() {
    this.el.betRows.innerHTML = '';
    this.rowRefs = {};
    for (const h of this.horses) {
      const row = document.createElement('div');
      row.className = 'bet-row';

      const swatch = document.createElement('span');
      swatch.className = 'swatch';
      swatch.style.background = h.color;

      const name = document.createElement('span');
      name.className = 'hname';
      name.textContent = h.name;

      const stats = document.createElement('span');
      stats.className = 'hstats';

      const odds = document.createElement('span');
      odds.className = 'odds';

      const bet = document.createElement('span');
      bet.className = 'betamt';

      const plus = document.createElement('button');
      plus.className = 'chip-btn';
      plus.textContent = '+';
      plus.title = `Bet $${this.selectedChip} on ${h.name}`;
      plus.addEventListener('click', () => { this.addBet(h.name); this.updateUI(); });

      const minus = document.createElement('button');
      minus.className = 'chip-btn small';
      minus.textContent = '−';
      minus.title = `Remove bets on ${h.name}`;
      minus.addEventListener('click', () => { this.betting.removeBet(h.name); this.updateUI(); });

      row.append(swatch, name, stats, odds, bet, plus, minus);
      this.el.betRows.appendChild(row);
      this.rowRefs[h.name] = { row, stats, odds, bet, plus };
    }
  }

  addBet(horseName) {
    if (this.state !== 'betting') return;
    this.betting.placeBet(horseName, this.selectedChip);
  }

  updateUI() {
    this.el.balance.textContent = `$${this.betting.balance}`;
    for (const h of this.horses) {
      const ref = this.rowRefs[h.name];
      const rec = getRecord(this.memory, h.name);
      const pred = predictedTime(rec);
      const hist = rec.history.slice(-5).map((x) => x.time.toFixed(1)).join(', ');
      ref.stats.textContent = rec.races
        ? `${rec.races} runs · ${rec.wins}W · best ${rec.bestTime ? rec.bestTime.toFixed(2) : '--'}s` +
          (hist ? ` · last: ${hist}s` : '')
        : 'ROOKIE — no memory of past runs';
      ref.odds.textContent = `${(this.odds[h.name] ?? 2).toFixed(1)}×`;
      ref.bet.textContent = this.betting.bets[h.name] ? `$${this.betting.bets[h.name]}` : '';
      ref.plus.disabled = this.state !== 'betting';
    }
    this.el.startBtn.disabled = this.state === 'racing';
    this.el.startBtn.textContent = this.state === 'racing' ? 'RACE IN PROGRESS…' : '🏇 START RACE';
    this.el.totalBet.textContent = `$${this.betting.totalWagered}`;

    // log
    this.el.log.innerHTML = '';
    for (const entry of this.betting.history) {
      const li = document.createElement('li');
      const cls = entry.profit > 0 ? 'win' : entry.profit < 0 ? 'lose' : '';
      li.className = cls;
      li.textContent =
        `${entry.time} — ${entry.winner} won · wagered $${entry.staked} · ` +
        `${entry.profit >= 0 ? '+' : ''}$${entry.profit} · bank $${entry.balance}`;
      this.el.log.appendChild(li);
    }
  }

  updateLiveUI() {
    // lightweight per-frame status line only
    let msg;
    if (this.state === 'betting') {
      msg = `Balance $${this.betting.balance} · Chip $${this.selectedChip} · Click + (or a horse on track) to bet · SPACE to start`;
    } else if (this.state === 'racing') {
      const leader = [...this.horses]
        .sort((a, b) => (b.currentCheckpointIndex - a.currentCheckpointIndex))
        .find((h) => !h.hasFinished);
      msg = `Race time ${this.raceTime().toFixed(1)}s · Leader: ${leader ? leader.name : this.order[0]}`;
    } else {
      msg = `Winner: ${this.order[0]}!`;
      if (this.settlement && this.settlement.staked > 0) {
        msg += ` Payout ${this.settlement.profit >= 0 ? '+' : ''}$${this.settlement.profit}`;
      }
    }
    if (this.el.status.textContent !== msg) this.el.status.textContent = msg;
  }
}

// ============================================================================
// AUTO-START: js/boot.js dynamically imports this module when the player
// presses START RACE on the classic betting screen. Booting the full game
// immediately skips the redundant second betting phase — the race starts at
// once with whatever wagers were carried over from the boot screen.
// ============================================================================
if (typeof window !== 'undefined' && typeof document !== 'undefined') {
  window.addEventListener('DOMContentLoaded', () => {
    const boot = window.__derbyBoot || {};
    if (!boot.requested) return; // normal load: wait for a later START press
    try {
      const canvas = document.getElementById('game');
      const game = new DerbyGame(canvas, boot.bets, boot.balance, boot.chip);
      game.enableAutoWipeOnExit(!!boot.wipeOnExit);
      window.__derby = game;      // signal to boot.js: full mode is live
      window.__derbyMode = 'full';
      window.__derbyBooted = true;
      game.startRace();           // betting -> racing right away
      game.start();               // begin the render/sim loop
    } catch (err) {
      console.error(err);
      window.__derbyBootFailed = err; // boot.js polls this and falls back to lite
    }
  });
}
