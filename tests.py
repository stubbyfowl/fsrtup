#!/usr/bin/env python3
"""FortPy Compiler + VM Test Suite"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from lexer import Lexer, TokenType
from parser import Parser
from compiler import Compiler
from vm import VirtualMachine

PASS = '\033[92m✓\033[0m'
FAIL = '\033[91m✗\033[0m'
tests_run = tests_passed = 0

def compile_and_run(source):
    tokens = Lexer(source).tokenize()
    cu = Parser(tokens).parse()
    module = Compiler().compile(cu)
    vm = VirtualMachine(module)
    return vm.run(capture=True)

def test(name, source, expected):
    global tests_run, tests_passed
    tests_run += 1
    try:
        output = compile_and_run(source)
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
        print(f"  {FAIL} {name} — {type(e).__name__}: {e}")

def test_dis(name, source, expected_ops):
    """Check that compiler emits specific opcodes."""
    global tests_run, tests_passed
    tests_run += 1
    from bytecode import Op
    tokens = Lexer(source).tokenize()
    cu = Parser(tokens).parse()
    module = Compiler().compile(cu)
    entry = module.units[module.entry]
    emitted_ops = [i.op for i in entry.code]
    for op in expected_ops:
        if op not in emitted_ops:
            print(f"  {FAIL} {name} — missing opcode {op.name}")
            print(f"       Emitted: {[o.name for o in emitted_ops]}")
            return
    print(f"  {PASS} {name}")
    tests_passed += 1

from bytecode import Op

print("\n── Bytecode Emission Tests (compiler correctness) ───────────────────")

test_dis("emits PUSH_INT for literals",
    "program t\n  print *, 42\nend program t",
    [Op.PUSH_INT, Op.PRINT_NL, Op.HALT])

test_dis("emits STORE/LOAD for variables",
    "program t\n  integer :: x\n  x = 7\n  print *, x\nend program t",
    [Op.STORE, Op.LOAD, Op.PRINT_NL, Op.HALT])

test_dis("emits ADD for addition",
    "program t\n  print *, 3 + 4\nend program t",
    [Op.PUSH_INT, Op.PUSH_INT, Op.ADD, Op.PRINT_NL])

test_dis("emits MUL for multiplication",
    "program t\n  print *, 3 * 4\nend program t",
    [Op.PUSH_INT, Op.PUSH_INT, Op.MUL, Op.PRINT_NL])

test_dis("emits POW for **",
    "program t\n  print *, 2**8\nend program t",
    [Op.PUSH_INT, Op.PUSH_INT, Op.POW, Op.PRINT_NL])

test_dis("emits JUMP_FALSE for IF",
    "program t\n  if (1 == 1) then\n    print *, 'y'\n  end if\nend program t",
    [Op.JUMP_FALSE, Op.JUMP])

test_dis("emits JUMP for DO loop back-edge",
    "program t\n  integer :: i\n  do i = 1, 3\n    print *, i\n  end do\nend program t",
    [Op.STORE, Op.JUMP, Op.HALT])

test_dis("emits ALLOC_ARR for array declaration",
    "program t\n  integer :: a(10)\nend program t",
    [Op.ALLOC_ARR, Op.HALT])

test_dis("emits CALL_BUILTIN for sqrt()",
    "program t\n  print *, sqrt(9.0)\nend program t",
    [Op.CALL_BUILTIN, Op.PRINT_NL])

test_dis("emits CALL for user function",
    "program t\n  print *, sq(3)\nend program t\ninteger function sq(n)\n  sq = n*n\nend function sq",
    [Op.CALL, Op.PRINT_NL])

test_dis("emits CONCAT for // operator",
    "program t\n  print *, 'a'//'b'\nend program t",
    [Op.CONCAT])

test_dis("emits NEG for unary minus",
    "program t\n  integer :: x\n  x = -5\n  print *, x\nend program t",
    [Op.NEG])

test_dis("emits CMP_GT for > comparison",
    "program t\n  if (5 > 3) print *, 'y'\nend program t",
    [Op.CMP_GT, Op.JUMP_FALSE])

print("\n── VM Execution Tests (end-to-end) ──────────────────────────────────")

test("Hello World",
    "program hello\n  print *, 'Hello, World!'\nend program hello",
    "Hello, World!")

test("Integer arithmetic",
    "program t\n  integer :: x\n  x = 3 + 4 * 2 - 1\n  print *, x\nend program t",
    "10")

test("Real arithmetic",
    "program t\n  real :: x\n  x = 1.0 / 4.0\n  print *, x\nend program t",
    "0.250000")

test("Power operator",
    "program t\n  integer :: x\n  x = 2**8\n  print *, x\nend program t",
    "256")

test("String concat",
    "program t\n  print *, 'Hello'//' '//'World'\nend program t",
    "Hello World")

test("IF true branch",
    "program t\n  if (10 > 5) then\n    print *, 'big'\n  else\n    print *, 'small'\n  end if\nend program t",
    "big")

test("IF false branch",
    "program t\n  if (3 > 5) then\n    print *, 'big'\n  else\n    print *, 'small'\n  end if\nend program t",
    "small")

test("ELSEIF chain",
    "program t\n  integer :: x\n  x = 5\n  if (x > 10) then\n    print *, 'large'\n  elseif (x > 3) then\n    print *, 'medium'\n  else\n    print *, 'small'\n  end if\nend program t",
    "medium")

test("DO loop sum",
    "program t\n  integer :: i, s\n  s = 0\n  do i = 1, 5\n    s = s + i\n  end do\n  print *, s\nend program t",
    "15")

test("DO loop with step",
    "program t\n  integer :: i, s\n  s = 0\n  do i = 10, 1, -2\n    s = s + i\n  end do\n  print *, s\nend program t",
    "30")

test("DO WHILE loop",
    "program t\n  integer :: i\n  i = 1\n  do while (i <= 5)\n    i = i + 1\n  end do\n  print *, i\nend program t",
    "6")

test("Nested loops",
    "program t\n  integer :: i, j, s\n  s = 0\n  do i = 1, 3\n    do j = 1, 3\n      s = s + 1\n    end do\n  end do\n  print *, s\nend program t",
    "9")

test("EXIT from loop",
    "program t\n  integer :: i\n  do i = 1, 100\n    if (i == 5) exit\n  end do\n  print *, i\nend program t",
    "5")

test("CYCLE in loop",
    "program t\n  integer :: i, s\n  s = 0\n  do i = 1, 10\n    if (mod(i,2) == 0) cycle\n    s = s + i\n  end do\n  print *, s\nend program t",
    "25")

test("Array read/write",
    "program t\n  integer :: a(5), i, s\n  do i = 1, 5\n    a(i) = i * i\n  end do\n  s = 0\n  do i = 1, 5\n    s = s + a(i)\n  end do\n  print *, s\nend program t",
    "55")

test("User function",
    "program t\n  integer :: square\n  print *, square(7)\nend program t\ninteger function square(n)\n  integer, intent(in) :: n\n  square = n * n\nend function square",
    "49")

test("Subroutine call",
    "program t\n  integer :: x\n  x = 5\n  call double(x)\n  print *, x\nend program t\nsubroutine double(x)\n  integer, intent(inout) :: x\n  x = x * 2\nend subroutine double",
    "10")

test("Builtin sqrt",
    "program t\n  real :: x\n  x = sqrt(9.0)\n  print *, x\nend program t",
    "3.000000")

test("Builtin abs",
    "program t\n  print *, abs(-42)\nend program t",
    "42")

test("Builtin mod",
    "program t\n  print *, mod(10, 3)\nend program t",
    "1")

test("LOGICAL operators",
    "program t\n  logical :: a, b\n  a = .TRUE.\n  b = .FALSE.\n  if (a .AND. .NOT. b) then\n    print *, 'yes'\n  end if\nend program t",
    "yes")

test("PARAMETER constant",
    "program t\n  integer, parameter :: N = 42\n  print *, N\nend program t",
    "42")

test("String length builtin",
    "program t\n  print *, len('hello')\nend program t",
    "5")

test("GOTO with label",
    "program t\n  integer :: x\n  x = 0\n  x = x + 1\n  if (x < 3) goto 10\n  print *, x\n10 continue\n  if (x < 3) goto 10\n  print *, x\nend program t",
    "3 3")

print(f"\n{'─'*60}")
print(f"Results: {tests_passed}/{tests_run} tests passed", end='')
if tests_passed == tests_run:
    print(f"  {PASS} All tests passed!")
else:
    print(f"  {FAIL} {tests_run-tests_passed} test(s) failed")
    sys.exit(1)
