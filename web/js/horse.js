// ============================================================================
// HORSE CLASS - port of models/horse.py (steering behaviors + learning)
// Improvements over the pygame version:
//  * maxSpeed scales with learned skill (horse "improves with new attempts")
//  * remembers a preferred racing line per checkpoint segment from its best
//    past run and follows it with extra weight on later attempts
// ============================================================================

import { Vector2, distance } from './vector2.js';
import { NodeState } from './grid.js';
import { TOTAL_CHECKPOINTS } from './memory.js';

function hashString(str) {
  let h = 2166136261;
  for (let i = 0; i < str.length; i++) { h ^= str.charCodeAt(i); h = Math.imul(h, 16777619); }
  return Math.abs(h);
}

export class Horse {
  constructor(x, y, color) {
    this.position = new Vector2(x, y);
    this.velocity = new Vector2(Math.random() * 4 - 2, Math.random() * 4 - 2);
    this.acceleration = new Vector2(0, 0);

    this.name = '';
    this.index = 0;

    // steering parameters
    // base speed tuned so a rookie lap takes ~16s at 60 FPS; each horse gets
    // a fixed (deterministic) talent offset so races are competitive but not
    // identical — memory/learning then layers on top of that.
    this.talent = 0; // set via setName() so it is deterministic per horse
    this.baseMaxSpeed = 13.5 * (1 + this.talent);
    this.maxSpeed = this.baseMaxSpeed;
    this.maxForce = 0.3;

    this.separationWeight = 1.0;
    this.pathWeight = 3.0;
    this.trackAttractionWeight = 3.0;
    this.barrierAvoidanceWeight = 5.0;
    this.checkpointWeight = 5.0;
    this.clockwiseWeight = 4.0;
    this.lineWeight = 0; // grows with experience

    // pathfinding
    this.target = null;
    this.currentPath = [];
    this.pathUpdateTimer = 0;
    this.pathUpdateInterval = 30;
    this.track = null;

    this.color = color;
    this.size = 10;

    // race state
    this.distanceTraveled = 0;
    this.currentCheckpointIndex = 0;
    this.totalCheckpoints = TOTAL_CHECKPOINTS;
    this.checkpointReachedTime = 0;
    this.hasFinished = false;
    this.finishTime = null;
    this.segmentTimes = new Array(TOTAL_CHECKPOINTS).fill(null);
    this.raceStartTime = null;
    this.lastCheckpointStamp = null;

    // barrier memory
    this.barrierMemory = new Set();
    this.maxMemorySize = 50;
    this.barrierDetectionRadius = 80;
    this.consecutiveBarrierHits = 0;
    this.maxConsecutiveHits = 8;
    this.lastBarrierHit = 0;

    // stuck detection
    this.stuckTimer = 0;
    this.stuckThreshold = 120;
    this.lastPosition = new Vector2(x, y);
    this.resetCooldown = 0;
    this.resetsThisRace = 0;

    // wrong direction tracking
    this.wrongDirectionPenalty = 0;

    // trail
    this.pathHistory = [];
    this.pathHistoryMax = 30;

    // learned preferred line (per segment), restored from memory
    this.preferredLine = {};   // segIndex -> [[x,y],...]
    this.skill = 0;
    this.attempts = 0;
  }

  setName(name, index) {
    this.name = name;
    this.index = index;
    // deterministic talent in [-0.15, +0.15] derived from the horse's identity
    const hsh = hashString(name + '|' + this.color);
    this.talent = ((hsh % 41) - 20) / 100; // -0.20..+0.20
    this.baseMaxSpeed = 13.5 * (1 + this.talent);
    this.applySkill(this.skill);
  }

  applySkill(skill) {
    // Horse improves with experience: up to +25% top speed and stronger
    // recall of its preferred racing line.
    this.skill = skill;
    this.maxSpeed = this.baseMaxSpeed * (1 + 0.25 * skill);
    this.lineWeight = 2.5 * skill;
  }

  now() { return this.track ? this.track.simTime : performance.now() / 1000; }

