"""
BIOLOGY: CELLS - Genome
"""

import math
import random
from dataclasses import dataclass

from mss.core.universe import format_duration


@dataclass
class Genome:
    """
    The full set of a cell's heritable traits. Many aspects of a cell's
    life can evolve: tolerance to pH, oxygen, toxins, and radiation,
    metabolic rate, lifespan, and even the cell's own MUTATION RATE -
    meaning selection can act not only on "what temperature suits this
    cell" but also on "how fast can this species change at all"
    (the evolution of evolvability, a real phenomenon in biology).
    """
    optimal_temp: float = 310.15        # K, optimal temperature
    temp_tolerance: float = 4.0         # K, tolerance without stress
    nutrient_need: float = 1.0          # nominal nutrient units per step
    optimal_ph: float = 7.0             # optimal environment pH
    ph_tolerance: float = 2.0           # pH tolerance without stress
    oxygen_need: float = 0.21           # oxygen fraction in the environment (as on Earth)
    oxygen_tolerance: float = 0.15      # oxygen tolerance
    radiation_resistance: float = 0.0   # 0..1, fraction of radiation dose that is "absorbed"
    toxin_resistance: float = 0.0       # 0..1, fraction of chemical toxicity that is "absorbed"
    metabolic_rate: float = 1.0         # multiplier for growth/division/consumption speed
    max_lifespan_s: float = math.inf    # aging: death by age (inf = does not age)
    mutation_rate: float = 1.0          # multiplier for offspring mutation strength/frequency

    # base random-step size for mutation of each trait
    _MUTATION_STEP = {
        "optimal_temp": 1.5, "temp_tolerance": 0.5, "nutrient_need": 0.05,
        "optimal_ph": 0.2, "ph_tolerance": 0.15, "oxygen_need": 0.02,
        "oxygen_tolerance": 0.02, "radiation_resistance": 0.02,
        "toxin_resistance": 0.02, "metabolic_rate": 0.05, "mutation_rate": 0.05,
    }
    # traits clamped to the 0..1 range (fractions/probabilities)
    _CLAMP_01 = {"radiation_resistance", "toxin_resistance"}
    # traits that cannot become negative/zero (physical meaning requires > 0)
    _CLAMP_POSITIVE = {"nutrient_need", "temp_tolerance", "ph_tolerance",
                        "oxygen_need", "oxygen_tolerance", "metabolic_rate", "mutation_rate"}

    def mutate(self, radiation_boost: float = 0.0) -> "Genome":
        """
        Returns a new (mutated) offspring genome. radiation_boost is an
        extra multiplier on mutation strength from ionizing radiation:
        radiation is a real mutagen, so mutations are more frequent and
        stronger under exposure.
        """
        rate = max(0.05, self.mutation_rate) * (1.0 + max(0.0, radiation_boost))
        values = {}
        for field_name, base_step in self._MUTATION_STEP.items():
            current = getattr(self, field_name)
            delta = random.gauss(0, base_step * rate)
            new_val = current + delta
            if field_name in self._CLAMP_01:
                new_val = min(1.0, max(0.0, new_val))
            if field_name in self._CLAMP_POSITIVE:
                new_val = max(0.01, new_val)
            values[field_name] = new_val
        # lifespan mutates MULTIPLICATIVELY, not additively (otherwise an
        # immortal cell with max_lifespan_s=inf could never "acquire"
        # aging, since adding to inf always gives inf)
        if self.max_lifespan_s == math.inf:
            values["max_lifespan_s"] = math.inf
        else:
            values["max_lifespan_s"] = max(1.0, self.max_lifespan_s * random.gauss(1.0, 0.05 * rate))
        return Genome(**values)

    def summary(self) -> str:
        lifespan = "does not age" if self.max_lifespan_s == math.inf else format_duration(self.max_lifespan_s)
        return (
            f"T_opt={self.optimal_temp:.1f}K+/-{self.temp_tolerance:.1f}  "
            f"pH_opt={self.optimal_ph:.2f}+/-{self.ph_tolerance:.2f}  "
            f"O2_opt={self.oxygen_need:.2f}+/-{self.oxygen_tolerance:.2f}  "
            f"radiation resistance={self.radiation_resistance*100:.0f}%  "
            f"toxin resistance={self.toxin_resistance*100:.0f}%  "
            f"metabolism={self.metabolic_rate:.2f}x  "
            f"mutability={self.mutation_rate:.2f}x  "
            f"lifespan={lifespan}"
        )
