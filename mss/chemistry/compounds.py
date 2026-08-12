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

import math
from dataclasses import dataclass
from fractions import Fraction
from typing import Dict, Tuple


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
