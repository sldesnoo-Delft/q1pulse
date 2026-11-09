# Q1Pulse tests

The tests run on [Q1Simulator](https://github.com/sldesnoo-Delft/q1simulator) by default,
or on a Qblox Cluster with one QCM and one QRM.

Each test builds a program, compiles it, compares the Q1ASM listing with the reference
listing in `q1_v2/` (ISA v2) or `q1/` (ISA v1), runs it, and checks results where possible.

## Running

| Command | What it does |
|---------|--------------|
| `pytest` | All tests on the simulator with ISA v2 (~40 s). |
| `pytest -m "not slow"` | Skip the slow CSD tests (~3 s). |
| `pytest --isa 1` | Simulator with Q1ASM ISA v1. ISA v2-only tests are skipped. |
| `pytest tests/test_ramp.py --plot` | Show plots of the simulated output. Close the windows to continue. |
| `pytest --hw 192.168.0.2 -k ramp` | Run on hardware. The same program also runs on a simulator; its output is plotted as reference for the oscilloscope. |
| `pytest --hw 192.168.0.2 --plot tests/test_sync.py` | Hardware-only scope test (`hw_only`), with the reference plot shown. |
| `pytest --update-golden` | Accept the generated listings as new reference listings. Review with `git diff`. |

Other options: `--qcm-slot` (default 8), `--qrm-slot` (default 10), `--no-reference`.

Output is written to `tests/output/` (not tracked):
- `output/<sim|hw|reference>/<q1|q1_v2>/<program>/`: generated listings,
- `output/plots/`: plots. These are always saved when running on hardware, and with `--plot`.

## Running one test interactively (IPython, Spyder)

Run a test file, e.g. `%run test_ramp.py` or `runfile('test_ramp.py')`.
The `__main__` block calls `run_interactive(test_ramp)`: it runs that one test function without pytest
and shows the plots, like the original scripts.

- Simulator or hardware: set `INTERACTIVE_HW_ADDRESS`, `INTERACTIVE_ISA_VERSION` and `INTERACTIVE_REFERENCE`
  in [q1test.py](q1test.py), or pass them as arguments:
  `run_interactive(test_ramp, hw_address="192.168.0.2")`.
- Parametrized tests get their parameters as keyword arguments: `run_interactive(test_if_rt, a=0, c=1, d=3)`.
- The returned object gives access to the executed programs, e.g. `q1 = run_interactive(test_ramp)`,
  then `q1.runs[-1].instrument` and `q1.runs[-1].program`.
- Listing differences are printed, not raised. Assertions in the test do raise.
- The simulator cluster is recreated on every run. A hardware connection is reused.

## Writing a test

```python
from q1test import Target, run_interactive


def build(t: Target):
    instrument = t.new_instrument()
    instrument.add_qcm(t.qcm)
    instrument.add_control('P1', t.qcm.name, [2])

    p = instrument.new_program('my_test')   # name of reference listing directory
    p.P1.block_pulse(100, 0.5)

    p.compile(listing=True, annotate=True)
    return instrument, p


def test_my_test(q1):
    run = q1.run(build)       # build, check listing, execute, plot
    # run.main.get_variables(), run.main.get_registers('P1'),
    # run.main.get_acquisition_bins('R1', 'default'), run.main.get_output('P1') (simulator only)


if __name__ == "__main__":
    run_interactive(test_my_test)
```

`build` is called once per target: for the hardware and for the simulator reference.
Use `t.is_simulator` for settings that only apply to one of them, and
`set_mock_data()` for simulated acquisition data (ignored on hardware).

To run a program multiple times with different variable values:
```python
    run = q1.prepare(build)
    run.execute(variables={"a": 0}, label="a=0")
```

Markers: `hw_only`, `isa_v2`, `slow`. Known bugs are marked `xfail(strict=True)` with the DEVNOTES number,
so they start failing as soon as the bug is fixed.

A new test has no reference listing yet. Run it once with `--update-golden` and commit the listing.
