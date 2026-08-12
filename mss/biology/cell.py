"""
BIOLOGY: CELLS - Cell

A cell with its own optimal temperature, tolerance, and nutrient need.
It grows/divides/dies under a simple homeostasis model. On division its
traits MUTATE slightly - in an environment where the real temperature
differs from the optimum, later generations gradually "adapt" to it
through natural selection (survivors whose mutation happened to be
favorable go on to divide).

All genetics live in a separate Genome object (see mss.biology.genome) -
a cell's evolvable traits go well beyond temperature: pH, oxygen,
resistance to radiation and toxins, metabolic rate, lifespan, and even
the cell's own mutation rate. The old simple API (step) is kept
UNCHANGED for backward compatibility - the newer, full API lives in
step_in_environment() and is used by Population (see population.py).
"""

import random
from typing import Optional, TYPE_CHECKING

from mss.biology.genome import Genome

if TYPE_CHECKING:
    from mss.biology.environment import Environment


class Cell:
    """
    See module docstring. MUTATION_RATE/MUTATION_STRENGTH below are only
    used by the legacy simple API (step); the full API uses Genome.mutate().
    """

    MUTATION_RATE = 0.15     # chance of a noticeable mutation on division (legacy simple API)
    MUTATION_STRENGTH = 1.5  # how many kelvins the optimum may shift by (legacy simple API)

    def __init__(
        self,
        species: str,
        optimal_temp: float = 310.15,   # 37 C by default (a human cell)
        temp_tolerance: float = 4.0,    # K allowed deviation without stress
        nutrient_need: float = 1.0,
        genome: Optional[Genome] = None,
        age_s: float = 0.0,
    ):
        self.species = species
        self.genome = genome or Genome(
            optimal_temp=optimal_temp, temp_tolerance=temp_tolerance, nutrient_need=nutrient_need,
        )
        self.health = 1.0
        self.generation = 0
        self.alive = True
        self.age_s = age_s

    # --- backward-compatible properties: old code read these fields
    # directly on the cell; they now simply proxy to self.genome --------
    @property
    def optimal_temp(self) -> float:
        return self.genome.optimal_temp

    @property
    def temp_tolerance(self) -> float:
        return self.genome.temp_tolerance

    @property
    def nutrient_need(self) -> float:
        return self.genome.nutrient_need

    def step(self, environment_temp: float, nutrients_available: float,
              radiation_uSv: float = 0.0) -> Optional["Cell"]:
        """
        OLD simple API (kept unchanged for backward compatibility with the
        CLI's cell-growth demo). For the newer environment/evolution-over-
        time system, use step_in_environment().

        radiation_uSv - ionizing radiation dose for this step (uSv).
        Radiation increases cellular stress, raises the chance of a
        noticeable mutation on division (radiation-induced mutagenesis),
        and at a high enough dose can kill the cell instantly.
        """
        if not self.alive:
            return None

        # an acute high dose can kill the cell outright, before chronic stress is even applied
        if radiation_uSv > 5000 and random.random() < min(0.9, radiation_uSv / 20000):
            self.alive = False
            return None

        temp_diff = abs(environment_temp - self.optimal_temp)
        stress = max(0.0, (temp_diff - self.temp_tolerance) / 20)
        nutrient_ratio = min(1.0, nutrients_available / self.nutrient_need)
        radiation_stress = radiation_uSv / 2000.0  # chronic contribution to damage

        self.health += (nutrient_ratio * 0.15) - stress - radiation_stress - 0.03
        self.health = max(0.0, min(1.0, self.health))

        if self.health <= 0:
            self.alive = False
            return None

        if self.health > 0.85 and random.random() < 0.35:
            self.generation += 1
            self.health *= 0.7  # division costs resources

            child_optimal = self.optimal_temp
            child_tolerance = self.temp_tolerance
            mutation_chance = min(0.95, self.MUTATION_RATE + radiation_uSv / 3000.0)
            if random.random() < mutation_chance:
                # radiation not only triggers mutation more often, it also makes it stronger
                strength = self.MUTATION_STRENGTH * (1.0 + radiation_uSv / 1000.0)
                child_optimal += random.uniform(-strength, strength)
                child_tolerance = max(0.5, child_tolerance + random.uniform(-0.3, 0.3))

            child = Cell(self.species, child_optimal, child_tolerance, self.nutrient_need)
            child.generation = self.generation
            return child

        return None

    def step_in_environment(self, environment: "Environment", dt_seconds: float = 1.0) -> Optional["Cell"]:
        """
        NEW full API: stress is computed for EACH environmental condition
        separately (temperature, pH, oxygen, chemical toxicity,
        background radiation), factoring in the cell's genetic
        resistance to each, then summed. Used by Population for evolution
        over time in a player-controlled environment.
        """
        if not self.alive:
            return None

        g = self.genome
        self.age_s += dt_seconds

        # aging: death by age, if a finite max_lifespan_s is set
        if self.age_s > g.max_lifespan_s:
            self.alive = False
            return None

        temp_stress = max(0.0, (abs(environment.temperature - g.optimal_temp) - g.temp_tolerance) / 20)
        ph_stress = max(0.0, (abs(environment.ph - g.optimal_ph) - g.ph_tolerance) / 5)
        o2_stress = max(0.0, (abs(environment.oxygen_level - g.oxygen_need) - g.oxygen_tolerance) / 0.3)
        toxin_stress = environment.toxicity * (1 - g.toxin_resistance)

        # IMPORTANT: the dose is computed from a CLAMPED window dt_clamped,
        # not the full dt_seconds. When time is skipped ahead (skip_time),
        # a single step may represent years or millennia of simulated
        # time - if the dose accumulated over that whole span at once,
        # radiation would disproportionately dominate the other stress
        # factors (which are all computed "per step", not "over all
        # elapsed time"). This also roughly reflects a real effect in
        # radiobiology: chronic radiation spread out over time does less
        # harm than the same dose received all at once.
        dt_clamped = min(dt_seconds, 5.0)
        dose_sv = (environment.radiation_background_uSv_h * dt_clamped / 3600.0) / 1e6
        radiation_stress = dose_sv * 5e4 * (1 - g.radiation_resistance)
        acute_death_chance = max(0.0, dose_sv - 1.0) * 0.3 * (1 - g.radiation_resistance)

        # crowding: the denser the population relative to the
        # environment's nutrient density, the less each cell actually
        # gets (handled by Population.step via effective nutrient
        # density). Consumption also scales with metabolic_rate -
        # otherwise "fast metabolism" would have no evolutionary cost
        # (only benefit, no trade-off), and selection would push it up
        # without bound, causing unbounded population blow-up. In
        # reality, fast metabolism always demands more resources - same
        # here.
        effective_nutrient_need = g.nutrient_need * g.metabolic_rate
        nutrient_ratio = min(1.0, environment.nutrient_density / effective_nutrient_need)

        total_stress = temp_stress + ph_stress + o2_stress + toxin_stress + radiation_stress
        self.health += (nutrient_ratio * 0.15 * g.metabolic_rate - total_stress - 0.03) * dt_clamped
        self.health = max(0.0, min(1.0, self.health))

        if random.random() < acute_death_chance:
            self.alive = False
            return None
        if self.health <= 0:
            self.alive = False
            return None

        # The chance of division depends not only on the cell's health but
        # also on the REAL availability of resources right now
        # (nutrient_ratio) - as in real ecology: even a healthy individual
        # reproduces less often when resources are scarce. Without this
        # factor, health reacts to crowding with a one-step lag, and the
        # population can overshoot the environment's carrying capacity
        # almost to a hard limit before it starts to fall.
        division_chance = min(0.95, 0.35 * g.metabolic_rate * dt_clamped * nutrient_ratio)
        if self.health > 0.85 and random.random() < division_chance:
            self.generation += 1
            self.health *= 0.7
            child = Cell(self.species, genome=g.mutate(radiation_boost=radiation_stress))
            child.generation = self.generation
            return child

        return None

    def __repr__(self):
        status = "alive" if self.alive else "dead"
        return (f"<{self.species} generation={self.generation} health={self.health:.2f} "
                f"optimum={self.optimal_temp:.1f}K ({status})>")
