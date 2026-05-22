# Fsrtup — Open-Source Fortran 77/90 Compiler

A true compiler for Fortran 77/90 written in pure Python 3.
**It does not interpret source code.** It compiles Fortran to stack-based
bytecode, which a separate VM then executes — no AST is touched at runtime.

## Compiler Pipeline

```
Fortran source (.f90)
        │
        ▼
   ┌─────────┐
   │  Lexer  │  tokenises source, strips comments/whitespace
   └────┬────┘
        │  List[Token]
        ▼
   ┌─────────┐
   │  Parser │  recursive-descent, builds typed AST
   └────┬────┘
        │  CompilationUnit (AST)
        ▼
   ┌──────────────────┐
   │ Semantic Analyzer│  symbol table, scope resolution, type checking
   └────────┬─────────┘
        │  annotated AST + symbol tables
        ▼
   ┌──────────┐
   │ Compiler │  traverses AST, EMITS bytecode instructions
   └────┬─────┘       (no values computed here — only instructions)
        │  BytecodeModule (.fbc)
        ▼
   ┌──────────────────────┐
   │  Virtual Machine     │  executes bytecode, knows nothing of Fortran
   └──────────────────────┘
        │
        ▼
     Output
```

The `.fbc` bytecode file is a **standalone artifact** — it can be executed
without the source file, just like a `.class` or `.pyc` file.

## Bytecode Instruction Set

| Instruction    | Description                            |
|----------------|----------------------------------------|
| `PUSH_INT n`   | Push integer constant                  |
| `PUSH_REAL f`  | Push real constant                     |
| `PUSH_STR s`   | Push string constant                   |
| `PUSH_BOOL b`  | Push logical constant                  |
| `LOAD name`    | Load variable onto stack               |
| `STORE name`   | Pop stack, store into variable         |
| `LOAD_ARR name`| Array element load (index on stack)    |
| `STORE_ARR name`| Array element store                   |
| `ADD / SUB / MUL / DIV / POW` | Arithmetic           |
| `NEG`          | Unary negation                         |
| `CONCAT`       | String concatenation (//)              |
| `CMP_EQ/NE/LT/LE/GT/GE` | Comparisons               |
| `LOGICAL_AND/OR/NOT` | Logical operators                |
| `JUMP addr`    | Unconditional jump                     |
| `JUMP_FALSE addr` | Jump if top-of-stack is false       |
| `JUMP_TRUE addr`  | Jump if top-of-stack is true        |
| `PRINT_NL n`   | Pop n items, print space-separated     |
| `CALL (name,n)`| Call user-defined function/subroutine  |
| `CALL_BUILTIN (name,n)` | Call built-in function        |
| `RETURN`       | Return from subroutine                 |
| `RETURN_VAL`   | Return with value from function        |
| `ALLOC_ARR (name,ndim)` | Allocate array                |
| `POP`          | Discard top of stack                   |
| `HALT`         | End program                            |

## Usage

```bash
# Compile Fortran to .fbc bytecode
python3 src/fsrtup.py compile hello.f90

# Execute the bytecode (source not needed)
python3 src/fsrtup.py exec hello.fbc

# Compile and run in one step
python3 src/fsrtup.py run hello.f90

# Show bytecode disassembly
python3 src/fsrtup.py dis hello.f90

# Parse + type-check only
python3 src/fsrtup.py check hello.f90
```

## Example: What the compiler emits

For `x = 5 + 2 * 3`:

```
PUSH_INT  5
PUSH_INT  2
PUSH_INT  3
MUL
ADD
STORE  'x'
```

For `DO i = 1, n`:
```
PUSH_INT 1
STORE '__step_i__' ...
PUSH_INT 1
STORE '__step_i__'
<loop_top>:
LOAD '__step_i__'
PUSH_INT 0
CMP_GT
JUMP_TRUE <step_pos>
LOAD 'i'
LOAD '__stop_i__'
CMP_GE
JUMP <merge>
<step_pos>:
LOAD 'i'
LOAD '__stop_i__'
CMP_LE
<merge>:
JUMP_FALSE <exit>
  ... body ...
LOAD 'i'
LOAD '__step_i__'
ADD
STORE 'i'
JUMP <loop_top>
<exit>:
```

## Source layout

```
src/
├── lexer.py      Tokeniser → List[Token]
├── ast_nodes.py  AST node dataclasses
├── parser.py     Recursive-descent parser → CompilationUnit AST
├── semantic.py   Symbol tables, type checking, scope resolution
├── bytecode.py   Instruction set (Op enum) + BytecodeModule
├── compiler.py   AST → BytecodeModule  ← THE COMPILER
├── vm.py         BytecodeModule → output  ← THE VM
└── fsrtup.py     CLI driver

examples/
├── hello.f90
├── fibonacci.f90
├── math_demo.f90
└── bubblesort.f90
```

## Language support

- `PROGRAM`, `SUBROUTINE`, `FUNCTION` units
- `INTEGER`, `REAL`, `DOUBLE PRECISION`, `LOGICAL`, `CHARACTER`
- `IF / ELSEIF / ELSE / END IF` blocks and single-line IF
- `DO` counted loops, `DO WHILE`, infinite `DO`
- `CYCLE`, `EXIT`, `GOTO`
- 1-D arrays with `ALLOC_ARR` bytecode
- `PRINT *`, `WRITE`
- `IMPLICIT NONE`, `PARAMETER`
- All arithmetic operators including `**`
- `.AND.`, `.OR.`, `.NOT.`, `.EQ.`, `.NE.`, etc. (with short-circuit)
- 40+ built-in functions

## License

MIT — free to use, modify, distribute.
