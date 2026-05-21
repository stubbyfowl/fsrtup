"""
FortPy Interpreter — Tree-walking interpreter for the Fortran AST.
Supports the full subset parsed by the FortPy parser.
"""
import math
import sys
from typing import Any, Dict, List, Optional
from ast_nodes import *


class FortranError(Exception):
    pass

class StopException(Exception):
    def __init__(self, code=0):
        self.code = code

class ReturnException(Exception):
    def __init__(self, value=None):
        self.value = value

class GotoException(Exception):
    def __init__(self, label: int):
        self.label = label

class CycleException(Exception):
    pass

class ExitException(Exception):
    pass


# ── Built-in functions ────────────────────────────────────────────────────────
def _builtin_abs(args): return abs(args[0])
def _builtin_int(args): return int(args[0])
def _builtin_real(args): return float(args[0])
def _builtin_dble(args): return float(args[0])
def _builtin_mod(args): return args[0] % args[1]
def _builtin_max(args): return max(args)
def _builtin_min(args): return min(args)
def _builtin_sqrt(args): return math.sqrt(args[0])
def _builtin_exp(args): return math.exp(args[0])
def _builtin_log(args): return math.log(args[0])
def _builtin_log10(args): return math.log10(args[0])
def _builtin_sin(args): return math.sin(args[0])
def _builtin_cos(args): return math.cos(args[0])
def _builtin_tan(args): return math.tan(args[0])
def _builtin_asin(args): return math.asin(args[0])
def _builtin_acos(args): return math.acos(args[0])
def _builtin_atan(args): return math.atan(args[0])
def _builtin_atan2(args): return math.atan2(args[0], args[1])
def _builtin_floor(args): return math.floor(args[0])
def _builtin_ceiling(args): return math.ceil(args[0])
def _builtin_len(args): return len(str(args[0]))
def _builtin_trim(args): return str(args[0]).rstrip()
def _builtin_adjustl(args): return str(args[0]).lstrip()
def _builtin_adjustr(args): return str(args[0]).rstrip()
def _builtin_index(args): return str(args[0]).find(str(args[1])) + 1  # 1-based
def _builtin_char(args): return chr(int(args[0]))
def _builtin_ichar(args): return ord(str(args[0])[0])
def _builtin_nint(args): return round(args[0])
def _builtin_sign(args): return abs(args[0]) * (1 if args[1] >= 0 else -1)
def _builtin_sum(args):
    a = args[0]
    return sum(a.flatten() if hasattr(a, 'flatten') else a)
def _builtin_size(args):
    a = args[0]
    return len(a) if isinstance(a, list) else 1
def _builtin_maxval(args):
    a = args[0]
    return max(a) if isinstance(a, list) else a
def _builtin_minval(args):
    a = args[0]
    return min(a) if isinstance(a, list) else a

BUILTINS = {
    'abs': _builtin_abs, 'int': _builtin_int, 'real': _builtin_real,
    'dble': _builtin_dble, 'dexp': lambda a: math.exp(a[0]),
    'mod': _builtin_mod, 'max': _builtin_max, 'min': _builtin_min,
    'sqrt': _builtin_sqrt, 'dsqrt': _builtin_sqrt,
    'exp': _builtin_exp, 'log': _builtin_log, 'alog': _builtin_log,
    'log10': _builtin_log10, 'sin': _builtin_sin, 'dsin': _builtin_sin,
    'cos': _builtin_cos, 'dcos': _builtin_cos, 'tan': _builtin_tan,
    'asin': _builtin_asin, 'acos': _builtin_acos,
    'atan': _builtin_atan, 'atan2': _builtin_atan2,
    'floor': _builtin_floor, 'ceiling': _builtin_ceiling,
    'len': _builtin_len, 'trim': _builtin_trim,
    'adjustl': _builtin_adjustl, 'adjustr': _builtin_adjustr,
    'index': _builtin_index, 'char': _builtin_char, 'ichar': _builtin_ichar,
    'nint': _builtin_nint, 'sign': _builtin_sign,
    'sum': _builtin_sum, 'size': _builtin_size,
    'maxval': _builtin_maxval, 'minval': _builtin_minval,
    'float': lambda a: float(a[0]),
    'sngl': lambda a: float(a[0]),
    'idint': lambda a: int(a[0]),
    'iabs': lambda a: abs(int(a[0])),
    'amax1': _builtin_max, 'amin1': _builtin_min,
    'amax0': _builtin_max, 'amin0': _builtin_min,
    'dim': lambda a: max(a[0] - a[1], 0),
    'dprod': lambda a: float(a[0]) * float(a[1]),
    'len_trim': lambda a: len(str(a[0]).rstrip()),
}