  requestNewPath(pathfinder) {
    if (this.target === null || this.hasFinished) return;
    // Safety net: never let a path search run unbounded. If the horse is far
    // from any known track point, skip searching entirely and steer straight
    // at the checkpoint (the attractToTrack/Checkpoint forces recover it).
    const nearTrack = this.track
      ? this.track.isPositionOnTrack(this.position)
      : true;
    if (!nearTrack) { this.currentPath = []; return; }
    const start = [this.position.x, this.position.y];
    const end = [this.target.x, this.target.y];
    const result = pathfinder.findPath(start, end);
    if (result.success) {
      this.currentPath = result.path;
      if (this.currentPath.length > 1) {
        const first = this.currentPath[0];
        const d = Math.hypot(first[0] - this.position.x, first[1] - this.position.y);
        if (d < 20) this.currentPath.shift();
      }
    }
  }

  updateCheckpoint() {
    if (this.hasFinished || !this.track) return;
    if (this.currentCheckpointIndex >= this.totalCheckpoints) return;

    const cp = this.track.checkpointPositions[this.currentCheckpointIndex];
    const dist = distance(this.position, cp);

    if (dist < this.track.checkpointRadius && this.checkpointReachedTime === 0) {
      const t = this.now();
      this.segmentTimes[this.currentCheckpointIndex] =
        this.lastCheckpointStamp == null ? t - this.raceStartTime : t - this.lastCheckpointStamp;
      this.lastCheckpointStamp = t;

      // did this segment beat my remembered line? If so, memorize this route.
      const segKey = String(this.currentCheckpointIndex);
      if (this.currentPath.length > 1) {
        const prev = this.preferredLine[segKey];
        const lenOf = (line) => {
          let L = 0;
          for (let i = 1; i < line.length; i++)
            L += Math.hypot(line[i][0] - line[i - 1][0], line[i][1] - line[i - 1][1]);
          return L;
        };
        if (!prev || lenOf(this.currentPath) < lenOf(prev) * 0.98) {
          this.preferredLine[segKey] = this.currentPath.slice(0, 60);
        }
      }

      if (this.currentCheckpointIndex === this.totalCheckpoints - 1) {
        this.markFinished();
        return;
      }

      this.currentCheckpointIndex += 1;
      this.checkpointReachedTime = 20;
      this.target = this.track.checkpointPositions[this.currentCheckpointIndex];
      this.barrierMemory.clear();
      this.consecutiveBarrierHits = 0;
      this.stuckTimer = 0;
      this.wrongDirectionPenalty = 0;
      this.requestNewPath(this.track.pathfinder);
    }

    if (this.checkpointReachedTime > 0) this.checkpointReachedTime -= 1;
  }

  checkIfStuck() {
    if (this.hasFinished) return false;
    if (this.resetCooldown > 0) { this.resetCooldown -= 1; return false; }

    const moved = distance(this.position, this.lastPosition);
    this.lastPosition = new Vector2(this.position.x, this.position.y);

    // "stuck" = barely moving for a long time (real stall), not just wandering
    const slow = this.velocity.mag() < 0.6 * this.maxSpeed;
    if (moved < 0.7 && slow) this.stuckTimer += 2;
    else this.stuckTimer = Math.max(0, this.stuckTimer - 2);

    if (this.stuckTimer > this.stuckThreshold) return true;
    if (this.consecutiveBarrierHits > this.maxConsecutiveHits) return true;
    if (this.wrongDirectionPenalty > 40 && (this._wdFrames || 0) > 25) return true;
    return false;
  }

  resetToStart() {
    if (this.hasFinished || !this.track) return;
    this.resetsThisRace += 1;

    const startPos = this.track.getStartPosition(this.index);
    this.position = startPos.copy();
    const forward = this.track.getForwardDirection(this.position);
    this.velocity = new Vector2(forward.x * 2, forward.y * 2);

    this.currentCheckpointIndex = 0;
    this.checkpointReachedTime = 0;
    this.barrierMemory.clear();
    this.consecutiveBarrierHits = 0;
    this.stuckTimer = 0;
    this.resetCooldown = 60;
    this.wrongDirectionPenalty = 0;
    this.pathHistory = [];
    this.lastPosition = this.position.copy();

    // re-route fresh around any barriers I now remember
    this.target = this.track.checkpointPositions[0];
    this.requestNewPath(this.track.pathfinder);
  }

