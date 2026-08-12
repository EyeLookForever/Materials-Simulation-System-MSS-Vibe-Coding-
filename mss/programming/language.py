"""
PROGRAMMING - the player designs their OWN language and then writes code in it

Idea: programming is engineering too, and in the spirit of the
simulation it should require BUILDING what the code will run on first
(a device of category "Microchip (Prototype)" from the Workshop), and
only then defining a language and writing a program.

Honest about scope: this is not a parser for a full derived grammar
(BNF and so on) - that wouldn't fit in one project and isn't needed for
the goal of "the player invents their own language". Instead there's a
small fixed set of CANONICAL commands (variables, arithmetic, branches,
loops, device calls) - and the player decides what WORDS these commands
are called in their language. The same program at the technical level
can look like English, like slang, or like a string of emoji - that's
what creating your own programming language means: your own vocabulary
layered on top of a shared grammar (one command per line).
"""

from dataclasses import dataclass, field
from typing import Dict

CANONICAL_COMMANDS: Dict[str, str] = {
    "SET": "variable = value",
    "ADD": "variable += value",
    "SUB": "variable -= value",
    "MUL": "variable *= value",
    "DIV": "variable /= value",
    "MOD": "variable %= value (remainder)",
    "PRINT": "print a variable or text",
    "READ": "variable <- substance/device.property",
    "CALL": "call a device [on a substance]  (output port)",
    "IF": "if variable OP value - start of a condition",
    "ELSE": "else",
    "ENDIF": "end of condition",
    "LOOP": "repeat N times - start of a loop",
    "ENDLOOP": "end of loop",
    "WHILE": "while variable OP value - start of a conditional loop",
    "ENDWHILE": "end of WHILE loop",
    "WAIT": "nominal tick (reserved)",
    # --- ALU operations (arithmetic logic unit): logic and shifts, not
    # just +-*/ - which is exactly what a real hardware ALU does
    "AND": "variable = a AND b (0/1)",
    "OR": "variable = a OR b (0/1)",
    "XOR": "variable = a XOR b (0/1)",
    "NOT": "variable = NOT a (0/1)",
    "SHL": "variable = a << N (shift left)",
    "SHR": "variable = a >> N (shift right)",
    # --- math functions
    "SQRT": "variable = sqrt(a)",
    "RANDOM": "variable = random integer from A to B",
    # --- addressed memory (what the data/address bus is for): memory size
    # is limited by REALLY BUILT Register/Bus devices - without them only
    # a few "default" cells are available
    "STORE": "memory[address] = value",
    "LOAD": "variable = memory[address]",
    # --- jumps and subroutines (the program counter can be moved directly) ---
    "LABEL": "a label - a jump target, does nothing on its own",
    "GOTO": "unconditional jump to a label",
    "CALLSUB": "call a subroutine at a label (save the return point)",
    "RETURN": "return from a subroutine",
}


class ProgramError(Exception):
    """A compile-time or run-time error in a player's program."""


@dataclass
class LanguageSpec:
    """
    A programming language invented by the player: a mapping from the
    engine's canonical command (e.g. "LOOP") to the word the player chose
    (e.g. "repeat" or "loopz" or "cycle!!!"). Commands left unset keep
    their canonical name by default.
    """
    name: str
    keywords: Dict[str, str]        # CANONICAL -> the player's word
    reverse: Dict[str, str] = field(init=False)

    def __post_init__(self):
        self.reverse = {token: canon for canon, token in self.keywords.items()}

    def translate_line(self, line: str) -> str:
        """Translates a line of the player's program into canonical form for the VM."""
        parts = line.split()
        if not parts:
            return line
        canon = self.reverse.get(parts[0], parts[0])
        return " ".join([canon] + parts[1:])

    def describe(self) -> str:
        lines = [f"Language '{self.name}' - command dictionary:"]
        for canon, meaning in CANONICAL_COMMANDS.items():
            token = self.keywords.get(canon, canon)
            lines.append(f"  {token:12s} -> {canon:8s} ({meaning})")
        return "\n".join(lines)
