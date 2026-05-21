#!/usr/bin/env python3
"""
Fsrtup — A Fortran 77/90 interpreter written in Python

Usage:
  fsrtup run <file.f90>    Interpret the program
  fsrtup check <file.f90>  Parse & check only (no run)
  fsrtup dump <file.f90>   Dump token stream
  fsrtup ast <file.f90>    Dump AST
  fsrtup -h | --help
"""

import sys
import os
import argparse
import pprint

# Add src directory to path when running from project root
sys.path.insert(0, os.path.dirname(__file__))

from lexer import Lexer
from parser import Parser, ParseError
from interpreter import Interpreter
from ast_nodes import CompilationUnit

def load_source(path: str) -> str:
    try:
        with open(path, 'r') as f:
            return f.read()
    except FileNotFoundError:
        print(f"Error: File '{path}' not found.", file=sys.stderr)
        sys.exit(1)


def detect_fixed_form(path: str) -> bool:
    """Heuristic: .f or .for extensions usually mean fixed-form."""
    ext = os.path.splitext(path)[1].lower()
    return ext in ('.f', '.for', '.f77')


def cmd_tokens(args):
    source = load_source(args.file)
    fixed = detect_fixed_form(args.file)
    lexer = Lexer(source, fixed_form=fixed)
    tokens = lexer.tokenize()
    for tok in tokens:
        print(tok)


def cmd_ast(args):
    source = load_source(args.file)
    fixed = detect_fixed_form(args.file)
    lexer = Lexer(source, fixed_form=fixed)
    tokens = lexer.tokenize()
    try:
        parser = Parser(tokens)
        cu = parser.parse()
        pprint.pprint(cu, width=100)
    except ParseError as e:
        print(f"Parse error: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_check(args):
    source = load_source(args.file)
    fixed = detect_fixed_form(args.file)
    lexer = Lexer(source, fixed_form=fixed)
    tokens = lexer.tokenize()
    try:
        parser = Parser(tokens)
        cu = parser.parse()
        unit_names = [u.name for u in cu.units]
        print(f"OK — {len(cu.units)} program unit(s): {', '.join(unit_names)}")
    except ParseError as e:
        print(f"Parse error: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_run(args):
    source = load_source(args.file)
    fixed = detect_fixed_form(args.file)
    lexer = Lexer(source, fixed_form=fixed)
    tokens = lexer.tokenize()
    try:
        parser = Parser(tokens)
        cu = parser.parse()
    except ParseError as e:
        print(f"Parse error: {e}", file=sys.stderr)
        sys.exit(1)

    interp = Interpreter()
    interp.load(cu)
    try:
        interp.run(capture_output=False)
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        sys.exit(130)
    except Exception as e:
        print(f"Runtime error: {e}", file=sys.stderr)
        sys.exit(1)


def main():

    parser = argparse.ArgumentParser(
        prog='fsrtup',
        description='fsrtup — Fortran 77/90 interpreter')
    sub = parser.add_subparsers(dest='command')

    p_run = sub.add_parser('run', help='Run a Fortran program')
    p_run.add_argument('file', help='Source file (.f90, .f)')
    p_run.set_defaults(func=cmd_run)

    p_check = sub.add_parser('check', help='Parse and check a Fortran program')
    p_check.add_argument('file')
    p_check.set_defaults(func=cmd_check)

    p_dump = sub.add_parser('dump', help='Dump token stream')
    p_dump.add_argument('file')
    p_dump.set_defaults(func=cmd_tokens)

    p_ast = sub.add_parser('ast', help='Dump AST')
    p_ast.add_argument('file')
    p_ast.set_defaults(func=cmd_ast)

    args = parser.parse_args()
    if not hasattr(args, 'func'):
        parser.print_help()
        sys.exit(1)
    args.func(args)


if __name__ == '__main__':
    main()
