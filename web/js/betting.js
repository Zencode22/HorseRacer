// ============================================================================
// PLAYER BETTING SYSTEM (fake money)
//  * Bankroll lives in sessionStorage -> wiped when the tab/browser closes
//    ("memory can be wiped ... when the program is exited out")
//  * Player places bets on horses before each race; pari-mutuel-style payout
//    with a house edge, odds derived from each horse's remembered performance.
// ============================================================================

import { STARTING_BALANCE, BET_CHIP_VALUES, BALANCE_KEY } from './config.js';

export class BettingSystem {
  constructor(overrideBalance = null) {
    this.balance = overrideBalance != null ? overrideBalance : this._loadBalance();
    this.bets = {};          // horseName -> amount wagered this race
    this.lastResults = null; // payout summary of previous race
    this.history = [];       // recent race results for the UI log
  }

  _loadBalance() {
    try {
      const v = sessionStorage.getItem(BALANCE_KEY);
      if (v === null) return STARTING_BALANCE;
      const n = parseInt(v, 10);
      return Number.isFinite(n) && n >= 0 ? n : STARTING_BALANCE;
    } catch (e) {
      return STARTING_BALANCE;
    }
  }

  _saveBalance() {
    try { sessionStorage.setItem(BALANCE_KEY, String(this.balance)); } catch (e) { /* ignore */ }
  }

  get chipValues() { return BET_CHIP_VALUES; }

  get totalWagered() {
    return Object.values(this.bets).reduce((a, b) => a + b, 0);
  }

  canAfford(amount) {
    return amount > 0 && amount <= this.balance - this.totalWagered;
  }

  placeBet(horseName, amount) {
    if (!this.canAfford(amount)) return false;
    this.bets[horseName] = (this.bets[horseName] || 0) + amount;
    this._saveBalance();
    return true;
  }

  removeBet(horseName) {
    if (this.bets[horseName]) {
      delete this.bets[horseName];
      this._saveBalance();
    }
  }

  clearBets() {
    this.bets = {};
    this._saveBalance();
  }

  // Pari-mutuel pool with 8% takeout. Unbet winners pay $2 to show.
  settle(winnerName) {
    const pool = this.totalWagered;
    let payout = 0;
    const details = [];

    for (const [name, amt] of Object.entries(this.bets)) {
      if (name === winnerName) {
        const winPool = this.bets[winnerName] || 0;
        const netPool = pool * 0.92;
        const share = winPool > 0 ? (amt / winPool) * netPool : 2;
        payout += share;
        details.push({ name, bet: amt, won: share });
      } else {
        details.push({ name, bet: amt, won: 0 });
      }
    }

    payout = Math.round(payout);
    const profit = payout - pool;
    this.balance += payout; // staked money was already deducted from spendable balance
    this._saveBalance();

    this.lastResults = {
      winner: winnerName,
      staked: pool,
      payout,
      profit,
      details,
    };
    this.history.unshift({
      winner: winnerName,
      staked: pool,
      profit,
      balance: this.balance,
      time: new Date().toLocaleTimeString(),
    });
    if (this.history.length > 8) this.history.pop();

    this.bets = {};
    return this.lastResults;
  }

  resetBankroll() {
    this.balance = STARTING_BALANCE;
    this.bets = {};
    this.lastResults = null;
    this.history = [];
    this._saveBalance();
  }
}
