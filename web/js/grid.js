// ============================================================================
// GRID + NODES - port of models/grid.py & models/node.py
// NodeState: 0 = UNWALKABLE, 1 = RACE_TRACK
// ============================================================================

export const NodeState = { UNWALKABLE: 0, RACE_TRACK: 1 };

export class Grid {
  constructor(width, height, nodeSize = 10.0) {
    this.width = width;
    this.height = height;
    this.nodeSize = nodeSize;
    // state[x][y] — flat Uint8Array backing view for O(1) resets and fast
    // neighbor lookups during pathfinding (was a jagged array of Arrays).
    this.flat = new Uint8Array(width * height);
    this.state = [];
    for (let x = 0; x < width; x++) {
      const col = new Array(height).fill(NodeState.UNWALKABLE);
      this.state.push(col);
    }
  }

  _syncCol(x) {
    const col = this.state[x];
    const off = x * this.height;
    for (let y = 0; y < this.height; y++) this.flat[off + y] = col[y];
  }

  setState(x, y, st) {
    if (this.isValidPosition(x, y)) { this.state[x][y] = st; this.flat[x * this.height + y] = st; }
  }

  getNode(x, y) {
    return this.isValidPosition(x, y) ? this.state[x][y] : null;
  }

  isValidPosition(x, y) {
    return x >= 0 && x < this.width && y >= 0 && y < this.height;
  }

  worldToGrid(wx, wy) {
    let gx = Math.floor(wx / this.nodeSize);
    let gy = Math.floor(wy / this.nodeSize);
    gx = Math.max(0, Math.min(gx, this.width - 1));
    gy = Math.max(0, Math.min(gy, this.height - 1));
    return [gx, gy];
  }

  gridToWorld(gx, gy) {
    return [gx * this.nodeSize + this.nodeSize / 2, gy * this.nodeSize + this.nodeSize / 2];
  }

  createTrackBarriers(trackPoints, trackWidth) {
    if (trackPoints.length < 2) return;

    // O(1) full reset via the typed array (was a nested loop over ~6k cells).
    this.flat.fill(NodeState.UNWALKABLE);
    for (let x = 0; x < this.width; x++) this.state[x].fill(NodeState.UNWALKABLE);

    for (let i = 0; i < trackPoints.length; i++) {
      const p1 = trackPoints[i];
      const p2 = trackPoints[(i + 1) % trackPoints.length];
      const a = this.worldToGrid(p1[0], p1[1]);
      const b = this.worldToGrid(p2[0], p2[1]);
      this._markTrackWidth(a, b, trackWidth);
    }
  }

  _markTrackWidth(start, end, width) {
    const points = this._getLinePoints(start[0], start[1], end[0], end[1]);
    const radiusCells = Math.max(1, Math.floor(width / (2 * this.nodeSize)));
    const r2 = radiusCells * radiusCells;
    for (const [x, y] of points) {
      const xLo = Math.max(0, x - radiusCells), xHi = Math.min(this.width - 1, x + radiusCells);
      const yLo = Math.max(0, y - radiusCells), yHi = Math.min(this.height - 1, y + radiusCells);
      for (let nx = xLo; nx <= xHi; nx++) {
        const col = this.state[nx];
        const ddx = nx - x;
        const base = nx * this.height;
        for (let ny = yLo; ny <= yHi; ny++) {
          const ddy = ny - y;
          if (ddx * ddx + ddy * ddy <= r2) {
            col[ny] = NodeState.RACE_TRACK;
            this.flat[base + ny] = NodeState.RACE_TRACK;
          }
        }
      }
    }
  }

  _getLinePoints(x0, y0, x1, y1) {
    // Bresenham's line algorithm
    const points = [];
    const dx = Math.abs(x1 - x0), dy = -Math.abs(y1 - y0);
    const sx = x0 < x1 ? 1 : -1, sy = y0 < y1 ? 1 : -1;
    let err = dx + dy;
    for (;;) {
      points.push([x0, y0]);
      if (x0 === x1 && y0 === y1) break;
      const e2 = 2 * err;
      if (e2 >= dy) { if (x0 === x1) break; err += dy; x0 += sx; }
      if (e2 <= dx) { if (y0 === y1) break; err += dx; y0 += sy; }
    }
    return points;
  }
}
