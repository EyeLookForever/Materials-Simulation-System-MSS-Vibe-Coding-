"""
Shared math utilities used by physics, biology, and engineering below.
"""

import math
from dataclasses import dataclass
from typing import List


@dataclass
class Vector2D:
    """A simple 2D vector for position/velocity/force."""
    x: float = 0.0
    y: float = 0.0

    def __add__(self, other: "Vector2D") -> "Vector2D":
        return Vector2D(self.x + other.x, self.y + other.y)

    def __sub__(self, other: "Vector2D") -> "Vector2D":
        return Vector2D(self.x - other.x, self.y - other.y)

    def scale(self, k: float) -> "Vector2D":
        return Vector2D(self.x * k, self.y * k)

    def magnitude(self) -> float:
        return math.sqrt(self.x ** 2 + self.y ** 2)

    def dot(self, other: "Vector2D") -> float:
        return self.x * other.x + self.y * other.y

    def __repr__(self):
        return f"({self.x:.2f}, {self.y:.2f})"


class Stats:
    """Basic statistics - useful for describing cell populations, etc."""

    @staticmethod
    def mean(values: List[float]) -> float:
        return sum(values) / len(values) if values else 0.0

    @staticmethod
    def variance(values: List[float]) -> float:
        if len(values) < 2:
            return 0.0
        m = Stats.mean(values)
        return sum((v - m) ** 2 for v in values) / (len(values) - 1)

    @staticmethod
    def stdev(values: List[float]) -> float:
        return math.sqrt(Stats.variance(values))
