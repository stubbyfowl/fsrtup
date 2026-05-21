# Fsrtup — Fortran 77/90 Interpreter

A pure-Python interpreter for a substantial subset of Fortran 77/90, built from scratch with a hand-written lexer, recursive-descent parser, and tree-walking interpreter.

## Features

- **Lexer**: Full tokenization of free-form and fixed-form Fortran (`.f90` / `.f`)
- **Parser**: Recursive-descent parser producing a typed AST
- **Interpreter**: Tree-walking interpreter with environment-based scoping

### Supported language features
- Data types: `INTEGER`, `REAL`, `DOUBLE PRECISION`, `LOGICAL`, `CHARACTER`
- Control flow: `IF/THEN/ELSEIF/ELSE/ENDIF`, `DO`, `DO WHILE`, `GOTO`, `CYCLE`, `EXIT`
- Subprograms: `FUNCTION`, `SUBROUTINE` with `INTENT(IN/OUT/INOUT)`
- Arrays: 1D array declarations and element access
- I/O: `PRINT *`, `WRITE`, `READ`
- Declarations: `IMPLICIT NONE`, `PARAMETER`, `DIMENSION`
- Operators: arithmetic, relational (both symbolic and `.EQ.` style), logical, string concat `//`
- 40+ built-in intrinsics: `ABS`, `SQRT`, `SIN`, `COS`, `MOD`, `MAX`, `MIN`, `LEN`, `TRIM`, etc.

## Installation

No dependencies required — just Python 3.8+.

```bash
# Clone or extract the project
cd fsrtup

# Run directly
python3 src/fsrtup.py run examples/hello.f90
```

### Optional: install as a command

```bash
pip install --editable .
fsrtup run examples/hello.f90
```

## Usage

```
fsrtup run   <file.f90>   # Run a Fortran program
fsrtup check <file.f90>   # Parse and syntax-check only
fsrtup dump  <file.f90>   # Dump the token stream
fsrtup ast   <file.f90>   # Dump the AST
```

## Examples

```bash
python3 src/fsrtup.py run examples/hello.f90
python3 src/fsrtup.py run examples/fibonacci.f90
python3 src/fsrtup.py run examples/math_demo.f90
```

## Running tests

```bash
python3 tests/test_fsrtup.py
```

Expected: **35/35 tests passed**.

## Project structure

```
fsrtup/
├── src/
│   ├── fsrtup.py       # CLI entry point
│   ├── lexer.py        # Tokenizer
│   ├── ast_nodes.py    # AST node dataclasses
│   ├── parser.py       # Recursive-descent parser
│   └── interpreter.py  # Tree-walking interpreter
├── examples/
│   ├── hello.f90
│   ├── fibonacci.f90
│   └── math_demo.f90
├── tests/
│   └── test_fsrtup.py
└── README.md
```

## Architecture

```
Source (.f90)
    │
    ▼
 Lexer          → Token stream
    │
    ▼
 Parser         → AST (CompilationUnit)
    │
    ▼
 Interpreter    → Output
```

The interpreter uses a chain of `Environment` objects for scoping, with the global environment holding all top-level program units. Functions and subroutines run in their own fresh environment with parameters pre-bound.
