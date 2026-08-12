"""
PROGRAMMING - Interpreter

A line-based virtual machine: numeric variables, ALU arithmetic and logic
(AND/OR/XOR/NOT/shifts), conditions (IF/ELSE/ENDIF), counted loops
(LOOP/ENDLOOP) and conditional loops (WHILE/ENDWHILE), labels and jumps
(LABEL/GOTO), subroutines (CALLSUB/RETURN), addressed memory
(STORE/LOAD), calling built devices (CALL), and reading their stats and
substance properties (READ).

IMPORTANT: the amount of addressable memory is NOT an arbitrary engine
constant - it's computed from the REALLY BUILT hardware (see
_compute_memory_size). Without a built Register or Data/Address Bus,
only 16 "default" memory cells are available - programming here also
requires building what the code will run on first.
"""

import math
import random
from typing import Dict, List, Optional, Tuple, TYPE_CHECKING

from mss.programming.language import LanguageSpec, ProgramError

if TYPE_CHECKING:
    from mss.engineering.devices import Workshop
    from mss.chemistry.substance import Substance


class Interpreter:
    DEFAULT_MEMORY_SIZE = 16

    def __init__(self, language: LanguageSpec, workshop: "Workshop", substances: Dict[str, "Substance"]):
        self.language = language
        self.workshop = workshop
        self.substances = substances
        self.variables: Dict[str, float] = {}
        self.output: List[str] = []
        self.memory_size = self._compute_memory_size()
        self.memory: List[float] = [0.0] * self.memory_size
        self.call_stack: List[int] = []

    def _compute_memory_size(self) -> int:
        """Memory size = a function of the actually built hardware, not a constant."""
        best = self.DEFAULT_MEMORY_SIZE
        for d in self.workshop.devices.values():
            if d.category == "Register (Memory Cell)":
                bits = d.stats.get("bit_width", 8)
                best = max(best, int(bits) * 4)  # nominal: an N-bit register -> N*4 cells
            if d.category == "Data & Address Bus (Prototype)":
                addr_bits = d.stats.get("address_bus_width_bit", 8)
                best = max(best, min(2 ** int(addr_bits), 4096))  # a sane ceiling
        return best

    def _value(self, token: str) -> float:
        if token in self.variables:
            return self.variables[token]
        try:
            return float(token)
        except ValueError:
            raise ProgramError(f"Unknown variable or number: '{token}'")

    def _read_property(self, name: str, prop: str) -> float:
        if name in self.substances:
            obj = self.substances[name]
            value = getattr(obj, prop, None)
            if value is None or callable(value):
                raise ProgramError(f"Substance '{name}' has no numeric property '{prop}'")
            return float(value)
        if name in self.workshop.devices:
            device = self.workshop.devices[name]
            if prop in device.stats:
                return float(device.stats[prop])
            if prop in device.state:
                return float(device.state[prop])
            raise ProgramError(f"Device '{name}' has no stat '{prop}'")
        raise ProgramError(f"No substance or device named '{name}' found")

    @staticmethod
    def _match_blocks(canon_lines: List[List[str]]) -> Tuple[
        Dict[int, Dict[str, Optional[int]]], Dict[int, int], Dict[int, int], Dict[str, int]
    ]:
        if_map: Dict[int, Dict[str, Optional[int]]] = {}
        loop_map: Dict[int, int] = {}
        while_map: Dict[int, int] = {}
        labels: Dict[str, int] = {}
        stack: List[List] = []
        for i, tokens in enumerate(canon_lines):
            cmd = tokens[0] if tokens else ""
            if cmd == "IF":
                stack.append(["IF", i, None])
            elif cmd == "LOOP":
                stack.append(["LOOP", i, None])
            elif cmd == "WHILE":
                stack.append(["WHILE", i, None])
            elif cmd == "ELSE":
                if not stack or stack[-1][0] != "IF":
                    raise ProgramError(f"ELSE without a matching IF (line {i + 1})")
                stack[-1][2] = i
            elif cmd == "ENDIF":
                if not stack or stack[-1][0] != "IF":
                    raise ProgramError(f"ENDIF without a matching IF (line {i + 1})")
                _, start, else_idx = stack.pop()
                if_map[start] = {"else": else_idx, "end": i}
            elif cmd == "ENDLOOP":
                if not stack or stack[-1][0] != "LOOP":
                    raise ProgramError(f"ENDLOOP without a matching LOOP (line {i + 1})")
                _, start, _ = stack.pop()
                loop_map[start] = i
            elif cmd == "ENDWHILE":
                if not stack or stack[-1][0] != "WHILE":
                    raise ProgramError(f"ENDWHILE without a matching WHILE (line {i + 1})")
                _, start, _ = stack.pop()
                while_map[start] = i
            elif cmd == "LABEL":
                if len(tokens) < 2:
                    raise ProgramError(f"LABEL with no name (line {i + 1})")
                name = tokens[1]
                if name in labels:
                    raise ProgramError(f"Label '{name}' declared more than once (line {i + 1})")
                labels[name] = i
        if stack:
            raise ProgramError("Not all IF/LOOP/WHILE blocks are closed (missing ENDIF/ENDLOOP/ENDWHILE).")
        return if_map, loop_map, while_map, labels

    def run(self, program_lines: List[str], max_steps: int = 5000) -> List[str]:
        self.output = []
        self.variables = {}
        self.call_stack = []
        canon_lines = [self.language.translate_line(l).split() for l in program_lines]
        if_map, loop_map, while_map, labels = self._match_blocks(canon_lines)
        else_to_endif = {info["else"]: info["end"] for info in if_map.values() if info["else"] is not None}
        endloop_to_loop = {end: start for start, end in loop_map.items()}
        endwhile_to_while = {end: start for start, end in while_map.items()}
        loop_counters: Dict[int, int] = {}

        def cmp_op(a: float, b: float, op: str) -> bool:
            cond = {"==": a == b, "!=": a != b, ">": a > b,
                    "<": a < b, ">=": a >= b, "<=": a <= b}.get(op)
            if cond is None:
                raise ProgramError(f"Unknown comparison operator '{op}'")
            return cond

        pc = 0
        steps = 0
        while pc < len(canon_lines):
            steps += 1
            if steps > max_steps:
                raise ProgramError("Execution step limit exceeded - looks like an infinite loop.")

            tokens = canon_lines[pc]
            if not tokens:
                pc += 1
                continue
            cmd, args = tokens[0], tokens[1:]

            try:
                if cmd == "SET":
                    self.variables[args[0]] = self._value(args[1])
                elif cmd in ("ADD", "SUB", "MUL", "DIV", "MOD"):
                    a = self.variables.get(args[0], 0.0)
                    b = self._value(args[1])
                    if cmd == "ADD":
                        r = a + b
                    elif cmd == "SUB":
                        r = a - b
                    elif cmd == "MUL":
                        r = a * b
                    elif cmd == "MOD":
                        if b == 0:
                            raise ProgramError(f"Division by zero in MOD (line {pc + 1})")
                        r = a % b
                    else:
                        if b == 0:
                            raise ProgramError(f"Division by zero (line {pc + 1})")
                        r = a / b
                    self.variables[args[0]] = r
                elif cmd in ("AND", "OR", "XOR"):
                    # ALU logic: result variable = f(variable A, variable/value B)
                    a = bool(self._value(args[1]))
                    b = bool(self._value(args[2]))
                    r = {"AND": a and b, "OR": a or b, "XOR": a != b}[cmd]
                    self.variables[args[0]] = 1.0 if r else 0.0
                elif cmd == "NOT":
                    a = bool(self._value(args[1]))
                    self.variables[args[0]] = 0.0 if a else 1.0
                elif cmd in ("SHL", "SHR"):
                    a = int(self._value(args[1]))
                    n = int(self._value(args[2]))
                    self.variables[args[0]] = float((a << n) if cmd == "SHL" else (a >> n))
                elif cmd == "SQRT":
                    a = self._value(args[1])
                    if a < 0:
                        raise ProgramError(f"SQRT of a negative number (line {pc + 1})")
                    self.variables[args[0]] = math.sqrt(a)
                elif cmd == "RANDOM":
                    lo, hi = int(self._value(args[1])), int(self._value(args[2]))
                    self.variables[args[0]] = float(random.randint(min(lo, hi), max(lo, hi)))
                elif cmd == "STORE":
                    addr = int(self._value(args[0]))
                    if not (0 <= addr < self.memory_size):
                        raise ProgramError(
                            f"Address {addr} is outside available memory (0..{self.memory_size - 1}) - "
                            f"build a bigger Register or Data/Address Bus (line {pc + 1})"
                        )
                    self.memory[addr] = self._value(args[1])
                elif cmd == "LOAD":
                    addr = int(self._value(args[1]))
                    if not (0 <= addr < self.memory_size):
                        raise ProgramError(
                            f"Address {addr} is outside available memory (0..{self.memory_size - 1}) (line {pc + 1})"
                        )
                    self.variables[args[0]] = self.memory[addr]
                elif cmd == "PRINT":
                    if len(args) == 1 and args[0] in self.variables:
                        self.output.append(f"{args[0]} = {self.variables[args[0]]:.3f}")
                    else:
                        self.output.append(" ".join(args))
                elif cmd == "READ":
                    var, target_name, prop = args[0], args[1], args[2]
                    self.variables[var] = self._read_property(target_name, prop)
                elif cmd == "CALL":
                    device = self.workshop.devices.get(args[0])
                    if device is None:
                        raise ProgramError(f"Device '{args[0]}' has not been built")
                    target = self.substances.get(args[1]) if len(args) > 1 else None
                    self.output.append(device.use(target))
                elif cmd == "IF":
                    var, op, val = args[0], args[1], args[2]
                    cond = cmp_op(self._value(var), self._value(val), op)
                    info = if_map[pc]
                    if not cond:
                        pc = info["else"] if info["else"] is not None else info["end"]
                elif cmd == "ELSE":
                    pc = else_to_endif[pc]
                elif cmd == "ENDIF":
                    pass
                elif cmd == "LOOP":
                    n = int(self._value(args[0]))
                    loop_counters.setdefault(pc, n)
                elif cmd == "ENDLOOP":
                    start = endloop_to_loop[pc]
                    loop_counters[start] -= 1
                    if loop_counters[start] > 0:
                        pc = start
                        continue
                    else:
                        del loop_counters[start]
                elif cmd == "WHILE":
                    var, op, val = args[0], args[1], args[2]
                    cond = cmp_op(self._value(var), self._value(val), op)
                    if not cond:
                        pc = while_map[pc]  # jump right past ENDWHILE
                elif cmd == "ENDWHILE":
                    pc = endwhile_to_while[pc]  # jump back to WHILE - condition is re-checked
                    continue
                elif cmd == "LABEL":
                    pass  # a label does nothing on its own at run time
                elif cmd == "GOTO":
                    name = args[0]
                    if name not in labels:
                        raise ProgramError(f"Unknown label '{name}' (line {pc + 1})")
                    pc = labels[name]
                    continue
                elif cmd == "CALLSUB":
                    name = args[0]
                    if name not in labels:
                        raise ProgramError(f"Unknown label '{name}' (line {pc + 1})")
                    if len(self.call_stack) > 200:
                        raise ProgramError("Subroutine call stack overflow (recursion too deep).")
                    self.call_stack.append(pc)
                    pc = labels[name]
                    continue
                elif cmd == "RETURN":
                    if not self.call_stack:
                        raise ProgramError(f"RETURN without a matching CALLSUB (line {pc + 1})")
                    pc = self.call_stack.pop()
                elif cmd == "WAIT":
                    pass
                else:
                    raise ProgramError(f"Unknown command '{cmd}' (line {pc + 1}: '{' '.join(tokens)}')")
            except IndexError:
                raise ProgramError(f"Not enough arguments on line {pc + 1}: '{' '.join(tokens)}'")

            pc += 1

        return self.output


COMPUTE_CATEGORY = "Microchip (Prototype)"  # the device category able to run programs
