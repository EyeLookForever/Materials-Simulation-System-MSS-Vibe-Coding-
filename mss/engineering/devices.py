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

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, TYPE_CHECKING

from mss.physics.radiation import ISOTOPES, RadiationEngine
from mss.engineering.invention import InventionEngine

if TYPE_CHECKING:
    from mss.chemistry.substance import Substance


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

