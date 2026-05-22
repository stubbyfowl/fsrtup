"""
FortPy Semantic Analyzer
Builds a symbol table, resolves types, checks declarations, and
annotates the AST. Produces no output — only validates.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from ast_nodes import *


class SemanticError(Exception):
    def __init__(self, message: str, line: int = 0):
        super().__init__(f"Semantic error at line {line}: {message}")
        self.line = line


# ── Symbol ────────────────────────────────────────────────────────────────────

@dataclass
class Symbol:
    name: str
    type_name: str          # 'integer', 'real', 'logical', 'character', 'double precision'
    is_array: bool = False
    dimensions: List[int] = field(default_factory=list)   # sizes per dimension
    is_parameter: bool = False
    is_function: bool = False
    is_subroutine: bool = False
    intent: Optional[str] = None
    value: Any = None       # for PARAMETERs (compile-time constants)


# ── Scope ─────────────────────────────────────────────────────────────────────

class Scope:
    def __init__(self, name: str, parent: Optional['Scope'] = None):
        self.name = name
        self.parent = parent
        self.symbols: Dict[str, Symbol] = {}

    def define(self, sym: Symbol):
        self.symbols[sym.name.lower()] = sym

    def lookup(self, name: str) -> Optional[Symbol]:
        name = name.lower()
        if name in self.symbols:
            return self.symbols[name]
        if self.parent:
            return self.parent.lookup(name)
        return None

    def lookup_local(self, name: str) -> Optional[Symbol]:
        return self.symbols.get(name.lower())


# ── Built-in function signatures ──────────────────────────────────────────────

BUILTIN_RETURN_TYPES = {
    'abs': 'real', 'int': 'integer', 'real': 'real', 'dble': 'real',
    'mod': 'integer', 'max': 'real', 'min': 'real',
    'sqrt': 'real', 'exp': 'real', 'log': 'real', 'log10': 'real',
    'sin': 'real', 'cos': 'real', 'tan': 'real',
    'asin': 'real', 'acos': 'real', 'atan': 'real', 'atan2': 'real',
    'floor': 'integer', 'ceiling': 'integer', 'nint': 'integer',
    'sign': 'real', 'len': 'integer', 'trim': 'character',
    'adjustl': 'character', 'adjustr': 'character',
    'index': 'integer', 'char': 'character', 'ichar': 'integer',
    'len_trim': 'integer', 'sum': 'real', 'size': 'integer',
    'maxval': 'real', 'minval': 'real',
    'dsqrt': 'real', 'dsin': 'real', 'dcos': 'real', 'dexp': 'real',
    'float': 'real', 'sngl': 'real', 'idint': 'integer',
    'iabs': 'integer', 'amax1': 'real', 'amin1': 'real',
    'dprod': 'real', 'dim': 'real',
}


def implicit_type(name: str) -> str:
    """Fortran implicit typing: I-N => integer, else real."""
    return 'integer' if name[0].lower() in 'ijklmn' else 'real'


# ── Analyzer ──────────────────────────────────────────────────────────────────

class SemanticAnalyzer:
    def __init__(self):
        self.global_scope = Scope('__global__')
        self.errors: List[str] = []
        self.implicit_none: bool = False

    def analyze(self, cu: CompilationUnit):
        # First pass: register all program unit names
        for unit in cu.units:
            if isinstance(unit, Subroutine):
                sym = Symbol(name=unit.name, type_name='void', is_subroutine=True)
                self.global_scope.define(sym)
            elif isinstance(unit, Function):
                ret = unit.return_type.name if unit.return_type else implicit_type(unit.name)
                sym = Symbol(name=unit.name, type_name=ret, is_function=True)
                self.global_scope.define(sym)

        # Second pass: analyze each unit
        for unit in cu.units:
            self._analyze_unit(unit)

    def _analyze_unit(self, unit: ProgramUnit):
        scope = Scope(unit.name, parent=self.global_scope)
        self.implicit_none = False

        # Check IMPLICIT NONE
        for decl in unit.declarations:
            if isinstance(decl, ImplicitNone):
                self.implicit_none = True

        # Register parameters (function/subroutine arguments)
        params = getattr(unit, 'params', [])
        for p in params:
            # Type determined by declarations below; pre-register with implicit type
            scope.define(Symbol(name=p, type_name=implicit_type(p)))

        # Process declarations
        for decl in unit.declarations:
            self._analyze_decl(decl, scope)

        # Analyze body statements
        for stmt in unit.body:
            self._analyze_stmt(stmt, scope)

    def _analyze_decl(self, decl: Any, scope: Scope):
        if isinstance(decl, ImplicitNone):
            return
        if isinstance(decl, ParameterStmt):
            for name, expr in decl.assignments:
                sym = scope.lookup(name)
                if sym is None:
                    type_name = implicit_type(name)
                    sym = Symbol(name=name, type_name=type_name, is_parameter=True)
                    scope.define(sym)
                sym.is_parameter = True
            return
        if isinstance(decl, VarDecl):
            type_name = decl.type_spec.name
            for name in decl.names:
                dims = []
                if name in decl.dimensions:
                    # Evaluate constant dimension sizes
                    for d in decl.dimensions[name]:
                        if isinstance(d, IntLiteral):
                            dims.append(d.value)
                        else:
                            dims.append(-1)  # dynamic / unknown at compile time
                sym = Symbol(
                    name=name,
                    type_name=type_name,
                    is_array=bool(dims),
                    dimensions=dims,
                    is_parameter=decl.is_parameter,
                    intent=decl.intent,
                )
                scope.define(sym)

    def _analyze_stmt(self, stmt: Any, scope: Scope):
        if stmt is None:
            return
        if isinstance(stmt, LabelStmt):
            self._analyze_stmt(stmt.stmt, scope)
        elif isinstance(stmt, AssignStmt):
            self._check_expr(stmt.value, scope)
        elif isinstance(stmt, PrintStmt):
            for item in stmt.items:
                self._check_expr(item, scope)
        elif isinstance(stmt, WriteStmt):
            for item in stmt.items:
                self._check_expr(item, scope)
        elif isinstance(stmt, IfStmt):
            self._check_expr(stmt.condition, scope)
            self._analyze_stmt(stmt.then_stmt, scope)
        elif isinstance(stmt, IfBlock):
            self._check_expr(stmt.condition, scope)
            for s in stmt.then_body:
                self._analyze_stmt(s, scope)
            for cond, body in stmt.elseif_clauses:
                self._check_expr(cond, scope)
                for s in body:
                    self._analyze_stmt(s, scope)
            if stmt.else_body:
                for s in stmt.else_body:
                    self._analyze_stmt(s, scope)
        elif isinstance(stmt, DoLoop):
            if stmt.var:
                # Ensure loop variable exists
                if scope.lookup(stmt.var) is None:
                    scope.define(Symbol(name=stmt.var, type_name='integer'))
            for s in stmt.body:
                self._analyze_stmt(s, scope)
        elif isinstance(stmt, CallStmt):
            for arg in stmt.args:
                self._check_expr(arg, scope)
        elif isinstance(stmt, (VarDecl, ImplicitNone, ParameterStmt)):
            self._analyze_decl(stmt, scope)

    def _check_expr(self, expr: Any, scope: Scope):
        if expr is None:
            return
        if isinstance(expr, Identifier):
            name = expr.name.lower()
            if name in BUILTIN_RETURN_TYPES:
                return
            sym = scope.lookup(name)
            if sym is None and self.implicit_none:
                self.errors.append(
                    f"Line {expr.line}: undeclared variable '{name}' (IMPLICIT NONE active)")
        elif isinstance(expr, (BinOp, UnaryOp)):
            self._check_expr(getattr(expr, 'left', None), scope)
            self._check_expr(getattr(expr, 'right', None), scope)
            self._check_expr(getattr(expr, 'operand', None), scope)
        elif isinstance(expr, FunctionCall):
            for arg in expr.args:
                self._check_expr(arg, scope)
        elif isinstance(expr, ArrayRef):
            for idx in expr.indices:
                self._check_expr(idx, scope)

    def type_of(self, expr: Any, scope: Scope) -> str:
        """Infer the type of an expression."""
        if isinstance(expr, IntLiteral):
            return 'integer'
        if isinstance(expr, RealLiteral):
            return 'real'
        if isinstance(expr, StringLiteral):
            return 'character'
        if isinstance(expr, LogicalLiteral):
            return 'logical'
        if isinstance(expr, Identifier):
            sym = scope.lookup(expr.name)
            return sym.type_name if sym else implicit_type(expr.name)
        if isinstance(expr, FunctionCall):
            name = expr.name.lower()
            if name in BUILTIN_RETURN_TYPES:
                return BUILTIN_RETURN_TYPES[name]
            sym = scope.lookup(name)
            return sym.type_name if sym else implicit_type(name)
        if isinstance(expr, BinOp):
            lt = self.type_of(expr.left, scope)
            rt = self.type_of(expr.right, scope)
            if 'real' in (lt, rt) or 'double precision' in (lt, rt):
                return 'real'
            return lt
        if isinstance(expr, UnaryOp):
            return self.type_of(expr.operand, scope)
        return 'real'
