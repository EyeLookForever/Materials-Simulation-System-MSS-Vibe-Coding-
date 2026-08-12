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

import itertools
from typing import List, Tuple, TYPE_CHECKING

from mss.physics.radiation import ISOTOPES

if TYPE_CHECKING:
    from mss.chemistry.substance import Substance


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
