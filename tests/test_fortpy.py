#!/usr/bin/env python3
"""
FortPy Test Suite — Tests for the lexer, parser, and interpreter.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from lexer import Lexer, TokenType
from parser import Parser
from interpreter import Interpreter
from ast_nodes import *

PASS = '\033[92m✓\033[0m'
FAIL = '\033[91m✗\033[0m'
tests_run = 0
tests_passed = 0


def run_fortran(source: str) -> str:
    lexer = Lexer(source)
    tokens = lexer.tokenize()
    parser = Parser(tokens)
    cu = parser.parse()
    interp = Interpreter()
    interp.load(cu)
    return interp.run(capture_output=True)


def test(name: str, source: str, expected: str):
    global tests_run, tests_passed
    tests_run += 1
    try:
        output = run_fortran(source)
        out_norm = ' '.join(output.split())
        exp_norm = ' '.join(expected.split())
        if out_norm == exp_norm:
            print(f"  {PASS} {name}")
            tests_passed += 1
        else:
            print(f"  {FAIL} {name}")
            print(f"       Expected: {expected!r}")
            print(f"       Got:      {output!r}")
    except Exception as e:
        print(f"  {FAIL} {name} — Exception: {e}")


def test_lexer(name: str, source: str, expected_types):
    global tests_run, tests_passed
    tests_run += 1
    lexer = Lexer(source)
    tokens = [t.type for t in lexer.tokenize() if t.type not in (TokenType.NEWLINE, TokenType.EOF)]
    if tokens == list(expected_types):
        print(f"  {PASS} {name}")
        tests_passed += 1
    else:
        print(f"  {FAIL} {name}")
        print(f"       Expected: {[t.name for t in expected_types]}")
        print(f"       Got:      {[t.name for t in tokens]}")


# ── Lexer Tests ───────────────────────────────────────────────────────────────
print("\n── Lexer Tests ──────────────────────────────────────────────────────")
test_lexer("Integer literal",   "42",       [TokenType.INTEGER_LIT])
test_lexer("Real literal",      "3.14",     [TokenType.REAL_LIT])
test_lexer("String literal",    "'hello'",  [TokenType.STRING_LIT])
test_lexer("Power operator",    "2**10",    [TokenType.INTEGER_LIT, TokenType.POWER, TokenType.INTEGER_LIT])
test_lexer("Concat operator",   "//'x'",    [TokenType.CONCAT, TokenType.STRING_LIT])
test_lexer("Comparison ops",    "a == b",   [TokenType.IDENTIFIER, TokenType.EQ_EQ, TokenType.IDENTIFIER])
test_lexer("Dot operator .AND.", ".AND.",   [TokenType.AND])
test_lexer("Dot operator .TRUE.", ".TRUE.", [TokenType.LOGICAL_LIT])
test_lexer("Comment skipped",  "x ! comment", [TokenType.IDENTIFIER, TokenType.COMMENT])


# ── Parser Tests ──────────────────────────────────────────────────────────────
print("\n── Parser Tests ─────────────────────────────────────────────────────")

def test_parse(name: str, source: str, expected_type):
    global tests_run, tests_passed
    tests_run += 1
    try:
        lexer = Lexer(source)
        tokens = lexer.tokenize()
        parser = Parser(tokens)
        cu = parser.parse()
        assert len(cu.units) > 0
        unit = cu.units[0]
        if isinstance(unit, expected_type):
            print(f"  {PASS} {name}")
            tests_passed += 1
        else:
            print(f"  {FAIL} {name} — Got {type(unit).__name__}")
    except Exception as e:
        print(f"  {FAIL} {name} — {e}")

test_parse("PROGRAM unit",    "program foo\nend program foo",                  Program)
test_parse("SUBROUTINE unit", "subroutine bar(x)\nend subroutine bar",         Subroutine)
test_parse("FUNCTION unit",   "integer function baz(n)\nbaz = n\nend function baz", Function)
test_parse("Implicit main",   "print *, 'hi'",                                 Program)


# ── Interpreter Tests ─────────────────────────────────────────────────────────
print("\n── Interpreter Tests ────────────────────────────────────────────────")

test("Hello World", """
program hello
  print *, 'Hello, World!'
