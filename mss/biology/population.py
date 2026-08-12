"""
EVOLUTION AND ENVIRONMENT - Population

A population of cells of one species in a specific Environment. Can take
a single evolution step (step) or SKIP AHEAD a large amount of time at
once (skip_time) - evolution here is directly tied to simulated time
(including the universe's overall clock, Universe.elapsed_time_s), and
that time can be skipped instead of the player stepping through it
manually.

Crowding is modeled through carrying_capacity (the environment's
capacity) - the closer the population is to that capacity, the less
each cell actually gets in resources (the ordinary logistic population
growth model, not something invented just for this simulation).
"""

import random
from typing import Dict, List, Optional

from mss.biology.cell import Cell
from mss.biology.genome import Genome
from mss.biology.environment import Environment
from mss.core.universe import Universe, format_duration


class Population:
    def __init__(
        self,
        species: str,
        environment: Environment,
        genome: Optional[Genome] = None,
        initial_size: int = 1,
        carrying_capacity: int = 300,
    ):
        self.species = species
        self.environment = environment
        self.cells: List[Cell] = [Cell(species, genome=genome or Genome()) for _ in range(max(1, initial_size))]
        self.carrying_capacity = carrying_capacity
        self.elapsed_s: float = 0.0
        self.history: List[Dict[str, float]] = []

    def step(self, dt_seconds: float, universe: Optional[Universe] = None) -> None:
        self.environment.apply_natural_dynamics(dt_seconds, universe)

        # logistic crowding: temporarily "shrink" the nutrient density the
        # cells see this step, proportional to how close the population is
        # to the environment's capacity (a real ecological model)
        crowding = max(0.05, 1.0 - len(self.cells) / max(1, self.carrying_capacity))
        real_density = self.environment.nutrient_density
        self.environment.nutrient_density = real_density * crowding
        try:
            new_cells = []
            for c in self.cells:
                if c.alive:
                    child = c.step_in_environment(self.environment, dt_seconds)
                    if child:
                        new_cells.append(child)
            self.cells = [c for c in self.cells if c.alive] + new_cells
        finally:
            self.environment.nutrient_density = real_density  # restore the "real" value

        # Hard safety valve: the soft crowding above acts with a ONE-STEP
        # DELAY (it's computed BEFORE this step's cell division), so with a
        # large dt_seconds (time skip) the population can briefly overshoot
        # the environment's capacity. Real ecology knows this as a
        # population "crash" from overcrowding - some individuals die from
        # a sudden resource shortage, essentially at random.
        hard_limit = max(10, self.carrying_capacity * 2)
        if len(self.cells) > hard_limit:
            self.cells = random.sample(self.cells, hard_limit)

        self.elapsed_s += dt_seconds

    def skip_time(
        self,
        total_seconds: float,
        dt_step: Optional[float] = None,
        universe: Optional[Universe] = None,
        max_steps: int = 2000,
        log_every: int = 50,
    ) -> Dict[str, float]:
        """
        Skips ahead total_seconds of simulated time, running many small
        evolution steps in a row (a "fast-forward"), without requiring
        the player to step through each one manually. dt_step is chosen
        automatically to stay within max_steps steps (otherwise, at a
        scale of thousands of years, we'd need one-second steps and
        compute forever).
        """
        if total_seconds <= 0:
            return self.stats()
        if dt_step is None:
            dt_step = max(total_seconds / max_steps, 1.0)
        steps = max(1, min(int(total_seconds / dt_step), max_steps))
        for i in range(steps):
            if not self.cells:
                break
            self.step(dt_step, universe)
            if log_every and i % log_every == 0:
                self.history.append(self.stats())
        self.history.append(self.stats())
        return self.stats()

    def stats(self) -> Dict[str, float]:
        alive = [c for c in self.cells if c.alive]
        n = len(alive)
        if n == 0:
            return {"population": 0, "elapsed_s": self.elapsed_s}
        avg = lambda attr: sum(getattr(c.genome, attr) for c in alive) / n
        return {
            "population": n,
            "elapsed_s": self.elapsed_s,
            "avg_optimal_temp": avg("optimal_temp"),
            "avg_temp_tolerance": avg("temp_tolerance"),
            "avg_optimal_ph": avg("optimal_ph"),
            "avg_radiation_resistance": avg("radiation_resistance"),
            "avg_toxin_resistance": avg("toxin_resistance"),
            "avg_metabolic_rate": avg("metabolic_rate"),
            "avg_mutation_rate": avg("mutation_rate"),
            "max_generation": max(c.generation for c in alive),
        }

    def summary(self) -> str:
        s = self.stats()
        if s["population"] == 0:
            return f"Population '{self.species}' went extinct (t={format_duration(self.elapsed_s)})."
        drift = ""
        if len(self.history) >= 2:
            first, last = self.history[0], self.history[-1]
            if first.get("population", 0) > 0 and last.get("population", 0) > 0:
                d_temp = last["avg_optimal_temp"] - first["avg_optimal_temp"]
                drift = f"\n  Temperature-optimum drift since observation began: {d_temp:+.2f}K"
        return (
            f"Population '{self.species}' in environment '{self.environment.name}' "
            f"(t={format_duration(self.elapsed_s)})\n"
            f"  Individuals: {s['population']} / capacity {self.carrying_capacity}, "
            f"max generation: {s['max_generation']}\n"
            f"  Average temperature optimum: {s['avg_optimal_temp']:.1f}K "
            f"(tolerance +/-{s['avg_temp_tolerance']:.1f}K)\n"
            f"  Average pH optimum: {s['avg_optimal_ph']:.2f}\n"
            f"  Radiation resistance: {s['avg_radiation_resistance']*100:.1f}%  "
            f"Toxin resistance: {s['avg_toxin_resistance']*100:.1f}%\n"
            f"  Metabolism: {s['avg_metabolic_rate']:.2f}x  "
            f"Mutability: {s['avg_mutation_rate']:.2f}x"
            f"{drift}"
        )
