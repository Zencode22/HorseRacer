# ============================================================================
# VECTOR2 CLASS
# ============================================================================

import math

class Vector2:
    """2D vector class for position and velocity"""
    def __init__(self, x=0, y=0):
        self.x = x
        self.y = y

    def add(self, other):
        self.x += other.x
        self.y += other.y

    def sub(self, other):
        self.x -= other.x
        self.y -= other.y

    def mult(self, scalar):
        self.x *= scalar
        self.y *= scalar

    def div(self, scalar):
        if scalar != 0:
            self.x /= scalar
            self.y /= scalar

    def mag(self):
        return math.sqrt(self.x ** 2 + self.y ** 2)

    def normalize(self):
        m = self.mag()
        if m > 0:
            self.div(m)

    def limit(self, max_val):
        if self.mag() > max_val:
            self.normalize()
            self.mult(max_val)

    def copy(self):
        return Vector2(self.x, self.y)

    def distance_to(self, other):
        return math.sqrt((self.x - other.x) ** 2 + (self.y - other.y) ** 2)

    def __add__(self, other):
        return Vector2(self.x + other.x, self.y + other.y)

    def __sub__(self, other):
        return Vector2(self.x - other.x, self.y - other.y)

    def __mul__(self, scalar):
        return Vector2(self.x * scalar, self.y * scalar)

    def __truediv__(self, scalar):
        if scalar != 0:
            return Vector2(self.x / scalar, self.y / scalar)
        return Vector2(self.x, self.y)

    def __repr__(self):
        return f"Vector2({self.x:.1f}, {self.y:.1f})"


def distance(a, b):
    """Distance between two Vector2 objects"""
    return math.sqrt((a.x - b.x) ** 2 + (a.y - b.y) ** 2)