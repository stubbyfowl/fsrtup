"""
FortPy Virtual Machine

Executes a BytecodeModule produced by the Compiler.
The VM has NO knowledge of Fortran source, tokens, or AST nodes.
It only knows about bytecode instructions and the operand stack.

Architecture:
  - Operand stack        (values pushed/popped by instructions)
  - Call stack           (frames for function/subroutine calls)
  - Variable store       (dict per frame, indexed by name)
  - Instruction pointer  (index into current frame's code list)
"""

import math
from typing import Any, Dict, List, Optional
from bytecode import Op, Instruction, CompiledUnit, BytecodeModule


class VMError(RuntimeError):
    pass


# ── Built-in function implementations ────────────────────────────────────────
# These are the ONLY place runtime evaluation happens.
# The compiler emits CALL_BUILTIN; the VM dispatches here.

def _builtin_abs(args):    return abs(args[0])
def _builtin_int(args):    return int(args[0])
def _builtin_real(args):   return float(args[0])
def _builtin_dble(args):   return float(args[0])
def _builtin_mod(args):    return args[0] % args[1]
def _builtin_max(args):    return max(args)
def _builtin_min(args):    return min(args)
def _builtin_sqrt(args):   return math.sqrt(float(args[0]))
def _builtin_exp(args):    return math.exp(float(args[0]))
def _builtin_log(args):    return math.log(float(args[0]))
def _builtin_log10(args):  return math.log10(float(args[0]))
def _builtin_sin(args):    return math.sin(float(args[0]))
def _builtin_cos(args):    return math.cos(float(args[0]))
def _builtin_tan(args):    return math.tan(float(args[0]))
def _builtin_asin(args):   return math.asin(float(args[0]))
def _builtin_acos(args):   return math.acos(float(args[0]))
def _builtin_atan(args):   return math.atan(float(args[0]))
def _builtin_atan2(args):  return math.atan2(float(args[0]), float(args[1]))
def _builtin_floor(args):  return math.floor(args[0])
def _builtin_ceiling(args):return math.ceil(args[0])
def _builtin_nint(args):   return round(args[0])
def _builtin_sign(args):   return abs(args[0]) * (1 if args[1] >= 0 else -1)
def _builtin_len(args):    return len(str(args[0]))
def _builtin_trim(args):   return str(args[0]).rstrip()
def _builtin_adjustl(args):return str(args[0]).lstrip()
def _builtin_adjustr(args):return str(args[0]).rstrip()
def _builtin_index(args):  return str(args[0]).find(str(args[1])) + 1
def _builtin_char(args):   return chr(int(args[0]))
def _builtin_ichar(args):  return ord(str(args[0])[0])
def _builtin_len_trim(args): return len(str(args[0]).rstrip())
def _builtin_sum(args):    a = args[0]; return sum(a) if isinstance(a, list) else a
def _builtin_size(args):   a = args[0]; return len(a) if isinstance(a, list) else 1
def _builtin_maxval(args): a = args[0]; return max(a) if isinstance(a, list) else a
def _builtin_minval(args): a = args[0]; return min(a) if isinstance(a, list) else a

BUILTINS: Dict[str, Any] = {
    'abs': _builtin_abs, 'int': _builtin_int, 'real': _builtin_real,
    'dble': _builtin_dble, 'mod': _builtin_mod, 'max': _builtin_max,
    'min': _builtin_min, 'sqrt': _builtin_sqrt, 'dsqrt': _builtin_sqrt,
    'exp': _builtin_exp,  'dexp': _builtin_exp,
    'log': _builtin_log,  'alog': _builtin_log,
    'log10': _builtin_log10, 'sin': _builtin_sin, 'dsin': _builtin_sin,
    'cos': _builtin_cos,  'dcos': _builtin_cos,
    'tan': _builtin_tan,  'asin': _builtin_asin,
    'acos': _builtin_acos, 'atan': _builtin_atan, 'atan2': _builtin_atan2,
    'floor': _builtin_floor, 'ceiling': _builtin_ceiling,
    'nint': _builtin_nint, 'sign': _builtin_sign,
    'len': _builtin_len, 'trim': _builtin_trim,
    'adjustl': _builtin_adjustl, 'adjustr': _builtin_adjustr,
    'index': _builtin_index, 'char': _builtin_char, 'ichar': _builtin_ichar,
    'len_trim': _builtin_len_trim, 'sum': _builtin_sum, 'size': _builtin_size,
    'maxval': _builtin_maxval, 'minval': _builtin_minval,
    'float': lambda a: float(a[0]), 'sngl': lambda a: float(a[0]),
    'idint': lambda a: int(a[0]),   'iabs': lambda a: abs(int(a[0])),
    'amax1': _builtin_max, 'amin1': _builtin_min,
    'amax0': _builtin_max, 'amin0': _builtin_min,
    'dim': lambda a: max(float(a[0]) - float(a[1]), 0.0),
    'dprod': lambda a: float(a[0]) * float(a[1]),
}


