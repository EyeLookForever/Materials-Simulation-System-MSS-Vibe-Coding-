"""
CHEMISTRY ENGINE
"""

from typing import Dict, Tuple

from mss.chemistry.elements import PERIODIC_TABLE
from mss.chemistry.substance import Substance


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
