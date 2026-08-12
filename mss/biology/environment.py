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

import math
from typing import Dict, Optional, TYPE_CHECKING

from mss.chemistry.substance import Substance
from mss.physics.radiation import ISOTOPES, AVOGADRO, DecayEngine, RadiationEngine
from mss.core.universe import format_duration

if TYPE_CHECKING:
    from mss.core.universe import Universe


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
