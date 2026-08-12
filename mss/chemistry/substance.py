"""
SUBSTANCE - an arbitrary substance (a mixture of elements in any proportion)
"""

from dataclasses import dataclass
from typing import Dict, Optional

from mss.chemistry.elements import PERIODIC_TABLE, State
from mss.chemistry.compounds import KNOWN_COMPOUNDS, CompoundData, empirical_ratio
from mss.physics.radiation import ISOTOPES, AVOGADRO, DecayEngine, format_half_life


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