  markFinished() {
    this.hasFinished = true;
    this.finishTime = this.now() - this.raceStartTime;
    this.velocity = new Vector2(0, 0);
    this.target = null;
    this.currentPath = [];
  }

  seek(target) {
    const desired = target.copy().sub(this.position);
    if (desired.mag() === 0) return new Vector2(0, 0);
    desired.normalize().mult(this.maxSpeed);
    const steer = desired.sub(this.velocity);
    steer.limit(this.maxForce);
    return steer;
  }

  separation(horses) {
    const steer = new Vector2(0, 0);
    let count = 0;
    for (const other of horses) {
      if (other === this) continue;
      const d = distance(this.position, other.position);
      if (d > 0 && d < 15) {
        const diff = this.position.copy().sub(other.position).normalize().div(Math.max(d, 1));
        steer.add(diff);
        count += 1;
      }
    }
    if (count > 0) {
      steer.div(count);
      if (steer.mag() > 0) {
        steer.normalize().mult(this.maxSpeed).sub(this.velocity);
        steer.limit(this.maxForce);
      }
    }
    return steer;
  }

  attractToCheckpoint() {
    if (this.hasFinished || !this.track) return new Vector2(0, 0);
    if (this.currentCheckpointIndex >= this.totalCheckpoints) return new Vector2(0, 0);
    return this.seek(this.track.checkpointPositions[this.currentCheckpointIndex]);
  }

  attractToTrack() {
    if (this.hasFinished || !this.track) return new Vector2(0, 0);
    const nearest = this.track.getNearestTrackPosition(this.position);
    if (distance(this.position, nearest) > 20) return this.seek(nearest);
    return new Vector2(0, 0);
  }

  avoidBarriers() {
    if (this.hasFinished || !this.track) return new Vector2(0, 0);
    const grid = this.track.grid;
    const steer = new Vector2(0, 0);
    let count = 0;
    let hit = false;

    const center = grid.worldToGrid(this.position.x, this.position.y);
    for (let dx = -3; dx <= 3; dx++) {
      for (let dy = -3; dy <= 3; dy++) {
        if (dx === 0 && dy === 0) continue;
        const gx = center[0] + dx, gy = center[1] + dy;
        const node = grid.getNode(gx, gy);
        if (node !== null && node !== NodeState.RACE_TRACK) {
          const w = grid.gridToWorld(gx, gy);
          const barrier = new Vector2(w[0], w[1]);
          if (this.barrierMemory.size < this.maxMemorySize) this.barrierMemory.add(`${gx},${gy}`);

          const dist = distance(this.position, barrier);
          if (dist < this.barrierDetectionRadius) {
            const away = this.position.copy().sub(barrier).normalize();
            let weight = 5.0; // remembered barrier gets stronger avoidance
            if (dist < 20) { weight *= 2.0; hit = true; }
            away.mult(weight / Math.max(dist, 1));
            steer.add(away);
            count += 1;
          }
        }
      }
    }

    if (hit) { this.consecutiveBarrierHits += 1; this.lastBarrierHit = 10; }
    else this.consecutiveBarrierHits = Math.max(0, this.consecutiveBarrierHits - 1);

    if (count > 0) {
      steer.div(count);
      if (steer.mag() > 0) {
        steer.normalize().mult(this.maxSpeed * 1.5).sub(this.velocity);
        steer.limit(this.maxForce * 2);
      }
    }
    return steer;
  }

