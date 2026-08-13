#!/usr/bin/env python3
"""
Materials Simulation System (MSS)
v0.0000000000001 - Experimental Prototype

SINGLE-FILE EDITION.

Everything below (math/vector helpers, the simulation clock, the
periodic table, known compounds, an arbitrary Substance, nuclear
physics/radiation, basic mechanics/electricity, the chemistry engine,
cell/genome/environment/population biology, the invention engine and
buildable devices/workshop, the player-defined programming language and
its interpreter, and the interactive CLI) is normally split across many
files under the mss/ package (see the accompanying
PROJECT_STRUCTURE.txt for that layout). This file merges all of it into
one module, keeping the same section comments, so it can be dropped in
and run on its own with:

    python3 materials_simulation_system.py

Package layout (for reference - this is what the split version looks like):
    core          - shared math tools and the simulation clock (Universe)
    chemistry     - periodic table, known compounds, arbitrary substances
    physics       - heat/mechanics/electricity and nuclear physics
    biology       - genomes, cells, environments, evolving populations
    engineering   - invention discovery and buildable devices
    programming   - a tiny player-defined programming language and VM
    cli           - the interactive command-line demo
"""

import itertools
import math
import random
from dataclasses import dataclass, field
from enum import Enum
from fractions import Fraction
from typing import Dict, List, Optional, Tuple


# ============================================================================
# CORE / MATH UTILITIES (Vector2D, Stats)
# (from original module: mss/core/vectors.py)
# ============================================================================

"""
Shared math utilities used by physics, biology, and engineering below.
"""



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


# ============================================================================
# CORE / UNIVERSE, TIMERS, REMINDERS
# (from original module: mss/core/universe.py)
# ============================================================================

"""
Universe - the container for a simulation's physical constants and its
own simulated clock. Since the engine already deals with durations of
time (radioactive half-lives), it makes sense for the Universe to carry
a single "now" that decay, timers, and reminders all advance against.
See advance_time().
"""




def format_duration(seconds: float) -> str:
    """
    Human-readable formatting for an arbitrary duration (auto unit choice).
    Shared by universe time, timers/reminders, and half-lives (see
    format_half_life in mss.physics.radiation) so time is always displayed
    the same way everywhere.
    """
    if seconds == 0:
        return "0 s"
    if seconds == math.inf:
        return "unlimited"
    if seconds < 1e-3:
        return f"{seconds * 1e6:.1f} us"
    if seconds < 1:
        return f"{seconds * 1e3:.1f} ms"
    if seconds < 60:
        return f"{seconds:.1f} s"
    if seconds < 3600:
        return f"{seconds / 60:.1f} min"
    if seconds < 86400:
        return f"{seconds / 3600:.1f} h"
    years = seconds / (365.25 * 86400)
    if years < 1:
        return f"{seconds / 86400:.1f} days"
    if years < 1e4:
        return f"{years:.1f} years"
    return f"{years:.3e} years"


class Universe:
    """
    Container for the physical constants of a simulation run.
    """

    def __init__(
        self,
        name: str = "Universe-Alpha",
        gravity: float = 9.81,                # m/s^2
        speed_of_light: float = 299_792_458,   # m/s
        planck: float = 6.626e-34,             # Planck constant
        gas_constant: float = 8.314,           # J/(mol*K)
    ):
        self.name = name
        self.gravity = gravity
        self.speed_of_light = speed_of_light
        self.planck = planck
        self.gas_constant = gas_constant

        # --- Simulation clock ------------------------------------------
        self.elapsed_time_s: float = 0.0
        self.timers: Dict[str, "Timer"] = {}
        self.reminders: Dict[str, "Reminder"] = {}
        self._tracked_substances: List["Substance"] = []

    def __repr__(self):
        return (f"<Universe '{self.name}' g={self.gravity} "
                f"c={self.speed_of_light:.3e} h={self.planck:.3e} "
                f"t={format_duration(self.elapsed_time_s)}>")

    # --- Time: tracking decay, timers, reminders ------------------------

    def track(self, substance: "Substance") -> "Substance":
        """
        Registers a substance so it decays AUTOMATICALLY when the
        universe's time is advanced (advance_time), instead of only
        manually via substance.decay_step(...).
        """
        if substance not in self._tracked_substances:
            self._tracked_substances.append(substance)
        return substance

    def add_timer(self, name: str, duration_s: float, message: str = "",
                  repeating: bool = False) -> "Timer":
        """A countdown timer: fires after duration_s seconds from now."""
        timer = Timer(name=name, duration_s=duration_s, remaining_s=duration_s,
                      message=message, repeating=repeating)
        self.timers[name] = timer
        return timer

    def add_reminder(self, name: str, in_seconds: float, message: str) -> "Reminder":
        """A one-off reminder: fires once the universe's clock reaches the target time."""
        reminder = Reminder(name=name, trigger_at_s=self.elapsed_time_s + in_seconds, message=message)
        self.reminders[name] = reminder
        return reminder

    def advance_time(self, dt_seconds: float) -> List[str]:
        """
        Advances the universe's clock by dt_seconds. During that time:
          - every tracked() radioactive substance decays for real
            (Substance.decay_step);
          - every timer ticks and may fire;
          - every reminder is checked and may fire.
        Returns a list of text events that occurred (an empty list just
        means time passed with nothing notable happening).
        """
        if dt_seconds < 0:
            raise ValueError("Time cannot flow backwards in this simulation.")
        events: List[str] = []
        self.elapsed_time_s += dt_seconds

        for substance in self._tracked_substances:
            if substance.is_radioactive():
                substance.decay_step(dt_seconds)

        for timer in self.timers.values():
            fired_before = timer.fired_count
            if timer.tick(dt_seconds):
                times = timer.fired_count - fired_before
                suffix = f": {timer.message}" if timer.message else ""
                count_note = f" (x{times})" if times > 1 else ""
                events.append(f"Timer '{timer.name}' fired{count_note}{suffix}")

        for reminder in self.reminders.values():
            if reminder.check(self.elapsed_time_s):
                events.append(f"Reminder '{reminder.name}': {reminder.message}")

        return events

    def format_elapsed_time(self) -> str:
        return format_duration(self.elapsed_time_s)


