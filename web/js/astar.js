// ============================================================================
// A* PATHFINDING - port of pathfinding/astar.py (most direct route)
// ============================================================================

import { NodeState } from './grid.js';

export class PathRequest {
  constructor(startPos, endPos) {
    this.startPos = startPos;
    this.endPos = endPos;
    this.path = [];
    this.success = false;
  }
}

// ============================================================================
// LOAD-TIME PERFORMANCE NOTES
// The original port ran A* with a linear-scan "open set" over a dense
// 106x60 cell grid. During page load every horse requested several paths and
// each search could expand thousands of cells -> the main thread blocked for
// minutes before the first frame ever painted. Fixes:
//   1. Binary-heap priority queue (O(log n) pops instead of O(open-set)).
//   2. Typed-array scratch buffers allocated once per Pathfinding instance.
//   3. Bounded iterations + wall-clock budget per search (never blocks long).
//   4. Adaptive fallback: straight line to goal when the full search cannot
//      finish in time — horses still steer sensibly, races stay correct.
//   5. Results are cached, so repeated identical requests are free.
// ============================================================================

class MinHeap {
  constructor() { this.ks = []; this.fs = []; this.size = 0; }
  push(k, f) {
    let i = this.size++;
    this.ks[i] = k; this.fs[i] = f;
    while (i > 0) {
      const p = (i - 1) >> 1;
      if (this.fs[p] <= this.fs[i]) break;
      this._swap(i, p); i = p;
    }
  }
  pop() {
    if (this.size === 0) return -1;
    const top = this.ks[0];
    this.size -= 1;
    if (this.size > 0) {
      this.ks[0] = this.ks[this.size];
      this.fs[0] = this.fs[this.size];
      let i = 0;
      for (;;) {
        const l = i * 2 + 1, r = l + 1;
        let m = i;
        if (l < this.size && this.fs[l] < this.fs[m]) m = l;
        if (r < this.size && this.fs[r] < this.fs[m]) m = r;
        if (m === i) break;
        this._swap(i, m); i = m;
      }
    }
    return top;
  }
  _swap(a, b) {
    const k = this.ks[a]; this.ks[a] = this.ks[b]; this.ks[b] = k;
    const f = this.fs[a]; this.fs[a] = this.fs[b]; this.fs[b] = f;
  }
}

export class Pathfinding {
  constructor(grid, opts = {}) {
    this.grid = grid;
    this.cache = new Map();
    this.maxIterations = opts.maxIterations ?? 6000;
    this.timeBudgetMs = opts.timeBudgetMs ?? 8;

    const cols = grid.width, rows = grid.height;
    this.W = cols;
    this.total = cols * rows;
    this.gScore = new Float64Array(this.total);
    this.cameFrom = new Int32Array(this.total);
    this.stamp = new Int32Array(this.total); // generation marks: no re-fill cost
    this.closed = new Uint8Array(this.total);
    this.gen = 0;
  }

