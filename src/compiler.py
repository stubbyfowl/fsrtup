"""
FortPy Compiler — AST → Bytecode

This is the actual compiler. It traverses the AST and EMITS instructions
into a flat bytecode stream. It does NOT evaluate anything at compile time
(except constant folding for simple literals).

Each AST visitor method calls emit() to write instructions.
No Python values are computed here — only instructions are generated.
"""

from typing import List, Dict, Optional, Any
from ast_nodes import *
from bytecode import Op, Instruction, CompiledUnit, BytecodeModule
from semantic import SemanticAnalyzer, Scope, Symbol, implicit_type, BUILTIN_RETURN_TYPES


class CompileError(Exception):
    def __init__(self, message: str, line: int = 0):
        super().__init__(f"Compile error at line {line}: {message}")
        self.line = line


class Compiler:
    """
    Translates a CompilationUnit AST into a BytecodeModule.

    The compiler traverses the AST exactly once. For each statement
    and expression it emits bytecode instructions via self.emit().
    No runtime values are computed here.
    """

    def __init__(self):
        self._code: List[Instruction] = []
        self._unit: Optional[CompiledUnit] = None
        self._units: Dict[str, CompiledUnit] = {}
        self._label_counter = 0
        self._label_targets: Dict[int, int] = {}  # label number → instruction index
        self._pending_patches: Dict[int, List[int]] = {}  # label → list of instr indices to patch
        self._loop_exit_labels: List[int] = []   # stack of loop exit labels (for EXIT)
        self._loop_cont_labels: List[int] = []   # stack of loop continue labels (for CYCLE)
        self._scope: Optional[Scope] = None
        self._semantic: SemanticAnalyzer = SemanticAnalyzer()

    # ── Emission helpers ──────────────────────────────────────────────────────

    def emit(self, op: Op, arg: Any = None, comment: str = '') -> int:
        """Append an instruction and return its index."""
        idx = len(self._code)
        self._code.append(Instruction(op, arg, comment))
        return idx

    def current_addr(self) -> int:
        return len(self._code)

    def new_label(self) -> int:
        self._label_counter += 1
        return self._label_counter

    def place_label(self, label: int):
        """Mark current position as the target of `label`."""
        addr = self.current_addr()
        self._label_targets[label] = addr
        # Patch all forward jumps that referenced this label
        if label in self._pending_patches:
            for instr_idx in self._pending_patches.pop(label):
                self._code[instr_idx].arg = addr

    def emit_jump(self, op: Op, label: int, comment: str = '') -> int:
        """Emit a jump to a (possibly not yet placed) label."""
        idx = self.emit(op, label, comment)   # arg is label, will be patched
        addr = self._label_targets.get(label)
        if addr is not None:
            self._code[idx].arg = addr        # already placed → patch immediately
        else:
            self._pending_patches.setdefault(label, []).append(idx)
        return idx

    def patch_jump(self, instr_idx: int, target_addr: int):
        """Retroactively fix a jump instruction's target."""
        self._code[instr_idx].arg = target_addr

    # ── Entry point ───────────────────────────────────────────────────────────

    def compile(self, cu: CompilationUnit) -> BytecodeModule:
        # Run semantic analysis first
        self._semantic.analyze(cu)
        if self._semantic.errors:
            for e in self._semantic.errors:
                print(f"Warning: {e}")

        entry_name = None
        for unit in cu.units:
            self._compile_unit(unit)
            if isinstance(unit, Program) and entry_name is None:
                entry_name = unit.name.lower()

        if entry_name is None:
            # Implicit main
            entry_name = next(iter(self._units))

        return BytecodeModule(units=self._units, entry=entry_name)

    # ── Compile a program unit ────────────────────────────────────────────────

    def _compile_unit(self, unit: ProgramUnit):
        name = unit.name.lower()
        params = [p.lower() for p in getattr(unit, 'params', [])]
        is_func = isinstance(unit, Function)

        compiled = CompiledUnit(name=name, params=params, is_function=is_func)
        self._unit = compiled
        self._units[name] = compiled
        self._code = compiled.code

        # Build scope for this unit
        self._scope = Scope(name, parent=self._semantic.global_scope)
        for p in params:
            self._scope.define(Symbol(name=p, type_name=implicit_type(p)))

        # Process declarations — emit ALLOC_ARR for arrays
        for decl in unit.declarations:
            self._compile_decl(decl)

        # Compile body statements
        for stmt in unit.body:
            self._compile_stmt(stmt)

        # Implicit RETURN / HALT at end
        if isinstance(unit, Program):
            self.emit(Op.HALT, comment='end of program')
        else:
            if is_func:
                # Load return variable (same name as function) and return it
                self.emit(Op.LOAD, name, comment='implicit return value')
                self.emit(Op.RETURN_VAL)
            else:
                self.emit(Op.RETURN)

    # ── Declarations ──────────────────────────────────────────────────────────

    def _compile_decl(self, decl: Any):
        if isinstance(decl, (ImplicitNone, ParameterStmt)):
            return   # compile-time only; no runtime code needed
        if not isinstance(decl, VarDecl):
            return

        type_name = decl.type_spec.name
        for name in decl.names:
            lname = name.lower()
            self._scope.define(Symbol(
                name=lname,
                type_name=type_name,
                is_array=lname in decl.dimensions,
                intent=decl.intent,
            ))
            if lname in decl.dimensions:
                # Emit dimension sizes onto stack, then ALLOC_ARR
                dims = decl.dimensions[lname]
                for d in dims:
                    self._compile_expr(d)
                self.emit(Op.ALLOC_ARR, (lname, len(dims)),
                          comment=f'allocate {lname}({", ".join("?" for _ in dims)})')
            elif lname in decl.initial_values:
                self._compile_expr(decl.initial_values[lname])
                self.emit(Op.STORE, lname, comment=f'init {lname}')

    # ── Statements ────────────────────────────────────────────────────────────

    def _compile_stmt(self, stmt: Any):
        if stmt is None:
            return

        if isinstance(stmt, LabelStmt):
            # Map Fortran source label → current bytecode address
            self._label_targets[stmt.label] = self.current_addr()
            if stmt.label in self._pending_patches:
                for idx in self._pending_patches.pop(stmt.label):
                    self._code[idx].arg = self.current_addr()
            self._compile_stmt(stmt.stmt)

        elif isinstance(stmt, AssignStmt):
            self._compile_assign(stmt)

        elif isinstance(stmt, PrintStmt):
            self._compile_print(stmt)

        elif isinstance(stmt, WriteStmt):
            self._compile_write(stmt)

        elif isinstance(stmt, ReadStmt):
            pass   # TODO: READ from stdin (deferred)

        elif isinstance(stmt, IfStmt):
            self._compile_if_stmt(stmt)

        elif isinstance(stmt, IfBlock):
            self._compile_if_block(stmt)

        elif isinstance(stmt, DoLoop):
            self._compile_do(stmt)

        elif isinstance(stmt, GotoStmt):
            self.emit_jump(Op.JUMP, stmt.label, comment=f'goto {stmt.label}')

        elif isinstance(stmt, ContinueStmt):
            pass   # no-op in bytecode (label target already handled)

        elif isinstance(stmt, ReturnStmt):
            if self._unit and self._unit.is_function:
                self.emit(Op.LOAD, self._unit.name, comment='return value')
                self.emit(Op.RETURN_VAL)
            else:
                self.emit(Op.RETURN)

        elif isinstance(stmt, StopStmt):
            if stmt.code:
                self._compile_expr(stmt.code)
                self.emit(Op.POP)
            self.emit(Op.HALT, comment='STOP')

        elif isinstance(stmt, CallStmt):
            self._compile_call_stmt(stmt)

        elif isinstance(stmt, CycleStmt):
            if self._loop_cont_labels:
                self.emit_jump(Op.JUMP, self._loop_cont_labels[-1], comment='CYCLE')

        elif isinstance(stmt, ExitStmt):
            if self._loop_exit_labels:
                self.emit_jump(Op.JUMP, self._loop_exit_labels[-1], comment='EXIT')

        elif isinstance(stmt, (VarDecl, ImplicitNone, ParameterStmt)):
            self._compile_decl(stmt)

    # ── Assignment ────────────────────────────────────────────────────────────

    def _compile_assign(self, stmt: AssignStmt):
        """Compile: target = expr"""
        self._compile_expr(stmt.value)

        target = stmt.target
        if isinstance(target, Identifier):
            self.emit(Op.STORE, target.name.lower(),
                      comment=f'{target.name} =')
        elif isinstance(target, ArrayRef):
            # Stack before STORE_ARR: [..., value, idx1, idx2, ...]
            # We already have value on stack; now push indices
            for idx_expr in target.indices:
                self._compile_expr(idx_expr)
            self.emit(Op.STORE_ARR, target.name.lower(),
                      comment=f'{target.name}(...) =')

    # ── Print ─────────────────────────────────────────────────────────────────

    def _compile_print(self, stmt: PrintStmt):
        """PRINT *, item1, item2, ..."""
        count = len(stmt.items)
        for item in stmt.items:
            self._compile_expr(item)
        self.emit(Op.PRINT_NL, count, comment='PRINT *')

    def _compile_write(self, stmt: WriteStmt):
        count = len(stmt.items)
        for item in stmt.items:
            self._compile_expr(item)
        self.emit(Op.PRINT_NL, count, comment='WRITE')

    # ── IF ────────────────────────────────────────────────────────────────────

    def _compile_if_stmt(self, stmt: IfStmt):
        """Single-line IF (cond) stmt"""
        self._compile_expr(stmt.condition)
        skip_label = self.new_label()
        self.emit_jump(Op.JUMP_FALSE, skip_label, comment='if false, skip')
        self._compile_stmt(stmt.then_stmt)
        self.place_label(skip_label)

    def _compile_if_block(self, stmt: IfBlock):
        """IF (...) THEN / ELSEIF / ELSE / END IF"""
        end_label = self.new_label()

        # IF condition
        self._compile_expr(stmt.condition)
        next_label = self.new_label()
        self.emit_jump(Op.JUMP_FALSE, next_label, comment='if false → next branch')

        # THEN body
        for s in stmt.then_body:
            self._compile_stmt(s)
        self.emit_jump(Op.JUMP, end_label, comment='jump to end if')

        # ELSEIF clauses
        for elif_cond, elif_body in stmt.elseif_clauses:
            self.place_label(next_label)
            next_label = self.new_label()
            self._compile_expr(elif_cond)
            self.emit_jump(Op.JUMP_FALSE, next_label, comment='elseif false → next')
            for s in elif_body:
                self._compile_stmt(s)
            self.emit_jump(Op.JUMP, end_label, comment='jump to end if')

        # ELSE body
        self.place_label(next_label)
        if stmt.else_body:
            for s in stmt.else_body:
                self._compile_stmt(s)

        self.place_label(end_label)

    # ── DO loops ──────────────────────────────────────────────────────────────

    def _compile_do(self, stmt: DoLoop):
        exit_label = self.new_label()
        cont_label = self.new_label()
        self._loop_exit_labels.append(exit_label)
        self._loop_cont_labels.append(cont_label)

        if stmt.condition is not None:
            # DO WHILE (cond)
            loop_top = self.new_label()
            self.place_label(loop_top)
            self._compile_expr(stmt.condition)
            self.emit_jump(Op.JUMP_FALSE, exit_label, comment='do while: exit if false')
            for s in stmt.body:
                self._compile_stmt(s)
            self.place_label(cont_label)
            self.emit_jump(Op.JUMP, loop_top, comment='do while: loop back')

        elif stmt.var is None:
            # Infinite DO
            loop_top = self.new_label()
            self.place_label(loop_top)
            for s in stmt.body:
                self._compile_stmt(s)
            self.place_label(cont_label)
            self.emit_jump(Op.JUMP, loop_top, comment='infinite do: loop back')

        else:
            # Counted DO var = start, stop [, step]
            var = stmt.var.lower()

            # Initialise loop variable
            self._compile_expr(stmt.start)
            self.emit(Op.STORE, var, comment=f'do {var} = start')

            # Compile stop and step — store in hidden temps
            stop_var  = f'__stop_{var}__'
            step_var  = f'__step_{var}__'
            self._compile_expr(stmt.stop)
            self.emit(Op.STORE, stop_var, comment='do stop')
            if stmt.step:
                self._compile_expr(stmt.step)
            else:
                self.emit(Op.PUSH_INT, 1, comment='default step = 1')
            self.emit(Op.STORE, step_var, comment='do step')

            # Loop test: if step > 0: var <= stop; if step < 0: var >= stop
            loop_top = self.new_label()
            self.place_label(loop_top)

            # Condition: (step > 0 AND var <= stop) OR (step <= 0 AND var >= stop)
            # Simplified: emit (var - stop) * sign(step) <= 0
            # For correctness emit both branches:
            #   load step; PUSH 0; CMP_GT → if true: load var <= stop, else var >= stop
            step_pos_label = self.new_label()
            merge_label    = self.new_label()

            self.emit(Op.LOAD, step_var)
            self.emit(Op.PUSH_INT, 0)
            self.emit(Op.CMP_GT)
            self.emit_jump(Op.JUMP_TRUE, step_pos_label, comment='step > 0?')

            # step <= 0: var >= stop
            self.emit(Op.LOAD, var)
            self.emit(Op.LOAD, stop_var)
            self.emit(Op.CMP_GE)
            self.emit_jump(Op.JUMP, merge_label)

            self.place_label(step_pos_label)
            # step > 0: var <= stop
            self.emit(Op.LOAD, var)
            self.emit(Op.LOAD, stop_var)
            self.emit(Op.CMP_LE)

            self.place_label(merge_label)
            self.emit_jump(Op.JUMP_FALSE, exit_label, comment='do: exit if past stop')

            # Body
            for s in stmt.body:
                self._compile_stmt(s)

            # Increment: var = var + step
            self.place_label(cont_label)
            self.emit(Op.LOAD, var)
            self.emit(Op.LOAD, step_var)
            self.emit(Op.ADD, comment=f'{var} += step')
            self.emit(Op.STORE, var)
            self.emit_jump(Op.JUMP, loop_top, comment='do: loop back')

        self.place_label(exit_label)
        self._loop_exit_labels.pop()
        self._loop_cont_labels.pop()

    # ── CALL statement ────────────────────────────────────────────────────────

    def _compile_call_stmt(self, stmt: CallStmt):
        """CALL subroutine(args...)"""
        for arg in stmt.args:
            self._compile_expr(arg)
        name = stmt.name.lower()
        self.emit(Op.CALL, (name, len(stmt.args)), comment=f'call {name}')
        # Discard return value (subroutines don't return values)
        # (VM will push None; we pop it)
        self.emit(Op.POP, comment='discard sub result')

    # ── Expressions ───────────────────────────────────────────────────────────

    def _compile_expr(self, node: Any):
        """
        Compile an expression: emit instructions so that after execution,
        the value of the expression is on top of the VM stack.
        Nothing is evaluated here — only instructions are emitted.
        """
        if node is None:
            self.emit(Op.PUSH_INT, 0)
            return

        if isinstance(node, IntLiteral):
            self.emit(Op.PUSH_INT, node.value)

        elif isinstance(node, RealLiteral):
            self.emit(Op.PUSH_REAL, node.value)

        elif isinstance(node, StringLiteral):
            self.emit(Op.PUSH_STR, node.value)

        elif isinstance(node, LogicalLiteral):
            self.emit(Op.PUSH_BOOL, 1 if node.value else 0)

        elif isinstance(node, Identifier):
            self.emit(Op.LOAD, node.name.lower(), comment=node.name)

        elif isinstance(node, ArrayRef):
            # Push indices onto stack, then LOAD_ARR
            for idx in node.indices:
                self._compile_expr(idx)
            self.emit(Op.LOAD_ARR, node.name.lower(),
                      comment=f'{node.name}({"..."})')

        elif isinstance(node, UnaryOp):
            self._compile_expr(node.operand)
            if node.op == '-':
                self.emit(Op.NEG)
            elif node.op.upper() in ('.NOT.', 'NOT'):
                self.emit(Op.LOGICAL_NOT)

        elif isinstance(node, BinOp):
            self._compile_binop(node)

        elif isinstance(node, FunctionCall):
            self._compile_func_call(node)

        else:
            self.emit(Op.PUSH_INT, 0, comment=f'unknown expr {type(node).__name__}')

    def _compile_binop(self, node: BinOp):
        op = node.op.upper()

        # Short-circuit .AND.
        if op == '.AND.':
            false_label = self.new_label()
            end_label   = self.new_label()
            self._compile_expr(node.left)
            self.emit_jump(Op.JUMP_FALSE, false_label, comment='.AND. short-circuit')
            self._compile_expr(node.right)
            self.emit_jump(Op.JUMP, end_label)
            self.place_label(false_label)
            self.emit(Op.PUSH_BOOL, 0)
            self.place_label(end_label)
            return

        # Short-circuit .OR.
        if op == '.OR.':
            true_label = self.new_label()
            end_label  = self.new_label()
            self._compile_expr(node.left)
            self.emit_jump(Op.JUMP_TRUE, true_label, comment='.OR. short-circuit')
            self._compile_expr(node.right)
            self.emit_jump(Op.JUMP, end_label)
            self.place_label(true_label)
            self.emit(Op.PUSH_BOOL, 1)
            self.place_label(end_label)
            return

        # General: compile both operands, then emit op
        self._compile_expr(node.left)
        self._compile_expr(node.right)

        dispatch = {
            '+': Op.ADD, '-': Op.SUB, '*': Op.MUL, '/': Op.DIV, '**': Op.POW,
            '//': Op.CONCAT,
            '==': Op.CMP_EQ, '.EQ.': Op.CMP_EQ,
            '/=': Op.CMP_NE, '.NE.': Op.CMP_NE,
            '<':  Op.CMP_LT, '.LT.': Op.CMP_LT,
            '<=': Op.CMP_LE, '.LE.': Op.CMP_LE,
            '>':  Op.CMP_GT, '.GT.': Op.CMP_GT,
            '>=': Op.CMP_GE, '.GE.': Op.CMP_GE,
        }
        instr_op = dispatch.get(op) or dispatch.get(node.op)
        if instr_op:
            self.emit(instr_op, comment=node.op)
        else:
            self.emit(Op.ADD, comment=f'unknown op {node.op}')

    def _compile_func_call(self, node: FunctionCall):
        """
        Compile a function call expression.
        Push args, then emit CALL_BUILTIN or CALL.
        After this, the return value is on top of the stack.
        """
        name = node.name.lower()
        argc = len(node.args)

        # Check if it's a known variable (array access via function-call syntax)
        sym = self._scope.lookup(name) if self._scope else None
        if sym and sym.is_array:
            for idx in node.args:
                self._compile_expr(idx)
            self.emit(Op.LOAD_ARR, name, comment=f'{name}(...)')
            return

        # Push all arguments
        for arg in node.args:
            self._compile_expr(arg)

        if name in BUILTIN_RETURN_TYPES:
            self.emit(Op.CALL_BUILTIN, (name, argc), comment=f'{name}()')
        else:
            self.emit(Op.CALL, (name, argc), comment=f'{name}()')
