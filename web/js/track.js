// ============================================================================
// RACE TRACK - port of track/race_track.py (square track, clockwise)
// Geometry is identical to the Python version. The grid keeps only the plain
// track ring walkable; the "invisible barrier" that forced horses the long way
// around is replaced by ordered checkpoints + a wrong-direction penalty.
// ============================================================================

import { Grid } from './grid.js';
import { Vector2 } from './vector2.js';
import { Pathfinding } from './astar.js';
import { WIDTH, HEIGHT, TRACK_WIDTH, COLORS } from './config.js';

export class RaceTrack {
  constructor(width = WIDTH, height = HEIGHT) {
    this.width = width;
    this.height = height;

    this.trackPoints = this._createSquareTrack();
    this.trackDirection = this._calculateTrackDirection();

    // Start and finish on the SAME CORNER (top-right)
    this.startLinePos = this._getPointOnEdge('right', 0.1);
    this.finishLinePos = this._getPointOnEdge('top', 0.9);

    this.checkpoints = this._createCheckpointsWithStartFinish();
    this.checkpointPositions = this.checkpoints.map((cp) => new Vector2(cp[0], cp[1]));
    this.checkpointRadius = 40;
    this.checkpointColors = this._createCheckpointColors();

    this.fixedStartPositions = this._calculateFixedStartPositions();

    const nodeSize = 12.0;
    this.grid = new Grid(Math.floor(width / nodeSize), Math.floor(height / nodeSize), nodeSize);
    this.grid.createTrackBarriers(this.trackPoints, TRACK_WIDTH);

    this.pathfinder = new Pathfinding(this.grid);
    this.goal = new Vector2(this.finishLinePos[0], this.finishLinePos[1]);

    this.staticSurface = this._createStaticSurface();

    // Shared simulation clock (seconds, advanced one frame per update) so
    // finish times are real seconds even when the sim runs headless/fast.
    this.simTime = 0;
  }

  _createSquareTrack() {
    const points = [];
    const lx = this.width * 0.25, rx = this.width * 0.55;
    const ty = this.height * 0.2, by = this.height * 0.8;

    for (let i = 0; i < 12; i++) points.push([lx + (rx - lx) * (i / 11), ty]);      // top L->R
    for (let i = 1; i < 12; i++) points.push([rx, ty + (by - ty) * (i / 11)]);      // right T->B
    for (let i = 1; i < 12; i++) points.push([rx - (rx - lx) * (i / 11), by]);      // bottom R->L
    for (let i = 1; i < 12; i++) points.push([lx, by - (by - ty) * (i / 11)]);      // left B->T
    return points;
  }

  _getPointOnEdge(edge, t) {
    const lx = this.width * 0.25, rx = this.width * 0.55;
    const ty = this.height * 0.2, by = this.height * 0.8;
    if (edge === 'top') return [lx + (rx - lx) * t, ty];
    if (edge === 'right') return [rx, ty + (by - ty) * t];
    if (edge === 'bottom') return [rx - (rx - lx) * t, by];
    if (edge === 'left') return [lx, by - (by - ty) * t];
    return [lx, ty];
  }

  _createCheckpointsWithStartFinish() {
    const checkpoints = [this.startLinePos];
    const numIntermediate = 7;
    const total = this.trackPoints.length;

    let startIdx = 0, minDist = Infinity;
    for (let i = 0; i < total; i++) {
      const p = this.trackPoints[i];
      const d = Math.hypot(p[0] - this.startLinePos[0], p[1] - this.startLinePos[1]);
      if (d < minDist) { minDist = d; startIdx = i; }
    }

    for (let i = 1; i <= numIntermediate; i++) {
      const offset = Math.floor(i * (total / (numIntermediate + 1)));
      checkpoints.push(this.trackPoints[(startIdx + offset) % total]);
    }
    checkpoints.push(this.finishLinePos);
    return checkpoints;
  }

  _createCheckpointColors() {
    return [
      '#22ff22',
      '#ff3b30', '#ff9500', '#ffd60a', '#22ff22', '#00ffff', '#3b82f6', '#a855f7',
      '#ff3b30',
    ];
  }

  _calculateTrackDirection() {
    const dirs = [];
    for (let i = 0; i < this.trackPoints.length; i++) {
      const c = this.trackPoints[i];
      const n = this.trackPoints[(i + 1) % this.trackPoints.length];
      const dx = n[0] - c[0], dy = n[1] - c[1];
      const len = Math.hypot(dx, dy);
      dirs.push(len > 0 ? new Vector2(dx / len, dy / len) : new Vector2(0, 0));
    }
    return dirs;
  }

  _calculateFixedStartPositions() {
    const positions = [];
    const sp = new Vector2(this.startLinePos[0], this.startLinePos[1]);

    let nextIdx = null;
    for (let i = 0; i < this.trackPoints.length; i++) {
      const p = this.trackPoints[i];
      if (Math.hypot(p[0] - sp.x, p[1] - sp.y) < 20) { nextIdx = (i + 1) % this.trackPoints.length; break; }
    }
    if (nextIdx === null) return positions;

    const np = new Vector2(this.trackPoints[nextIdx][0], this.trackPoints[nextIdx][1]);
    const dx = np.x - sp.x, dy = np.y - sp.y;
    const len = Math.hypot(dx, dy);
    if (len > 0) {
      const dirX = dx / len, dirY = dy / len;
      const perpX = -dirY, perpY = dirX;
      const spacing = TRACK_WIDTH / 7;
      for (let i = 0; i < 6; i++) {
        const offset = (i + 1 - 3.5) * spacing;
        positions.push(new Vector2(sp.x + dirX * 10 + perpX * offset, sp.y + dirY * 10 + perpY * offset));
      }
    }
    return positions;
  }