  findPath(startWorld, endWorld, useCache = true) {
    const cacheKey = `${startWorld[0].toFixed(1)},${startWorld[1].toFixed(1)}->${endWorld[0].toFixed(1)},${endWorld[1].toFixed(1)}`;
    if (useCache && this.cache.has(cacheKey)) return this.cache.get(cacheKey);

    const request = new PathRequest(startWorld, endWorld);
    const g = this.grid;
    const sx = Math.floor(startWorld[0] / g.nodeSize);
    const sy = Math.floor(startWorld[1] / g.nodeSize);
    const ex = Math.floor(endWorld[0] / g.nodeSize);
    const ey = Math.floor(endWorld[1] / g.nodeSize);

    const TRACK = NodeState.RACE_TRACK;
    const at = (x, y) => (x >= 0 && x < this.W && y >= 0 && y < g.height) ? g.state[x][y] : 0;

    if (at(sx, sy) !== TRACK || at(ex, ey) !== TRACK) {
      return request; // not on track -> no path (do NOT cache failures)
    }

    // Trivially close? Straight line is good enough and costs nothing.
    if (Math.abs(sx - ex) <= 2 && Math.abs(sy - ey) <= 2) {
      request.path = [g.gridToWorld(sx, sy), g.gridToWorld(ex, ey)];
      request.success = true;
      this.cache.set(cacheKey, request);
      return request;
    }

    const deadline = performance.now() + this.timeBudgetMs;
    const gen = ++this.gen;
    const W = this.W;
    const startI = sx * W + sy, endI = ex * W + ey;

    const heap = new MinHeap();
    const hOf = (x, y) => Math.hypot(x - ex, y - ey);

    this.gScore[startI] = 0;
    this.stamp[startI] = gen;
    this.cameFrom[startI] = -1;
    this.closed[startI] = 0;
    heap.push(startI, hOf(sx, sy));

    let found = false;
    let iter = 0;
    while (heap.size > 0 && iter++ < this.maxIterations) {
      if ((iter & 255) === 0 && performance.now() > deadline) break; // time's up
      const cur = heap.pop();
      if (this.stamp[cur] !== gen || this.closed[cur]) continue;
      if (cur === endI) { found = true; break; }
      this.closed[cur] = 1;

      const cx = Math.floor(cur / W), cy = cur % W;
      const cg = this.gScore[cur];
      for (let d = 0; d < 8; d++) {
        const dx = DIR_X[d], dy = DIR_Y[d];
        const nx = cx + dx, ny = cy + dy;
        if (nx < 0 || nx >= this.W || ny < 0 || ny >= g.height) continue;
        if (at(nx, ny) !== TRACK) continue;
        if (dx !== 0 && dy !== 0) { // no corner cutting
          if (at(cx + dx, cy) !== TRACK || at(cx, cy + dy) !== TRACK) continue;
        }
        const ni = nx * W + ny;
        if (this.closed[ni]) continue;
        const fresh = this.stamp[ni] !== gen;
        if (fresh) { this.stamp[ni] = gen; this.closed[ni] = 0; }
        const tentative = cg + STEP_COST[d];
        if (fresh || tentative < this.gScore[ni]) {
          this.gScore[ni] = tentative;
          this.cameFrom[ni] = cur;
          heap.push(ni, tentative + hOf(nx, ny));
        }
      }
    }

    if (found) {
      const cells = [];
      for (let k = endI; k !== -1; k = this.cameFrom[k]) {
        cells.push([Math.floor(k / W), k % W]);
      }
      cells.reverse();
      request.path = cells.map(([x, y]) => g.gridToWorld(x, y));
      request.success = true;
      this.cache.set(cacheKey, request);
      return request;
    }

    // Fallback within the time budget: straight-line corridor toward the
    // goal (both endpoints verified walkable above). Cheap, sane steering.
    request.path = this._lineFallback(sx, sy, ex, ey);
    request.success = request.path.length >= 2;
    // Only cache the real A* result; retries may succeed later.
    return request;
  }

  _lineFallback(sx, sy, ex, ey) {
    const g = this.grid;
    const pts = [];
    const dx = ex - sx, dy = ey - sy;
    const steps = Math.max(Math.abs(dx), Math.abs(dy));
    for (let i = 0; i <= steps; i += 2) {
      const x = Math.round(sx + (dx * i) / steps);
      const y = Math.round(sy + (dy * i) / steps);
      pts.push(g.gridToWorld(x, y));
    }
    pts.push(g.gridToWorld(ex, ey));
    return pts;
  }

  clearCache() { this.cache.clear(); }
}

const DIR_X = [1, -1, 0, 0, 1, 1, -1, -1];
const DIR_Y = [0, 0, 1, -1, 1, -1, 1, -1];
const STEP_COST = [1, 1, 1, 1, Math.SQRT2, Math.SQRT2, Math.SQRT2, Math.SQRT2];
