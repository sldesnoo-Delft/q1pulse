# Q1Pulse dev notes

Working list of known issues, remarks and work in progress.
Numbers are stable: refer to items as `#4`, `R3`, etc. Don't renumber; move fixed items to *Done*.

Status values: `open`, `in progress`, `fixed`, `won't fix`.

## Open bugs

| #  | Area | Issue | Status | Notes |
|----|------|-------|--------|-------|
| 2  | [lang/math_expressions.py](../q1pulse/lang/math_expressions.py) `BinaryCondition` | Integer comparisons are unsigned. `R.n = -3; if_(R.n < 2)` takes the else branch. | open | Only float uses signed `ComparisonOp`s (`TODO add signed int`). README claims "Signed integer comparisons are emulated". Confirmed in Q1Simulator (ISA v2). Test: `test_condition_evaluation_negative` (xfail). |
| 4  | [lang/loops.py](../q1pulse/lang/loops.py) `RangeLoop` | Negative step gives one iteration too many: `loop_range(80, 0, -20)` → n=5, `range` gives 4 (extra iteration with value 0). | open | Use `n = len(range(start, stop, step))`. Test: `test_loop_range_pulse_count` (xfail). Fixing it changes the reference listing `q1*/loop_range`. |
| 5  | [lang/loops.py](../q1pulse/lang/loops.py), [lang/flow_statements.py](../q1pulse/lang/flow_statements.py) | Loop with n=0 (e.g. `loop_range(5, 5)`) is not skipped. | open | ISA v2 (`sub`+`jg`): body runs once. ISA v1 (`loop` with 0): probably ~2³² iterations. `LoopDurationStatement` adjusts time by `(n-1)*t_loop` → negative. Raise an error for n < 1, or skip the loop. |
| 6  | [lang/loops.py](../q1pulse/lang/loops.py) `ArrayLoop` | Type check compares `get_dtype(values[0])` with itself, so mixed types like `[0.1, 0, 0.3]` pass. | open | Should be `get_dtype(value)`. Also `max(literal_values)` raises `ValueError` when all values are expressions. |
| 7  | [lang/loops.py](../q1pulse/lang/loops.py) `LinspaceLoop` | `loop_linspace(a, b, 1)` raises `ZeroDivisionError`. | open | numpy returns `[start]`; use step 0 when n == 1. |
| 10 | [lang/math_expressions.py](../q1pulse/lang/math_expressions.py) `Multiply` | Float `-1.0 * -1.0` gives `-1.0`. `-1.0` is encoded as `0x80000000` (−2³¹); `muls32h` gives 2³⁰ and the `lsl 1` added for #1 overflows to `0x80000000`. Only this exact input pair overflows; `-1.0 * -0.999` = 0.999 is correct. | open | Cheapest fix: encode `-1.0` as `-(2³¹−1)` (`0x80000001`) in `_float_to_f32`, so the float range is symmetric. Values computed at run time (e.g. `-0.5 + -0.5`) can still produce `0x80000000`. Alternative: saturate after the multiply (costs cycles). Confirmed in Q1Simulator (ISA v2). |
| 11 | [assembler/generator.py](../q1pulse/assembler/generator.py) `mul32h` / `arg_f` | `register * negative float literal` does not assemble: the literal is passed as unsigned immediate (`muls32h R1,3221225472,R2` for −0.5), and Q1Simulator rejects immediates ≥ 2³¹ for `muls32h`. Every negative float literal fails. `move` accepts the same value. | open | Not checked on hardware. Fix: pass a signed immediate for the multiply instructions, or move the literal into a temp register first. Independent of #1. |
| 9  | [program.py](../q1pulse/program.py), sequencer `if_` | Assignment to a program register inside a sequencer-local block is executed unconditionally on the other sequencers. In `tests/test_if_rt_2seq.py`, `with P2.if_(R.a > R.c): R.c = 10` sets `R.c = 10` on P1 for every value of `a`. | open (question) | Is this intended? Options: raise an error for `p.R` assignment inside `Pn.if_()`, or add the assignment only to that sequencer. The test only asserts P2's value. |

## Remarks / cleanup

