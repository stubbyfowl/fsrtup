"""
FortPy AST — Abstract Syntax Tree node definitions
"""
from dataclasses import dataclass, field
from typing import List, Optional, Any, Union


# ── Base ──────────────────────────────────────────────────────────────────────
@dataclass
class Node:
    """Base AST node."""
    pass


# ── Types ─────────────────────────────────────────────────────────────────────
@dataclass
class TypeSpec(Node):
    name: str  # 'integer', 'real', 'logical', 'character', 'double precision'
    kind: Optional[Any] = None
    length: Optional[Any] = None  # for CHARACTER*(n)
    line: int = 0


# ── Expressions ───────────────────────────────────────────────────────────────
@dataclass
class IntLiteral(Node):
    value: int
    line: int = 0

@dataclass
class RealLiteral(Node):
    value: float
    line: int = 0

@dataclass
class StringLiteral(Node):
    value: str
    line: int = 0

@dataclass
class LogicalLiteral(Node):
    value: bool
    line: int = 0

@dataclass
class Identifier(Node):
    name: str
    line: int = 0

@dataclass
class ArrayRef(Node):
    name: str
    indices: List[Any]
    line: int = 0

@dataclass
class BinOp(Node):
    op: str
    left: Any
    right: Any
    line: int = 0

@dataclass
class UnaryOp(Node):
    op: str
    operand: Any
    line: int = 0

@dataclass
class FunctionCall(Node):
    name: str
    args: List[Any]
    line: int = 0


# ── Statements ────────────────────────────────────────────────────────────────
@dataclass
class AssignStmt(Node):
    target: Any  # Identifier or ArrayRef
    value: Any
    line: int = 0

@dataclass
class PrintStmt(Node):
    fmt: Any  # '*' or format string or label
    items: List[Any]
    line: int = 0

@dataclass
class WriteStmt(Node):
    unit: Any
    fmt: Any
    items: List[Any]
    line: int = 0

@dataclass
class ReadStmt(Node):
    unit: Any
    fmt: Any
    items: List[Any]
    line: int = 0

@dataclass
class IfStmt(Node):
    """Single-line IF."""
    condition: Any
    then_stmt: Any
    line: int = 0

@dataclass
class IfBlock(Node):
    """IF ... THEN / ELSEIF / ELSE / END IF block."""
    condition: Any
    then_body: List[Any]
    elseif_clauses: List[Any]  # list of (condition, body)
    else_body: Optional[List[Any]]
    line: int = 0

@dataclass
class DoLoop(Node):
    var: Optional[str]   # None for DO WHILE
    start: Optional[Any]
    stop: Optional[Any]
    step: Optional[Any]
    condition: Optional[Any]  # for DO WHILE
    body: List[Any]
    label: Optional[int] = None
    line: int = 0

@dataclass
class GotoStmt(Node):
    label: int
    line: int = 0

@dataclass
class LabelStmt(Node):
    label: int
    stmt: Any
    line: int = 0

@dataclass
class ContinueStmt(Node):
    line: int = 0

@dataclass
class ReturnStmt(Node):
    line: int = 0

@dataclass
class StopStmt(Node):
    code: Optional[Any] = None
    line: int = 0

@dataclass
class CallStmt(Node):
    name: str
    args: List[Any]
    line: int = 0

@dataclass
class CycleStmt(Node):
    line: int = 0

@dataclass
class ExitStmt(Node):
    line: int = 0


# ── Declarations ──────────────────────────────────────────────────────────────
@dataclass
class VarDecl(Node):
    type_spec: TypeSpec
    names: List[str]
    dimensions: dict = field(default_factory=dict)  # name -> [dim_expr, ...]
    initial_values: dict = field(default_factory=dict)
    is_parameter: bool = False
    intent: Optional[str] = None
    line: int = 0

@dataclass
class ImplicitNone(Node):
    line: int = 0

@dataclass
class ParameterStmt(Node):
    assignments: List[Any]  # list of (name, expr)
    line: int = 0


# ── Program Units ─────────────────────────────────────────────────────────────
@dataclass
class ProgramUnit(Node):
    name: str
    body: List[Any]
    declarations: List[Any]
    line: int = 0

@dataclass
class Program(ProgramUnit):
    pass

@dataclass
class Subroutine(ProgramUnit):
    params: List[str] = field(default_factory=list)

@dataclass
class Function(ProgramUnit):
    params: List[str] = field(default_factory=list)
    return_type: Optional[TypeSpec] = None

@dataclass
class Module(ProgramUnit):
    pass

@dataclass
class CompilationUnit(Node):
    units: List[Any]
    line: int = 0
