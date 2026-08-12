"""
CHEMISTRY: ELEMENTS
"""

from dataclasses import dataclass
from enum import Enum
from typing import Dict


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