@dataclass
class Timer:
    """
    A countdown timer living in the time of a specific Universe.
    If repeating=True, it automatically restarts after firing (handy for
    periodic events like "check the reactor every 10 minutes").
    """
    name: str
    duration_s: float
    remaining_s: float
    message: str = ""
    repeating: bool = False
    fired_count: int = 0

    def tick(self, dt_seconds: float) -> bool:
        """
        Advances the timer by dt_seconds. Returns True if it fired at
        least once. The number of firings is computed ANALYTICALLY
        (via division) rather than in a loop - otherwise a huge jump in
        time (e.g. "advance by one half-life of uranium-238" = 4.5
        billion years) with a repeating timer on the order of minutes
        would try to run trillions of iterations and hang.
        """
        if not self.repeating and self.fired_count > 0:
            return False  # a one-off timer has already fired
        if self.duration_s <= 0:
            return False
        self.remaining_s -= dt_seconds
        if self.remaining_s > 0:
            return False
        if not self.repeating:
            self.fired_count += 1
            self.remaining_s = 0.0
            return True
        overshoot = -self.remaining_s
        periods_fired = 1 + int(overshoot // self.duration_s)
        self.fired_count += periods_fired
        self.remaining_s = self.duration_s - (overshoot % self.duration_s)
        return True

    def summary(self) -> str:
        state = "pending" if self.remaining_s > 0 else "fired"
        return (f"{self.name}: {format_duration(max(0.0, self.remaining_s))} remaining "
                f"({state}, fired: {self.fired_count}"
                f"{', repeating' if self.repeating else ''})")


@dataclass
class Reminder:
    """
    A one-off reminder tied to the universe's absolute time
    (elapsed_time_s) rather than a countdown - useful for "remind me when
    the fuel has decayed" or "remind me at year 1000".
    """
    name: str
    trigger_at_s: float
    message: str
    fired: bool = False

    def check(self, current_time_s: float) -> bool:
        if not self.fired and current_time_s >= self.trigger_at_s:
            self.fired = True
            return True
        return False

    def summary(self, current_time_s: float) -> str:
        if self.fired:
            return f"{self.name}: fired - {self.message}"
        remaining = max(0.0, self.trigger_at_s - current_time_s)
        return f"{self.name}: in {format_duration(remaining)} - {self.message}"


# ============================================================================
# CHEMISTRY / PERIODIC TABLE OF ELEMENTS
# (from original module: mss/chemistry/elements.py)
# ============================================================================

"""
CHEMISTRY: ELEMENTS
"""



class State(Enum):
    SOLID = "solid"
    LIQUID = "liquid"
    GAS = "gas"
    PLASMA = "plasma"


@dataclass
class Element:
    symbol: str
    name: str
    atomic_mass: float          # amu
    melting_point: float        # K
    boiling_point: float        # K
    density: float              # g/cm^3
    valence: int
    electronegativity: float    # Pauling scale
    conductivity: float         # 0..1 (normalized)
    flammability: float         # 0..1
    reactivity: float           # 0..1

    def state_at(self, temp_k: float) -> State:
        if temp_k < self.melting_point:
            return State.SOLID
        if temp_k < self.boiling_point:
            return State.LIQUID
        if temp_k < self.boiling_point * 5:
            return State.GAS
        return State.PLASMA


PERIODIC_TABLE: Dict[str, Element] = {}


def _reg(*args):
    e = Element(*args)
    PERIODIC_TABLE[e.symbol] = e


# symbol, name, atomic_mass, melting(K), boiling(K), density(g/cm3),
# valence, electronegativity, conductivity(0-1), flammability(0-1), reactivity(0-1)
_reg("H", "Hydrogen", 1.008, 14.01, 20.28, 0.00009, 1, 2.20, 0.05, 0.90, 0.60)
_reg("He", "Helium", 4.0026, 0.95, 4.22, 0.000179, 0, 0.00, 0.00, 0.00, 0.00)
_reg("C", "Carbon", 12.011, 3823, 4098, 2.267, 4, 2.55, 0.10, 0.60, 0.30)
_reg("N", "Nitrogen", 14.007, 63.15, 77.36, 0.001251, 3, 3.04, 0.00, 0.00, 0.20)
_reg("O", "Oxygen", 15.999, 54.36, 90.20, 0.001429, 2, 3.44, 0.00, 0.00, 0.80)
_reg("F", "Fluorine", 18.998, 53.53, 85.03, 0.001696, 1, 3.98, 0.00, 0.00, 0.99)
_reg("Na", "Sodium", 22.99, 370.87, 1156, 0.971, 1, 0.93, 0.85, 0.90, 0.95)
_reg("Mg", "Magnesium", 24.305, 923, 1363, 1.738, 2, 1.31, 0.75, 0.85, 0.60)
_reg("Al", "Aluminum", 26.982, 933.47, 2792, 2.70, 3, 1.61, 0.85, 0.20, 0.40)
_reg("Si", "Silicon", 28.085, 1687, 3538, 2.33, 4, 1.90, 0.30, 0.05, 0.20)
_reg("P", "Phosphorus", 30.974, 317.3, 550, 1.82, 5, 2.19, 0.05, 0.95, 0.70)
_reg("S", "Sulfur", 32.06, 388.36, 717.87, 2.07, 6, 2.58, 0.05, 0.70, 0.40)
_reg("Cl", "Chlorine", 35.45, 171.6, 239.11, 0.003214, 1, 3.16, 0.00, 0.00, 0.90)
_reg("K", "Potassium", 39.098, 336.53, 1032, 0.862, 1, 0.82, 0.90, 0.95, 0.98)
_reg("Ca", "Calcium", 40.078, 1115, 1757, 1.55, 2, 1.00, 0.65, 0.40, 0.70)
_reg("Fe", "Iron", 55.845, 1811, 3134, 7.874, 3, 1.83, 0.70, 0.10, 0.50)
_reg("Cu", "Copper", 63.546, 1357.77, 2835, 8.96, 2, 1.90, 0.95, 0.05, 0.30)
_reg("Zn", "Zinc", 65.38, 692.68, 1180, 7.14, 2, 1.65, 0.60, 0.20, 0.55)
_reg("Ag", "Silver", 107.87, 1234.93, 2435, 10.49, 1, 1.93, 0.99, 0.02, 0.20)
_reg("Au", "Gold", 196.97, 1337.33, 3129, 19.30, 3, 2.54, 0.90, 0.00, 0.05)
_reg("U", "Uranium", 238.03, 1405.3, 4404, 19.1, 6, 1.38, 0.20, 0.00, 0.85)
_reg("Li", "Lithium", 6.94, 453.65, 1615, 0.534, 1, 0.98, 0.80, 0.95, 0.99)
_reg("Ti", "Titanium", 47.867, 1941, 3560, 4.506, 4, 1.54, 0.35, 0.05, 0.35)
_reg("Ni", "Nickel", 58.693, 1728, 3186, 8.908, 2, 1.91, 0.65, 0.05, 0.35)
_reg("Sn", "Tin", 118.71, 505.08, 2875, 7.265, 4, 1.96, 0.55, 0.05, 0.25)
_reg("Pb", "Lead", 207.2, 600.61, 2022, 11.34, 2, 2.33, 0.45, 0.00, 0.20)

# The elements below are needed mainly as "chemical carriers" for isotopes
# from the nuclear physics section (see ISOTOPES in mss.physics.radiation) -
# without them, a Substance with a composition like {"Co": 1} could not
# compute ordinary chemical properties (conductivity, density, etc.) and
# would raise an error.
_reg("Co", "Cobalt", 58.933, 1768, 3200, 8.90, 2, 1.88, 0.45, 0.05, 0.40)
_reg("I", "Iodine", 126.90, 386.85, 457.4, 4.93, 1, 2.66, 0.02, 0.10, 0.60)
_reg("Cs", "Cesium", 132.91, 301.59, 944, 1.93, 1, 0.79, 0.90, 0.98, 0.99)
_reg("Ba", "Barium", 137.33, 1000, 2170, 3.51, 2, 0.89, 0.45, 0.60, 0.75)
_reg("Sr", "Strontium", 87.62, 1050, 1655, 2.64, 2, 0.95, 0.50, 0.60, 0.70)
_reg("Y", "Yttrium", 88.906, 1799, 3609, 4.47, 3, 1.22, 0.35, 0.10, 0.40)
_reg("Zr", "Zirconium", 91.224, 2128, 4650, 6.52, 4, 1.33, 0.24, 0.05, 0.30)
_reg("Th", "Thorium", 232.04, 2023, 5061, 11.7, 4, 1.30, 0.14, 0.00, 0.55)
_reg("Ra", "Radium", 226.03, 973, 2010, 5.50, 2, 0.90, 0.35, 0.00, 0.80)
_reg("Rn", "Radon", 222.02, 202, 211.5, 0.00973, 0, 2.20, 0.00, 0.00, 0.00)
_reg("Po", "Polonium", 209.98, 527, 1235, 9.20, 4, 2.00, 0.30, 0.00, 0.50)
_reg("Bi", "Bismuth", 208.98, 544.7, 1837, 9.78, 3, 2.02, 0.15, 0.00, 0.25)
_reg("Pa", "Protactinium", 231.04, 1841, 4300, 15.37, 5, 1.50, 0.20, 0.00, 0.50)
_reg("Np", "Neptunium", 237.05, 917, 4273, 20.45, 5, 1.36, 0.20, 0.00, 0.60)
_reg("Am", "Americium", 243.06, 1449, 2880, 12.00, 3, 1.30, 0.20, 0.00, 0.55)
_reg("Xe", "Xenon", 131.29, 161.4, 165.03, 0.0058, 0, 2.60, 0.00, 0.00, 0.00)

# The elements below are needed for electronics (the "chips and boards"
# section): classic semiconductors, dopants, and refractory conductors
# for contacts.
_reg("Ge", "Germanium", 72.63, 1211.4, 3106, 5.323, 4, 2.01, 0.40, 0.00, 0.15)
_reg("Ga", "Gallium", 69.723, 302.9, 2673, 5.91, 3, 1.81, 0.50, 0.00, 0.35)
_reg("As", "Arsenic", 74.922, 1090, 887, 5.727, 3, 2.18, 0.30, 0.00, 0.40)
_reg("B", "Boron", 10.81, 2349, 4200, 2.34, 3, 2.04, 0.15, 0.05, 0.30)
_reg("W", "Tungsten", 183.84, 3695, 5828, 19.25, 6, 2.36, 0.31, 0.00, 0.15)
_reg("Ta", "Tantalum", 180.95, 3290, 5731, 16.69, 5, 1.50, 0.31, 0.00, 0.15)


# ============================================================================
# CHEMISTRY / KNOWN COMPOUNDS (REAL-DATA ANCHORS)
# (from original module: mss/chemistry/compounds.py)
# ============================================================================

"""
KNOWN COMPOUNDS - real-data "anchors"

Problem this fixes: previously the properties of ANY substance were
computed as a weighted average over its elements. For water (H2O) that
gave an absurd result - "plasma at room temperature". Real chemistry
doesn't work like an average: atoms combining into a compound form a
structure with its own properties.

Solution: keep a database of real compounds. When a substance's
composition (reduced to a simple integer formula, e.g. H2O1) matches one
of the known compounds, we use its REAL data. If there's no match (the
player mixed something that doesn't occur in nature), we still fall back
to the averaging formula, but explicitly mark it as an ESTIMATE rather
than an exact value, so the model is never presented as fact.
"""



@dataclass
class CompoundData:
    name: str
    formula_ratio: Dict[str, int]   # empirical formula, e.g. {"H": 2, "O": 1}
    melting_point: float            # K
    boiling_point: float            # K
    density: float                  # g/cm^3
    conductivity: float             # 0..1
    flammability: float             # 0..1
    reactivity: float               # 0..1


def _ratio_key(formula_ratio: Dict[str, int]) -> Tuple[Tuple[str, int], ...]:
    """Normalized key for comparing formulas (reduced to simplest form)."""
    g = 0
    for v in formula_ratio.values():
        g = math.gcd(g, v)
    g = g or 1
    return tuple(sorted((s, v // g) for s, v in formula_ratio.items()))


def empirical_ratio(composition: Dict[str, float]) -> Tuple[Tuple[str, int], ...]:
    """
    Turns mole fractions (e.g. {'H': 0.667, 'O': 0.333}) into the simplest
    integer formula (e.g. H2O -> (('H', 2), ('O', 1))). Used to match an
    arbitrary composition against the known-compound database. If the
    composition doesn't reduce to small integers (denominator > 8), we
    don't look for a match - the substance is treated as "exotic".
    """
    items = sorted(composition.items())
    if not items:
        return tuple()
    min_frac = min(v for _, v in items if v > 0)
    try:
        fracs = {s: Fraction(v / min_frac).limit_denominator(8) for s, v in items}
    except (ZeroDivisionError, ValueError):
        return tuple()

    denom = 1
    for f in fracs.values():
        denom = denom * f.denominator // math.gcd(denom, f.denominator)

    ints = {s: round(f * denom) for s, f in fracs.items()}
    return _ratio_key(ints)


KNOWN_COMPOUNDS: Dict[Tuple[Tuple[str, int], ...], CompoundData] = {}


def _reg_compound(name, formula_ratio, melting, boiling, density, conductivity, flammability, reactivity):
    cd = CompoundData(name, formula_ratio, melting, boiling, density, conductivity, flammability, reactivity)
    KNOWN_COMPOUNDS[_ratio_key(formula_ratio)] = cd


# name, {formula}, melt(K), boil(K), density(g/cm3), conductivity, flammability, reactivity
_reg_compound("Water (H2O)", {"H": 2, "O": 1}, 273.15, 373.15, 1.00, 0.005, 0.00, 0.10)
_reg_compound("Methane (CH4)", {"C": 1, "H": 4}, 90.7, 111.7, 0.42, 0.00, 0.95, 0.40)
_reg_compound("Carbon dioxide (CO2)", {"C": 1, "O": 2}, 216.6, 194.7, 1.56, 0.00, 0.00, 0.20)
_reg_compound("Ammonia (NH3)", {"N": 1, "H": 3}, 195.4, 239.8, 0.73, 0.01, 0.55, 0.50)
_reg_compound("Table salt (NaCl)", {"Na": 1, "Cl": 1}, 1074.0, 1686.0, 2.16, 0.02, 0.00, 0.05)
_reg_compound("Quartz/sand (SiO2)", {"Si": 1, "O": 2}, 1986.0, 2503.0, 2.65, 0.00, 0.00, 0.05)
_reg_compound("Iron oxide/rust (Fe2O3)", {"Fe": 2, "O": 3}, 1838.0, 3273.0, 5.24, 0.10, 0.00, 0.10)
_reg_compound("Aluminum oxide (Al2O3)", {"Al": 2, "O": 3}, 2345.0, 3253.0, 3.95, 0.00, 0.00, 0.05)
_reg_compound("Quicklime (CaO)", {"Ca": 1, "O": 1}, 2886.0, 3123.0, 3.34, 0.00, 0.00, 0.60)
_reg_compound("Chalk/limestone (CaCO3)", {"Ca": 1, "C": 1, "O": 3}, 1612.0, 3000.0, 2.71, 0.00, 0.00, 0.05)
_reg_compound("Zinc oxide (ZnO)", {"Zn": 1, "O": 1}, 2248.0, 2360.0, 5.61, 0.05, 0.00, 0.10)
_reg_compound("Magnesium oxide (MgO)", {"Mg": 1, "O": 1}, 3125.0, 3873.0, 3.58, 0.00, 0.00, 0.05)
_reg_compound("Sulfuric acid (H2SO4)", {"H": 2, "S": 1, "O": 4}, 283.5, 610.0, 1.84, 0.30, 0.00, 0.85)
_reg_compound("Caustic soda (NaOH)", {"Na": 1, "O": 1, "H": 1}, 596.0, 1661.0, 2.13, 0.20, 0.00, 0.80)
_reg_compound("Potassium chloride (KCl)", {"K": 1, "Cl": 1}, 1043.0, 1693.0, 1.98, 0.03, 0.00, 0.05)
_reg_compound("Baking soda (NaHCO3)", {"Na": 1, "H": 1, "C": 1, "O": 3}, 323.0, 423.0, 2.20, 0.02, 0.00, 0.10)
_reg_compound("Titanium dioxide (TiO2)", {"Ti": 1, "O": 2}, 2116.0, 3245.0, 4.23, 0.00, 0.00, 0.05)
_reg_compound("Nickel oxide (NiO)", {"Ni": 1, "O": 1}, 2228.0, 3273.0, 6.67, 0.10, 0.00, 0.15)
_reg_compound("Tin oxide (SnO2)", {"Sn": 1, "O": 2}, 1903.0, 2143.0, 6.95, 0.15, 0.00, 0.10)
_reg_compound("Lead oxide (PbO)", {"Pb": 1, "O": 1}, 1161.0, 1743.0, 9.53, 0.05, 0.00, 0.10)
_reg_compound("Lithium hydroxide (LiOH)", {"Li": 1, "O": 1, "H": 1}, 744.0, 1899.0, 1.46, 0.15, 0.00, 0.55)
_reg_compound("Ethanol (C2H6O)", {"C": 2, "H": 6, "O": 1}, 159.0, 351.5, 0.789, 0.00, 0.85, 0.35)
_reg_compound("Acetic acid (C2H4O2)", {"C": 2, "H": 4, "O": 2}, 289.8, 391.2, 1.049, 0.02, 0.30, 0.60)
_reg_compound("Hydrogen peroxide (H2O2)", {"H": 2, "O": 2}, 272.7, 423.4, 1.45, 0.01, 0.00, 0.70)
_reg_compound("Glucose (C6H12O6)", {"C": 6, "H": 12, "O": 6}, 423.0, 800.0, 1.54, 0.00, 0.20, 0.10)
_reg_compound("Tin chloride (SnCl4)", {"Sn": 1, "Cl": 4}, 240.9, 387.6, 2.23, 0.10, 0.00, 0.35)
_reg_compound("Lead(IV) oxide (PbO2)", {"Pb": 1, "O": 2}, 563.0, 563.0, 9.38, 0.20, 0.00, 0.30)
_reg_compound("Titanium chloride (TiCl4)", {"Ti": 1, "Cl": 4}, 250.0, 409.0, 1.73, 0.05, 0.00, 0.50)
# Extra hydrogen compounds - the more of these are in the anchor database,
# the less often a player's hydrogen-bearing substance falls through to the
# rough averaging formula (see LIMIT #1 in mss.chemistry.substance) and the
# rarer the physically absurd results become, like "a liquid at 300K
# behaves like plasma", as once happened with water.
_reg_compound("Hydrogen chloride/hydrochloric acid (HCl)", {"H": 1, "Cl": 1}, 158.97, 188.1, 1.49, 0.05, 0.00, 0.85)
_reg_compound("Hydrogen fluoride (HF)", {"H": 1, "F": 1}, 189.6, 292.9, 0.99, 0.05, 0.00, 0.90)
_reg_compound("Hydrogen sulfide (H2S)", {"H": 2, "S": 1}, 187.7, 213.6, 0.99, 0.00, 0.90, 0.60)
_reg_compound("Phosphoric acid (H3PO4)", {"H": 3, "P": 1, "O": 4}, 315.5, 407.0, 1.885, 0.15, 0.00, 0.50)
_reg_compound("Ammonium chloride (NH4Cl)", {"N": 1, "H": 4, "Cl": 1}, 611.0, 793.0, 1.53, 0.02, 0.00, 0.10)


# ============================================================================
# PHYSICS / NUCLEAR PHYSICS (ISOTOPES, DECAY, RADIATION)
# (from original module: mss/physics/radiation.py)
# ============================================================================

"""
NUCLEAR PHYSICS - radioactivity, alpha/beta/gamma radiation, activity,
decay chains, dosimetry, and radiation shielding.

Scope is deliberately limited to educational nuclear physics: half-life,
the law of radioactive decay N(t) = N0 * e^(-lambda*t), activity
(Bq/Ci), radiation types and their attenuation by matter, and dose. This
is the SAME data found in any high-school table of nuclides. There is,
deliberately, NO critical mass, enrichment, or weapon-design content -
nothing that would give an engineering advantage toward building a
weapon. Isotopes are drawn from the natural uranium-238 decay series and
well-known household/medical sources (smoke detectors, radiotherapy,
radiocarbon dating) - U-235 and Pu-239 are intentionally excluded, even
though their half-lives are also public knowledge.
"""




AVOGADRO = 6.02214076e23  # particles/mol


def format_half_life(seconds: float) -> str:
    """Half-life: same formatting as format_duration, but 'stable' instead of 'unlimited'."""
    if seconds == math.inf:
        return "stable"
    return format_duration(seconds)


@dataclass
class Isotope:
    symbol: str               # e.g. "U238"
    element: str               # element symbol, e.g. "U"
    mass_number: int           # mass number A
    half_life_s: float         # half-life, s (math.inf for stable isotopes)
    decay_mode: str            # "alpha" | "beta-" | "beta+" | "stable"
    decay_energy_MeV: float    # decay energy, MeV
    emits_gamma: bool = False  # whether the decay is accompanied by gamma radiation
    daughter: Optional[str] = None  # daughter isotope symbol (None if stable)

    def __repr__(self):
        return f"<Isotope {self.symbol} {self.decay_mode} T1/2={format_half_life(self.half_life_s)}>"


ISOTOPES: Dict[str, Isotope] = {}


def _reg_isotope(symbol, element, mass_number, half_life_s, decay_mode,
                  decay_energy_MeV, emits_gamma=False, daughter=None):
    ISOTOPES[symbol] = Isotope(symbol, element, mass_number, half_life_s,
                                decay_mode, decay_energy_MeV, emits_gamma, daughter)


YEAR = 365.25 * 86400  # seconds in a year

# --- Uranium-238 natural decay series (fully public data) -----------------
_reg_isotope("U238", "U", 238, 4.468e9 * YEAR, "alpha", 4.27, daughter="Th234")
_reg_isotope("Th234", "Th", 234, 24.1 * 86400, "beta-", 0.27, emits_gamma=True, daughter="Pa234")
_reg_isotope("Pa234", "Pa", 234, 1.17 * 60, "beta-", 2.20, emits_gamma=True, daughter="U234")
_reg_isotope("U234", "U", 234, 245_500 * YEAR, "alpha", 4.86, daughter="Th230")
_reg_isotope("Th230", "Th", 230, 75_380 * YEAR, "alpha", 4.77, daughter="Ra226")
_reg_isotope("Ra226", "Ra", 226, 1600 * YEAR, "alpha", 4.87, emits_gamma=True, daughter="Rn222")
_reg_isotope("Rn222", "Rn", 222, 3.82 * 86400, "alpha", 5.59, daughter="Po218")
_reg_isotope("Po218", "Po", 218, 3.1 * 60, "alpha", 6.11, daughter="Pb214")
_reg_isotope("Pb214", "Pb", 214, 26.8 * 60, "beta-", 1.02, emits_gamma=True, daughter="Bi214")
_reg_isotope("Bi214", "Bi", 214, 19.9 * 60, "beta-", 3.27, emits_gamma=True, daughter="Po214")
_reg_isotope("Po214", "Po", 214, 164.3e-6, "alpha", 7.83, daughter="Pb210")
_reg_isotope("Pb210", "Pb", 210, 22.3 * YEAR, "beta-", 0.06, daughter="Bi210")
_reg_isotope("Bi210", "Bi", 210, 5.013 * 86400, "beta-", 1.16, daughter="Po210")
_reg_isotope("Po210", "Po", 210, 138.376 * 86400, "alpha", 5.41, daughter="Pb206")
_reg_isotope("Pb206", "Pb", 206, math.inf, "stable", 0.0)

# --- Well-known household/medical/geological isotopes ----------------------
_reg_isotope("C14", "C", 14, 5730 * YEAR, "beta-", 0.156, daughter="N14")
_reg_isotope("N14", "N", 14, math.inf, "stable", 0.0)
_reg_isotope("K40", "K", 40, 1.248e9 * YEAR, "beta-", 1.31, daughter="Ca40")
_reg_isotope("Ca40", "Ca", 40, math.inf, "stable", 0.0)
_reg_isotope("H3", "H", 3, 12.32 * YEAR, "beta-", 0.0186, daughter="He3")
_reg_isotope("He3", "He", 3, math.inf, "stable", 0.0)
_reg_isotope("Co60", "Co", 60, 5.27 * YEAR, "beta-", 2.82, emits_gamma=True, daughter="Ni60")
_reg_isotope("Ni60", "Ni", 60, math.inf, "stable", 0.0)
_reg_isotope("I131", "I", 131, 8.02 * 86400, "beta-", 0.97, emits_gamma=True, daughter="Xe131")
_reg_isotope("Xe131", "Xe", 131, math.inf, "stable", 0.0)
_reg_isotope("Cs137", "Cs", 137, 30.17 * YEAR, "beta-", 1.17, emits_gamma=True, daughter="Ba137")
_reg_isotope("Ba137", "Ba", 137, math.inf, "stable", 0.0)
_reg_isotope("Sr90", "Sr", 90, 28.8 * YEAR, "beta-", 0.546, daughter="Y90")
_reg_isotope("Y90", "Y", 90, 64.1 * 3600, "beta-", 2.28, daughter="Zr90")
_reg_isotope("Zr90", "Zr", 90, math.inf, "stable", 0.0)
_reg_isotope("Am241", "Am", 241, 432.2 * YEAR, "alpha", 5.49, emits_gamma=True, daughter="Np237")
_reg_isotope("Np237", "Np", 237, 2.14e6 * YEAR, "alpha", 4.96, daughter=None)


class DecayEngine:
    """The law of radioactive decay and decay chains."""

    @staticmethod
    def decay_constant(isotope: Isotope) -> float:
        """lambda = ln2 / T1/2 (1/s). Zero for stable isotopes."""
        if isotope.half_life_s == math.inf or isotope.half_life_s <= 0:
            return 0.0
        return math.log(2) / isotope.half_life_s

    @staticmethod
    def remaining_fraction(isotope: Isotope, elapsed_s: float) -> float:
        """Fraction of the original atom count remaining after elapsed_s."""
        return math.exp(-DecayEngine.decay_constant(isotope) * elapsed_s)

    @staticmethod
    def activity(isotope: Isotope, n_atoms: float) -> float:
        """Activity A = lambda*N, decays per second (becquerels)."""
        return DecayEngine.decay_constant(isotope) * n_atoms

    @staticmethod
    def decay_chain(symbol: str, max_steps: int = 20) -> List[Isotope]:
        """The sequence of isotopes from symbol down to a stable product."""
        chain, seen = [], set()
        current = ISOTOPES.get(symbol)
        while current is not None and current.symbol not in seen and len(chain) < max_steps:
            chain.append(current)
            seen.add(current.symbol)
            current = ISOTOPES.get(current.daughter) if current.daughter else None
        return chain

    @staticmethod
    def simulate_chain(start_symbol: str, n_atoms0: float, total_time_s: float,
                        steps: int = 2000) -> Dict[str, float]:
        """
        Numerically (Euler's method) computes how many atoms of each
        isotope in the decay chain remain after total_time_s. A
        simplification of the exact Bateman equations - plenty good
        enough to demonstrate a decay chain in the simulation, but not
        for precise nuclear-physics calculations.
        """
        chain = DecayEngine.decay_chain(start_symbol)
        populations = {iso.symbol: 0.0 for iso in chain}
        if not populations:
            return populations
        populations[start_symbol] = n_atoms0
        steps = max(1, steps)
        dt = total_time_s / steps
        for _ in range(steps):
            deltas = {sym: 0.0 for sym in populations}
            for iso in chain:
                n = populations[iso.symbol]
                if n <= 0 or iso.half_life_s == math.inf:
                    continue
                decayed = min(DecayEngine.decay_constant(iso) * n * dt, n)
                deltas[iso.symbol] -= decayed
                if iso.daughter and iso.daughter in populations:
                    deltas[iso.daughter] += decayed
            for sym in populations:
                populations[sym] = max(0.0, populations[sym] + deltas[sym])
        return populations


class RadiationEngine:
    """
    A simplified (simulation-only, NOT medical/dosimetric!) model of
    shielding attenuation and dose-rate estimation. Constants are tuned
    for plausible simulation balance and to illustrate the three
    radiation types for teaching purposes - this is not a substitute for
    real dosimetry calculations.
    """

    DOSE_TIERS = [
        (10.0, "background level (nominally safe)"),
        (100.0, "elevated (reduce exposure time)"),
        (1000.0, "dangerous (shielding required)"),
        (math.inf, "critically dangerous in the simulation model"),
    ]

    @staticmethod
    def attenuation(radiation_type: str, shield: Optional["Substance"], thickness_cm: float) -> float:
        """Fraction of radiation passing through the shield (0..1). No shield -> 1.0."""
        if thickness_cm <= 0 or shield is None:
            return 1.0
        density = max(shield.density, 0.01)
        if radiation_type == "alpha":
            # alpha particles are stopped by a sheet of paper / a few cm of air
            return 0.0 if thickness_cm > 0.01 else 1.0
        if radiation_type in ("beta-", "beta+", "beta"):
            stopping_thickness_cm = 0.5 / density  # rough estimate (denser metal is more effective)
            if thickness_cm >= stopping_thickness_cm:
                return 0.0
            return max(0.0, 1 - thickness_cm / stopping_thickness_cm)
        if radiation_type == "gamma":
            mu = 0.02 * density  # cm^-1, grows linearly with shield density
            return math.exp(-mu * thickness_cm)
        return 1.0

    @staticmethod
    def dose_rate_uSv_per_hour(isotope: Isotope, activity_bq: float, distance_m: float,
                                 attenuation_fraction: float = 1.0) -> float:
        """
        A very simplified dose rate (uSv/h) from a point source: inverse
        square of distance x decay energy x shielding attenuation.
        Coefficients are tuned for simulation balance, NOT for real
        radiation safety.
        """
        distance_m = max(distance_m, 0.05)
        flux = activity_bq / (4 * math.pi * distance_m ** 2)
        gamma_bonus = 1.6 if isotope.emits_gamma else 1.0
        raw_uSv_h = flux * isotope.decay_energy_MeV * 0.02 * gamma_bonus
        return raw_uSv_h * attenuation_fraction

    @classmethod
    def classify_dose(cls, dose_uSv_per_hour: float) -> str:
        for threshold, label in cls.DOSE_TIERS:
            if dose_uSv_per_hour < threshold:
                return label
        return cls.DOSE_TIERS[-1][1]


# ============================================================================
# CHEMISTRY / SUBSTANCE
# (from original module: mss/chemistry/substance.py)
# ============================================================================

"""
SUBSTANCE - an arbitrary substance (a mixture of elements in any proportion)
"""




@dataclass
class Substance:
    name: str
    composition: Dict[str, float]      # element symbol -> mole fraction
    temperature: float = 293.15        # K (room temperature by default)
    pressure: float = 1.0              # atm
    amount_mol: float = 1.0            # amount of substance, mol (for nuclear physics)
    isotope: Optional[str] = None      # isotope symbol from ISOTOPES, if radioactive

    def _weighted(self, attr: str) -> float:
        total = sum(self.composition.values())
        if total == 0:
            return 0.0
        return sum(
            getattr(PERIODIC_TABLE[sym], attr) * frac
            for sym, frac in self.composition.items()
        ) / total

    def matched_compound(self) -> Optional[CompoundData]:
        """Looks for a match between this composition and a known real compound."""
        key = empirical_ratio(self.composition)
        if not key:
            return None
        return KNOWN_COMPOUNDS.get(key)

    def is_known_compound(self) -> bool:
        return self.matched_compound() is not None

    def data_source(self) -> str:
        """Transparency: real data or a model estimate?"""
        return "real data" if self.is_known_compound() else "estimate (averaging model)"

    def _property(self, attr: str) -> float:
        """
        If the composition matches a known substance, use its real
        property (the anchor). Otherwise fall back to a weighted average
        over the elements, flagged as an estimate (see data_source()).
        """
        compound = self.matched_compound()
        if compound is not None:
            return getattr(compound, attr)
        return self._weighted(attr)

    @property
    def melting_point(self) -> float:
        return self._property("melting_point")

    @property
    def boiling_point(self) -> float:
        return self._property("boiling_point")

    @property
    def density(self) -> float:
        return self._property("density")

    @property
    def conductivity(self) -> float:
        return self._property("conductivity")

    @property
    def flammability(self) -> float:
        return self._property("flammability")

    @property
    def reactivity(self) -> float:
        return self._property("reactivity")

    def state(self) -> State:
        if self.temperature < self.melting_point:
            return State.SOLID
        if self.temperature < self.boiling_point:
            return State.LIQUID
        if self.temperature < self.boiling_point * 5:
            return State.GAS
        return State.PLASMA

    def formula(self) -> str:
        total = sum(self.composition.values())
        parts = []
        for sym, frac in sorted(self.composition.items(), key=lambda x: -x[1]):
            pct = round(frac / total * 100)
            parts.append(f"{sym}{pct}%")
        return " ".join(parts)

    def ph_estimate(self) -> Optional[float]:
        """
        A rough acidity/alkalinity estimate for substances containing
        hydrogen and/or oxygen. This is a heuristic (not a real
        dissociation calculation): metals with OH groups (bases) push it
        toward alkaline, high reactivity pushes it toward acidic. Returns
        None if the concept of pH doesn't apply (no H or O present).
        """
        if "H" not in self.composition and "O" not in self.composition:
            return None
        metal_symbols = {"Na", "K", "Li", "Ca", "Mg"}
        has_metal = any(s in self.composition for s in metal_symbols)
        base_ph = 10.5 if has_metal else 7.0 - self.reactivity * 6.0
        return max(0.0, min(14.0, base_ph))

    # --- Nuclear physics: isotopic composition and radioactivity --------

    def set_isotope(self, symbol: str, amount_mol: Optional[float] = None) -> "Substance":
        """Marks the substance as (predominantly) made of the given isotope."""
        if symbol not in ISOTOPES:
            raise ValueError(f"Unknown isotope '{symbol}'. Available: {', '.join(sorted(ISOTOPES))}")
        self.isotope = symbol
        if amount_mol is not None:
            self.amount_mol = amount_mol
        return self

    def is_radioactive(self) -> bool:
        if not self.isotope:
            return False
        iso = ISOTOPES.get(self.isotope)
        return iso is not None and iso.decay_mode != "stable"

    def activity_bq(self) -> float:
        """The substance's activity in becquerels (decays per second)."""
        if not self.is_radioactive():
            return 0.0
        iso = ISOTOPES[self.isotope]
        n_atoms = self.amount_mol * AVOGADRO
        return DecayEngine.activity(iso, n_atoms)

    def decay_step(self, elapsed_s: float) -> None:
        """
        Advances the decay of this isotope in time: how much of the
        substance (in moles) remains after elapsed_s. Daughter products
        are not tracked here - for a full chain see DecayEngine.simulate_chain.
        """
        if not self.is_radioactive():
            return
        iso = ISOTOPES[self.isotope]
        self.amount_mol *= DecayEngine.remaining_fraction(iso, elapsed_s)

    def summary(self) -> str:
        compound = self.matched_compound()
        recognized = f"  Recognized as: {compound.name}\n" if compound else ""
        approx_mark = "~" if compound is None else "="
        ph = self.ph_estimate()
        ph_line = f"  pH~{ph:.1f}\n" if ph is not None else ""
        radiation_line = ""
        if self.isotope:
            iso = ISOTOPES.get(self.isotope)
            if iso is not None:
                activity = self.activity_bq()
                radiation_line = (
                    f"  [RAD] Isotope: {iso.symbol}  Decay mode: {iso.decay_mode}  "
                    f"T1/2={format_half_life(iso.half_life_s)}\n"
                    f"  Amount: {self.amount_mol:.6g} mol  "
                    f"Activity~{activity:.3e} Bq ({activity/3.7e10:.3e} Ci)\n"
                )
        return (
            f"{self.name} [{self.formula()}]\n"
            f"{recognized}"
            f"  Data source: {self.data_source()}\n"
            f"  Temperature: {self.temperature:.1f} K "
            f"({self.temperature - 273.15:.1f} C) - {self.state().value}\n"
            f"  Melting pt{approx_mark}{self.melting_point:.1f}K  "
            f"Boiling pt{approx_mark}{self.boiling_point:.1f}K\n"
            f"  Density{approx_mark}{self.density:.2f} g/cm3  "
            f"Conductivity={self.conductivity:.2f}  "
            f"Flammability={self.flammability:.2f}  "
            f"Reactivity={self.reactivity:.2f}\n"
            f"{ph_line}"
            f"{radiation_line}".rstrip()
        )


# ============================================================================
# PHYSICS / MECHANICS & ELECTRICITY
# (from original module: mss/physics/mechanics.py)
# ============================================================================

"""
PHYSICS ENGINE - heat transfer, state transitions, and basic
mechanics/electricity.
"""





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


# ============================================================================
# CHEMISTRY / CHEMISTRY ENGINE
# (from original module: mss/chemistry/engine.py)
# ============================================================================

"""
CHEMISTRY ENGINE
"""




class ChemistryEngine:
    """
    Mixes substances together. A reaction occurs if the average
    reactivity of the components is high enough - then energy is
    released (heat) and a "reaction product" is produced. This is not a
    lookup table of reactions, it's a formula.
    """

    REACTION_THRESHOLD = 0.55

    @classmethod
    def mix(cls, a: Substance, b: Substance) -> Tuple[Substance, float, bool]:
        combined: Dict[str, float] = {}
        for sym, frac in a.composition.items():
            combined[sym] = combined.get(sym, 0.0) + frac
        for sym, frac in b.composition.items():
            combined[sym] = combined.get(sym, 0.0) + frac

        avg_reactivity = (a.reactivity + b.reactivity) / 2
        # a bigger electronegativity gap raises the chance of a vigorous reaction
        electroneg_gap = abs(
            sum(PERIODIC_TABLE[s].electronegativity * f for s, f in a.composition.items()) / sum(a.composition.values())
            - sum(PERIODIC_TABLE[s].electronegativity * f for s, f in b.composition.items()) / sum(b.composition.values())
        )
        reaction_score = avg_reactivity * 0.7 + min(electroneg_gap / 3, 1.0) * 0.3

        avg_temp = (a.temperature + b.temperature) / 2
        result = Substance(f"{a.name} + {b.name}", combined, temperature=avg_temp)

        reacted = reaction_score > cls.REACTION_THRESHOLD
        energy_released = 0.0
        if reacted:
            energy_released = reaction_score * 800  # nominal joules
            result.temperature += energy_released / 40  # nominal heating
            result.name = f"Reaction product ({a.name}+{b.name})"

        return result, energy_released, reacted


# ============================================================================
# BIOLOGY / GENOME
# (from original module: mss/biology/genome.py)
# ============================================================================

"""
BIOLOGY: CELLS - Genome
"""




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


# ============================================================================
# BIOLOGY / CELL
# (from original module: mss/biology/cell.py)
# ============================================================================

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


# ============================================================================
# BIOLOGY / ENVIRONMENT
# (from original module: mss/biology/environment.py)
# ============================================================================

"""
EVOLUTION AND ENVIRONMENT - Environment

An "environment" is a set of conditions a cell population lives in. The
player can change these conditions DIRECTLY (artificial selection - the
player decides where to push evolution), or turn on auto_dynamics, in
which some conditions change ON THEIR OWN - not randomly, but by the
same deterministic rules as in reality:

  - real substances placed into the environment (add_substance) set the
    environment's pH, toxicity, and radiation background from their real
    physical/chemical properties (Substance.ph_estimate(), reactivity),
    and, if the substance has an assigned isotope, from the real law of
    radioactive decay (see mss.physics.radiation) - the background from
    such a source decays on its own over time rather than staying
    forever;
  - with auto-dynamics on, temperature and light level follow a daily
    and seasonal cycle (an ordinary sine wave over the universe's clock -
    like a planet's rotation and axial tilt, not randomness).
"""





class Environment:
    def __init__(
        self,
        name: str,
        temperature: float = 293.15,
        ph: float = 7.0,
        oxygen_level: float = 0.21,
        salinity: float = 0.0,
        light_level: float = 1.0,
        pressure_atm: float = 1.0,
        nutrient_density: float = 1.0,
        toxicity: float = 0.0,
        radiation_background_uSv_h: float = 0.1,
        auto_dynamics: bool = False,
        day_length_s: float = 86400.0,
        year_length_s: float = 365.25 * 86400.0,
    ):
        self.name = name
        self.temperature = temperature
        self.ph = ph
        self.oxygen_level = oxygen_level
        self.salinity = salinity
        self.light_level = light_level
        self.pressure_atm = pressure_atm
        self.nutrient_density = nutrient_density
        self.toxicity = toxicity
        self.radiation_background_uSv_h = radiation_background_uSv_h
        self.auto_dynamics = auto_dynamics
        self.day_length_s = day_length_s
        self.year_length_s = year_length_s
        self.substances: Dict[str, Substance] = {}
        self.elapsed_s: float = 0.0
        self._base_temperature = temperature  # baseline the day/season cycle oscillates around

    def add_substance(self, substance: Substance) -> None:
        """Places a REAL substance into the environment; conditions are recomputed from its real properties."""
        self.substances[substance.name] = substance
        self._recompute_from_substances()

    def remove_substance(self, name: str) -> Optional[Substance]:
        s = self.substances.pop(name, None)
        self._recompute_from_substances()
        return s

    def _recompute_from_substances(self) -> None:
        """pH, toxicity, nutrient density, and radiation background - from the real chemistry/physics of the substances present."""
        if not self.substances:
            return
        subs = list(self.substances.values())
        # pH doesn't apply to every substance (see Substance.ph_estimate) -
        # only substances where it's defined are considered; if none
        # qualify, pH is left untouched
        ph_values = [p for p in (s.ph_estimate() for s in subs) if p is not None]
        if ph_values:
            self.ph = sum(ph_values) / len(ph_values)
        self.toxicity = min(1.0, sum(s.reactivity for s in subs) / len(subs))
        # organic substances (contain both C and H) act as a food source
        organic_bonus = sum(0.3 for s in subs if "C" in s.composition and "H" in s.composition)
        self.nutrient_density = max(0.05, 1.0 + organic_bonus - self.toxicity * 0.5)
        radiation = 0.1  # ordinary natural background, nominal uSv/h
        for s in subs:
            if s.isotope and s.amount_mol > 0:
                iso = ISOTOPES.get(s.isotope)
                if iso is not None:
                    activity = DecayEngine.activity(iso, s.amount_mol * AVOGADRO)
                    radiation += RadiationEngine.dose_rate_uSv_per_hour(iso, activity, distance_m=1.0)
        self.radiation_background_uSv_h = radiation

    def apply_natural_dynamics(self, dt_seconds: float, universe: Optional["Universe"] = None) -> None:
        """
        Advances "natural" changes to the environment over dt_seconds:
          1) environment substances with an assigned isotope decay FOR
             REAL (the same Substance.decay_step used everywhere else in
             the simulation), and the radiation background, pH, and
             toxicity are recomputed;
          2) if auto_dynamics is on, temperature and light level follow a
             deterministic daily + seasonal cycle.
        Nothing here is chosen randomly - that's what sets "natural"
        changes apart from arbitrary randomness.
        """
        self.elapsed_s += dt_seconds
        decayed = False
        for s in self.substances.values():
            if s.isotope and s.amount_mol > 0:
                s.decay_step(dt_seconds)
                decayed = True
        if decayed:
            self._recompute_from_substances()

        if self.auto_dynamics:
            t = universe.elapsed_time_s if universe is not None else self.elapsed_s
            day_phase = (t % self.day_length_s) / self.day_length_s
            self.light_level = max(0.0, math.sin(day_phase * 2 * math.pi))
            year_phase = (t % self.year_length_s) / self.year_length_s
            seasonal_amplitude, daily_amplitude = 8.0, 3.0  # K
            self.temperature = (
                self._base_temperature
                + seasonal_amplitude * math.sin(year_phase * 2 * math.pi)
                + daily_amplitude * math.sin(day_phase * 2 * math.pi)
            )

    def set_condition(self, field_name: str, value: float) -> None:
        """Direct player intervention on environment conditions (artificial selection)."""
        if not hasattr(self, field_name):
            raise ValueError(f"Unknown environment condition: {field_name}")
        setattr(self, field_name, value)
        if field_name == "temperature":
            self._base_temperature = value

    def summary(self) -> str:
        subs = ", ".join(self.substances) if self.substances else "(none)"
        return (
            f"Environment '{self.name}' (t={format_duration(self.elapsed_s)})\n"
            f"  Temperature: {self.temperature:.1f}K ({self.temperature - 273.15:.1f}C)  "
            f"pH: {self.ph:.2f}  Oxygen: {self.oxygen_level:.2f}\n"
            f"  Salinity: {self.salinity:.2f}  Light level: {self.light_level:.2f}  "
            f"Pressure: {self.pressure_atm:.2f} atm\n"
            f"  Nutrient density: {self.nutrient_density:.2f}  Toxicity: {self.toxicity:.2f}  "
            f"Radiation background: {self.radiation_background_uSv_h:.4f} uSv/h\n"
            f"  Auto-dynamics (day/night/seasons): {'on' if self.auto_dynamics else 'off'}\n"
            f"  Substances present: {subs}"
        )


# ============================================================================
# BIOLOGY / POPULATION
# (from original module: mss/biology/population.py)
# ============================================================================

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


# ============================================================================
# ENGINEERING / INVENTION ENGINE
# (from original module: mss/engineering/invention.py)
# ============================================================================

"""
INVENTION ENGINE - free-form invention through physical properties

Key idea: there is NO fixed list of recipes. Instead, every substance is
analyzed for its physical properties and gets a set of "engineering
functions" (conductor, energy source, etc.). A combination of functions
from several objects can add up to a recognizable technology.

This gives real freedom: the player can take ANY elements in ANY
proportions - the result is computed from formulas, not looked up in a
database of "if you have copper and zinc, that's brass".
"""





class InventionEngine:
    """
    See module docstring. The function set is deliberately broad, and
    more importantly demonstrates the logic for adding your own functions
    and rules: each function is just a predicate over physical
    properties, with no dependency on specific substance names.
    """

    FUNCTIONS = {
        "Electrical Conductor": lambda p: p["conductivity"] > 0.6,
        "Semiconductor": lambda p: 0.25 <= p["conductivity"] <= 0.6 and p["melting_point"] > 800,
        "Insulator": lambda p: p["conductivity"] < 0.15,
        "Energy Source": lambda p: p["reactivity"] > 0.6 and p["flammability"] > 0.4,
        "Explosive": lambda p: p["reactivity"] > 0.75 and p["flammability"] > 0.6 and p["density"] < 3,
        "Structural Material": lambda p: p["density"] > 2 and p["melting_point"] > 500,
        "Refractory Material": lambda p: p["melting_point"] > 1800 and p["flammability"] < 0.1,
        "Catalyst": lambda p: 0.35 < p["reactivity"] < 0.75,
        "Coolant": lambda p: p["boiling_point"] < 250,
        "Lubricant": lambda p: p["melting_point"] < 400 and p["reactivity"] < 0.3 and p["density"] < 3,
        "Solvent": lambda p: p["boiling_point"] < 400 and p["conductivity"] < 0.05 and p["flammability"] < 0.2,
        "Radioactive Source": lambda p: p["reactivity"] > 0.8 and p["density"] > 15,
        "Battery Electrolyte": lambda p: 0.1 <= p["conductivity"] <= 0.4 and p["reactivity"] > 0.3,
        "Dense Shielding Material": lambda p: p["density"] > 9.5,
        # --- ELECTRONICS: same principles (a numeric predicate over
        # properties, no substance names) - but now these functions serve
        # not just individual devices but BUILDING BLOCKS of a board/chip.
        "Piezoelectric Crystal (Resonator)": lambda p: p["conductivity"] < 0.1 and p["melting_point"] > 1500 and 2.0 <= p["density"] <= 3.5,
        "Solder Contact": lambda p: 0.4 <= p["conductivity"] <= 0.99 and p["melting_point"] < 1300,
        "Power Conductor": lambda p: p["conductivity"] > 0.8 and p["density"] > 7,
        # The functions below key off the substance's REAL isotopic
        # composition (Substance.isotope), not chemical properties -
        # see analyze() below.
        "Alpha Emitter": lambda p: p.get("decay_mode") == "alpha" and p.get("activity_bq", 0) > 0,
        "Beta Emitter": lambda p: p.get("decay_mode") in ("beta-", "beta+") and p.get("activity_bq", 0) > 0,
        "Gamma Source": lambda p: p.get("emits_gamma", False) and p.get("activity_bq", 0) > 0,
        "Ionizing Radiation Source": lambda p: p.get("activity_bq", 0) > 0,
    }

    # Combinations of functions (2 or more) -> which technology category
    # this resembles. Not the only correct list: you can (and should)
    # extend your own rules - this is simply a key frozenset(...) ->
    # technology name.
    TECH_RULES = {
        frozenset({"Electrical Conductor", "Energy Source"}): "Battery / Electrical Circuit",
        frozenset({"Electrical Conductor", "Structural Material"}): "Electronic Device Frame",
        frozenset({"Structural Material", "Coolant"}): "Cooling System",
        frozenset({"Catalyst", "Energy Source"}): "Engine / Reactor (Prototype)",
        frozenset({"Insulator", "Electrical Conductor"}): "Insulated Cable",
        frozenset({"Radioactive Source", "Structural Material"}): "Nuclear Reactor (Prototype)",
        frozenset({"Semiconductor", "Electrical Conductor"}): "Transistor / Diode (Electronics Prototype)",
        frozenset({"Semiconductor", "Insulator", "Electrical Conductor"}): "Microchip (Prototype)",
        frozenset({"Explosive", "Structural Material"}): "Ammunition / Detonating Device",
        frozenset({"Lubricant", "Structural Material"}): "Mechanism With Moving Parts",
        frozenset({"Solvent", "Catalyst"}): "Chemical Synthesis Reactor",
        frozenset({"Battery Electrolyte", "Electrical Conductor"}): "Rechargeable Battery",
        frozenset({"Refractory Material", "Energy Source"}): "Rocket Engine (Prototype)",
        frozenset({"Refractory Material", "Electrical Conductor"}): "Heating Element",
        frozenset({"Semiconductor", "Insulator"}): "Dosimeter (Geiger Counter)",
        frozenset({"Dense Shielding Material", "Structural Material"}): "Radiation Shield (Protection)",
        frozenset({"Alpha Emitter", "Structural Material"}): "Ionization Smoke Detector (Prototype)",
        frozenset({"Gamma Source", "Structural Material"}): "Radiation Sterilizer (Prototype)",
        frozenset({"Ionizing Radiation Source", "Electrical Conductor"}): "Radioisotope Power Source (Prototype)",
        # --- ELECTRONICS: a tree from board to processor. Each line is a
        # NEW combination of functions that doesn't overlap any other
        # (otherwise two different devices would be unlocked by the same
        # combination of materials, erasing the distinction between them).
        # The build order (what depends on what) is set by PREREQUISITES
        # in devices.py.
        frozenset({"Insulator", "Electrical Conductor", "Structural Material"}): "Printed Circuit Board (PCB, Blank)",
        frozenset({"Solder Contact", "Insulator"}): "Contact Pads (Blank)",
        frozenset({"Power Conductor", "Structural Material"}): "Power Bus (High-current)",
        frozenset({"Solder Contact", "Electrical Conductor"}): "I/O Port (Connector)",
        frozenset({"Piezoelectric Crystal (Resonator)", "Electrical Conductor"}): "Clock Generator (Prototype)",
        frozenset({"Semiconductor", "Electrical Conductor", "Structural Material"}): "Register (Memory Cell)",
        frozenset({"Semiconductor", "Electrical Conductor", "Refractory Material"}): "Arithmetic Logic Unit (ALU, Prototype)",
        frozenset({"Semiconductor", "Insulator", "Structural Material"}): "Program Counter (Prototype)",
        frozenset({"Power Conductor", "Insulator"}): "Data & Address Bus (Prototype)",
        frozenset({"Semiconductor", "Refractory Material", "Insulator"}): "Processor (Integrated, Prototype)",
    }

    @classmethod
    def analyze(cls, obj: "Substance") -> set:
        props = dict(
            conductivity=obj.conductivity,
            reactivity=obj.reactivity,
            flammability=obj.flammability,
            density=obj.density,
            melting_point=obj.melting_point,
            boiling_point=obj.boiling_point,
        )
        if obj.isotope:
            iso = ISOTOPES.get(obj.isotope)
            if iso is not None:
                props["decay_mode"] = iso.decay_mode
                props["emits_gamma"] = iso.emits_gamma
                props["activity_bq"] = obj.activity_bq()
        return {name for name, rule in cls.FUNCTIONS.items() if rule(props)}

    @classmethod
    def combine(cls, objects: List["Substance"]) -> Tuple[set, List[str]]:
        all_functions = set()
        for o in objects:
            all_functions |= cls.analyze(o)

        discovered = []
        for size in range(2, len(all_functions) + 1):
            for combo in itertools.combinations(all_functions, size):
                key = frozenset(combo)
                if key in cls.TECH_RULES and cls.TECH_RULES[key] not in discovered:
                    discovered.append(cls.TECH_RULES[key])

        return all_functions, discovered


# ============================================================================
# ENGINEERING / DEVICES & WORKSHOP
# (from original module: mss/engineering/devices.py)
# ============================================================================

"""
WORKSHOP & DEVICES - from "discoveries" to real technologies

InventionEngine only answers "what is even POSSIBLE to make from these
materials" - that's a DISCOVERY. But a discovery isn't a thing you can
use. This module adds a second layer:

    DISCOVERY   (which technology is possible in principle)
        |
    BUILD       (Device - a real object with stats computed from the
                 exact properties of the substances used)
        |
    USE         (device.use(...) really changes the world: cools a
                 substance, releases energy, wears out with use)

Plus a dependency tree (PREREQUISITES): some technologies require the
player to have already built simpler devices first. That's what makes
this engineering, not just combination-hunting.
"""





def _agg(objects: List["Substance"], attr: str) -> float:
    """Average value of a property across a list of substances."""
    if not objects:
        return 0.0
    return sum(getattr(o, attr) for o in objects) / len(objects)


def _minv(objects: List["Substance"], attr: str) -> float:
    """Minimum of a property across the components - the 'weakest link' sets the limit."""
    return min((getattr(o, attr) for o in objects), default=0.0)


def _maxv(objects: List["Substance"], attr: str) -> float:
    """Maximum of a property across the components - the 'best component' sets the ceiling."""
    return max((getattr(o, attr) for o in objects), default=0.0)


def _default_stats(objects: List["Substance"]) -> Dict[str, float]:
    return {
        "nominal_power": round(_agg(objects, "reactivity") * 100, 1),
        "reliability_pct": round((1 - _agg(objects, "reactivity")) * 100, 1),
    }


# The stat formula for each known technology category. Each formula is a
# function of the list of substances used (their REAL computed
# properties), so the same device built from different materials always
# gets different, honestly computed numbers.
STAT_FORMULAS = {
    "Battery / Electrical Circuit": lambda o: {
        "capacity_Wh": round(_agg(o, "reactivity") * _agg(o, "flammability") * _agg(o, "density") * 50, 1),
        "voltage_V": round(_agg(o, "conductivity") * 12, 2),
    },
    "Rechargeable Battery": lambda o: {
        "capacity_Wh": round(_agg(o, "conductivity") * _agg(o, "reactivity") * 80, 1),
        "voltage_V": round(_agg(o, "conductivity") * 10, 2),
        "charge_cycles": round(200 + _agg(o, "conductivity") * 800),
    },
    "Electronic Device Frame": lambda o: {
        "max_load_kg": round(_agg(o, "density") * 50, 1),
        # the weakest (lowest-melting) component sets the limit for the whole structure
        "max_operating_temp_K": round(_minv(o, "melting_point"), 1),
    },
    "Cooling System": lambda o: {
        # the best (lowest-boiling) component is what acts as the coolant
        "cooling_power_W": round(min(20000, 20000 / max(_minv(o, "boiling_point"), 1)), 1),
        "min_achievable_temp_K": round(_minv(o, "boiling_point"), 1),
    },
    "Heating Element": lambda o: {
        # the heating filament should be as refractory as possible
        "heating_power_W": round(_maxv(o, "melting_point") * _agg(o, "conductivity") / 2, 1),
        "max_temp_K": round(_maxv(o, "melting_point"), 1),
    },
    "Insulated Cable": lambda o: {
        # insulation is set by the best insulator (lowest conductivity),
        # and current capacity by the best conductor (highest conductivity)
        "max_voltage_V": round((1 - min(_minv(o, "conductivity"), 0.99)) * 1000, 1),
        "max_current_A": round(_maxv(o, "conductivity") * 100, 1),
    },
    "Transistor / Diode (Electronics Prototype)": lambda o: {
        "switching_speed_MHz": round(_maxv(o, "conductivity") * 100, 1),
        "max_temp_K": round(_minv(o, "melting_point"), 1),
    },
    "Microchip (Prototype)": lambda o: {
        "compute_power_MIPS": round(_agg(o, "conductivity") * _agg(o, "density") * 10, 1),
        "power_consumption_W": round((1 - _agg(o, "conductivity")) * 5 + 1, 2),
    },
    "Engine / Reactor (Prototype)": lambda o: {
        "power_kW": round(_agg(o, "reactivity") * _agg(o, "flammability") * 50, 1),
        "efficiency_pct": round((1 - _agg(o, "reactivity")) * 100, 1),
    },
    "Nuclear Reactor (Prototype)": lambda o: {
        "energy_MW": round(_agg(o, "reactivity") * _agg(o, "density") * 2, 2),
        "nominal_safety_period_years": round(10 / (_agg(o, "reactivity") + 0.01), 1),
    },
    "Ammunition / Detonating Device": lambda o: {
        "explosion_power_kJ": round(_agg(o, "reactivity") * _agg(o, "flammability") * 200, 1),
        "nominal_radius_m": round(_agg(o, "reactivity") * _agg(o, "flammability") * 20, 1),
    },
    "Mechanism With Moving Parts": lambda o: {
        "efficiency_pct": round((1 - _agg(o, "reactivity")) * 90 + 10, 1),
        "max_load_kg": round(_agg(o, "density") * 30, 1),
    },
    "Chemical Synthesis Reactor": lambda o: {
        "throughput_mol_per_h": round(_agg(o, "reactivity") * 50, 1),
        "product_purity_pct": round((1 - _agg(o, "reactivity")) * 50 + 50, 1),
    },
    "Rocket Engine (Prototype)": lambda o: {
        "thrust_kN": round(_agg(o, "reactivity") * _agg(o, "melting_point") / 50, 1),
        "specific_impulse_s": round(_agg(o, "melting_point") / 10, 1),
    },
    "Dosimeter (Geiger Counter)": lambda o: {
        "sensitivity_counts_per_Bq": round(_agg(o, "conductivity") * 50 + 5, 1),
        "max_measurable_activity_Bq": round(1e9 * (_agg(o, "conductivity") + 0.1), 0),
    },
    "Radiation Shield (Protection)": lambda o: {
        "thickness_cm": round(max(1.0, _agg(o, "density") / 2), 1),
        "density_g_cm3": round(_agg(o, "density"), 2),
    },
    "Ionization Smoke Detector (Prototype)": lambda o: {
        "relative_sensitivity": round(_agg(o, "conductivity") * 10 + 1, 1),
        "service_life_years": 15.0,  # nominal, by analogy with real Am-241 detectors
    },
    "Radiation Sterilizer (Prototype)": lambda o: {
        "treatment_dose_kGy": round(_agg(o, "density") * 2, 1),
        "throughput_kg_per_h": round(_agg(o, "density") * 5, 1),
    },
    "Radioisotope Power Source (Prototype)": lambda o: {
        "conversion_efficiency_pct": round(_agg(o, "conductivity") * 8 + 2, 1),  # thermoelectrics are low-power - kept honest, not inflated
    },
    # --- ELECTRONICS: the higher up the tree a block is (board -> bus ->
    # processor), the more its stats rely on the stats of its COMPONENTS
    # rather than the raw substances - just like real engineering, where a
    # processor is described in terms of registers/ALU/buses, not directly
    # in terms of silicon and copper.
    "Printed Circuit Board (PCB, Blank)": lambda o: {
        "layers": round(1 + _agg(o, "density") / 5),
        "max_trace_density_per_cm": round(_maxv(o, "conductivity") * 20, 1),
        "dielectric_strength_kV_per_mm": round((1 - _minv(o, "conductivity")) * 40, 1),
    },
    "Contact Pads (Blank)": lambda o: {
        "pad_count": round(_maxv(o, "conductivity") * 200),
        "max_current_per_pad_A": round(_maxv(o, "conductivity") * 5, 2),
    },
    "Power Bus (High-current)": lambda o: {
        "max_current_A": round(_maxv(o, "conductivity") * _agg(o, "density") * 10, 1),
        "voltage_drop_V_per_m": round((1 - _maxv(o, "conductivity")) * 2, 3),
    },
    "I/O Port (Connector)": lambda o: {
        "line_count": round(4 + _agg(o, "conductivity") * 28),
        "max_frequency_MHz": round(_agg(o, "conductivity") * 50, 1),
    },
    "Clock Generator (Prototype)": lambda o: {
        # the more stable (refractory/pure) the resonator, the higher the frequency and lower the drift
        "frequency_MHz": round(_minv(o, "melting_point") / 40, 2),
        "stability_ppm": round(max(1.0, 100 - _agg(o, "density") * 5), 1),
    },
    "Register (Memory Cell)": lambda o: {
        "bit_width": round(4 + _agg(o, "conductivity") * 28),
        "access_time_ns": round(max(0.5, 50 * (1 - _agg(o, "conductivity"))), 2),
    },
    "Arithmetic Logic Unit (ALU, Prototype)": lambda o: {
        "bit_width": round(4 + _agg(o, "conductivity") * 28),
        "ops_per_cycle": round(1 + _agg(o, "conductivity") * 3),
    },
    "Program Counter (Prototype)": lambda o: {
        "bit_width": min(20, round(8 + _agg(o, "conductivity") * 24)),
    },
    "Data & Address Bus (Prototype)": lambda o: {
        "data_bus_width_bit": round(4 + _agg(o, "conductivity") * 28),
        "address_bus_width_bit": min(24, round(8 + _maxv(o, "conductivity") * 16)),
        "throughput_MBps": round(_agg(o, "conductivity") * _minv(o, "melting_point") / 20, 1),
    },
    "Processor (Integrated, Prototype)": lambda o: {
        "clock_frequency_MHz": round(_agg(o, "conductivity") * _agg(o, "density") * 15, 1),
        "bit_width": round(4 + _agg(o, "conductivity") * 28),
        "heat_output_W": round(_agg(o, "density") * _agg(o, "conductivity") * 3, 1),
    },
}


# Dependency tree: to build the technology on the left, you must already
# have a BUILT (not just discovered) device of every category on the
# right. Categories with no entry here are considered "base" (tier 1) -
# buildable immediately after discovery.
PREREQUISITES: Dict[str, List[str]] = {
    "Transistor / Diode (Electronics Prototype)": ["Insulated Cable"],
    "Microchip (Prototype)": ["Transistor / Diode (Electronics Prototype)"],
    "Rechargeable Battery": ["Battery / Electrical Circuit"],
    "Engine / Reactor (Prototype)": ["Mechanism With Moving Parts"],
    "Rocket Engine (Prototype)": ["Heating Element", "Battery / Electrical Circuit"],
    "Nuclear Reactor (Prototype)": ["Rechargeable Battery", "Cooling System"],
    "Dosimeter (Geiger Counter)": ["Transistor / Diode (Electronics Prototype)"],
    "Radiation Sterilizer (Prototype)": ["Radiation Shield (Protection)"],
    "Radioisotope Power Source (Prototype)": ["Radiation Shield (Protection)"],
    # --- ELECTRONICS: the board is the foundation (tier 1). Pads, the
    # power bus, the port, and the clock generator depend on it (tier 2).
    # The register and the ALU each require an already-BUILT microchip (in
    # reality, that's literally a grid of transistors). The program
    # counter needs a register (a register with auto-increment is exactly
    # what it is) AND a clock generator (no clock, nothing to count). The
    # data/address bus connects the register and the port. The processor
    # sits at the top: it requires everything at once.
    "Contact Pads (Blank)": ["Printed Circuit Board (PCB, Blank)"],
    "Power Bus (High-current)": ["Printed Circuit Board (PCB, Blank)"],
    "I/O Port (Connector)": ["Contact Pads (Blank)"],
    "Clock Generator (Prototype)": ["Printed Circuit Board (PCB, Blank)"],
    "Register (Memory Cell)": ["Microchip (Prototype)"],
    "Arithmetic Logic Unit (ALU, Prototype)": ["Microchip (Prototype)"],
    "Program Counter (Prototype)": ["Register (Memory Cell)", "Clock Generator (Prototype)"],
    "Data & Address Bus (Prototype)": ["Register (Memory Cell)", "I/O Port (Connector)"],
    "Processor (Integrated, Prototype)": [
        "Arithmetic Logic Unit (ALU, Prototype)",
        "Register (Memory Cell)",
        "Program Counter (Prototype)",
        "Data & Address Bus (Prototype)",
        "Clock Generator (Prototype)",
    ],
}


@dataclass
class Device:
    """
    A real, built instance of a technology - unlike a "discovery" (which
    only says "this is theoretically possible"). A device has exact
    stats, a state (wear/charge), and can really do something via .use().
    """
    name: str
    category: str
    stats: Dict[str, float]
    components: List[str]
    tier: int
    state: Dict[str, float] = field(default_factory=dict)

    def use(self, target=None) -> str:
        handler = DEVICE_EFFECTS.get(self.category, _use_generic)
        return handler(self, target)

    def summary(self) -> str:
        stats_str = ", ".join(f"{k}={v:.2f}" for k, v in self.stats.items())
        condition = self.state.get("condition", 1.0) * 100
        return (
            f"{self.name} [{self.category}] - tier {self.tier}\n"
            f"  Components: {', '.join(self.components)}\n"
            f"  Stats: {stats_str}\n"
            f"  Condition: {condition:.0f}%"
        )


# --- Device behavior on use (device.use(...)) ------------------------

def _use_cooling(device: Device, target: Optional["Substance"]) -> str:
    if target is None:
        return f"{device.name}: needs a target (substance) to cool."
    power = device.stats.get("cooling_power_W", 500) * device.state.get("condition", 1.0)
    delta = min(power / 100, max(0.0, target.temperature - 0.1))
    target.temperature -= delta
    device.state["condition"] = max(0.0, device.state.get("condition", 1.0) - 0.05)
    return (f"{device.name} cools '{target.name}' by {delta:.1f}K "
            f"(now {target.temperature:.1f}K). Device wear: "
            f"{(1 - device.state['condition']) * 100:.0f}%")


def _use_heating(device: Device, target: Optional["Substance"]) -> str:
    if target is None:
        return f"{device.name}: needs a target (substance) to heat."
    power = device.stats.get("heating_power_W", 100) * device.state.get("condition", 1.0)
    delta = power / 50
    target.temperature += delta
    device.state["condition"] = max(0.0, device.state.get("condition", 1.0) - 0.05)
    return (f"{device.name} heats '{target.name}' by {delta:.1f}K "
            f"(now {target.temperature:.1f}K). Device wear: "
            f"{(1 - device.state['condition']) * 100:.0f}%")


def _use_battery(device: Device, target=None) -> str:
    charge = device.state.get("charge_wh", device.stats.get("capacity_Wh", 0.0))
    used = min(charge, 5.0)
    device.state["charge_wh"] = charge - used
    device.state["condition"] = max(0.0, device.state.get("condition", 1.0) - 0.02)
    return (f"{device.name} delivers {used:.1f} Wh of energy. "
            f"Charge remaining: {device.state['charge_wh']:.1f} Wh.")


def _use_generic(device: Device, target=None) -> str:
    device.state["condition"] = max(0.0, device.state.get("condition", 1.0) - 0.03)
    stats_str = ", ".join(f"{k}={v:.2f}" for k, v in device.stats.items())
    return (f"{device.name} is used. Stats: {stats_str}. "
            f"Condition: {device.state['condition'] * 100:.0f}%")


def _use_dosimeter(device: Device, target: Optional["Substance"]) -> str:
    if target is None:
        return f"{device.name}: needs a target (substance) to measure."
    activity = target.activity_bq()
    device.state["condition"] = max(0.0, device.state.get("condition", 1.0) - 0.01)
    if activity <= 0 or not target.isotope:
        return f"{device.name}: no radioactivity detected in '{target.name}' (0 Bq)."
    iso = ISOTOPES[target.isotope]
    dose = RadiationEngine.dose_rate_uSv_per_hour(iso, activity, distance_m=1.0)
    verdict = RadiationEngine.classify_dose(dose)
    return (f"{device.name} measures '{target.name}' (isotope {iso.symbol}, {iso.decay_mode}): "
            f"activity={activity:.3e} Bq, dose at 1m~{dose:.2f} uSv/h - {verdict}.\n"
            f"  [Simulation estimate, not for real radiation-safety use.]")


class _ShieldProxy:
    """A lightweight stand-in that has the density attribute RadiationEngine.attenuation needs."""
    def __init__(self, density: float):
        self.density = density


def _use_shield(device: Device, target: Optional["Substance"]) -> str:
    thickness = device.stats.get("thickness_cm", 1.0) * device.state.get("condition", 1.0)
    shield_density = device.stats.get("density_g_cm3", 5)
    shield_proxy = _ShieldProxy(shield_density)
    lines = [f"{device.name} (thickness {thickness:.1f}cm, density {shield_density:.1f} g/cm3) attenuates:"]
    for rtype, label in (("alpha", "alpha"), ("beta-", "beta"), ("gamma", "gamma")):
        remaining = RadiationEngine.attenuation(rtype, shield_proxy, thickness)
        lines.append(f"  {label} radiation: transmits {remaining*100:.1f}%, blocks {(1-remaining)*100:.1f}%")
    device.state["condition"] = max(0.0, device.state.get("condition", 1.0) - 0.01)
    if target is not None and target.isotope:
        iso = ISOTOPES[target.isotope]
        rtype = "alpha" if iso.decay_mode == "alpha" else ("gamma" if iso.emits_gamma else "beta-")
        atten = RadiationEngine.attenuation(rtype, shield_proxy, thickness)
        dose_unshielded = RadiationEngine.dose_rate_uSv_per_hour(iso, target.activity_bq(), distance_m=1.0)
        dose_shielded = dose_unshielded * atten
        lines.append(f"  Against '{target.name}': dose at 1m reduced from {dose_unshielded:.1f} to {dose_shielded:.1f} uSv/h")
    return "\n".join(lines)


def _use_reactor(device: Device, target: Optional["Substance"]) -> str:
    """
    A real decay-driven nuclear reactor: the fuel must be a substance
    with an assigned isotope (Substance.set_isotope(...)). Power is
    computed from the REAL fuel activity (DecayEngine), and the fuel is
    physically consumed with each use.
    """
    if target is None or not target.isotope:
        return f"{device.name}: needs fuel - a substance with an assigned isotope (Substance.set_isotope(...))."
    iso = ISOTOPES.get(target.isotope)
    if iso is None or iso.decay_mode == "stable":
        return f"{device.name}: isotope '{target.isotope}' is stable, nothing to decay."
    activity = target.activity_bq()
    efficiency = device.stats.get("efficiency_pct", 30) / 100
    power_w = activity * iso.decay_energy_MeV * 1.602176634e-13 * efficiency
    consumed_mol = target.amount_mol * 0.001
    target.amount_mol = max(0.0, target.amount_mol - consumed_mol)
    device.state["condition"] = max(0.0, device.state.get("condition", 1.0) - 0.01)
    return (f"{device.name} processes fuel '{target.name}' (isotope {iso.symbol}): "
            f"activity={activity:.3e} Bq, power~{power_w:.3e} W. "
            f"Fuel remaining: {target.amount_mol:.6g} mol.")


DEVICE_EFFECTS = {
    "Cooling System": _use_cooling,
    "Heating Element": _use_heating,
    "Battery / Electrical Circuit": _use_battery,
    "Rechargeable Battery": _use_battery,
    "Dosimeter (Geiger Counter)": _use_dosimeter,
    "Radiation Shield (Protection)": _use_shield,
    "Nuclear Reactor (Prototype)": _use_reactor,
}


class Workshop:
    """
    The player's workshop: tracks which technologies have been discovered
    (known_tech) and which devices have actually been built (devices).
    Workshop is what checks the dependency tree and refuses to build a
    technology whose simpler prerequisite devices haven't been built yet.
    """

    def __init__(self):
        self.known_tech: set = set()
        self.devices: Dict[str, Device] = {}

    def discover(self, objects: List["Substance"]) -> Tuple[set, List[str], List[str]]:
        functions, tech_list = InventionEngine.combine(objects)
        newly = [t for t in tech_list if t not in self.known_tech]
        self.known_tech.update(tech_list)
        return functions, tech_list, newly

    def tier_of(self, category: str, _memo: Optional[Dict[str, int]] = None) -> int:
        _memo = _memo if _memo is not None else {}
        if category in _memo:
            return _memo[category]
        prereqs = PREREQUISITES.get(category, [])
        tier = 1 if not prereqs else 1 + max(self.tier_of(p, _memo) for p in prereqs)
        _memo[category] = tier
        return tier

    def missing_prerequisites(self, category: str) -> List[str]:
        prereqs = PREREQUISITES.get(category, [])
        built_categories = {d.category for d in self.devices.values()}
        return [p for p in prereqs if p not in built_categories]

    def buildable_now(self) -> List[str]:
        """Categories that are discovered and whose prerequisites have all been built."""
        return [t for t in self.known_tech if not self.missing_prerequisites(t)]

    @staticmethod
    def _slugify(text: str) -> str:
        """Turns an arbitrary string into a whitespace/slash-free identifier -
        needed so a device name can be used in a player program (the
        language is line-based and splits on whitespace)."""
        cleaned = text.replace("/", "").replace("(", "").replace(")", "")
        return "_".join(cleaned.split())

    def build(self, category: str, objects: List["Substance"], device_name: Optional[str] = None) -> Device:
        if category not in self.known_tech:
            raise ValueError("This technology hasn't been discovered yet - find the right combination of functions first (menu option 7).")
        missing = self.missing_prerequisites(category)
        if missing:
            raise ValueError(f"Missing built prerequisite devices: {', '.join(missing)}")

        formula = STAT_FORMULAS.get(category, _default_stats)
        stats = formula(objects)
        count = sum(1 for d in self.devices.values() if d.category == category) + 1
        name = self._slugify(device_name) if device_name else f"{self._slugify(category)}_{count}"

        device = Device(
            name=name,
            category=category,
            stats=stats,
            components=[o.name for o in objects],
            tier=self.tier_of(category),
        )
        device.state["condition"] = 1.0
        if "capacity_Wh" in stats:
            device.state["charge_wh"] = stats["capacity_Wh"]

        self.devices[name] = device
        return device


# ============================================================================
# PROGRAMMING / LANGUAGE SPEC
# (from original module: mss/programming/language.py)
# ============================================================================

"""
PROGRAMMING - the player designs their OWN language and then writes code in it

Idea: programming is engineering too, and in the spirit of the
simulation it should require BUILDING what the code will run on first
(a device of category "Microchip (Prototype)" from the Workshop), and
only then defining a language and writing a program.

Honest about scope: this is not a parser for a full derived grammar
(BNF and so on) - that wouldn't fit in one project and isn't needed for
the goal of "the player invents their own language". Instead there's a
small fixed set of CANONICAL commands (variables, arithmetic, branches,
loops, device calls) - and the player decides what WORDS these commands
are called in their language. The same program at the technical level
can look like English, like slang, or like a string of emoji - that's
what creating your own programming language means: your own vocabulary
layered on top of a shared grammar (one command per line).
"""


CANONICAL_COMMANDS: Dict[str, str] = {
    "SET": "variable = value",
    "ADD": "variable += value",
    "SUB": "variable -= value",
    "MUL": "variable *= value",
    "DIV": "variable /= value",
    "MOD": "variable %= value (remainder)",
    "PRINT": "print a variable or text",
    "READ": "variable <- substance/device.property",
    "CALL": "call a device [on a substance]  (output port)",
    "IF": "if variable OP value - start of a condition",
    "ELSE": "else",
    "ENDIF": "end of condition",
    "LOOP": "repeat N times - start of a loop",
    "ENDLOOP": "end of loop",
    "WHILE": "while variable OP value - start of a conditional loop",
    "ENDWHILE": "end of WHILE loop",
    "WAIT": "nominal tick (reserved)",
    # --- ALU operations (arithmetic logic unit): logic and shifts, not
    # just +-*/ - which is exactly what a real hardware ALU does
    "AND": "variable = a AND b (0/1)",
    "OR": "variable = a OR b (0/1)",
    "XOR": "variable = a XOR b (0/1)",
    "NOT": "variable = NOT a (0/1)",
    "SHL": "variable = a << N (shift left)",
    "SHR": "variable = a >> N (shift right)",
    # --- math functions
    "SQRT": "variable = sqrt(a)",
    "RANDOM": "variable = random integer from A to B",
    # --- addressed memory (what the data/address bus is for): memory size
    # is limited by REALLY BUILT Register/Bus devices - without them only
    # a few "default" cells are available
    "STORE": "memory[address] = value",
    "LOAD": "variable = memory[address]",
    # --- jumps and subroutines (the program counter can be moved directly) ---
    "LABEL": "a label - a jump target, does nothing on its own",
    "GOTO": "unconditional jump to a label",
    "CALLSUB": "call a subroutine at a label (save the return point)",
    "RETURN": "return from a subroutine",
}


class ProgramError(Exception):
    """A compile-time or run-time error in a player's program."""


@dataclass
class LanguageSpec:
    """
    A programming language invented by the player: a mapping from the
    engine's canonical command (e.g. "LOOP") to the word the player chose
    (e.g. "repeat" or "loopz" or "cycle!!!"). Commands left unset keep
    their canonical name by default.
    """
    name: str
    keywords: Dict[str, str]        # CANONICAL -> the player's word
    reverse: Dict[str, str] = field(init=False)

    def __post_init__(self):
        self.reverse = {token: canon for canon, token in self.keywords.items()}

    def translate_line(self, line: str) -> str:
        """Translates a line of the player's program into canonical form for the VM."""
        parts = line.split()
        if not parts:
            return line
        canon = self.reverse.get(parts[0], parts[0])
        return " ".join([canon] + parts[1:])

    def describe(self) -> str:
        lines = [f"Language '{self.name}' - command dictionary:"]
        for canon, meaning in CANONICAL_COMMANDS.items():
            token = self.keywords.get(canon, canon)
            lines.append(f"  {token:12s} -> {canon:8s} ({meaning})")
        return "\n".join(lines)


# ============================================================================
# PROGRAMMING / INTERPRETER (VM)
# (from original module: mss/programming/interpreter.py)
# ============================================================================

"""
PROGRAMMING - Interpreter

A line-based virtual machine: numeric variables, ALU arithmetic and logic
(AND/OR/XOR/NOT/shifts), conditions (IF/ELSE/ENDIF), counted loops
(LOOP/ENDLOOP) and conditional loops (WHILE/ENDWHILE), labels and jumps
(LABEL/GOTO), subroutines (CALLSUB/RETURN), addressed memory
(STORE/LOAD), calling built devices (CALL), and reading their stats and
substance properties (READ).

IMPORTANT: the amount of addressable memory is NOT an arbitrary engine
constant - it's computed from the REALLY BUILT hardware (see
_compute_memory_size). Without a built Register or Data/Address Bus,
only 16 "default" memory cells are available - programming here also
requires building what the code will run on first.
"""





class Interpreter:
    DEFAULT_MEMORY_SIZE = 16

    def __init__(self, language: LanguageSpec, workshop: "Workshop", substances: Dict[str, "Substance"]):
        self.language = language
        self.workshop = workshop
        self.substances = substances
        self.variables: Dict[str, float] = {}
        self.output: List[str] = []
        self.memory_size = self._compute_memory_size()
        self.memory: List[float] = [0.0] * self.memory_size
        self.call_stack: List[int] = []

    def _compute_memory_size(self) -> int:
        """Memory size = a function of the actually built hardware, not a constant."""
        best = self.DEFAULT_MEMORY_SIZE
        for d in self.workshop.devices.values():
            if d.category == "Register (Memory Cell)":
                bits = d.stats.get("bit_width", 8)
                best = max(best, int(bits) * 4)  # nominal: an N-bit register -> N*4 cells
            if d.category == "Data & Address Bus (Prototype)":
                addr_bits = d.stats.get("address_bus_width_bit", 8)
                best = max(best, min(2 ** int(addr_bits), 4096))  # a sane ceiling
        return best

    def _value(self, token: str) -> float:
        if token in self.variables:
            return self.variables[token]
        try:
            return float(token)
        except ValueError:
            raise ProgramError(f"Unknown variable or number: '{token}'")

    def _read_property(self, name: str, prop: str) -> float:
        if name in self.substances:
            obj = self.substances[name]
            value = getattr(obj, prop, None)
            if value is None or callable(value):
                raise ProgramError(f"Substance '{name}' has no numeric property '{prop}'")
            return float(value)
        if name in self.workshop.devices:
            device = self.workshop.devices[name]
            if prop in device.stats:
                return float(device.stats[prop])
            if prop in device.state:
                return float(device.state[prop])
            raise ProgramError(f"Device '{name}' has no stat '{prop}'")
        raise ProgramError(f"No substance or device named '{name}' found")

    @staticmethod
    def _match_blocks(canon_lines: List[List[str]]) -> Tuple[
        Dict[int, Dict[str, Optional[int]]], Dict[int, int], Dict[int, int], Dict[str, int]
    ]:
        if_map: Dict[int, Dict[str, Optional[int]]] = {}
        loop_map: Dict[int, int] = {}
        while_map: Dict[int, int] = {}
        labels: Dict[str, int] = {}
        stack: List[List] = []
        for i, tokens in enumerate(canon_lines):
            cmd = tokens[0] if tokens else ""
            if cmd == "IF":
                stack.append(["IF", i, None])
            elif cmd == "LOOP":
                stack.append(["LOOP", i, None])
            elif cmd == "WHILE":
                stack.append(["WHILE", i, None])
            elif cmd == "ELSE":
                if not stack or stack[-1][0] != "IF":
                    raise ProgramError(f"ELSE without a matching IF (line {i + 1})")
                stack[-1][2] = i
            elif cmd == "ENDIF":
                if not stack or stack[-1][0] != "IF":
                    raise ProgramError(f"ENDIF without a matching IF (line {i + 1})")
                _, start, else_idx = stack.pop()
                if_map[start] = {"else": else_idx, "end": i}
            elif cmd == "ENDLOOP":
                if not stack or stack[-1][0] != "LOOP":
                    raise ProgramError(f"ENDLOOP without a matching LOOP (line {i + 1})")
                _, start, _ = stack.pop()
                loop_map[start] = i
            elif cmd == "ENDWHILE":
                if not stack or stack[-1][0] != "WHILE":
                    raise ProgramError(f"ENDWHILE without a matching WHILE (line {i + 1})")
                _, start, _ = stack.pop()
                while_map[start] = i
            elif cmd == "LABEL":
                if len(tokens) < 2:
                    raise ProgramError(f"LABEL with no name (line {i + 1})")
                name = tokens[1]
                if name in labels:
                    raise ProgramError(f"Label '{name}' declared more than once (line {i + 1})")
                labels[name] = i
        if stack:
            raise ProgramError("Not all IF/LOOP/WHILE blocks are closed (missing ENDIF/ENDLOOP/ENDWHILE).")
        return if_map, loop_map, while_map, labels

    def run(self, program_lines: List[str], max_steps: int = 5000) -> List[str]:
        self.output = []
        self.variables = {}
        self.call_stack = []
        canon_lines = [self.language.translate_line(l).split() for l in program_lines]
        if_map, loop_map, while_map, labels = self._match_blocks(canon_lines)
        else_to_endif = {info["else"]: info["end"] for info in if_map.values() if info["else"] is not None}
        endloop_to_loop = {end: start for start, end in loop_map.items()}
        endwhile_to_while = {end: start for start, end in while_map.items()}
        loop_counters: Dict[int, int] = {}

        def cmp_op(a: float, b: float, op: str) -> bool:
            cond = {"==": a == b, "!=": a != b, ">": a > b,
                    "<": a < b, ">=": a >= b, "<=": a <= b}.get(op)
            if cond is None:
                raise ProgramError(f"Unknown comparison operator '{op}'")
            return cond

        pc = 0
        steps = 0
        while pc < len(canon_lines):
            steps += 1
            if steps > max_steps:
                raise ProgramError("Execution step limit exceeded - looks like an infinite loop.")

            tokens = canon_lines[pc]
            if not tokens:
                pc += 1
                continue
            cmd, args = tokens[0], tokens[1:]

            try:
                if cmd == "SET":
                    self.variables[args[0]] = self._value(args[1])
                elif cmd in ("ADD", "SUB", "MUL", "DIV", "MOD"):
                    a = self.variables.get(args[0], 0.0)
                    b = self._value(args[1])
                    if cmd == "ADD":
                        r = a + b
                    elif cmd == "SUB":
                        r = a - b
                    elif cmd == "MUL":
                        r = a * b
                    elif cmd == "MOD":
                        if b == 0:
                            raise ProgramError(f"Division by zero in MOD (line {pc + 1})")
                        r = a % b
                    else:
                        if b == 0:
                            raise ProgramError(f"Division by zero (line {pc + 1})")
                        r = a / b
                    self.variables[args[0]] = r
                elif cmd in ("AND", "OR", "XOR"):
                    # ALU logic: result variable = f(variable A, variable/value B)
                    a = bool(self._value(args[1]))
                    b = bool(self._value(args[2]))
                    r = {"AND": a and b, "OR": a or b, "XOR": a != b}[cmd]
                    self.variables[args[0]] = 1.0 if r else 0.0
                elif cmd == "NOT":
                    a = bool(self._value(args[1]))
                    self.variables[args[0]] = 0.0 if a else 1.0
                elif cmd in ("SHL", "SHR"):
                    a = int(self._value(args[1]))
                    n = int(self._value(args[2]))
                    self.variables[args[0]] = float((a << n) if cmd == "SHL" else (a >> n))
                elif cmd == "SQRT":
                    a = self._value(args[1])
                    if a < 0:
                        raise ProgramError(f"SQRT of a negative number (line {pc + 1})")
                    self.variables[args[0]] = math.sqrt(a)
                elif cmd == "RANDOM":
                    lo, hi = int(self._value(args[1])), int(self._value(args[2]))
                    self.variables[args[0]] = float(random.randint(min(lo, hi), max(lo, hi)))
                elif cmd == "STORE":
                    addr = int(self._value(args[0]))
                    if not (0 <= addr < self.memory_size):
                        raise ProgramError(
                            f"Address {addr} is outside available memory (0..{self.memory_size - 1}) - "
                            f"build a bigger Register or Data/Address Bus (line {pc + 1})"
                        )
                    self.memory[addr] = self._value(args[1])
                elif cmd == "LOAD":
                    addr = int(self._value(args[1]))
                    if not (0 <= addr < self.memory_size):
                        raise ProgramError(
                            f"Address {addr} is outside available memory (0..{self.memory_size - 1}) (line {pc + 1})"
                        )
                    self.variables[args[0]] = self.memory[addr]
                elif cmd == "PRINT":
                    if len(args) == 1 and args[0] in self.variables:
                        self.output.append(f"{args[0]} = {self.variables[args[0]]:.3f}")
                    else:
                        self.output.append(" ".join(args))
                elif cmd == "READ":
                    var, target_name, prop = args[0], args[1], args[2]
                    self.variables[var] = self._read_property(target_name, prop)
                elif cmd == "CALL":
                    device = self.workshop.devices.get(args[0])
                    if device is None:
                        raise ProgramError(f"Device '{args[0]}' has not been built")
                    target = self.substances.get(args[1]) if len(args) > 1 else None
                    self.output.append(device.use(target))
                elif cmd == "IF":
                    var, op, val = args[0], args[1], args[2]
                    cond = cmp_op(self._value(var), self._value(val), op)
                    info = if_map[pc]
                    if not cond:
                        pc = info["else"] if info["else"] is not None else info["end"]
                elif cmd == "ELSE":
                    pc = else_to_endif[pc]
                elif cmd == "ENDIF":
                    pass
                elif cmd == "LOOP":
                    n = int(self._value(args[0]))
                    loop_counters.setdefault(pc, n)
                elif cmd == "ENDLOOP":
                    start = endloop_to_loop[pc]
                    loop_counters[start] -= 1
                    if loop_counters[start] > 0:
                        pc = start
                        continue
                    else:
                        del loop_counters[start]
                elif cmd == "WHILE":
                    var, op, val = args[0], args[1], args[2]
                    cond = cmp_op(self._value(var), self._value(val), op)
                    if not cond:
                        pc = while_map[pc]  # jump right past ENDWHILE
                elif cmd == "ENDWHILE":
                    pc = endwhile_to_while[pc]  # jump back to WHILE - condition is re-checked
                    continue
                elif cmd == "LABEL":
                    pass  # a label does nothing on its own at run time
                elif cmd == "GOTO":
                    name = args[0]
                    if name not in labels:
                        raise ProgramError(f"Unknown label '{name}' (line {pc + 1})")
                    pc = labels[name]
                    continue
                elif cmd == "CALLSUB":
                    name = args[0]
                    if name not in labels:
                        raise ProgramError(f"Unknown label '{name}' (line {pc + 1})")
                    if len(self.call_stack) > 200:
                        raise ProgramError("Subroutine call stack overflow (recursion too deep).")
                    self.call_stack.append(pc)
                    pc = labels[name]
                    continue
                elif cmd == "RETURN":
                    if not self.call_stack:
                        raise ProgramError(f"RETURN without a matching CALLSUB (line {pc + 1})")
                    pc = self.call_stack.pop()
                elif cmd == "WAIT":
                    pass
                else:
                    raise ProgramError(f"Unknown command '{cmd}' (line {pc + 1}: '{' '.join(tokens)}')")
            except IndexError:
                raise ProgramError(f"Not enough arguments on line {pc + 1}: '{' '.join(tokens)}'")

            pc += 1

        return self.output


COMPUTE_CATEGORY = "Microchip (Prototype)"  # the device category able to run programs


# ============================================================================
# CLI / INTERACTIVE DEMO
# (from original module: mss/cli.py)
# ============================================================================

"""
CLI - interactive demo
"""




def print_elements():
    print("\nAvailable elements:")
    for sym, e in PERIODIC_TABLE.items():
        print(f"  {sym:3s} - {e.name}")


def input_composition() -> Dict[str, float]:
    comp = {}
    print("Enter elements one at a time (symbol and fraction), blank line to finish.")
    while True:
        raw = input("  Element (e.g. 'Fe 0.7') or Enter to finish: ").strip()
        if not raw:
            break
        try:
            sym, frac = raw.split()
            sym = sym.strip()
            frac = float(frac)
            if sym not in PERIODIC_TABLE:
                print("  Unknown element symbol.")
                continue
            comp[sym] = comp.get(sym, 0.0) + frac
        except ValueError:
            print("  Format: SYMBOL FRACTION, e.g.: Cu 0.5")
    return comp


def main():
    universe = Universe()
    substances: Dict[str, Substance] = {}
    cells: List[Cell] = []
    workshop = Workshop()
    languages: Dict[str, LanguageSpec] = {}
    programs: Dict[str, Dict[str, object]] = {}  # name -> {"lines": [...], "language": str}
    environments: Dict[str, Environment] = {}
    populations: Dict[str, Population] = {}

    print("=" * 70)
    print(" MATERIALS SIMULATION SYSTEM (MSS)")
    print(f" Welcome to universe: {universe}")
    print("=" * 70)

    while True:
        print("""
1.  Show the periodic table
2.  Create a substance
3.  Heat/cool a substance
4.  Mix two substances (chemical reaction)
5.  List substances
6.  Simulate cell growth (mutations + optional radiation background)
7.  Discover technologies (test a combination of substances)
8.  Build a technology (turn a discovery into a device)
9.  Use a built device
10. My technologies (list built devices)
11. Physics calculator (force, energy, Ohm's law)
12. Create your own programming language
13. Write a program in your language
14. Run a program on a built microchip
15. Universe info
16. Isotope table (half-life, decay mode)
17. Nuclear calculator (activity, decay, chain, dose and shielding)
18. Universe time: advance time, timers, reminders
19. Ecosystem: environment and evolution over time
0.  Exit
""")
        choice = input("Choice: ").strip()

        if choice == "1":
            print_elements()

        elif choice == "2":
            name = input("Substance name: ").strip() or "Unnamed"
            comp = input_composition()
            if not comp:
                print("Empty composition - substance not created.")
                continue
            temp = input("Starting temperature in K (Enter = 293.15): ").strip()
            temp = float(temp) if temp else 293.15
            s = Substance(name, comp, temperature=temp)
            radioactive = input("Make the substance radioactive (assign an isotope)? (y/N): ").strip().lower()
            if radioactive == "y":
                print("Available isotopes:", ", ".join(sorted(ISOTOPES)))
                iso_symbol = input("Isotope symbol: ").strip()
                if iso_symbol in ISOTOPES:
                    amount = input("Amount of substance, mol (Enter = 1.0): ").strip()
                    s.set_isotope(iso_symbol, float(amount) if amount else 1.0)
                else:
                    print("Unknown isotope - substance created without radioactivity.")
            substances[name] = s
            print("\nCreated:")
            print(s.summary())

        elif choice == "3":
            if not substances:
                print("No substances.")
                continue
            name = input(f"Which substance ({', '.join(substances)}): ").strip()
            if name not in substances:
                print("Not found.")
                continue
            delta = float(input("Change by how many kelvins (can be negative): "))
            PhysicsEngine.heat(substances[name], delta)
            print(substances[name].summary())

        elif choice == "4":
            if len(substances) < 2:
                print("Need at least 2 substances.")
                continue
            print(f"Available: {', '.join(substances)}")
            n1 = input("First substance: ").strip()
            n2 = input("Second substance: ").strip()
            if n1 not in substances or n2 not in substances:
                print("Not found.")
                continue
            result, energy, reacted = ChemistryEngine.mix(substances[n1], substances[n2])
            substances[result.name] = result
            if reacted:
                print(f"\nA reaction occurred! ~{energy:.0f} nominal J of energy released.")
            else:
                print("\nThe substances simply mixed, no vigorous reaction occurred.")
            print(result.summary())

        elif choice == "5":
            if not substances:
                print("Empty.")
            for s in substances.values():
                print("-" * 50)
                print(s.summary())

        elif choice == "6":
            species = input("Cell species name (Enter = 'TestCell'): ").strip() or "TestCell"
            opt_temp = input("Optimal temperature in K (Enter = 310.15): ").strip()
            opt_temp = float(opt_temp) if opt_temp else 310.15
            env_temp = float(input("Environment temperature in K: "))
            nutrients = float(input("Nutrient availability (0-2, 1=normal): "))
            radiation = input("Radiation background, uSv per step (Enter = 0, raises mutation/death risk): ").strip()
            radiation = float(radiation) if radiation else 0.0
            steps = int(input("How many steps to simulate: "))

            population = [Cell(species, opt_temp)]
            for step in range(steps):
                new_cells = []
                for c in population:
                    child = c.step(env_temp, nutrients, radiation_uSv=radiation)
                    if child:
                        new_cells.append(child)
                population = [c for c in population if c.alive] + new_cells
                alive_count = len(population)
                print(f"  Step {step+1}: living cells = {alive_count}")
                if alive_count == 0:
                    print("  The population went extinct.")
                    break
            if population:
                print("Example cell:", population[0])

        elif choice == "7":
            if not substances:
                print("Create some substances first.")
                continue
            print(f"Available: {', '.join(substances)}")
            names = input("List substances, comma separated, to combine: ").split(",")
            objs = [substances[n.strip()] for n in names if n.strip() in substances]
            if not objs:
                print("Nothing selected.")
                continue
            functions, tech, newly = workshop.discover(objs)
            print("\nDiscovered engineering functions of the materials:")
            for f in sorted(functions):
                print(f"  - {f}")
            if tech:
                print("\nPossible technologies from this combination:")
                for t in tech:
                    tag = " [NEW DISCOVERY]" if t in newly else " (already discovered)"
                    missing = workshop.missing_prerequisites(t)
                    ready = "" if not missing else f"  - must build first: {', '.join(missing)}"
                    print(f"  >>> {t}{tag}{ready}")
            else:
                print("\nDoesn't add up to a recognizable technology yet - "
                      "try a different combination or change the proportions/temperature.")

        elif choice == "8":
            ready = workshop.buildable_now()
            if not ready:
                print("No technologies are currently buildable. Discover some first (option 7),"
                      " and make sure all prerequisite technologies are built.")
                continue
            print("Buildable right now:")
            for t in ready:
                print(f"  - {t} (tier {workshop.tier_of(t)})")
            category = input("Which technology to build: ").strip()
            if category not in ready:
                print("This technology can't be built right now.")
                continue
            print(f"Substances on hand: {', '.join(substances) if substances else '(none)'}")
            names = input("Which substances to build from (comma separated): ").split(",")
            objs = [substances[n.strip()] for n in names if n.strip() in substances]
            if not objs:
                print("You must select at least one existing substance.")
                continue
            device_name = input("Device name (Enter = automatic): ").strip() or None
            try:
                device = workshop.build(category, objs, device_name)
            except ValueError as e:
                print(f"Could not build: {e}")
                continue
            print("\nBuilt:")
            print(device.summary())

        elif choice == "9":
            if not workshop.devices:
                print("You haven't built any devices yet.")
                continue
            print(f"Your devices: {', '.join(workshop.devices)}")
            dname = input("Which device to use: ").strip()
            if dname not in workshop.devices:
                print("Not found.")
                continue
            device = workshop.devices[dname]
            target = None
            if device.category in ("Cooling System", "Heating Element"):
                tname = input(f"Which substance to act on ({', '.join(substances)}): ").strip()
                target = substances.get(tname)
                if target is None:
                    print("Substance not found.")
                    continue
            print("\n" + device.use(target))

        elif choice == "10":
            if not workshop.devices:
                print("Nothing built yet.")
            for d in workshop.devices.values():
                print("-" * 50)
                print(d.summary())
            if workshop.known_tech:
                undiscovered_but_known = workshop.known_tech - {d.category for d in workshop.devices.values()}
                if undiscovered_but_known:
                    print("\nDiscovered but not yet built:")
                    for t in undiscovered_but_known:
                        missing = workshop.missing_prerequisites(t)
                        note = "" if not missing else f" (needs first: {', '.join(missing)})"
                        print(f"  - {t}{note}")

        elif choice == "11":
            print("""
What to calculate?
  a) F = m*a (force)
  b) Ek = (1/2)mv^2 (kinetic energy)
  c) Ep = mgh (potential energy, g of the current universe)
  d) p = m*v (momentum)
  e) Ohm's law (give any 2 of 3: V, I, R)
""")
            sub = input("Choice (a-e): ").strip().lower()
            try:
                if sub == "a":
                    m = float(input("Mass, kg: "))
                    a = float(input("Acceleration, m/s^2: "))
                    print(f"F = {PhysicsEngine.force(m, a):.3f} N")
                elif sub == "b":
                    m = float(input("Mass, kg: "))
                    v = float(input("Velocity, m/s: "))
                    print(f"Ek = {PhysicsEngine.kinetic_energy(m, v):.3f} J")
                elif sub == "c":
                    m = float(input("Mass, kg: "))
                    h = float(input("Height, m: "))
                    print(f"Ep = {PhysicsEngine.potential_energy(m, h, universe):.3f} J (g={universe.gravity})")
                elif sub == "d":
                    m = float(input("Mass, kg: "))
                    v = float(input("Velocity, m/s: "))
                    print(f"p = {PhysicsEngine.momentum(m, v):.3f} kg*m/s")
                elif sub == "e":
                    raw_v = input("Voltage V (Enter if unknown): ").strip()
                    raw_i = input("Current I (Enter if unknown): ").strip()
                    raw_r = input("Resistance R (Enter if unknown): ").strip()
                    v = float(raw_v) if raw_v else None
                    i = float(raw_i) if raw_i else None
                    r = float(raw_r) if raw_r else None
                    result = PhysicsEngine.ohms_law(voltage=v, current=i, resistance=r)
                    print(f"V={result['voltage_V']:.3f}  I={result['current_A']:.3f}  R={result['resistance_Ohm']:.3f}")
                else:
                    print("Unknown option.")
            except (ValueError, TypeError) as e:
                print(f"Input error: {e}")

        elif choice == "12":
            lang_name = input("Name of your programming language: ").strip() or "MyLanguage"
            print(f"\nCreating language '{lang_name}'. For each engine command, choose YOUR word.")
            print("Enter - keep the canonical English command name.\n")
            keywords: Dict[str, str] = {}
            used_tokens = set()
            for canon, meaning in CANONICAL_COMMANDS.items():
                while True:
                    token = input(f"  {canon:8s} ({meaning}) -> ").strip()
                    if not token:
                        token = canon
                    if token in used_tokens:
                        print("    That word is already used by another command, choose another.")
                        continue
                    used_tokens.add(token)
                    keywords[canon] = token
                    break
            lang = LanguageSpec(lang_name, keywords)
            languages[lang_name] = lang
            print("\nLanguage created!\n")
            print(lang.describe())

        elif choice == "13":
            if not languages:
                print("Create a programming language first (option 12).")
                continue
            print(f"Available languages: {', '.join(languages)}")
            lang_name = input("Which language to write in: ").strip()
            lang = languages.get(lang_name)
            if lang is None:
                print("Language not found.")
                continue
            prog_name = input("Program name: ").strip() or "program1"
            print("\nEnter the program line by line. A blank line ends input.")
            print("Hint - your language's dictionary:")
            print(lang.describe())
            print(f"\nDevices available for CALL: {', '.join(workshop.devices) or '(none yet)'}")
            print(f"Substances available for READ/CALL targets: {', '.join(substances) or '(none yet)'}\n")
            lines = []
            while True:
                line = input("  > ")
                if not line:
                    break
                lines.append(line)
            programs[prog_name] = {"lines": lines, "language": lang_name}
            print(f"Program '{prog_name}' saved ({len(lines)} lines).")

        elif choice == "14":
            chips = [d for d in workshop.devices.values() if d.category == COMPUTE_CATEGORY]
            if not chips:
                print(f"No device of category '{COMPUTE_CATEGORY}' has been built - "
                      f"there's nothing to run a program on. Build a microchip first "
                      f"(options 7 and 8).")
                continue
            if not programs:
                print("No programs have been written yet (option 13).")
                continue
            print(f"Microchips: {', '.join(d.name for d in chips)}")
            chip_name = input("Which microchip to run on: ").strip()
            if chip_name not in {d.name for d in chips}:
                print("No such microchip has been built.")
                continue
            print(f"Programs: {', '.join(programs)}")
            prog_name = input("Which program to run: ").strip()
            prog = programs.get(prog_name)
            if prog is None:
                print("Program not found.")
                continue
            lang = languages[prog["language"]]
            interpreter = Interpreter(lang, workshop, substances)
            print(f"\n--- Running '{prog_name}' on {chip_name} ---")
            try:
                output = interpreter.run(prog["lines"])
                for line in output:
                    print(" >", line)
                print("--- Program finished without errors ---")
            except ProgramError as e:
                print(f"Program execution error: {e}")

        elif choice == "15":
            print(universe)

        elif choice == "16":
            print(f"\n{'Isotope':8s} {'Decay mode':10s} {'Gamma?':7s} {'T1/2':>16s} {'Daughter':10s}")
            print("-" * 60)
            for sym in sorted(ISOTOPES):
                iso = ISOTOPES[sym]
                print(f"{iso.symbol:8s} {iso.decay_mode:10s} {'yes' if iso.emits_gamma else '-':7s} "
                      f"{format_half_life(iso.half_life_s):>16s} {iso.daughter or '(stable)':10s}")

        elif choice == "17":
            print("""
What to calculate?
  a) Substance activity (Bq) - from amount (mol) and isotope
  b) How much substance remains after a given time (decay law)
  c) Show the full decay chain of an isotope
  d) Simulate a decay chain over time (numerically)
  e) Dose rate at a distance, with or without shielding
""")
            sub = input("Choice (a-e): ").strip().lower()
            try:
                if sub == "a":
                    print("Available isotopes:", ", ".join(sorted(ISOTOPES)))
                    sym = input("Isotope: ").strip()
                    if sym not in ISOTOPES:
                        print("Unknown isotope.")
                        continue
                    amount = float(input("Amount, mol: "))
                    iso = ISOTOPES[sym]
                    activity = DecayEngine.activity(iso, amount * AVOGADRO)
                    print(f"Activity: {activity:.4e} Bq ({activity/3.7e10:.4e} Ci)")
                elif sub == "b":
                    print("Available isotopes:", ", ".join(sorted(ISOTOPES)))
                    sym = input("Isotope: ").strip()
                    if sym not in ISOTOPES:
                        print("Unknown isotope.")
                        continue
                    amount = float(input("Starting amount, mol: "))
                    years = float(input("After how many years: "))
                    iso = ISOTOPES[sym]
                    fraction = DecayEngine.remaining_fraction(iso, years * YEAR)
                    print(f"Remaining: {amount * fraction:.6g} mol ({fraction*100:.4f}% of original)")
                elif sub == "c":
                    print("Available isotopes:", ", ".join(sorted(ISOTOPES)))
                    sym = input("Isotope (chain start): ").strip()
                    if sym not in ISOTOPES:
                        print("Unknown isotope.")
                        continue
                    chain = DecayEngine.decay_chain(sym)
                    print(f"\nDecay chain of {sym} ({len(chain)} links):")
                    for iso in chain:
                        arrow = f" -> {iso.daughter}" if iso.daughter else " (stable)"
                        print(f"  {iso.symbol} [{iso.decay_mode}, T1/2={format_half_life(iso.half_life_s)}]{arrow}")
                elif sub == "d":
                    print("Available isotopes:", ", ".join(sorted(ISOTOPES)))
                    sym = input("Isotope (chain start): ").strip()
                    if sym not in ISOTOPES:
                        print("Unknown isotope.")
                        continue
                    amount = float(input("Starting amount, mol: "))
                    years = float(input("After how many years: "))
                    pops = DecayEngine.simulate_chain(sym, amount * AVOGADRO, years * YEAR)
                    print(f"\nChain composition after {years} years (in atoms):")
                    for isym, n in pops.items():
                        print(f"  {isym}: {n:.4e} atoms ({n/AVOGADRO:.4e} mol)")
                elif sub == "e":
                    print("Available isotopes:", ", ".join(sorted(ISOTOPES)))
                    sym = input("Source isotope: ").strip()
                    if sym not in ISOTOPES:
                        print("Unknown isotope.")
                        continue
                    amount = float(input("Amount, mol: "))
                    distance = float(input("Distance, m: "))
                    shield_density = input("Shield density, g/cm3 (Enter = no shielding): ").strip()
                    thickness = 0.0
                    density = 0.0
                    if shield_density:
                        density = float(shield_density)
                        thickness = float(input("Shield thickness, cm: "))
                    iso = ISOTOPES[sym]
                    activity = DecayEngine.activity(iso, amount * AVOGADRO)
                    rtype = "alpha" if iso.decay_mode == "alpha" else ("gamma" if iso.emits_gamma else "beta-")
                    atten = RadiationEngine.attenuation(rtype, _ShieldProxy(density), thickness) if density else 1.0
                    dose = RadiationEngine.dose_rate_uSv_per_hour(iso, activity, distance, atten)
                    print(f"\nActivity: {activity:.3e} Bq")
                    print(f"Dose rate: {dose:.3f} uSv/h - {RadiationEngine.classify_dose(dose)}")
                    print("[Simulation estimate, not for real radiation-safety use.]")
                else:
                    print("Unknown option.")
            except (ValueError, TypeError, ZeroDivisionError) as e:
                print(f"Input error: {e}")

        elif choice == "18":
            print(f"""
Universe time right now: {universe.format_elapsed_time()} (t={universe.elapsed_time_s:.3f} s)
What to do?
  a) Advance time forward (tick) - tracked substances decay,
     timers and reminders fire
  b) Create a countdown timer
  c) Create a reminder (in seconds, or by an isotope's half-life)
  d) Show all timers and reminders
  e) Put a substance on automatic decay tracking (track)
""")
            sub = input("Choice (a-e): ").strip().lower()
            try:
                if sub == "a":
                    print("Units: s / min / h / days / years")
                    unit = input("Which units is the time in (Enter = s): ").strip() or "s"
                    amount = float(input("How much: "))
                    factor = {"s": 1, "min": 60, "h": 3600, "days": 86400, "years": YEAR}.get(unit, 1)
                    dt = amount * factor
                    events = universe.advance_time(dt)
                    print(f"\nTime advanced by {format_duration(dt)}. "
                          f"Current universe time: {universe.format_elapsed_time()}.")
                    if events:
                        print("Events:")
                        for e in events:
                            print(f"  {e}")
                    else:
                        print("Nothing happened.")
                elif sub == "b":
                    name = input("Timer name: ").strip() or f"Timer{len(universe.timers)+1}"
                    print("Units: s / min / h / days / years")
                    unit = input("Which units is the duration in (Enter = min): ").strip() or "min"
                    amount = float(input("How much: "))
                    factor = {"s": 1, "min": 60, "h": 3600, "days": 86400, "years": YEAR}.get(unit, 60)
                    message = input("Message when it fires (Enter = no message): ").strip()
                    repeating = input("Repeating? (y/N): ").strip().lower() == "y"
                    timer = universe.add_timer(name, amount * factor, message, repeating)
                    print(f"Created: {timer.summary()}")
                elif sub == "c":
                    name = input("Reminder name: ").strip() or f"Reminder{len(universe.reminders)+1}"
                    message = input("Reminder text: ").strip() or "(no text)"
                    by_half_life = input("Tie it to an isotope's half-life? (y/N): ").strip().lower()
                    if by_half_life == "y":
                        print("Available isotopes:", ", ".join(sorted(ISOTOPES)))
                        sym = input("Isotope: ").strip()
                        if sym not in ISOTOPES or ISOTOPES[sym].half_life_s == math.inf:
                            print("Unknown or stable isotope - no half-life available.")
                            continue
                        in_seconds = ISOTOPES[sym].half_life_s
                        print(f"Half-life of {sym}: {format_half_life(in_seconds)}")
                    else:
                        print("Units: s / min / h / days / years")
                        unit = input("Which units (Enter = min): ").strip() or "min"
                        amount = float(input("In how long: "))
                        factor = {"s": 1, "min": 60, "h": 3600, "days": 86400, "years": YEAR}.get(unit, 60)
                        in_seconds = amount * factor
                    reminder = universe.add_reminder(name, in_seconds, message)
                    print(f"Created: {reminder.summary(universe.elapsed_time_s)}")
                elif sub == "d":
                    if not universe.timers and not universe.reminders:
                        print("No timers or reminders yet.")
                    if universe.timers:
                        print("\nTimers:")
                        for t in universe.timers.values():
                            print(f"  {t.summary()}")
                    if universe.reminders:
                        print("\nReminders:")
                        for r in universe.reminders.values():
                            print(f"  {r.summary(universe.elapsed_time_s)}")
                elif sub == "e":
                    if not substances:
                        print("Create a substance first (option 2).")
                        continue
                    print(f"Available: {', '.join(substances)}")
                    name = input("Which substance to track: ").strip()
                    if name not in substances:
                        print("Not found.")
                        continue
                    if not substances[name].isotope:
                        print("This substance is not radioactive (no isotope assigned) - nothing to track.")
                        continue
                    universe.track(substances[name])
                    print(f"'{name}' now decays automatically as time advances (option 18a).")
                else:
                    print("Unknown option.")
            except (ValueError, TypeError, ZeroDivisionError) as e:
                print(f"Input error: {e}")

        elif choice == "19":
            print("""
Ecosystem: an environment controlled by the player, and evolution over time.
What to do?
  a) Create an environment
  b) Change environment conditions manually (artificial selection)
  c) Toggle environment auto-dynamics (day/night/seasons - not random,
     a deterministic cycle)
  d) Place a created substance into the environment (its REAL chemistry/
     radiation changes the environment's pH, toxicity, and radiation background)
  e) Create a cell population in an environment
  f) One evolution step
  g) Skip time forward (fast-forward evolution by many years at once)
  h) Show a population report (traits, drift over time)
  i) List all environments and populations
""")
            sub = input("Choice (a-i): ").strip().lower()
            try:
                if sub == "a":
                    name = input("Environment name: ").strip() or f"Environment{len(environments)+1}"
                    temp = input("Temperature, K (Enter = 293.15): ").strip()
                    env = Environment(name, temperature=float(temp) if temp else 293.15)
                    environments[name] = env
                    print(f"Created:\n{env.summary()}")
                elif sub == "b":
                    if not environments:
                        print("Create an environment first (a).")
                        continue
                    print(f"Available: {', '.join(environments)}")
                    ename = input("Which environment: ").strip()
                    if ename not in environments:
                        print("Not found.")
                        continue
                    env = environments[ename]
                    print("Conditions: temperature(K), ph, oxygen_level(0-1), salinity(0-1), "
                          "light_level(0-1), pressure_atm, nutrient_density, toxicity(0-1), "
                          "radiation_background_uSv_h")
                    field_name = input("Which condition to change: ").strip()
                    value = float(input("New value: "))
                    env.set_condition(field_name, value)
                    print(f"Changed.\n{env.summary()}")
                elif sub == "c":
                    if not environments:
                        print("Create an environment first (a).")
                        continue
                    print(f"Available: {', '.join(environments)}")
                    ename = input("Which environment: ").strip()
                    if ename not in environments:
                        print("Not found.")
                        continue
                    env = environments[ename]
                    env.auto_dynamics = not env.auto_dynamics
                    print(f"Auto-dynamics for '{ename}': {'on' if env.auto_dynamics else 'off'}")
                elif sub == "d":
                    if not environments or not substances:
                        print("You need both an environment (a) and at least one created substance (option 2).")
                        continue
                    print(f"Environments: {', '.join(environments)}")
                    ename = input("Which environment: ").strip()
                    if ename not in environments:
                        print("Not found.")
                        continue
                    print(f"Substances: {', '.join(substances)}")
                    sname = input("Which substance to place: ").strip()
                    if sname not in substances:
                        print("Not found.")
                        continue
                    environments[ename].add_substance(substances[sname])
                    print(f"Placed.\n{environments[ename].summary()}")
                elif sub == "e":
                    if not environments:
                        print("Create an environment first (a).")
                        continue
                    print(f"Available: {', '.join(environments)}")
                    ename = input("In which environment: ").strip()
                    if ename not in environments:
                        print("Not found.")
                        continue
                    species = input("Species name: ").strip() or "Species1"
                    size = input("Initial population size (Enter = 10): ").strip()
                    size = int(size) if size else 10
                    capacity = input("Environment capacity, max individuals (Enter = 300): ").strip()
                    capacity = int(capacity) if capacity else 300
                    pop = Population(species, environments[ename], initial_size=size, carrying_capacity=capacity)
                    populations[species] = pop
                    print(f"Created.\n{pop.summary()}")
                elif sub == "f":
                    if not populations:
                        print("Create a population first (e).")
                        continue
                    print(f"Available: {', '.join(populations)}")
                    pname = input("Which population: ").strip()
                    if pname not in populations:
                        print("Not found.")
                        continue
                    print("Step units: s / min / h / days / years")
                    unit = input("In which units (Enter = days): ").strip() or "days"
                    factor = {"s": 1, "min": 60, "h": 3600, "days": 86400, "years": YEAR}.get(unit, 86400)
                    amount = input("How much (Enter = 1): ").strip()
                    amount = float(amount) if amount else 1.0
                    populations[pname].step(amount * factor, universe)
                    print(populations[pname].summary())
                elif sub == "g":
                    if not populations:
                        print("Create a population first (e).")
                        continue
                    print(f"Available: {', '.join(populations)}")
                    pname = input("Which population: ").strip()
                    if pname not in populations:
                        print("Not found.")
                        continue
                    print("Units: s / min / h / days / years")
                    unit = input("In which units (Enter = years): ").strip() or "years"
                    factor = {"s": 1, "min": 60, "h": 3600, "days": 86400, "years": YEAR}.get(unit, YEAR)
                    amount = float(input("Skip forward by how much: "))
                    populations[pname].skip_time(amount * factor, universe=universe)
                    print(f"\n{populations[pname].summary()}")
                elif sub == "h":
                    if not populations:
                        print("No populations yet.")
                        continue
                    print(f"Available: {', '.join(populations)}")
                    pname = input("Which population: ").strip()
                    if pname not in populations:
                        print("Not found.")
                        continue
                    print(f"\n{populations[pname].summary()}")
                    print(f"\n{populations[pname].environment.summary()}")
                elif sub == "i":
                    if not environments and not populations:
                        print("No environments or populations yet.")
                    if environments:
                        print("\nEnvironments:")
                        for e in environments.values():
                            print(f"  {e.summary()}")
                    if populations:
                        print("\nPopulations:")
                        for p in populations.values():
                            print(f"  {p.summary()}")
                else:
                    print("Unknown option.")
            except (ValueError, TypeError, ZeroDivisionError) as e:
                print(f"Input error: {e}")

        elif choice == "0":
            print("See you next simulation.")
            break

        else:
            print("Unknown menu option.")


# ============================================================================
# ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    main()
