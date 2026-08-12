"""
PHYSICS ENGINE - heat transfer, state transitions, and basic
mechanics/electricity.
"""

from dataclasses import dataclass, field
from typing import Dict, Optional, TYPE_CHECKING

from mss.core.vectors import Vector2D

if TYPE_CHECKING:
    from mss.chemistry.substance import Substance
    from mss.core.universe import Universe


class PhysicsEngine:
    """Heat transfer, state transitions, and basic mechanics/electricity."""

    @staticmethod
    def heat(substance: "Substance", delta_kelvin: float) -> "Substance":
        substance.temperature = max(0.0, substance.temperature + delta_kelvin)
        return substance

    @staticmethod
    def apply_pressure(substance: "Substance", atm: float) -> "Substance":
        # Simplification: increased pressure only sets the recorded value here.
        substance.pressure = atm
        return substance

    # --- Mechanics (Newton) ---------------------------------------------

    @staticmethod
    def force(mass_kg: float, acceleration: float) -> float:
        """F = m*a"""
        return mass_kg * acceleration

    @staticmethod
    def kinetic_energy(mass_kg: float, velocity: float) -> float:
        """E_k = (1/2)*m*v^2"""
        return 0.5 * mass_kg * velocity ** 2

    @staticmethod
    def potential_energy(mass_kg: float, height_m: float, universe: "Universe") -> float:
        """E_p = m*g*h (g comes from the specific universe's constant)"""
        return mass_kg * universe.gravity * height_m

    @staticmethod
    def momentum(mass_kg: float, velocity: float) -> float:
        """p = m*v"""
        return mass_kg * velocity

    # --- Electricity (Ohm's law) ------------------------------------------

    @staticmethod
    def ohms_law(voltage: Optional[float] = None,
                 current: Optional[float] = None,
                 resistance: Optional[float] = None) -> Dict[str, float]:
        """
        Ohm's law V = I*R. Pass exactly TWO known quantities (leave the
        third as None) - the method computes the missing one and returns
        all three.
        """
        known = [v is not None for v in (voltage, current, resistance)]
        if sum(known) != 2:
            raise ValueError("Exactly two of the three quantities (V, I, R) must be given.")
        if voltage is None:
            voltage = current * resistance
        elif current is None:
            current = voltage / resistance if resistance else 0.0
        elif resistance is None:
            resistance = voltage / current if current else 0.0
        return {"voltage_V": voltage, "current_A": current, "resistance_Ohm": resistance}


@dataclass
class PhysicalObject:
    """
    A body with mass, position, and velocity that can be pushed by a
    force and advanced through time (simple Newtonian integration).
    Demonstrates that math (Vector2D) and physics share common data types.
    """
    name: str
    mass_kg: float
    position: Vector2D = field(default_factory=Vector2D)
    velocity: Vector2D = field(default_factory=Vector2D)

    def apply_force(self, force: Vector2D, dt_seconds: float) -> None:
        acceleration = force.scale(1.0 / self.mass_kg)
        self.velocity = self.velocity + acceleration.scale(dt_seconds)
        self.position = self.position + self.velocity.scale(dt_seconds)

    def kinetic_energy(self) -> float:
        return PhysicsEngine.kinetic_energy(self.mass_kg, self.velocity.magnitude())
