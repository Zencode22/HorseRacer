// ============================================================================
// HORSE MEMORY - "Each horse recalls their past runs and improves with new
// attempts." Port of the ranking/persistence idea from models/ranking.py,
// extended into an actual learning system.
//
// Memory layout (per horse name):
// {
//   races: int, wins: int, bestTime: float|null, lastTime: float|null,
//   avgTime: float, totalResets: int,
//   history: [ {time, resets} ... ] (last 20 runs),
//   checkpointTimes: [float x 9]      (avg seconds per checkpoint segment),
//   skill: float                      (0..1 learned skill -> speed boost)
// }
// ============================================================================

import { NUM_HORSES, MEMORY_KEY } from './config.js';

export const TOTAL_CHECKPOINTS = 9;

export function freshMemory() {
  return {
    horses: {}, // name -> memory record
  };
}

export function emptyHorseRecord(name) {
  return {
    name,
    races: 0,
    wins: 0,
    bestTime: null,
    lastTime: null,
    avgTime: null,
    totalResets: 0,
    history: [],
    checkpointTimes: new Array(TOTAL_CHECKPOINTS).fill(null),
    skill: 0,
  };
}

export function loadMemory() {
  try {
    const raw = localStorage.getItem(MEMORY_KEY);
    if (!raw) return freshMemory();
    const data = JSON.parse(raw);
    if (!data || typeof data !== 'object' || !data.horses) return freshMemory();
    return data;
  } catch (e) {
    console.warn('Could not load horse memory:', e);
    return freshMemory();
  }
}

export function saveMemory(memory) {
  try {
    localStorage.setItem(MEMORY_KEY, JSON.stringify(memory));
  } catch (e) {
    console.warn('Could not save horse memory:', e);
  }
}

export function wipeMemory(memory, names) {
  for (const n of names) delete memory.horses[n];
  saveMemory(memory);
}

export function getRecord(memory, name) {
  if (!memory.horses[name]) memory.horses[name] = emptyHorseRecord(name);
  return memory.horses[name];
}

// Skill grows with completed races (diminishing returns), shrinks slightly
// when a run needed many stuck-resets (bad route recall).
export function computeSkill(record) {
  let s = Math.min(1, record.races * 0.12);
  const badRuns = record.history.filter((h) => h.resets > 0).length;
  s -= Math.min(0.2, badRuns * 0.02);
  return Math.max(0, Math.min(1, s));
}

export function recordFinish(record, finishTime, resets, segmentTimes) {
  record.races += 1;
  record.lastTime = finishTime;
  record.totalResets += resets;
  record.history.push({ time: finishTime, resets });
  if (record.history.length > 20) record.history.shift();

  record.bestTime = record.bestTime === null ? finishTime : Math.min(record.bestTime, finishTime);

  const times = record.history.map((h) => h.time);
  record.avgTime = times.reduce((a, b) => a + b, 0) / times.length;

  // Exponential moving average of per-checkpoint segment times -> used to
  // predict finishing order & set odds.
  for (let i = 0; i < segmentTimes.length && i < TOTAL_CHECKPOINTS; i++) {
    const t = segmentTimes[i];
    if (t == null) continue;
    const prev = record.checkpointTimes[i];
    record.checkpointTimes[i] = prev == null ? t : prev * 0.6 + t * 0.4;
  }

  record.skill = computeSkill(record);
}

export function predictedTime(record) {
  const known = record.checkpointTimes.filter((t) => t != null);
  if (known.length === 0) return null;
  const sumKnown = known.reduce((a, b) => a + b, 0);
  const avgKnown = sumKnown / known.length;
  return sumKnown + avgKnown * (TOTAL_CHECKPOINTS - known.length);
}

export function winProbability(records) {
  // inverse of predicted time (skill-shaved), normalized
  const preds = records.map((r) => {
    const p = predictedTime(r);
    if (p != null) return Math.max(4, p * (1 - 0.12 * r.skill));
    return 30 - 8 * r.skill; // no memory yet: skill still gives an edge
  });
  const inv = preds.map((p) => 1 / p);
  const tot = inv.reduce((a, b) => a + b, 0) || 1;
  return inv.map((v) => v / tot);
}

export function oddsFromProb(p) {
  return Math.max(1.1, Math.round((0.92 / p) * 10) / 10);
}