| #   | Area | Remark | Status |
|-----|------|--------|--------|
| R1  | `_float_to_f32` / `_32_float` | Scaling is asymmetric: encode with `2³¹ − 0.1`, decode with `2³¹ − 1`. Conversion helpers are duplicated in `assembler/generator.py` and `lang/program_variables.py`; move them to one place. | open |
| R2  | `Operand.__eq__` | Returns a `BinaryCondition`. That makes `Register` unhashable and `reg in list` always true. Consider `__hash__ = object.__hash__` and a `__bool__` on conditions that raises. | open |
| R3  | [program.py](../q1pulse/program.py) | `feedback_routing` raises `AttributeError` before `compile()`. `compile()` does not reset `_q1registers` / `_var_registers`. | open |
| R4  | various | User-facing errors raise plain `Exception` (`Program.__getitem__`, `_convert_frequency`, `_convert_phase`, `instrument.py`). Use the `Q1*Error` hierarchy. | open |
| R5  | `instrument.py`, `util/` | Warnings use `print` instead of `logger.warning` (e.g. "input overload"). | open |
| R6  | `Program.parallel`, `if_`, `__loop`, `generator.scope()`, `register_args` | Context managers do not use `try/finally`. An exception inside a `with` block (e.g. in Jupyter) leaves the timeline disabled or the scope open. | open |
| R7  | `Program.else_` | API is uneven: `else_` is a property (`with p.else_:`), while `if_()` / `elif_()` are calls. | open |
| R8  | `math_expressions.py`, `IfBlockStatement` | Duplicated code: same `_get_dtype` in Addition/Subtraction/Multiply; both branches of `IfBlockStatement.write_instruction` are nearly identical. | open |
| R9  | `tests/` | No automated tests: scripts plot results and contain no asserts. Turn them into pytest golden-file tests on Q1Simulator (diff `.q1asm` listings, assert simulator output / `log` values). Bugs #1–#4 would have been caught. | done: see [tests/README.md](../tests/README.md) |
| R10 | repo root | `TODO.txt` and `Compiler_notes.txt` are untracked design notes. Merge into *Design notes* below or move to `docs/`. | open |
| R13 | `Multiply` / `generator.mul32*` | On ISA v1 a multiply compiles to `muls32h`/`muls32l`, which does not exist in v1. The error only appears when the program is loaded (assembler error). Raise a `Q1CompileError` for multiplication on ISA v1. | open |
| R11 | `Q1Instrument` | A program hangs at `wait_sync` (stopped by timeout) when sequencers armed by an earlier `Q1Instrument` on the same modules are still synchronized. The test fixture resets the cluster before every test. Consider disabling sync on unused sequencers in `start_program`. | open |
| R12 | `tests/` | Reference listings `q1_v2/phase`, `phase_shifting` and `variables` are outdated after fixes #1 and #3. Review the diff and run `pytest --update-golden`. | done |

## Done

| #  | Issue | Resolution |
|----|-------|------------|
| 1  | Float multiply returned half the value (`0.5 * 0.5` → 0.125): `muls32h` on Q31 values yields Q30. | fixed; verified in Q1Simulator (→ 0.25) |
| 3  | ISA v2 `set_phase` / `shift_phase` with a register overwrote the user's register (`mulu32h R1,1e9,R1`). | fixed; result now goes to a temp register |
| 8  | `register_args.arg_f`: float-literal branch referenced undefined `asm_reg` (only with `comment_arg_conversions=True`). | fixed; uses `value` |

## Design notes / work in progress

Currently in [TODO.txt](../TODO.txt) and [Compiler_notes.txt](../Compiler_notes.txt) (untracked). Main topics:

- Timeline models: program serial/parallel, segment mode with fixed duration (pulse_lib), `reg_wait` on all sequencers.
- Program / instrument class split (`ProgramBase`, `Backend`, `InstrumentBase`).
- Subroutines (call via `R63` return address).
- Register optimization: dependency graph, skip unreferenced registers, cache float→int conversions.
- Constant multiply via shift/add, 32-bit multiply emulation, PRNG timing.
- Compiler: basic blocks, register scopes, reordering within blocks.
- Q1ASM wishlist for Qblox (RT settings/commands redesign, signed/unsigned jumps).
- Spin-qubit requests: DC / bias-T compensation, digitizer downsampling and threshold.
