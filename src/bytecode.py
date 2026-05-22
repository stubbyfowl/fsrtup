"""
FortPy Bytecode — Instruction set for the FortPy Virtual Machine.

Stack-based bytecode. All values live on the operand stack.
The compiler translates the AST into a flat list of Instructions.
The VM then executes the bytecode independently — no AST involved.

Instruction format:
    Instruction(op, arg=None)

Where `arg` is an integer, float, string, or None depending on opcode.
"""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, List, Optional


# ── Opcode definitions ────────────────────────────────────────────────────────

class Op(Enum):
    # ── Stack / constants ──────────────────────────────────────────────────
    PUSH_INT    = auto()   # arg: int literal      → push int
    PUSH_REAL   = auto()   # arg: float literal    → push float
    PUSH_STR    = auto()   # arg: str literal      → push str
    PUSH_BOOL   = auto()   # arg: 0/1              → push bool

    # ── Variables ─────────────────────────────────────────────────────────
    LOAD        = auto()   # arg: str name         → push value of var
    STORE       = auto()   # arg: str name         stack: [value] → ()
    LOAD_ARR    = auto()   # arg: str name         stack: [idx]   → value
    STORE_ARR   = auto()   # arg: str name         stack: [value, idx] → ()

    # ── Arithmetic ────────────────────────────────────────────────────────
    ADD         = auto()   # stack: [a, b] → a+b
    SUB         = auto()   # stack: [a, b] → a-b
    MUL         = auto()   # stack: [a, b] → a*b
    DIV         = auto()   # stack: [a, b] → a/b (int div if both int)
    POW         = auto()   # stack: [a, b] → a**b
    NEG         = auto()   # stack: [a]    → -a
    CONCAT      = auto()   # stack: [a, b] → str(a)//str(b)

    # ── Comparison ────────────────────────────────────────────────────────
    CMP_EQ      = auto()   # == or .EQ.
    CMP_NE      = auto()   # /= or .NE.
    CMP_LT      = auto()   # <  or .LT.
    CMP_LE      = auto()   # <= or .LE.
    CMP_GT      = auto()   # >  or .GT.
    CMP_GE      = auto()   # >= or .GE.

    # ── Logical ───────────────────────────────────────────────────────────
    LOGICAL_AND = auto()
    LOGICAL_OR  = auto()
    LOGICAL_NOT = auto()

    # ── Control flow ──────────────────────────────────────────────────────
    JUMP        = auto()   # arg: int addr          → unconditional jump
    JUMP_FALSE  = auto()   # arg: int addr          stack: [cond] → (), jump if false
    JUMP_TRUE   = auto()   # arg: int addr          stack: [cond] → (), jump if true

    # ── I/O ───────────────────────────────────────────────────────────────
    PRINT_NL    = auto()   # arg: int count         pop `count` items, print with spaces + newline
    PRINT_VAL   = auto()   # print top of stack (no newline, no pop)

    # ── Functions / subroutines ───────────────────────────────────────────
    CALL        = auto()   # arg: (name, argc)      call user function/sub
    CALL_BUILTIN= auto()   # arg: (name, argc)      call built-in function
    RETURN      = auto()   # return from function (return value on stack if func)
    RETURN_VAL  = auto()   # return with value

    # ── Array allocation ──────────────────────────────────────────────────
    ALLOC_ARR   = auto()   # arg: (name, ndim)      stack: [d1,d2,...] → allocate

    # ── Stack manipulation ────────────────────────────────────────────────
    POP         = auto()   # discard top
    DUP         = auto()   # duplicate top

    # ── Program control ───────────────────────────────────────────────────
    HALT        = auto()   # end of program


# ── Instruction ───────────────────────────────────────────────────────────────

@dataclass
class Instruction:
    op: Op
    arg: Any = None
    comment: str = ''      # optional human-readable annotation

    def __repr__(self):
        parts = [f'{self.op.name}']
        if self.arg is not None:
            parts.append(repr(self.arg))
        if self.comment:
            parts.append(f'; {self.comment}')
        return '  '.join(parts)


# ── Compiled function/program unit ────────────────────────────────────────────

@dataclass
class CompiledUnit:
    name: str
    params: List[str]       # parameter names in order
    is_function: bool
    code: List[Instruction] = field(default_factory=list)
    local_vars: List[str]   = field(default_factory=list)


# ── Bytecode module (output of compiler) ─────────────────────────────────────

@dataclass
class BytecodeModule:
    units: dict             # name → CompiledUnit
    entry: str              # name of main program unit

    def disassemble(self) -> str:
        lines = ['FortPy Bytecode Module', '=' * 60]
        for name, unit in self.units.items():
            header = f'UNIT  {name}'
            if unit.params:
                header += f'  params=({", ".join(unit.params)})'
            if unit.is_function:
                header += '  [FUNCTION]'
            lines.append('')
            lines.append(header)
            lines.append('-' * 50)
            for i, instr in enumerate(unit.code):
                lines.append(f'  {i:4d}  {instr}')
        return '\n'.join(lines)
