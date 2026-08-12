"""
Universe - the container for a simulation's physical constants and its
own simulated clock. Since the engine already deals with durations of
time (radioactive half-lives), it makes sense for the Universe to carry
a single "now" that decay, timers, and reminders all advance against.
See advance_time().
"""

import math
from dataclasses import dataclass
from typing import Dict, List, TYPE_CHECKING

if TYPE_CHECKING:
    from mss.chemistry.substance import Substance


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