end program hello
""", "Hello, World!")

test("Integer arithmetic", """
program arith
  integer :: x
  x = 3 + 4 * 2 - 1
  print *, x
end program arith
""", "10")

test("Real arithmetic", """
program reals
  real :: x
  x = 1.0 / 4.0
  print *, x
end program reals
""", "0.250000")

test("Power operator", """
program power
  integer :: x
  x = 2**8
  print *, x
end program power
""", "256")

test("String concatenation", """
program strcat
  print *, 'Hello' // ' ' // 'World'
end program strcat
""", "Hello World")

test("IF block - true branch", """
program iftest
  integer :: x
  x = 10
  if (x > 5) then
    print *, 'big'
  else
    print *, 'small'
  end if
end program iftest
""", "big")

test("IF block - false branch", """
program iftest2
  integer :: x
  x = 3
  if (x > 5) then
    print *, 'big'
  else
    print *, 'small'
  end if
end program iftest2
""", "small")

test("DO loop counting", """
program doloop
  integer :: i, s
  s = 0
  do i = 1, 5
    s = s + i
  end do
  print *, s
end program doloop
""", "15")

test("DO loop with step", """
program dostep
  integer :: i, s
  s = 0
  do i = 10, 1, -2
    s = s + i
  end do
  print *, s
end program dostep
""", "30")

test("DO WHILE loop", """
program dowhile
  integer :: i
  i = 1
  do while (i <= 5)
    i = i + 1
  end do
  print *, i
end program dowhile
""", "6")

test("Nested loops", """
program nested
  integer :: i, j, s
  s = 0
  do i = 1, 3
    do j = 1, 3
      s = s + 1
    end do
  end do
  print *, s
end program nested
""", "9")

test("User function call", """
program functest
  print *, square(7)
end program functest

integer function square(n)
  integer, intent(in) :: n
  square = n * n
end function square
""", "49")

test("Subroutine call", """
program subtest
  integer :: x
  x = 5
  call double(x)
  print *, x
end program subtest

subroutine double(x)
  integer, intent(inout) :: x
  x = x * 2
end subroutine double
""", "10")

test("Array operations", """
program arrtest
  integer :: a(5), i, s
  do i = 1, 5
    a(i) = i * i
  end do
  s = 0
  do i = 1, 5
    s = s + a(i)
  end do
  print *, s
end program arrtest
""", "55")

test("ELSEIF chain", """
program elseif_test
  integer :: x
  x = 5
  if (x > 10) then
    print *, 'large'
  elseif (x > 3) then
    print *, 'medium'
  else
    print *, 'small'
  end if
end program elseif_test
""", "medium")

test("Built-in ABS", """
program abstest
  print *, abs(-42)
end program abstest
""", "42")

test("Built-in SQRT", """
program sqrttest
  real :: x
  x = sqrt(9.0)
  print *, x
end program sqrttest
""", "3.000000")

test("LOGICAL operators", """
program logictest
  logical :: a, b
  a = .TRUE.
  b = .FALSE.
  if (a .AND. .NOT. b) then
    print *, 'yes'
  end if
end program logictest
""", "yes")

test("EXIT from loop", """
program exitloop
  integer :: i
  do i = 1, 100
    if (i == 5) exit
  end do
  print *, i
end program exitloop
""", "5")

test("CYCLE in loop", """
program cycleloop
  integer :: i, s
  s = 0
  do i = 1, 10
    if (mod(i, 2) == 0) cycle
    s = s + i
  end do
  print *, s
end program cycleloop
""", "25")

test("String length", """
program strlen
  print *, len('hello')
end program strlen
""", "5")

test("PARAMETER constant", """
program paramtest
  integer, parameter :: N = 42
  print *, N
end program paramtest
""", "42")


# ── Summary ───────────────────────────────────────────────────────────────────
print(f"\n{'─'*60}")
print(f"Results: {tests_passed}/{tests_run} tests passed", end='')
if tests_passed == tests_run:
    print(f"  {PASS} All tests passed!")
else:
    failed = tests_run - tests_passed
    print(f"  {FAIL} {failed} test(s) failed")
    sys.exit(1)
