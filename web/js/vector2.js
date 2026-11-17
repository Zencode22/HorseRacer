// ============================================================================
// VECTOR2 CLASS - port of models/vector2.py
// ============================================================================

export class Vector2 {
  constructor(x = 0, y = 0) {
    this.x = x;
    this.y = y;
  }
  add(o) { this.x += o.x; this.y += o.y; return this; }
  sub(o) { this.x -= o.x; this.y -= o.y; return this; }
  mult(s) { this.x *= s; this.y *= s; return this; }
  div(s) { if (s !== 0) { this.x /= s; this.y /= s; } return this; }
  mag() { return Math.hypot(this.x, this.y); }
  normalize() { const m = this.mag(); if (m > 0) this.div(m); return this; }
  limit(max) { if (this.mag() > max) { this.normalize(); this.mult(max); } return this; }
  copy() { return new Vector2(this.x, this.y); }
  distanceTo(o) { return Math.hypot(this.x - o.x, this.y - o.y); }
}

export function distance(a, b) {
  return Math.hypot(a.x - b.x, a.y - b.y);
}