# ── Call frame ────────────────────────────────────────────────────────────────

class Frame:
    def __init__(self, unit: CompiledUnit, ret_addr: int, ret_frame: Optional['Frame']):
        self.unit     = unit
        self.ip       = 0               # instruction pointer into unit.code
        self.vars: Dict[str, Any] = {}  # local variable store
        self.ret_addr = ret_addr        # unused (stack-managed), kept for clarity
        self.ret_frame= ret_frame       # frame to return to

    def load(self, name: str) -> Any:
        if name in self.vars:
            return self.vars[name]
        # Implicit-type default
        return 0 if name[0] in 'ijklmn' else 0.0

    def store(self, name: str, value: Any):
        self.vars[name] = value


# ── Virtual Machine ───────────────────────────────────────────────────────────

class VirtualMachine:
    def __init__(self, module: BytecodeModule):
        self.module  = module
        self.stack: List[Any] = []    # operand stack
        self.frame: Optional[Frame] = None
        self._output: List[str] = []
        self._capture = False

    # ── Stack ops ─────────────────────────────────────────────────────────────

    def push(self, value: Any):
        self.stack.append(value)

    def pop(self) -> Any:
        if not self.stack:
            raise VMError("Stack underflow")
        return self.stack.pop()

    def peek(self) -> Any:
        return self.stack[-1]

    # ── Output ────────────────────────────────────────────────────────────────

    def _emit_output(self, text: str):
        if self._capture:
            self._output.append(text)
        else:
            print(text)

    # ── Run ───────────────────────────────────────────────────────────────────

    def run(self, capture: bool = False) -> str:
        self._capture = capture
        self._output  = []

        entry = self.module.units[self.module.entry]
        self.frame = Frame(entry, ret_addr=-1, ret_frame=None)

        self._execute()
        return '\n'.join(self._output)

    def _execute(self):
        while True:
            frame = self.frame
            if frame.ip >= len(frame.unit.code):
                break
            instr = frame.unit.code[frame.ip]
            frame.ip += 1
            cont = self._dispatch(instr)
            if cont is False:
                break

    def _dispatch(self, instr: Instruction) -> Optional[bool]:
        op  = instr.op
        arg = instr.arg

        # ── Constants ─────────────────────────────────────────────────────
        if op == Op.PUSH_INT:
            self.push(int(arg))
        elif op == Op.PUSH_REAL:
            self.push(float(arg))
        elif op == Op.PUSH_STR:
            self.push(str(arg))
        elif op == Op.PUSH_BOOL:
            self.push(bool(arg))

        # ── Variables ─────────────────────────────────────────────────────
        elif op == Op.LOAD:
            self.push(self.frame.load(arg))
        elif op == Op.STORE:
            self.frame.store(arg, self.pop())
        elif op == Op.LOAD_ARR:
            # Stack: [i1, i2, ...] (n indices already pushed)
            # arg = (name, ndim) or just name — we use 1-D for now
            name = arg
            idx = int(self.pop()) - 1   # 1-based → 0-based
            arr = self.frame.load(name)
            if isinstance(arr, list) and 0 <= idx < len(arr):
                self.push(arr[idx])
            else:
                self.push(0)
        elif op == Op.STORE_ARR:
            name = arg
            idx = int(self.pop()) - 1   # 1-based → 0-based
            value = self.pop()
            arr = self.frame.load(name)
            if not isinstance(arr, list):
                arr = []
                self.frame.store(name, arr)
            while len(arr) <= idx:
                arr.append(0)
            arr[idx] = value

        # ── Arithmetic ────────────────────────────────────────────────────
        elif op == Op.ADD:
            b, a = self.pop(), self.pop()
            self.push(a + b)
        elif op == Op.SUB:
            b, a = self.pop(), self.pop()
            self.push(a - b)
        elif op == Op.MUL:
            b, a = self.pop(), self.pop()
            self.push(a * b)
        elif op == Op.DIV:
            b, a = self.pop(), self.pop()
            if isinstance(a, int) and isinstance(b, int):
                self.push(a // b)   # integer division
            else:
                self.push(a / b)
        elif op == Op.POW:
            b, a = self.pop(), self.pop()
            self.push(a ** b)
        elif op == Op.NEG:
            self.push(-self.pop())
        elif op == Op.CONCAT:
            b, a = self.pop(), self.pop()
            self.push(str(a) + str(b))

        # ── Comparison ────────────────────────────────────────────────────
        elif op == Op.CMP_EQ:
            b, a = self.pop(), self.pop(); self.push(a == b)
        elif op == Op.CMP_NE:
            b, a = self.pop(), self.pop(); self.push(a != b)
        elif op == Op.CMP_LT:
            b, a = self.pop(), self.pop(); self.push(a < b)
        elif op == Op.CMP_LE:
            b, a = self.pop(), self.pop(); self.push(a <= b)
        elif op == Op.CMP_GT:
            b, a = self.pop(), self.pop(); self.push(a > b)
        elif op == Op.CMP_GE:
            b, a = self.pop(), self.pop(); self.push(a >= b)

        # ── Logical ───────────────────────────────────────────────────────
        elif op == Op.LOGICAL_AND:
            b, a = self.pop(), self.pop(); self.push(bool(a) and bool(b))
        elif op == Op.LOGICAL_OR:
            b, a = self.pop(), self.pop(); self.push(bool(a) or bool(b))
        elif op == Op.LOGICAL_NOT:
            self.push(not bool(self.pop()))

        # ── Control flow ──────────────────────────────────────────────────
        elif op == Op.JUMP:
            self.frame.ip = arg
        elif op == Op.JUMP_FALSE:
            if not bool(self.pop()):
                self.frame.ip = arg
        elif op == Op.JUMP_TRUE:
            if bool(self.pop()):
                self.frame.ip = arg

        # ── I/O ───────────────────────────────────────────────────────────
        elif op == Op.PRINT_NL:
            count = arg
            # Pop `count` values (they were pushed in order, so reverse)
            items = [self.pop() for _ in range(count)]
            items.reverse()
            parts = [self._fmt(v) for v in items]
            self._emit_output(' '.join(parts))
        elif op == Op.PRINT_VAL:
            pass  # unused for now

        # ── Array allocation ──────────────────────────────────────────────
        elif op == Op.ALLOC_ARR:
            name, ndim = arg
            sizes = [int(self.pop()) for _ in range(ndim)]
            sizes.reverse()
            total = 1
            for s in sizes:
                total *= s
            arr = [0] * total
            self.frame.store(name, arr)

        # ── Stack ops ─────────────────────────────────────────────────────
        elif op == Op.POP:
            if self.stack:
                self.pop()
        elif op == Op.DUP:
            self.push(self.peek())

        # ── Function / subroutine call ────────────────────────────────────
        elif op == Op.CALL_BUILTIN:
            fname, argc = arg
            args = [self.pop() for _ in range(argc)]
            args.reverse()
            fn = BUILTINS.get(fname)
            if fn:
                result = fn(args)
            else:
                result = 0
            self.push(result)

        elif op == Op.CALL:
            fname, argc = arg
            # Pop arguments
            call_args = [self.pop() for _ in range(argc)]
            call_args.reverse()

            unit = self.module.units.get(fname)
            if unit is None:
                # Unknown — push 0 as placeholder
                self.push(0)
                return

            new_frame = Frame(unit, ret_addr=self.frame.ip, ret_frame=self.frame)
            # Bind positional arguments to parameter names
            for pname, pval in zip(unit.params, call_args):
                new_frame.store(pname, pval)
            self.frame = new_frame

        elif op == Op.RETURN:
            parent = self.frame.ret_frame
            if parent is None:
                return False   # return from main → halt
            # Pass back out-parameter mutations by name
            self._sync_out_params(self.frame)
            self.frame = parent
            self.push(None)   # subroutines push None (caller discards it)

        elif op == Op.RETURN_VAL:
            ret_val = self.pop()
            parent = self.frame.ret_frame
            if parent is None:
                return False
            self._sync_out_params(self.frame)
            self.frame = parent
            self.push(ret_val)

        # ── Halt ──────────────────────────────────────────────────────────
        elif op == Op.HALT:
            return False

        return True

    def _sync_out_params(self, frame: Frame):
        """
        After a subroutine call, sync mutated parameters back to the caller's
        frame. We do this by name matching since we don't have explicit
        pass-by-reference in bytecode.
        """
        parent = frame.ret_frame
        if parent is None:
            return
        for pname in frame.unit.params:
            if pname in frame.vars:
                parent.store(pname, frame.vars[pname])

    def _fmt(self, v: Any) -> str:
        if isinstance(v, bool):
            return 'T' if v else 'F'
        if isinstance(v, float):
            if v == 0.0:
                return '0.000000'
            abs_v = abs(v)
            if 0.001 <= abs_v < 1e7:
                s = f'{v:.6f}'
                parts = s.split('.')
                dec = parts[1].rstrip('0') or '0'
                dec = dec.ljust(6, '0')[:6]
                return f'{parts[0]}.{dec}'
            return f'{v:.6E}'
        if isinstance(v, list):
            return ' '.join(self._fmt(x) for x in v)
        if v is None:
            return ''
        return str(v)
