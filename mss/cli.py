"""
CLI - interactive demo
"""

import math
from typing import Dict, List

from mss.chemistry.elements import PERIODIC_TABLE
from mss.chemistry.substance import Substance
from mss.chemistry.engine import ChemistryEngine
from mss.physics.mechanics import PhysicsEngine
from mss.physics.radiation import (
    ISOTOPES, AVOGADRO, YEAR, DecayEngine, RadiationEngine, format_half_life,
)
from mss.biology.cell import Cell
from mss.biology.environment import Environment
from mss.biology.population import Population
from mss.engineering.devices import Workshop, _ShieldProxy
from mss.programming.language import CANONICAL_COMMANDS, LanguageSpec, ProgramError
from mss.programming.interpreter import Interpreter, COMPUTE_CATEGORY
from mss.core.universe import Universe, format_duration


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
