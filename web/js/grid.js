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
    // state[x][y]
    this.state = [];
    for (let x = 0; x < width; x++) {
      this.state.push(new Array(height).fill(NodeState.UNWALKABLE));
    }
  }

  setState(x, y, st) {
    if (this.isValidPosition(x, y)) this.state[x][y] = st;
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

    for (let x = 0; x < this.width; x++)
      for (let y = 0; y < this.height; y++)
        this.state[x][y] = NodeState.UNWALKABLE;

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
    for (const [x, y] of points) {
      for (let dx = -radiusCells; dx <= radiusCells; dx++) {
        for (let dy = -radiusCells; dy <= radiusCells; dy++) {
          const nx = x + dx, ny = y + dy;
          if (this.isValidPosition(nx, ny) && dx * dx + dy * dy <= radiusCells * radiusCells) {
            this.state[nx][ny] = NodeState.RACE_TRACK;
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