  enforceClockwise() {
    if (this.hasFinished || !this.track) return new Vector2(0, 0);
    const forward = this.track.getForwardDirection(this.position);
    if (this.velocity.mag() > 0) {
      const vn = this.velocity.copy().normalize();
      const dot = vn.x * forward.x + vn.y * forward.y;
      if (dot < 0) {
        this.wrongDirectionPenalty += 1;
        this._wdFrames = (this._wdFrames || 0) + 1;
        const turn = new Vector2(forward.x * this.maxSpeed, forward.y * this.maxSpeed).sub(this.velocity);
        turn.limit(this.maxForce * 2);
        return turn;
      } else if (dot < 0.5) {
        this._wdFrames = 0;
        const nudge = new Vector2(forward.x * this.maxSpeed, forward.y * this.maxSpeed).sub(this.velocity);
        nudge.limit(this.maxForce * 0.5);
        return nudge;
      }
    }
    this._wdFrames = 0;
    this.wrongDirectionPenalty = Math.max(0, this.wrongDirectionPenalty - 1);
    return new Vector2(0, 0);
  }

  lineBonus() {
    // Up to +8% speed when riding close to its remembered best line.
    const line = this.preferredLine[String(this.currentCheckpointIndex)];
    if (!line || line.length < 2 || this.skill <= 0) return 1;
    let minD = Infinity;
    for (const p of line) {
      const d = Math.hypot(p[0] - this.position.x, p[1] - this.position.y);
      if (d < minD) minD = d;
    }
    const closeness = Math.max(0, 1 - minD / 120); // 1 on the line, 0 far away
    return 1 + 0.08 * closeness * this.skill;
  }

  followPreferredLine() {
    const line = this.preferredLine[String(this.currentCheckpointIndex)];
    if (!line || line.length < 2) return new Vector2(0, 0);
    let next = null, minD = Infinity;
    for (const p of line) {
      const d = Math.hypot(p[0] - this.position.x, p[1] - this.position.y);
      if (d < 30) continue;
      if (d < minD) { minD = d; next = p; }
    }
    if (!next) return new Vector2(0, 0);
    return this.seek(new Vector2(next[0], next[1]));
  }

  followPath() {
    if (!this.currentPath.length) return new Vector2(0, 0);
    let nextPoint = null, minDist = Infinity;
    for (const p of this.currentPath) {
      const pv = new Vector2(p[0], p[1]);
      const d = distance(this.position, pv);
      if (d < 40) continue;
      if (d < minDist) { minDist = d; nextPoint = pv; }
    }
    if (nextPoint === null && this.target) return this.seek(this.target);
    return nextPoint ? this.seek(nextPoint) : new Vector2(0, 0);
  }

  applyForce(f) { this.acceleration.add(f); }

  flock(horses) {
    this._field = horses;
    if (this.hasFinished) return;

    if (this.checkIfStuck()) { this.resetToStart(); return; }
    this.updateCheckpoint();
    if (this.hasFinished) return;

    this.applyForce(this.separation(horses).mult(this.separationWeight));

    this.pathUpdateTimer += 1;
    if (this.pathUpdateTimer >= this.pathUpdateInterval) {
      if (this.target) this.requestNewPath(this.track.pathfinder);
      this.pathUpdateTimer = 0;
    }

    this.applyForce(this.followPath().mult(this.pathWeight));

    if (this.lineWeight > 0) {
      this.applyForce(this.followPreferredLine().mult(this.lineWeight));
    }

    this.applyForce(this.attractToTrack().mult(this.trackAttractionWeight));
    this.applyForce(this.avoidBarriers().mult(this.barrierAvoidanceWeight));
    this.applyForce(this.attractToCheckpoint().mult(this.checkpointWeight));
    this.applyForce(this.enforceClockwise().mult(this.clockwiseWeight));

    // small random jitter keeps races competitive and breaks symmetry
    if (this.raceStartTime != null) {
      const jitter = new Vector2(Math.random() - 0.5, Math.random() - 0.5).mult(0.08);
      this.applyForce(jitter);
    }
  }