  getStartPosition(horseIndex) {
    if (!this.fixedStartPositions.length) return new Vector2(this.width * 0.4, this.height * 0.5);
    return this.fixedStartPositions[horseIndex % this.fixedStartPositions.length].copy();
  }

  getSpreadStartPositions(numHorses) {
    return Array.from({ length: numHorses }, (_, i) => this.getStartPosition(i));
  }

  getTotalCheckpoints() { return this.checkpointPositions.length; }

  isPositionOnTrack(pos) {
    const [gx, gy] = this.grid.worldToGrid(pos.x, pos.y);
    return this.grid.getNode(gx, gy) === 1;
  }

  getNearestTrackPosition(pos) {
    let minDist = Infinity;
    let nearest = new Vector2(pos.x, pos.y);
    for (const p of this.trackPoints) {
      const d = Math.hypot(p[0] - pos.x, p[1] - pos.y);
      if (d < minDist) { minDist = d; nearest = new Vector2(p[0], p[1]); }
    }
    return nearest;
  }

  getForwardDirection(pos) {
    let minDist = Infinity, closestIdx = 0;
    for (let i = 0; i < this.trackPoints.length; i++) {
      const p = this.trackPoints[i];
      const d = Math.hypot(p[0] - pos.x, p[1] - pos.y);
      if (d < minDist) { minDist = d; closestIdx = i; }
    }
    return this.trackDirection[closestIdx].copy();
  }

  _createStaticSurface() {
    // Pre-render grass + track + checkpoints + labels once (like pygame surfaces)
    if (typeof document === 'undefined') return null; // headless (tests)
    const off = document.createElement('canvas');
    off.width = this.width;
    off.height = this.height;
    const ctx = off.getContext('2d');

    ctx.fillStyle = COLORS.GREEN;
    ctx.fillRect(0, 0, this.width, this.height);

    ctx.lineJoin = 'round';
    ctx.lineCap = 'round';
    const strokePath = (color, w) => {
      ctx.strokeStyle = color;
      ctx.lineWidth = w;
      ctx.beginPath();
      ctx.moveTo(this.trackPoints[0][0], this.trackPoints[0][1]);
      for (let i = 1; i < this.trackPoints.length; i++) ctx.lineTo(this.trackPoints[i][0], this.trackPoints[i][1]);
      ctx.closePath();
      ctx.stroke();
    };
    strokePath(COLORS.BROWN, TRACK_WIDTH);
    strokePath(COLORS.LIGHT_BROWN, TRACK_WIDTH - 20);
    strokePath('#f5f5f5', 3); // dashed-look center guide

    // direction arrows
    ctx.strokeStyle = 'rgba(255,255,255,0.8)';
    ctx.lineWidth = 2;
    for (let i = 0; i < this.trackPoints.length; i += 15) {
      const p = this.trackPoints[i], d = this.trackDirection[i];
      ctx.beginPath();
      ctx.moveTo(p[0], p[1]);
      ctx.lineTo(p[0] + d.x * 30, p[1] + d.y * 30);
      ctx.stroke();
    }

    // checkpoints
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    for (let i = 0; i < this.checkpointPositions.length; i++) {
      const cp = this.checkpointPositions[i];
      const color = this.checkpointColors[i];
      const isFirst = i === 0;
      const isLast = i === this.checkpointPositions.length - 1;
      const radius = isFirst || isLast ? 18 : 14;
      ctx.beginPath();
      ctx.arc(cp.x, cp.y, radius, 0, Math.PI * 2);
      ctx.fillStyle = color;
      ctx.fill();
      ctx.lineWidth = isFirst || isLast ? 3 : 2;
      ctx.strokeStyle = COLORS.WHITE;
      ctx.stroke();
      ctx.fillStyle = isFirst || isLast ? COLORS.BLACK : COLORS.WHITE;
      ctx.font = `${isFirst || isLast ? 15 : 12}px monospace`;
      ctx.fillText(isFirst ? 'S' : isLast ? 'F' : String(i), cp.x, cp.y);
    }

    // START / FINISH labels with outline
    const label = (text, x, y) => {
      ctx.font = 'bold 22px monospace';
      ctx.lineWidth = 3;
      ctx.strokeStyle = COLORS.BLACK;
      ctx.strokeText(text, x, y);
      ctx.fillStyle = COLORS.WHITE;
      ctx.fillText(text, x, y);
    };
    label('START', this.startLinePos[0] + 45, this.startLinePos[1] - 40);
    label('FINISH', this.finishLinePos[0] - 60, this.finishLinePos[1] - 55);

    // wooden fences
    const fence = (offset) => {
      const pts = [];
      for (let i = 0; i < this.trackPoints.length; i++) {
        const p = this.trackPoints[i];
        const n = this.trackPoints[(i + 1) % this.trackPoints.length];
        const dx = n[0] - p[0], dy = n[1] - p[1];
        const len = Math.hypot(dx, dy);
        if (len > 0) {
          const px = (-dy / len) * offset, py = (dx / len) * offset;
          pts.push([p[0] + px, p[1] + py]);
        }
      }
      ctx.strokeStyle = COLORS.WOOD;
      ctx.lineWidth = 3;
      ctx.beginPath();
      ctx.moveTo(pts[0][0], pts[0][1]);
      for (let i = 1; i < pts.length; i++) ctx.lineTo(pts[i][0], pts[i][1]);
      ctx.closePath();
      ctx.stroke();
    };
    fence(TRACK_WIDTH / 2 + 20);
    fence(-(TRACK_WIDTH / 2 + 20));

    return off;
  }

  draw(ctx) {
    if (this.staticSurface) ctx.drawImage(this.staticSurface, 0, 0);
  }
}
