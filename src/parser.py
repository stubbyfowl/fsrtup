"""
FortPy Parser — Recursive-descent parser for Fortran 77/90 subset.
Builds an AST from a token stream produced by the Lexer.
"""

from typing import List, Optional, Any, Tuple
from lexer import Token, TokenType, Lexer
from ast_nodes import *


class ParseError(Exception):
    def __init__(self, message: str, line: int = 0):
        super().__init__(f"Parse error at line {line}: {message}")
        self.line = line


class Parser:
    def __init__(self, tokens: List[Token]):
        # Filter out comments and consecutive newlines
        self.tokens = self._filter(tokens)
        self.pos = 0

    # ── Token utilities ───────────────────────────────────────────────────────

    def _filter(self, tokens: List[Token]) -> List[Token]:
        result = []
        prev_nl = False
        for t in tokens:
            if t.type == TokenType.COMMENT:
                continue
            if t.type == TokenType.NEWLINE:
                if not prev_nl:
                    result.append(t)
                prev_nl = True
            else:
                prev_nl = False
                result.append(t)
        return result

    def peek(self, offset: int = 0) -> Token:
        idx = self.pos + offset
        if idx < len(self.tokens):
            return self.tokens[idx]
        return self.tokens[-1]  # EOF

    def advance(self) -> Token:
        t = self.tokens[self.pos]
        if self.pos < len(self.tokens) - 1:
            self.pos += 1
        return t

    def check(self, *types: TokenType) -> bool:
        return self.peek().type in types

    def check_kw(self, *keywords: str) -> bool:
        t = self.peek()
        return t.type == TokenType.KEYWORD and t.value in keywords

    def match(self, *types: TokenType) -> Optional[Token]:
        if self.peek().type in types:
            return self.advance()
        return None

    def match_kw(self, *keywords: str) -> Optional[Token]:
        t = self.peek()
        if t.type == TokenType.KEYWORD and t.value in keywords:
            return self.advance()
        return None

    def expect(self, type_: TokenType, msg: str = '') -> Token:
        t = self.peek()
        if t.type != type_:
            raise ParseError(msg or f"Expected {type_.name}, got {t.value!r}", t.line)
        return self.advance()

    def expect_kw(self, kw: str) -> Token:
        t = self.peek()
        if not (t.type == TokenType.KEYWORD and t.value == kw):
            raise ParseError(f"Expected keyword '{kw}', got {t.value!r}", t.line)
        return self.advance()

    def skip_newlines(self):
        while self.check(TokenType.NEWLINE):
            self.advance()

    def consume_newline(self):
        """Consume a newline or semicolon (statement terminator)."""
        if self.check(TokenType.NEWLINE, TokenType.SEMICOLON):
            self.advance()
        elif not self.check(TokenType.EOF):
            # Tolerate missing newline before certain keywords
            pass

    def current_line(self) -> int:
        return self.peek().line

    # ── Entry point ───────────────────────────────────────────────────────────

    def parse(self) -> CompilationUnit:
        self.skip_newlines()
        units = []
        while not self.check(TokenType.EOF):
            unit = self.parse_program_unit()
            if unit:
                units.append(unit)
            self.skip_newlines()
        return CompilationUnit(units=units, line=0)

    # ── Program units ─────────────────────────────────────────────────────────

    def parse_program_unit(self) -> Any:
        t = self.peek()
        if t.type == TokenType.KEYWORD:
            if t.value == 'program':
                return self.parse_program()
            if t.value == 'subroutine':
                return self.parse_subroutine()
            if t.value == 'function':
                return self.parse_function()
            if t.value == 'module':
                return self.parse_module()
            # Type-prefixed function: INTEGER FUNCTION foo(...)
            if t.value in ('integer', 'real', 'double', 'complex', 'logical', 'character'):
                # Check if followed (possibly after type spec) by FUNCTION keyword
                saved_pos = self.pos
                type_spec = self.parse_type_spec()
                if self.check_kw('function'):
                    return self.parse_function(return_type=type_spec)
                # Not a function — restore position
                self.pos = saved_pos
        # Implicit main program
        return self.parse_implicit_program()

    def parse_program(self) -> Program:
        line = self.current_line()
        self.expect_kw('program')
        name = self.expect(TokenType.IDENTIFIER, "Expected program name").value
        self.consume_newline()
        decls, stmts = self.parse_body()
        self._expect_end('program', name)
        return Program(name=name, body=stmts, declarations=decls, line=line)

    def parse_subroutine(self) -> Subroutine:
        line = self.current_line()
        self.expect_kw('subroutine')
        # Name may be a keyword (e.g. 'double')
        t = self.peek()
        if t.type in (TokenType.IDENTIFIER, TokenType.KEYWORD):
            name = self.advance().value
        else:
            raise ParseError("Expected subroutine name", t.line)
        params = []
        if self.match(TokenType.LPAREN):
            while not self.check(TokenType.RPAREN, TokenType.EOF):
                params.append(self.expect(TokenType.IDENTIFIER).value)
                self.match(TokenType.COMMA)
            self.expect(TokenType.RPAREN)
        self.consume_newline()
        decls, stmts = self.parse_body()
        self._expect_end('subroutine', name)
        return Subroutine(name=name, params=params, body=stmts, declarations=decls, line=line)

    def parse_function(self, return_type=None) -> Function:
        line = self.current_line()
        self.expect_kw('function')
        name = self.expect(TokenType.IDENTIFIER, "Expected function name").value
        params = []
        if self.match(TokenType.LPAREN):
            while not self.check(TokenType.RPAREN, TokenType.EOF):
                params.append(self.expect(TokenType.IDENTIFIER).value)
                self.match(TokenType.COMMA)
            self.expect(TokenType.RPAREN)
        self.consume_newline()
        decls, stmts = self.parse_body()
        self._expect_end('function', name)
        return Function(name=name, params=params, return_type=return_type,
                        body=stmts, declarations=decls, line=line)

    def parse_module(self) -> Module:
        line = self.current_line()
        self.expect_kw('module')
        name = self.expect(TokenType.IDENTIFIER).value
        self.consume_newline()
        decls, stmts = self.parse_body()
        self._expect_end('module', name)
        return Module(name=name, body=stmts, declarations=decls, line=line)

    def parse_implicit_program(self) -> Program:
        """Source with no PROGRAM statement — wrap as implicit main."""
        line = self.current_line()
        decls, stmts = self.parse_body()
        return Program(name='main', body=stmts, declarations=decls, line=line)

    def _expect_end(self, unit_kw: str, name: str):
        self.skip_newlines()
        self.expect_kw('end')
        # Optional: END PROGRAM name, END SUBROUTINE name, etc.
        self.match_kw(unit_kw)
        t = self.peek()
        if t.type in (TokenType.IDENTIFIER, TokenType.KEYWORD) and t.value == name:
            self.advance()
        self.consume_newline()

    # ── Body (declarations + statements) ──────────────────────────────────────

    def parse_body(self) -> Tuple[List[Any], List[Any]]:
        self.skip_newlines()
        decls = []
        stmts = []
        in_decl_section = True

        while not self.check(TokenType.EOF):
            self.skip_newlines()
            t = self.peek()

            # Stop at end / contains
            if t.type == TokenType.KEYWORD and t.value in ('end', 'contains'):
                break

            # Try declaration
            if in_decl_section and self._is_declaration():
                d = self.parse_declaration()
                if d:
                    decls.append(d)
                continue

            in_decl_section = False

            # Statement
            stmt = self.parse_statement()
            if stmt is not None:
                stmts.append(stmt)

        return decls, stmts

    def _is_declaration(self) -> bool:
        t = self.peek()
        if t.type != TokenType.KEYWORD:
            return False
        return t.value in ('integer', 'real', 'double', 'complex', 'logical',
                           'character', 'implicit', 'parameter', 'dimension')

    # ── Declarations ──────────────────────────────────────────────────────────

    def parse_declaration(self) -> Any:
        line = self.current_line()
        t = self.peek()

        if t.value == 'implicit':
            return self.parse_implicit()
        if t.value == 'parameter':
            return self.parse_parameter_stmt()

        type_spec = self.parse_type_spec()
        # Handle FUNCTION with type prefix: INTEGER FUNCTION foo(...)
        if self.check_kw('function'):
            return self.parse_function(return_type=type_spec)

        dimensions: dict = {}
        initial_values: dict = {}
        is_parameter = False
        intent = None

        # Attribute list after ::
        if self.check(TokenType.DOUBLE_COLON):
            self.advance()
        elif self.check(TokenType.COMMA):
            # possible attributes: INTENT(IN), PARAMETER, DIMENSION(...)
            self.advance()
            attr = self.peek()
            if attr.type == TokenType.KEYWORD and attr.value == 'intent':
                self.advance()
                self.expect(TokenType.LPAREN)
                # intent value can be 'in', 'out', or 'inout' (two tokens: 'in'+'out')
                intent_parts = []
                while not self.check(TokenType.RPAREN, TokenType.EOF):
                    intent_parts.append(self.advance().value)
                intent = ''.join(intent_parts)
                self.expect(TokenType.RPAREN)
            elif attr.type == TokenType.KEYWORD and attr.value == 'parameter':
                self.advance()
                is_parameter = True
            elif attr.type == TokenType.KEYWORD and attr.value == 'dimension':
                self.advance()
                # parse dimensions; applied to all names later
            self.match(TokenType.DOUBLE_COLON)

        names = []
        while True:
            name = self.expect(TokenType.IDENTIFIER, "Expected variable name").value
            dims = []
            if self.check(TokenType.LPAREN):
                self.advance()
                while not self.check(TokenType.RPAREN, TokenType.EOF):
                    dims.append(self.parse_expr())
                    self.match(TokenType.COMMA)
                self.expect(TokenType.RPAREN)
            if dims:
                dimensions[name] = dims
            # Initial value
            if self.check(TokenType.EQ):
                self.advance()
                initial_values[name] = self.parse_expr()
            names.append(name)
            if not self.match(TokenType.COMMA):
                break

        self.consume_newline()
        return VarDecl(type_spec=type_spec, names=names, dimensions=dimensions,
                       initial_values=initial_values, is_parameter=is_parameter,
                       intent=intent, line=line)

    def parse_type_spec(self) -> TypeSpec:
        line = self.current_line()
        t = self.advance()
        name = t.value
        if name == 'double':
            self.expect_kw('precision')
            name = 'double precision'
        kind = None
        length = None
        if self.check(TokenType.LPAREN):
            self.advance()
            # CHARACTER*(n) or CHARACTER(LEN=n) or INTEGER(KIND=4)
            if self.check(TokenType.STAR):
                self.advance()
                length = self.parse_expr()
            else:
                inner = self.parse_expr()
                kind = inner
            self.expect(TokenType.RPAREN)
        elif self.check(TokenType.STAR):
            self.advance()
            length = self.parse_expr()
        return TypeSpec(name=name, kind=kind, length=length, line=line)

    def parse_implicit(self) -> ImplicitNone:
        line = self.current_line()
        self.expect_kw('implicit')
        self.expect_kw('none')
        self.consume_newline()
        return ImplicitNone(line=line)

    def parse_parameter_stmt(self) -> ParameterStmt:
        line = self.current_line()
        self.expect_kw('parameter')
        self.expect(TokenType.LPAREN)
        assignments = []
        while not self.check(TokenType.RPAREN, TokenType.EOF):
            name = self.expect(TokenType.IDENTIFIER).value
            self.expect(TokenType.EQ)
            val = self.parse_expr()
            assignments.append((name, val))
            self.match(TokenType.COMMA)
        self.expect(TokenType.RPAREN)
        self.consume_newline()
        return ParameterStmt(assignments=assignments, line=line)

    # ── Statements ────────────────────────────────────────────────────────────

    def parse_statement(self) -> Any:
        self.skip_newlines()
        line = self.current_line()
        t = self.peek()

        if t.type == TokenType.EOF:
            return None

        # Labeled statement
        if t.type == TokenType.INTEGER_LIT:
            label = int(self.advance().value)
            stmt = self.parse_statement()
            return LabelStmt(label=label, stmt=stmt, line=line)

        if t.type == TokenType.KEYWORD:
            kw = t.value
            if kw == 'if':      return self.parse_if()
            if kw == 'do':      return self.parse_do()
            if kw == 'print':   return self.parse_print()
            if kw == 'write':   return self.parse_write()
            if kw == 'read':    return self.parse_read()
            if kw == 'call':    return self.parse_call()
            if kw == 'return':
                self.advance(); self.consume_newline()
                return ReturnStmt(line=line)
            if kw == 'stop':
                self.advance()
                code = None
                if not self.check(TokenType.NEWLINE, TokenType.EOF, TokenType.SEMICOLON):
                    code = self.parse_expr()
                self.consume_newline()
                return StopStmt(code=code, line=line)
            if kw == 'continue':
                self.advance(); self.consume_newline()
                return ContinueStmt(line=line)
            if kw == 'goto':
                self.advance()
                label = int(self.expect(TokenType.INTEGER_LIT).value)
                self.consume_newline()
                return GotoStmt(label=label, line=line)
            if kw == 'cycle':
                self.advance(); self.consume_newline()
                return CycleStmt(line=line)
            if kw == 'exit':
                self.advance(); self.consume_newline()
                return ExitStmt(line=line)
            if kw in ('end', 'contains'):
                return None
            # Declarative keywords that appear in body (shouldn't happen ideally)
            if kw in ('integer', 'real', 'double', 'complex', 'logical',
                      'character', 'implicit', 'parameter', 'dimension'):
                return self.parse_declaration()

        # Assignment: identifier = expr  OR  array(i) = expr
        if t.type == TokenType.IDENTIFIER:
            return self.parse_assignment_or_call()

        # Unknown — skip
        self.advance()
        return None

    def parse_assignment_or_call(self) -> Any:
        line = self.current_line()
        name = self.advance().value   # identifier

        # Array ref or function call
        indices = []
        if self.check(TokenType.LPAREN):
            self.advance()
            while not self.check(TokenType.RPAREN, TokenType.EOF):
                indices.append(self.parse_expr())
                self.match(TokenType.COMMA)
            self.expect(TokenType.RPAREN)

        if self.check(TokenType.EQ):
            self.advance()
            value = self.parse_expr()
            self.consume_newline()
            if indices:
                return AssignStmt(target=ArrayRef(name=name, indices=indices, line=line),
                                  value=value, line=line)
            return AssignStmt(target=Identifier(name=name, line=line),
                              value=value, line=line)

        # Otherwise treat as subroutine call without CALL keyword
        self.consume_newline()
        return CallStmt(name=name, args=indices, line=line)

    def parse_if(self) -> Any:
        line = self.current_line()
        self.expect_kw('if')
        self.expect(TokenType.LPAREN)
        condition = self.parse_expr()
        self.expect(TokenType.RPAREN)

        # IF (...) THEN  → block
        if self.check_kw('then'):
            self.advance()
            self.consume_newline()
            then_body = []
            elseif_clauses = []
            else_body = None

            while True:
                self.skip_newlines()
                if self.check_kw('endif'):
                    self.advance(); self.consume_newline(); break
                if self.check_kw('end'):
                    self.advance()
                    self.match_kw('if')
                    self.consume_newline(); break
                if self.check_kw('elseif'):
                    self.advance()
                    self.expect(TokenType.LPAREN)
                    elif_cond = self.parse_expr()
                    self.expect(TokenType.RPAREN)
                    self.expect_kw('then')
                    self.consume_newline()
                    elif_body = []
                    while not (self.check_kw('elseif') or self.check_kw('else')
                               or self.check_kw('endif') or self.check_kw('end')
                               or self.check(TokenType.EOF)):
                        s = self.parse_statement()
                        if s: elif_body.append(s)
                    elseif_clauses.append((elif_cond, elif_body))
                    continue
                if self.check_kw('else'):
                    self.advance(); self.consume_newline()
                    else_body = []
                    while not (self.check_kw('endif') or self.check_kw('end')
                               or self.check(TokenType.EOF)):
                        s = self.parse_statement()
                        if s: else_body.append(s)
                    continue
                s = self.parse_statement()
                if s: then_body.append(s)

            return IfBlock(condition=condition, then_body=then_body,
                           elseif_clauses=elseif_clauses, else_body=else_body, line=line)

        # Single-line IF
        stmt = self.parse_statement()
        return IfStmt(condition=condition, then_stmt=stmt, line=line)

    def parse_do(self) -> DoLoop:
        line = self.current_line()
        self.expect_kw('do')

        label = None
        # Optional numeric label
        if self.check(TokenType.INTEGER_LIT):
            label = int(self.advance().value)

        # DO WHILE (cond)
        if self.check_kw('while'):
            self.advance()
            self.expect(TokenType.LPAREN)
            cond = self.parse_expr()
            self.expect(TokenType.RPAREN)
            self.consume_newline()
            body = self._parse_do_body(label)
            return DoLoop(var=None, start=None, stop=None, step=None,
                          condition=cond, body=body, label=label, line=line)

        # Infinite DO
        if self.check(TokenType.NEWLINE, TokenType.EOF):
            self.consume_newline()
            body = self._parse_do_body(label)
            return DoLoop(var=None, start=None, stop=None, step=None,
                          condition=None, body=body, label=label, line=line)

        # DO var = start, stop [, step]
        var = self.expect(TokenType.IDENTIFIER).value
        self.expect(TokenType.EQ)
        start = self.parse_expr()
        self.expect(TokenType.COMMA)
        stop = self.parse_expr()
        step = None
        if self.match(TokenType.COMMA):
            step = self.parse_expr()
        self.consume_newline()
        body = self._parse_do_body(label)
        return DoLoop(var=var, start=start, stop=stop, step=step,
                      condition=None, body=body, label=label, line=line)

    def _parse_do_body(self, label) -> List[Any]:
        body = []
        while not self.check(TokenType.EOF):
            self.skip_newlines()
            # END DO
            if self.check_kw('enddo'):
                self.advance(); self.consume_newline(); break
            if self.check_kw('end'):
                self.advance()
                if self.check_kw('do'):
                    self.advance()
                self.consume_newline(); break
            # Labeled CONTINUE terminates old-style DO
            t = self.peek()
            if t.type == TokenType.INTEGER_LIT and label and int(t.value) == label:
                self.advance()
                s = self.parse_statement()
                if s: body.append(s)
                break
            s = self.parse_statement()
            if s: body.append(s)
        return body

    def parse_print(self) -> PrintStmt:
        line = self.current_line()
        self.expect_kw('print')
        fmt = self._parse_io_format()
        items = []
        if self.check(TokenType.COMMA):
            self.advance()
            items = self._parse_io_list()
        self.consume_newline()
        return PrintStmt(fmt=fmt, items=items, line=line)

    def parse_write(self) -> WriteStmt:
        line = self.current_line()
        self.expect_kw('write')
        self.expect(TokenType.LPAREN)
        unit = self.parse_expr()
        fmt = None
        if self.match(TokenType.COMMA):
            fmt = self._parse_io_format()
        self.expect(TokenType.RPAREN)
        items = []
        if self.check(TokenType.COMMA):
            self.advance()
            items = self._parse_io_list()
        elif not self.check(TokenType.NEWLINE, TokenType.EOF, TokenType.SEMICOLON):
            items = self._parse_io_list()
        self.consume_newline()
        return WriteStmt(unit=unit, fmt=fmt, items=items, line=line)

    def parse_read(self) -> ReadStmt:
        line = self.current_line()
        self.expect_kw('read')
        self.expect(TokenType.LPAREN)
        unit = self.parse_expr()
        fmt = None
        if self.match(TokenType.COMMA):
            fmt = self._parse_io_format()
        self.expect(TokenType.RPAREN)
        items = []
        if self.check(TokenType.COMMA):
            self.advance()
            items = self._parse_io_list()
        elif not self.check(TokenType.NEWLINE, TokenType.EOF, TokenType.SEMICOLON):
            items = self._parse_io_list()
        self.consume_newline()
        return ReadStmt(unit=unit, fmt=fmt, items=items, line=line)

    def _parse_io_format(self) -> Any:
        t = self.peek()
        if t.type == TokenType.STAR:
            self.advance()
            return '*'
        return self.parse_expr()

    def _parse_io_list(self) -> List[Any]:
        items = []
        while not self.check(TokenType.NEWLINE, TokenType.EOF, TokenType.SEMICOLON):
            items.append(self.parse_expr())
            if not self.match(TokenType.COMMA):
                break
        return items

    def parse_call(self) -> CallStmt:
        line = self.current_line()
        self.expect_kw('call')
        # Name can be a keyword (e.g. subroutine named 'double')
        t = self.peek()
        if t.type in (TokenType.IDENTIFIER, TokenType.KEYWORD):
            name = self.advance().value
        else:
            name = self.expect(TokenType.IDENTIFIER).value
        args = []
        if self.match(TokenType.LPAREN):
            while not self.check(TokenType.RPAREN, TokenType.EOF):
                args.append(self.parse_expr())
                self.match(TokenType.COMMA)
            self.expect(TokenType.RPAREN)
        self.consume_newline()
        return CallStmt(name=name, args=args, line=line)

    # ── Expressions ───────────────────────────────────────────────────────────

    def parse_expr(self) -> Any:
        return self.parse_or_expr()

    def parse_or_expr(self) -> Any:
        left = self.parse_and_expr()
        while self.check(TokenType.OR):
            op = self.advance().value
            right = self.parse_and_expr()
            left = BinOp(op=op, left=left, right=right, line=left.line)
        return left

    def parse_and_expr(self) -> Any:
        left = self.parse_not_expr()
        while self.check(TokenType.AND):
            op = self.advance().value
            right = self.parse_not_expr()
            left = BinOp(op=op, left=left, right=right, line=left.line)
        return left

    def parse_not_expr(self) -> Any:
        if self.check(TokenType.NOT):
            line = self.current_line()
            op = self.advance().value
            operand = self.parse_comparison()
            return UnaryOp(op=op, operand=operand, line=line)
        return self.parse_comparison()

    def parse_comparison(self) -> Any:
        left = self.parse_concat()
        while self.check(TokenType.EQ_EQ, TokenType.NEQ, TokenType.LT,
                         TokenType.LE, TokenType.GT, TokenType.GE):
            op = self.advance().value
            right = self.parse_concat()
            left = BinOp(op=op, left=left, right=right, line=left.line)
        return left

    def parse_concat(self) -> Any:
        left = self.parse_add()
        while self.check(TokenType.CONCAT):
            op = self.advance().value
            right = self.parse_add()
            left = BinOp(op=op, left=left, right=right, line=left.line)
        return left

    def parse_add(self) -> Any:
        left = self.parse_mul()
        while self.check(TokenType.PLUS, TokenType.MINUS):
            op = self.advance().value
            right = self.parse_mul()
            left = BinOp(op=op, left=left, right=right, line=left.line)
        return left

    def parse_mul(self) -> Any:
        left = self.parse_power()
        while self.check(TokenType.STAR, TokenType.SLASH):
            op = self.advance().value
            right = self.parse_power()
            left = BinOp(op=op, left=left, right=right, line=left.line)
        return left

    def parse_power(self) -> Any:
        base = self.parse_unary()
        if self.check(TokenType.POWER):
            op = self.advance().value
            exp = self.parse_power()   # right-associative
            return BinOp(op=op, left=base, right=exp, line=base.line)
        return base

    def parse_unary(self) -> Any:
        line = self.current_line()
        if self.check(TokenType.MINUS):
            self.advance()
            operand = self.parse_primary()
            return UnaryOp(op='-', operand=operand, line=line)
        if self.check(TokenType.PLUS):
            self.advance()
            return self.parse_primary()
        return self.parse_primary()

    def parse_primary(self) -> Any:
        line = self.current_line()
        t = self.peek()

        if t.type == TokenType.INTEGER_LIT:
            self.advance()
            return IntLiteral(value=int(t.value), line=line)

        if t.type == TokenType.REAL_LIT:
            self.advance()
            v = t.value.replace('d', 'e').replace('D', 'e')
            return RealLiteral(value=float(v), line=line)

        if t.type == TokenType.STRING_LIT:
            self.advance()
            return StringLiteral(value=t.value, line=line)

        if t.type == TokenType.LOGICAL_LIT:
            self.advance()
            return LogicalLiteral(value=t.value == '.TRUE.', line=line)

        if t.type == TokenType.LPAREN:
            self.advance()
            expr = self.parse_expr()
            self.expect(TokenType.RPAREN)
            return expr

        if t.type == TokenType.IDENTIFIER:
            name = self.advance().value
            if self.check(TokenType.LPAREN):
                self.advance()
                args = []
                while not self.check(TokenType.RPAREN, TokenType.EOF):
                    args.append(self.parse_expr())
                    self.match(TokenType.COMMA)
                self.expect(TokenType.RPAREN)
                return FunctionCall(name=name, args=args, line=line)
            return Identifier(name=name, line=line)

        if t.type == TokenType.KEYWORD:
            # Some keywords can appear as identifiers in expressions (.TRUE. already handled)
            name = self.advance().value
            return Identifier(name=name, line=line)

        # Fallback
        self.advance()
        return Identifier(name=t.value, line=line)
