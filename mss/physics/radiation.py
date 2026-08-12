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

import math
from dataclasses import dataclass
from typing import Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from mss.chemistry.substance import Substance

from mss.core.universe import format_duration

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
