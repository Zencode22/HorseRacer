// ============================================================================
// Headless simulation harness for the browser port (web/js).
// Bundles the ES modules into plain JS and runs full races to verify that:
//   1. every horse completes the checkpoint circuit (no soft-locks)
//   2. horses improve over successive races via the memory/skill system
// Run with: node tests/harness.cjs
// ============================================================================
const fs = require('fs');

const read = (p) => fs.readFileSync('./web/js/' + p, 'utf8');

let SRC = ['vector2.js', 'grid.js', 'astar.js', 'config.js', 'track.js', 'memory.js', 'horse.js']
  .map(read).join('\n\n')
  .replace(/^export\s+/gm, '')          // strip ES module syntax
  .replace(/^import\s[^;]+;\s*$/gm, '');

SRC += `
module.exports = { RaceTrack, Horse, getRecord, recordFinish, winProbability, oddsFromProb,
                   WIDTH, HEIGHT, NUM_HORSES, HORSE_NAMES };
`;

const bundlePath = '/tmp/derby_bundle.cjs';
fs.writeFileSync(bundlePath, SRC);
const { RaceTrack, Horse, getRecord, recordFinish, winProbability, oddsFromProb,
        WIDTH, HEIGHT, NUM_HORSES, HORSE_NAMES } = require(bundlePath);

function makeSim() {
  const track = new RaceTrack(WIDTH, HEIGHT);
  const memory = { horses: {} };
  const starts = track.getSpreadStartPositions(NUM_HORSES);
  const colors = ['#ff3b30', '#3b82f6', '#ffd60a', '#a855f7', '#ff9500', '#e8e8e8'];
  const horses = [];
  for (let i = 0; i < NUM_HORSES; i++) {
    const h = new Horse(starts[i].x, starts[i].y, colors[i]);
    h.track = track;
    h.setName(HORSE_NAMES[i], i);
    h.applySkill(0);
    h.target = track.checkpointPositions[0];
    h.requestNewPath(track.pathfinder);
    horses.push(h);
  }
  return { track, memory, horses };
}

function runRace(sim) {
  const { memory, horses, track } = sim;
  for (const h of horses) {
    h.hasFinished = false; h.finishTime = null; h.currentCheckpointIndex = 0;
    h.checkpointReachedTime = 0; h.segmentTimes.fill(null); h.lastCheckpointStamp = null;
    h.resetsThisRace = 0; h.stuckTimer = 0; h.wrongDirectionPenalty = 0; h.consecutiveBarrierHits = 0;
    h.raceStartTime = track.simTime;
  }
  let frame = 0;
  const order = [];
  while (order.length < NUM_HORSES && frame < 60 * 240) {
    for (const h of horses) {
      if (h.hasFinished) continue;
      h.flock(horses);
      h.update([WIDTH, HEIGHT]);
      track.simTime += 1 / 60;
      if (h.hasFinished) {
        order.push(h.name);
        const rec = getRecord(memory, h.name);
        recordFinish(rec, h.finishTime, h.resetsThisRace, h.segmentTimes);
        rec.lines = h.preferredLine;
      }
    }
    frame++;
  }
  return { frame, order, times: horses.map((h) => ({ name: h.name, t: h.finishTime, resets: h.resetsThisRace, cp: h.currentCheckpointIndex })) };
}

let failures = 0;
const sim = makeSim();
console.log('checkpoints:', sim.track.getTotalCheckpoints());

let race1Slowest = null;
for (let r = 1; r <= 6; r++) {
  const res = runRace(sim);
  const done = res.times.filter((x) => x.t != null).length;
  if (r === 1) race1Slowest = Math.max(...res.times.map((x) => x.t ?? Infinity));
  console.log(`race ${r}: finished ${done}/${NUM_HORSES}, frames=${res.frame}`);
  for (const x of res.times) console.log('   ', x.name, x.t ? x.t.toFixed(2) + 's' : 'DNF(cp' + x.cp + ')', 'resets=' + x.resets);
  if (done < NUM_HORSES) { console.log('*** FAILURE: not all horses finished ***'); failures++; break; }
  for (const h of sim.horses) h.applySkill(getRecord(sim.memory, h.name).skill);
}

const skills = sim.horses.map((h) => getRecord(sim.memory, h.name).skill);
if (skills.some((s) => s <= 0)) { console.log('*** FAILURE: skill did not increase ***'); failures++; }

const finalAvg = sim.horses.reduce((a, h) => a + getRecord(sim.memory, h.name).avgTime, 0) / NUM_HORSES;
console.log(`improvement check: race-1 slowest finish ${race1Slowest?.toFixed(2)}s vs final avg ${finalAvg.toFixed(2)}s`);

const probs = winProbability(sim.horses.map((h) => getRecord(sim.memory, h.name)));
const odds = probs.map(oddsFromProb);
console.log('odds:', sim.horses.map((h, i) => `${h.name} ${odds[i].toFixed(1)}x`).join('  '));
if (Math.abs(probs.reduce((a, b) => a + b, 0) - 1) > 1e-6) { console.log('*** FAILURE: probabilities do not sum to 1 ***'); failures++; }

console.log(failures === 0 ? 'ALL CHECKS PASSED' : `${failures} FAILURE(S)`);
process.exit(failures === 0 ? 0 : 1);
