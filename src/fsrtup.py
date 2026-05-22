#!/usr/bin/env python3
"""
Fsrtup — Fortran 77/90 Compiler + Virtual Machine
======================================================
Pipeline:  Source → Lexer → Parser → AST → Semantic Analysis
                  → Compiler → Bytecode → VM → Output

Usage:
  fsrtup compile <file.f90>              Compile to .fbc bytecode file
  fsrtup run     <file.f90>              Compile and run
  fsrtup exec    <file.fbc>             Execute a .fbc bytecode file
  fsrtup dis     <file.f90>             Disassemble (show bytecode)
  fsrtup check   <file.f90>             Parse + semantic check only
  fsrtup tokens  <file.f90>             Dump token stream
  fsrtup ast     <file.f90>             Dump AST
"""

import sys, os, argparse, pickle, pprint
sys.path.insert(0, os.path.dirname(__file__))

from lexer import Lexer
from parser import Parser, ParseError
from compiler import Compiler, CompileError
from vm import VirtualMachine
from ast_nodes import CompilationUnit


BANNER = r"""
  ___         _   ___
 | __| ___ _ _| |_| _ \_  _
 | _| / _ \ '_|  _|  _/ || |
 |_|  \___/_|  \__|_|  \_, |
   Fortran Compiler + VM |__/
"""


def load_source(path):
    try:
        return open(path).read()
    except FileNotFoundError:
        print(f"Error: '{path}' not found.", file=sys.stderr); sys.exit(1)

def is_fixed(path):
    return os.path.splitext(path)[1].lower() in ('.f', '.for', '.f77')

def parse_source(path):
    src = load_source(path)
    lexer = Lexer(src, fixed_form=is_fixed(path))
    tokens = lexer.tokenize()
    try:
        return Parser(tokens).parse()
    except ParseError as e:
        print(f"Parse error: {e}", file=sys.stderr); sys.exit(1)

def compile_ast(cu):
    try:
        return Compiler().compile(cu)
    except CompileError as e:
        print(f"Compile error: {e}", file=sys.stderr); sys.exit(1)


# ── Commands ──────────────────────────────────────────────────────────────────

def cmd_tokens(args):
    src = load_source(args.file)
    for tok in Lexer(src, is_fixed(args.file)).tokenize():
        print(tok)

def cmd_ast(args):
    cu = parse_source(args.file)
    pprint.pprint(cu, width=120)

def cmd_check(args):
    cu = parse_source(args.file)
    module = compile_ast(cu)
    print(f"OK — {len(module.units)} unit(s): {', '.join(module.units)}")
    print(f"     Entry point: {module.entry}")

def cmd_dis(args):
    cu = parse_source(args.file)
    module = compile_ast(cu)
    print(module.disassemble())

def cmd_compile(args):
    cu = parse_source(args.file)
    module = compile_ast(cu)
    out = args.output or (os.path.splitext(args.file)[0] + '.fbc')
    with open(out, 'wb') as f:
        pickle.dump(module, f)
    total = sum(len(u.code) for u in module.units.values())
    print(f"Compiled {len(module.units)} unit(s), {total} instructions → {out}")

def cmd_exec(args):
    with open(args.file, 'rb') as f:
        module = pickle.load(f)
    VirtualMachine(module).run(capture=False)

def cmd_run(args):
    cu = parse_source(args.file)
    module = compile_ast(cu)
    try:
        VirtualMachine(module).run(capture=False)
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr); sys.exit(130)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    if len(sys.argv) == 1:
        print(BANNER); print(__doc__); sys.exit(0)

    ap = argparse.ArgumentParser(prog='fsrtup', description='fsrtup Fortran compiler')
    sub = ap.add_subparsers(dest='cmd')

    for name, help_ in [('run','Compile and run'), ('dis','Show bytecode'),
                         ('check','Parse+check'), ('tokens','Dump tokens'),
                         ('ast','Dump AST')]:
        p = sub.add_parser(name, help=help_)
        p.add_argument('file')

    p = sub.add_parser('compile', help='Compile to .fbc')
    p.add_argument('file')
    p.add_argument('-o', dest='output', default=None)

    p = sub.add_parser('exec', help='Run a .fbc file')
    p.add_argument('file')

    args = ap.parse_args()
    dispatch = {
        'run': cmd_run, 'dis': cmd_dis, 'check': cmd_check,
        'tokens': cmd_tokens, 'ast': cmd_ast,
        'compile': cmd_compile, 'exec': cmd_exec,
    }
    fn = dispatch.get(args.cmd)
    if fn: fn(args)
    else:  ap.print_help(); sys.exit(1)

if __name__ == '__main__':
    main()