  update(bounds) {
    if (this.lastBarrierHit > 0) this.lastBarrierHit -= 1;

    const oldPos = new Vector2(this.position.x, this.position.y);
    // racing chaos: occasional stumbles (more likely in a crowd) and surges.
    let chaos = 1;
    if (!this.hasFinished && this.raceStartTime != null) {
      let neighbors = 0;
      for (const o of this._field || []) {
        if (o !== this && !o.hasFinished && distance(this.position, o.position) < 60) neighbors++;
      }
      if (Math.random() < 0.004 + neighbors * 0.002) this._stumble = 25 + Math.floor(Math.random() * 20);
      if (this._stumble > 0) { this._stumble -= 1; chaos = 0.55; }
      else if (Math.random() < 0.004) chaos = 1.18; // lucky surge
    }
    this.velocity.add(this.acceleration);
    this.velocity.limit(this.maxSpeed * this.lineBonus() * chaos);
    if (this.velocity.mag() > 0) this.distanceTraveled += this.velocity.mag();
    this.position.add(this.velocity);
    this.acceleration = new Vector2(0, 0);

    this.pathHistory.push([this.position.x, this.position.y]);
    if (this.pathHistory.length > this.pathHistoryMax) this.pathHistory.shift();

    const [w, h] = bounds;
    if (this.position.x < 0) this.position.x = w;
    else if (this.position.x > w) this.position.x = 0;
    if (this.position.y < 0) this.position.y = h;
    else if (this.position.y > h) this.position.y = 0;

    if (this.track && !this.hasFinished && !this.track.isPositionOnTrack(this.position)) {
      const nearest = this.track.getNearestTrackPosition(this.position);
      if (distance(this.position, nearest) > 50) {
        const dir = nearest.copy().sub(this.position);
        if (dir.mag() > 0) { dir.normalize(); this.velocity = dir.mult(this.maxSpeed); }
      }
    }
  }

  draw(ctx) {
    // trail
    if (this.pathHistory.length > 1) {
      ctx.strokeStyle = this.color;
      ctx.globalAlpha = 0.35;
      ctx.lineWidth = 1;
      ctx.beginPath();
      for (let i = 0; i + 1 < this.pathHistory.length; i += 2) {
        ctx.moveTo(this.pathHistory[i][0], this.pathHistory[i][1]);
        ctx.lineTo(this.pathHistory[i + 1][0], this.pathHistory[i + 1][1]);
      }
      ctx.stroke();
      ctx.globalAlpha = 1;
    }

    const x = this.position.x, y = this.position.y;

    if (this.hasFinished) {
      ctx.strokeStyle = '#ffd60a';
      ctx.lineWidth = 3;
      ctx.beginPath(); ctx.arc(x, y, this.size + 5, 0, Math.PI * 2); ctx.stroke();
      ctx.fillStyle = this.color;
      ctx.beginPath(); ctx.arc(x, y, this.size, 0, Math.PI * 2); ctx.fill();
      ctx.fillStyle = '#000';
      ctx.font = '11px monospace';
      ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
      ctx.fillText('F', x, y);
      return;
    }

    if (this.velocity.mag() < 0.1) return;
    const angle = Math.atan2(this.velocity.y, this.velocity.x);
    const s = this.size;
    const tip = [x + s * 1.5 * Math.cos(angle), y + s * 1.5 * Math.sin(angle)];
    const left = [x - s * Math.cos(angle) + s * Math.sin(angle), y - s * Math.sin(angle) - s * Math.cos(angle)];
    const right = [x - s * Math.cos(angle) - s * Math.sin(angle), y - s * Math.sin(angle) + s * Math.cos(angle)];

    ctx.fillStyle = this.color;
    ctx.strokeStyle = '#000';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(tip[0], tip[1]);
    ctx.lineTo(left[0], left[1]);
    ctx.lineTo(right[0], right[1]);
    ctx.closePath();
    ctx.fill();
    ctx.stroke();

    // name tag
    ctx.fillStyle = '#fff';
    ctx.font = 'bold 11px monospace';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'bottom';
    ctx.fillText(this.name, x, y - 12);
  }
}