# ── Environment / call stack ──────────────────────────────────────────────────
class Environment:
    def __init__(self, parent: Optional['Environment'] = None):
        self.vars: Dict[str, Any] = {}
        self.parent = parent

    def get(self, name: str) -> Any:
        name = name.lower()
        if name in self.vars:
            return self.vars[name]
        if self.parent:
            return self.parent.get(name)
        # Implicit typing: I-N = integer, else real
        if name[0] in 'ijklmn':
            return 0
        return 0.0

    def set(self, name: str, value: Any):
        self.vars[name.lower()] = value

    def set_local(self, name: str, value: Any):
        self.vars[name.lower()] = value


# ── Interpreter ───────────────────────────────────────────────────────────────
class Interpreter:
    def __init__(self):
        self.global_env = Environment()
        self.units: Dict[str, Any] = {}  # program units by name
        self._output_buffer: List[str] = []
        self._capture_output = False

    def load(self, cu: CompilationUnit):
        for unit in cu.units:
            name = unit.name.lower()
            self.units[name] = unit

    def run(self, capture_output: bool = False) -> str:
        self._capture_output = capture_output
        self._output_buffer = []
        main = (self.units.get('main') or
                next((u for u in self.units.values() if isinstance(u, Program)), None))
        if main is None:
            raise FortranError("No PROGRAM unit found")
        try:
            self._exec_unit(main, self.global_env)
        except StopException:
            pass
        return '\n'.join(self._output_buffer)

    def _exec_unit(self, unit: ProgramUnit, parent_env: Environment):
        env = Environment(parent=parent_env)
        for decl in unit.declarations:
            self._exec_decl(decl, env)
        self._exec_stmts(unit.body, env)

    def _exec_decl(self, decl: Any, env: Environment):
        if isinstance(decl, ImplicitNone):
            return
        if isinstance(decl, ParameterStmt):
            for name, expr in decl.assignments:
                env.set(name, self._eval(expr, env))
            return
        if isinstance(decl, VarDecl):
            for name in decl.names:
                if name in decl.dimensions:
                    dims = [int(self._eval(d, env)) for d in decl.dimensions[name]]
                    total = 1
                    for d in dims:
                        total *= d
                    if name not in env.vars:
                        default = self._type_default(decl.type_spec.name)
                        env.set(name, [default] * total)
                else:
                    if name not in env.vars:
                        env.set(name, self._type_default(decl.type_spec.name))
                if name in decl.initial_values:
                    env.set(name, self._eval(decl.initial_values[name], env))

    def _type_default(self, type_name: str) -> Any:
        if type_name == 'integer': return 0
        if type_name == 'logical': return False
        if type_name == 'character': return ''
        return 0.0  # real, double precision, complex

    def _exec_stmts(self, stmts: List[Any], env: Environment):
        label_map: Dict[int, int] = {}
        for i, s in enumerate(stmts):
            if isinstance(s, LabelStmt):
                label_map[s.label] = i
        i = 0
        while i < len(stmts):
            stmt = stmts[i]
            try:
                self._exec_stmt(stmt, env)
            except GotoException as g:
                if g.label in label_map:
                    i = label_map[g.label]
                    continue
                raise
            i += 1

    def _exec_stmt(self, stmt: Any, env: Environment):
        if stmt is None:
            return
        if isinstance(stmt, LabelStmt):
            self._exec_stmt(stmt.stmt, env)
        elif isinstance(stmt, AssignStmt):
            self._exec_assign(stmt, env)
        elif isinstance(stmt, PrintStmt):
            self._exec_print(stmt, env)
        elif isinstance(stmt, WriteStmt):
            self._exec_write(stmt, env)
        elif isinstance(stmt, ReadStmt):
            self._exec_read(stmt, env)
        elif isinstance(stmt, IfStmt):
            if self._eval(stmt.condition, env):
                self._exec_stmt(stmt.then_stmt, env)
        elif isinstance(stmt, IfBlock):
            self._exec_if_block(stmt, env)
        elif isinstance(stmt, DoLoop):
            self._exec_do(stmt, env)
        elif isinstance(stmt, CallStmt):
            self._exec_call(stmt, env)
        elif isinstance(stmt, GotoStmt):
            raise GotoException(stmt.label)
        elif isinstance(stmt, ContinueStmt):
            pass
        elif isinstance(stmt, ReturnStmt):
            raise ReturnException()
        elif isinstance(stmt, StopStmt):
            code = self._eval(stmt.code, env) if stmt.code else 0
            raise StopException(code)
        elif isinstance(stmt, CycleStmt):
            raise CycleException()
        elif isinstance(stmt, ExitStmt):
            raise ExitException()
        elif isinstance(stmt, (VarDecl, ImplicitNone, ParameterStmt)):
            self._exec_decl(stmt, env)

    def _exec_assign(self, stmt: AssignStmt, env: Environment):
        value = self._eval(stmt.value, env)
        target = stmt.target
        if isinstance(target, Identifier):
            env.set(target.name, value)
        elif isinstance(target, ArrayRef):
            arr = env.get(target.name)
            if not isinstance(arr, list):
                arr = []
                env.set(target.name, arr)
            idx = self._array_index(target.indices, env)
            while len(arr) <= idx:
                arr.append(0)
            arr[idx] = value

    def _array_index(self, indices: List[Any], env: Environment) -> int:
        vals = [int(self._eval(i, env)) - 1 for i in indices]
        return vals[0] if len(vals) == 1 else vals[0]

    def _exec_if_block(self, stmt: IfBlock, env: Environment):
        if self._eval(stmt.condition, env):
            self._exec_stmts(stmt.then_body, env)
            return
        for cond, body in stmt.elseif_clauses:
            if self._eval(cond, env):
                self._exec_stmts(body, env)
                return
        if stmt.else_body is not None:
            self._exec_stmts(stmt.else_body, env)

    def _exec_do(self, stmt: DoLoop, env: Environment):
        # DO WHILE
        if stmt.condition is not None:
            while self._eval(stmt.condition, env):
                try:
                    self._exec_stmts(stmt.body, env)
                except CycleException:
                    continue
                except ExitException:
                    break
            return
        # Infinite DO
        if stmt.var is None:
            while True:
                try:
                    self._exec_stmts(stmt.body, env)
                except CycleException:
                    continue
                except ExitException:
                    break
            return
        # Counted DO
        start = self._eval(stmt.start, env)
        stop = self._eval(stmt.stop, env)
        step = self._eval(stmt.step, env) if stmt.step else 1
        env.set(stmt.var, start)
        val = start
        while (step > 0 and val <= stop) or (step < 0 and val >= stop):
            env.set(stmt.var, val)
            try:
                self._exec_stmts(stmt.body, env)
            except CycleException:
                pass
            except ExitException:
                break
            val += step

    def _exec_print(self, stmt: PrintStmt, env: Environment):
        items = [self._eval(item, env) for item in stmt.items]
        line = self._format_output(stmt.fmt, items)
        self._emit(line)

    def _exec_write(self, stmt: WriteStmt, env: Environment):
        items = [self._eval(item, env) for item in stmt.items]
        line = self._format_output(stmt.fmt, items)
        unit = self._eval(stmt.unit, env)
        if str(unit) in ('6', '*'):
            self._emit(line)

    def _exec_read(self, stmt: ReadStmt, env: Environment):
        try:
            line = input()
        except EOFError:
            return
        parts = line.split()
        for i, item in enumerate(stmt.items):
            if i < len(parts):
                if isinstance(item, Identifier):
                    cur = env.get(item.name)
                    if isinstance(cur, int):
                        env.set(item.name, int(parts[i]))
                    elif isinstance(cur, float):
                        env.set(item.name, float(parts[i]))
                    else:
                        env.set(item.name, parts[i])
                elif isinstance(item, ArrayRef):
                    arr = env.get(item.name)
                    idx = self._array_index(item.indices, env)
                    if isinstance(arr, list) and idx < len(arr):
                        arr[idx] = float(parts[i]) if '.' in parts[i] else int(parts[i])

    def _exec_call(self, stmt: CallStmt, env: Environment):
        name = stmt.name.lower()
        if name in self.units:
            unit = self.units[name]
            call_env = Environment(parent=self.global_env)
            if isinstance(unit, Subroutine):
                for param, arg in zip(unit.params, stmt.args):
                    call_env.set(param, self._eval(arg, env))
            for decl in unit.declarations:
                self._exec_decl(decl, call_env)
            try:
                self._exec_stmts(unit.body, call_env)
            except ReturnException:
                pass
            # Copy back out parameters
            if isinstance(unit, Subroutine):
                for param, arg in zip(unit.params, stmt.args):
                    if isinstance(arg, Identifier):
                        env.set(arg.name, call_env.get(param))

    def _format_output(self, fmt: Any, items: List[Any]) -> str:
        if fmt == '*' or fmt is None:
            parts = [self._fmt_value(item) for item in items]
            return ' '.join(parts)
        if isinstance(fmt, str):
            return ' '.join(self._fmt_value(i) for i in items)
        return ' '.join(self._fmt_value(i) for i in items)

    def _fmt_value(self, v: Any) -> str:
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
            return ' '.join(self._fmt_value(x) for x in v)
        return str(v)

    def _emit(self, text: str):
        if self._capture_output:
            self._output_buffer.append(text)
        else:
            print(text)

    # ── Expression evaluator ──────────────────────────────────────────────────
    def _eval(self, node: Any, env: Environment) -> Any:
        if node is None:
            return None
        if isinstance(node, IntLiteral):
            return node.value
        if isinstance(node, RealLiteral):
            return node.value
        if isinstance(node, StringLiteral):
            return node.value
        if isinstance(node, LogicalLiteral):
            return node.value
        if isinstance(node, Identifier):
            return env.get(node.name)
        if isinstance(node, ArrayRef):
            arr = env.get(node.name)
            if isinstance(arr, list):
                idx = self._array_index(node.indices, env)
                return arr[idx] if idx < len(arr) else 0
            return arr
        if isinstance(node, UnaryOp):
            val = self._eval(node.operand, env)
            if node.op == '-':
                return -val
            if node.op in ('.NOT.', 'not'):
                return not val
            return val
        if isinstance(node, BinOp):
            return self._eval_binop(node, env)
        if isinstance(node, FunctionCall):
            return self._eval_call(node, env)
        return 0

    def _eval_binop(self, node: BinOp, env: Environment) -> Any:
        op = node.op
        if op == '.AND.':
            return bool(self._eval(node.left, env)) and bool(self._eval(node.right, env))
        if op == '.OR.':
            return bool(self._eval(node.left, env)) or bool(self._eval(node.right, env))
        left = self._eval(node.left, env)
        right = self._eval(node.right, env)
        if op == '+': return left + right
        if op == '-': return left - right
        if op == '*': return left * right
        if op == '/':
            if isinstance(left, int) and isinstance(right, int):
                return left // right
            return left / right
        if op == '**': return left ** right
        if op == '//': return str(left) + str(right)
        if op in ('==', '.EQ.'): return left == right
        if op in ('/=', '.NE.'): return left != right
        if op in ('<', '.LT.'): return left < right
        if op in ('<=', '.LE.'): return left <= right
        if op in ('>', '.GT.'): return left > right
        if op in ('>=', '.GE.'): return left >= right
        return 0

    def _eval_call(self, node: FunctionCall, env: Environment) -> Any:
        name = node.name.lower()
        args = [self._eval(a, env) for a in node.args]

        if name in BUILTINS:
            return BUILTINS[name](args)

        # Check if this is actually an array access
        val = env.get(name)
        if isinstance(val, list):
            if args:
                idx = int(args[0]) - 1  # 1-based to 0-based
                return val[idx] if 0 <= idx < len(val) else 0
            return val

        # User-defined function
        if name in self.units:
            unit = self.units[name]
            call_env = Environment(parent=self.global_env)
            if isinstance(unit, Function):
                for param, arg in zip(unit.params, args):
                    call_env.set(param, arg)
                ret_default = 0 if name[0] in 'ijklmn' else 0.0
                if unit.return_type:
                    ret_default = self._type_default(unit.return_type.name)
                call_env.set(name, ret_default)
                for decl in unit.declarations:
                    self._exec_decl(decl, call_env)
                try:
                    self._exec_stmts(unit.body, call_env)
                except ReturnException:
                    pass
                return call_env.get(name)

        return 0
