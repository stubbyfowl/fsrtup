"""
FortPy Lexer - Tokenizes Fortran 77/90 source code
"""

import re
from dataclasses import dataclass
from enum import Enum, auto
from typing import List, Optional


class TokenType(Enum):
    # Literals
    INTEGER_LIT   = auto()
    REAL_LIT      = auto()
    STRING_LIT    = auto()
    LOGICAL_LIT   = auto()

    # Identifiers & Keywords
    IDENTIFIER    = auto()
    KEYWORD       = auto()

    # Operators
    PLUS          = auto()
    MINUS         = auto()
    STAR          = auto()
    SLASH         = auto()
    POWER         = auto()   # **
    EQ            = auto()   # =
    EQ_EQ         = auto()   # ==  or .EQ.
    NEQ           = auto()   # /=  or .NE.
    LT            = auto()   # <   or .LT.
    LE            = auto()   # <=  or .LE.
    GT            = auto()   # >   or .GT.
    GE            = auto()   # >=  or .GE.
    AND           = auto()   # .AND.
    OR            = auto()   # .OR.
    NOT           = auto()   # .NOT.
    CONCAT        = auto()   # //

    # Delimiters
    LPAREN        = auto()
    RPAREN        = auto()
    COMMA         = auto()
    COLON         = auto()
    DOUBLE_COLON  = auto()
    SEMICOLON     = auto()
    NEWLINE       = auto()
    EOF           = auto()

    # Comments (usually skipped)
    COMMENT       = auto()


KEYWORDS = {
    'program', 'end', 'integer', 'real', 'double', 'complex',
    'logical', 'character', 'if', 'then', 'else', 'elseif',
    'endif', 'do', 'enddo', 'while', 'print', 'write', 'read',
    'call', 'subroutine', 'function', 'return', 'stop', 'implicit',
    'none', 'parameter', 'dimension', 'continue', 'goto',
    'common', 'data', 'format', 'precision', 'use', 'module',
    'contains', 'intent', 'in', 'out', 'inout', 'allocate',
    'deallocate', 'nullify', 'allocatable', 'pointer', 'target',
    'cycle', 'exit', 'select', 'case', 'default', 'endselect',
    'open', 'close', 'rewind', 'backspace', 'inquire',
}


@dataclass
class Token:
    type: TokenType
    value: str
    line: int
    col: int

    def __repr__(self):
        return f"Token({self.type.name}, {self.value!r}, L{self.line}:C{self.col})"


class LexerError(Exception):
    def __init__(self, message: str, line: int, col: int):
        super().__init__(f"Lexer error at line {line}, col {col}: {message}")
        self.line = line
        self.col = col


