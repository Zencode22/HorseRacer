// ============================================================================
// A* PATHFINDING - port of pathfinding/astar.py (most direct route)
// ============================================================================

import { NodeState } from './grid.js';

class PathRequest {
  constructor(startPos, endPos) {
    this.startPos = startPos;
    this.endPos = endPos;
    this.path = [];
    this.success = false;
  }
}

export class Pathfinding {
  constructor(grid) {
    this.grid = grid;
    this.cache = new Map();
  }

  findPath(startWorld, endWorld, useCache = true) {
    const cacheKey = `${startWorld[0].toFixed(1)},${startWorld[1].toFixed(1)}->${endWorld[0].toFixed(1)},${endWorld[1].toFixed(1)}`;
    if (useCache && this.cache.has(cacheKey)) {
      const cached = this.cache.get(cacheKey);
      if (cached.success) return cached;
    }

    const request = new PathRequest(startWorld, endWorld);
    const g = this.grid;
    const [sx, sy] = g.worldToGrid(startWorld[0], startWorld[1]);
    const [ex, ey] = g.worldToGrid(endWorld[0], endWorld[1]);

    if (g.getNode(sx, sy) !== NodeState.RACE_TRACK || g.getNode(ex, ey) !== NodeState.RACE_TRACK) {
      return request; // not on track -> no path
    }

    const key = (x, y) => x * 10000 + y;
    const startK = key(sx, sy), endK = key(ex, ey);

    const openMap = new Map(); // k -> f
    const cameFrom = new Map();
    const gScore = new Map([[startK, 0]]);

    const h = (x, y) => Math.hypot(x - ex, y - ey);
    openMap.set(startK, h(sx, sy));
    const nodeXY = (k) => [Math.floor(k / 10000), k % 10000];

    const MAX_ITER = 20000;
    let iter = 0;

    while (openMap.size > 0 && iter++ < MAX_ITER) {
      // pop lowest f (grid is small enough for a linear scan)
      let bestK = -1, bestF = Infinity;
      for (const [k, f] of openMap) if (f < bestF) { bestF = f; bestK = k; }
      const [cx, cy] = nodeXY(bestK);
      openMap.delete(bestK);

      if (bestK === endK) {
        // reconstruct
        let k = endK;
        const cells = [];
        while (k !== undefined) { cells.push(nodeXY(k)); k = cameFrom.get(k); }
        cells.reverse();
        request.path = cells.map(([x, y]) => g.gridToWorld(x, y));
        request.success = true;
        this.cache.set(cacheKey, request);
        return request;
      }

      const cg = gScore.get(bestK);
      for (let dx = -1; dx <= 1; dx++) {
        for (let dy = -1; dy <= 1; dy++) {
          if (dx === 0 && dy === 0) continue;
          const nx = cx + dx, ny = cy + dy;
          if (!g.isValidPosition(nx, ny)) continue;
          if (g.getNode(nx, ny) !== NodeState.RACE_TRACK) continue;
          // prevent diagonal corner cutting
          if (dx !== 0 && dy !== 0) {
            if (g.getNode(cx + dx, cy) !== NodeState.RACE_TRACK ||
                g.getNode(cx, cy + dy) !== NodeState.RACE_TRACK) continue;
          }
          const nk = key(nx, ny);
          const step = Math.hypot(dx, dy);
          const tentative = cg + step;
          if (tentative < (gScore.has(nk) ? gScore.get(nk) : Infinity)) {
            cameFrom.set(nk, bestK);
            gScore.set(nk, tentative);
            openMap.set(nk, tentative + h(nx, ny));
          }
        }
      }
    }

    return request; // failed
  }

  clearCache() { this.cache.clear(); }
}