class Lexer:
    """
    Tokenizes Fortran source code (free-form and fixed-form).
    Case-insensitive per the Fortran standard.
    """

    def __init__(self, source: str, fixed_form: bool = False):
        self.source = source
        self.fixed_form = fixed_form
        self.pos = 0
        self.line = 1
        self.col = 1
        self.tokens: List[Token] = []

    def error(self, msg: str) -> LexerError:
        return LexerError(msg, self.line, self.col)

    def peek(self, offset: int = 0) -> Optional[str]:
        idx = self.pos + offset
        return self.source[idx] if idx < len(self.source) else None

    def advance(self) -> str:
        ch = self.source[self.pos]
        self.pos += 1
        if ch == '\n':
            self.line += 1
            self.col = 1
        else:
            self.col += 1
        return ch

    def match(self, expected: str) -> bool:
        if self.pos < len(self.source) and self.source[self.pos] == expected:
            self.advance()
            return True
        return False

    def skip_whitespace(self):
        while self.pos < len(self.source) and self.source[self.pos] in ' \t\r':
            self.advance()

    def read_comment(self) -> Token:
        start_col = self.col
        text = ''
        while self.pos < len(self.source) and self.source[self.pos] != '\n':
            text += self.advance()
        return Token(TokenType.COMMENT, text, self.line, start_col)

    def read_string(self, quote: str) -> Token:
        start_line, start_col = self.line, self.col
        self.advance()  # consume opening quote
        s = ''
        while self.pos < len(self.source):
            ch = self.source[self.pos]
            if ch == quote:
                self.advance()
                # Doubled quote = escaped quote
                if self.pos < len(self.source) and self.source[self.pos] == quote:
                    s += quote
                    self.advance()
                else:
                    break
            elif ch == '\n':
                raise self.error("Unterminated string literal")
            else:
                s += self.advance()
        return Token(TokenType.STRING_LIT, s, start_line, start_col)

    def read_number(self) -> Token:
        start_line, start_col = self.line, self.col
        num = ''
        is_real = False
        while self.pos < len(self.source) and self.source[self.pos].isdigit():
            num += self.advance()
        if self.pos < len(self.source) and self.source[self.pos] == '.':
            # Look ahead: ".EQ." etc. should not be consumed as decimal
            next_ch = self.peek(1)
            if next_ch and (next_ch.isdigit() or next_ch in 'eEdD'):
                is_real = True
                num += self.advance()  # consume '.'
                while self.pos < len(self.source) and self.source[self.pos].isdigit():
                    num += self.advance()
            elif next_ch and next_ch.isalpha() and next_ch.upper() not in 'EGLNOT':
                # Likely a decimal point before identifier — treat as real
                is_real = True
                num += self.advance()
        # Exponent
        if self.pos < len(self.source) and self.source[self.pos].upper() in ('E', 'D'):
            is_real = True
            num += self.advance()
            if self.pos < len(self.source) and self.source[self.pos] in ('+', '-'):
                num += self.advance()
            while self.pos < len(self.source) and self.source[self.pos].isdigit():
                num += self.advance()
        tok_type = TokenType.REAL_LIT if is_real else TokenType.INTEGER_LIT
        return Token(tok_type, num, start_line, start_col)

    def read_identifier_or_keyword(self) -> Token:
        start_line, start_col = self.line, self.col
        ident = ''
        while self.pos < len(self.source) and (self.source[self.pos].isalnum() or self.source[self.pos] == '_'):
            ident += self.advance()
        lower = ident.lower()
        if lower in KEYWORDS:
            return Token(TokenType.KEYWORD, lower, start_line, start_col)
        return Token(TokenType.IDENTIFIER, lower, start_line, start_col)

    def read_dot_operator(self) -> Token:
        """Read .AND. .OR. .NOT. .EQ. .NE. .LT. .LE. .GT. .GE. .TRUE. .FALSE."""
        start_line, start_col = self.line, self.col
        self.advance()  # consume '.'
        word = ''
        while self.pos < len(self.source) and self.source[self.pos].isalpha():
            word += self.advance()
        if self.pos < len(self.source) and self.source[self.pos] == '.':
            self.advance()  # consume closing '.'
        upper = word.upper()
        mapping = {
            'AND': TokenType.AND,
            'OR':  TokenType.OR,
            'NOT': TokenType.NOT,
            'EQ':  TokenType.EQ_EQ,
            'NE':  TokenType.NEQ,
            'LT':  TokenType.LT,
            'LE':  TokenType.LE,
            'GT':  TokenType.GT,
            'GE':  TokenType.GE,
            'TRUE':  TokenType.LOGICAL_LIT,
            'FALSE': TokenType.LOGICAL_LIT,
        }
        tok_type = mapping.get(upper, TokenType.IDENTIFIER)
        return Token(tok_type, f'.{upper}.', start_line, start_col)

    def tokenize(self) -> List[Token]:
        tokens = []
        while self.pos < len(self.source):
            self.skip_whitespace()
            if self.pos >= len(self.source):
                break

            ch = self.source[self.pos]
            line, col = self.line, self.col

            # Newline
            if ch == '\n':
                self.advance()
                tokens.append(Token(TokenType.NEWLINE, '\\n', line, col))
                continue

            # Fixed-form: column 1 C or * = comment
            if self.fixed_form and col == 1 and ch.upper() in ('C', '*'):
                tokens.append(self.read_comment())
                continue

            # Free-form: ! starts a comment
            if ch == '!':
                tokens.append(self.read_comment())
                continue

            # String literals
            if ch in ('"', "'"):
                tokens.append(self.read_string(ch))
                continue

            # Numbers
            if ch.isdigit():
                tokens.append(self.read_number())
                continue

            # Identifiers / keywords
            if ch.isalpha() or ch == '_':
                tokens.append(self.read_identifier_or_keyword())
                continue

            # Dot operators (.AND., .TRUE., etc.) or decimal numbers
            if ch == '.':
                next_ch = self.peek(1)
                if next_ch and next_ch.isdigit():
                    tokens.append(self.read_number())
                elif next_ch and next_ch.isalpha():
                    tokens.append(self.read_dot_operator())
                else:
                    self.advance()
                    tokens.append(Token(TokenType.IDENTIFIER, '.', line, col))
                continue

            # Multi-character operators
            if ch == '*':
                self.advance()
                if self.match('*'):
                    tokens.append(Token(TokenType.POWER, '**', line, col))
                else:
                    tokens.append(Token(TokenType.STAR, '*', line, col))
                continue

            if ch == '/':
                self.advance()
                if self.match('='):
                    tokens.append(Token(TokenType.NEQ, '/=', line, col))
                elif self.match('/'):
                    tokens.append(Token(TokenType.CONCAT, '//', line, col))
                else:
                    tokens.append(Token(TokenType.SLASH, '/', line, col))
                continue

            if ch == '=':
                self.advance()
                if self.match('='):
                    tokens.append(Token(TokenType.EQ_EQ, '==', line, col))
                else:
                    tokens.append(Token(TokenType.EQ, '=', line, col))
                continue

            if ch == '<':
                self.advance()
                if self.match('='):
                    tokens.append(Token(TokenType.LE, '<=', line, col))
                else:
                    tokens.append(Token(TokenType.LT, '<', line, col))
                continue

            if ch == '>':
                self.advance()
                if self.match('='):
                    tokens.append(Token(TokenType.GE, '>=', line, col))
                else:
                    tokens.append(Token(TokenType.GT, '>', line, col))
                continue

            if ch == ':':
                self.advance()
                if self.match(':'):
                    tokens.append(Token(TokenType.DOUBLE_COLON, '::', line, col))
                else:
                    tokens.append(Token(TokenType.COLON, ':', line, col))
                continue

            # Single-character tokens
            single = {
                '+': TokenType.PLUS,
                '-': TokenType.MINUS,
                '(': TokenType.LPAREN,
                ')': TokenType.RPAREN,
                ',': TokenType.COMMA,
                ';': TokenType.SEMICOLON,
            }
            if ch in single:
                self.advance()
                tokens.append(Token(single[ch], ch, line, col))
                continue

            # Line continuation (&)
            if ch == '&':
                self.advance()
                # skip rest of line and leading & on next line
                while self.pos < len(self.source) and self.source[self.pos] != '\n':
                    self.advance()
                continue

            # Unknown character — skip with warning
            self.advance()

        tokens.append(Token(TokenType.EOF, '', self.line, self.col))
        return tokens
