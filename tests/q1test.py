"""Test harness for running Q1Pulse tests on Q1Simulator or on Qblox hardware.

A test defines a *build function* that creates the instrument and program for a
`Target` and compiles it. The `q1` fixture (see conftest.py) calls the build
function, checks the Q1ASM listing against the reference listing in
`tests/q1_v2/` or `tests/q1/`, and runs the program.

When the tests run on hardware the same build function is also executed on a
simulator. The simulator output is plotted as a reference for the output that
is shown on the oscilloscope.

Example::

    def build(t: Target):
        instrument = t.new_instrument()
        instrument.add_qcm(t.qcm)
        instrument.add_control('P1', t.qcm.name, [2])
        p = instrument.new_program('my_test')
        p.P1.block_pulse(100, 0.5)
        p.compile(listing=True, annotate=True)
        return instrument, p

    def test_my_test(q1):
        q1.run(build)

    if __name__ == "__main__":
        run_interactive(test_my_test)

`run_interactive` runs one test function without pytest, e.g. in IPython or
Spyder, and shows the plots. Configure the target with the INTERACTIVE_*
settings below or with arguments of `run_interactive`.
"""
from __future__ import annotations

import difflib
import inspect
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import matplotlib.pyplot as pt
import numpy as np

from q1pulse.instrument import Q1Instrument
from q1pulse.program import Program
from q1pulse.lang.program_variables import IntVariable, FloatVariable


TESTS_DIR = Path(__file__).parent
OUTPUT_DIR = TESTS_DIR / "output"

DEFAULT_QCM_SLOT = 8
DEFAULT_QRM_SLOT = 10

# Settings for run_interactive().
INTERACTIVE_HW_ADDRESS: str | None = None
"""IP address of the Cluster, e.g. "192.168.0.2". None: run on simulator."""
INTERACTIVE_ISA_VERSION: tuple[int, int] = (2, 0)
"""ISA version of simulator. Ignored when running on hardware."""
INTERACTIVE_REFERENCE: bool = True
"""When running on hardware also run on simulator and plot the output as reference."""


@dataclass
class Target:
    """A cluster with one QCM and one QRM to run the tests on."""
    name: str
    """'sim', 'hw' or 'reference'."""
    cluster: Any
    qcm: Any
    qrm: Any
    is_simulator: bool
    isa_version: tuple[int, int]

    @property
    def isa_v2(self) -> bool:
        return self.isa_version[0] == 2

    @property
    def isa_dir(self) -> str:
        """Name of the directory with reference listings for this ISA."""
        return "q1_v2" if self.isa_v2 else "q1"

    @property
    def output_dir(self) -> Path:
        return OUTPUT_DIR / self.name / self.isa_dir

    def new_instrument(self, listing: bool = True) -> Q1Instrument:
        """Returns a new Q1Instrument writing its listings to the output directory.

        Args:
            listing: if False the instrument has no output path and no listing
                is written. Use this for tests without reference listing.
        """
        return Q1Instrument(str(self.output_dir) if listing else None)

    def reset(self):
        self.cluster.reset()


BuildFunction = Callable[[Target], tuple[Q1Instrument, Program]]


@dataclass
class Run:
    """A program built and compiled for one target."""
    target: Target
    instrument: Q1Instrument
    program: Program
    _loaded: bool = False

    def execute(self, variables: dict[str, int | float] | None = None):
        """Runs the program and waits till it has stopped.

        Args:
            variables: values for program variables to set before starting.
        """
        if variables:
            if not self._loaded:
                self.instrument.load_program(self.program)
            self.instrument.set_variables(variables)
        self.instrument.start_program(self.program)
        self.instrument.wait_stopped()
        self._loaded = True

    def get_variables(self) -> dict[str, dict[str, int | float]]:
        """Returns the values of the program variables per sequencer."""
        return self.instrument.get_variables(program=self.program)

    def get_registers(self, sequencer_name: str) -> dict[str, int | float]:
        """Returns the values of the registers of a sequencer after execution.

        Only registers allocated at the top level of the program are available.
        Registers in a loop or if block are released at the end of the block.

        Returns:
            dict with register name, e.g. 'R.a' or 'Rs.x', and the value
            converted to int or float.
        """
        if self.program.q1asm(sequencer_name) is None:
            raise Exception(f"Sequencer {sequencer_name} has not been executed: it has no IO instructions. "
                            "Compile with optimize=0 to execute it anyway.")
        reg_mapping = {
            name: asm_reg
            for name, asm_reg in self.program.register_mapping[sequencer_name].items()
            if name.startswith(("R.", "Rs."))
            }
        seq = self._get_sequencer(sequencer_name)
        module = self.instrument.modules[seq.module_name]
        values = module.get_sequencer_registers(seq.seq_nr, list(reg_mapping.values()))
        builder = self.program[sequencer_name]
        result = {}
        for name, asm_reg in reg_mapping.items():
            scope, short_name = name.split(".", 1)
            registers = self.program.R if scope == "R" else builder.Rs
            dtype = registers[short_name].dtype
            variable = FloatVariable() if dtype is float else IntVariable()
            result[name] = variable.value2python(values[asm_reg])
        return result

    def get_output(self, sequencer_name: str) -> dict[str, np.ndarray]:
        """Returns the simulated output [V] of a sequencer with 1 ns resolution.

        Returns:
            dict with output name and data. The name is the sequencer name for a
            single output, or the sequencer name with suffix '-I', '-Q' for IQ output.
        """
        if not self.target.is_simulator:
            raise Exception("Output is only available on the simulator")
        seq = self._get_sequencer(sequencer_name)
        module = self.instrument.modules[seq.module_name].pulsar
        output = module.get_output(channels=[seq.seq_nr])
        return {name: data.data for name, data in output.items()}

    def get_acquisition_bins(self, sequencer_name: str, acq_name: str):
        return self.instrument.get_acquisition_bins(sequencer_name, acq_name)

    def set_mock_data(self, sequencer_name: str, acq_name: str, data):
        """Sets acquisition mock data on the simulator. Does nothing on hardware."""
        set_mock_data(self.instrument, sequencer_name, acq_name, data)

    def _get_sequencer(self, sequencer_name):
        sequencers = self.instrument.controllers | self.instrument.readouts
        return sequencers[sequencer_name]


def count_pulses(data: np.ndarray, threshold: float) -> int:
    """Returns the number of times the data rises above threshold."""
    above = np.asarray(data) > threshold
    return int(np.count_nonzero(above[1:] & ~above[:-1]) + above[0])


def set_mock_data(instrument: Q1Instrument, sequencer_name: str, acq_name: str, data):
    """Sets acquisition mock data on the simulator. Does nothing on hardware."""
    seq = (instrument.controllers | instrument.readouts)[sequencer_name]
    module = instrument.modules[seq.module_name].pulsar
    sim_seq = module.sequencers[seq.seq_nr]
    if hasattr(sim_seq, "set_acquisition_mock_data"):
        sim_seq.set_acquisition_mock_data([data], name=acq_name, repeat=True)


@dataclass
class Q1TestRun:
    """The program built for the target and, on hardware, for the simulator reference."""
    main: Run
    reference: Run | None
    _q1test: Q1Test

    @property
    def instrument(self) -> Q1Instrument:
        return self.main.instrument

    @property
    def program(self) -> Program:
        return self.main.program

    @property
    def simulation(self) -> Run | None:
        """The run executed on a simulator: the main run or the hardware reference."""
        if self.main.target.is_simulator:
            return self.main
        return self.reference

    def execute(self, variables: dict[str, int | float] | None = None, label: str = ""):
        """Executes the program on the target and the reference simulator, and plots the output.

        Args:
            variables: values for program variables to set before starting.
            label: label for the plot when a program is executed multiple times.
        """
        self.main.execute(variables)
        if self.reference is not None:
            self.reference.execute(variables)
        self._q1test.plot(self, label)
        return self


class Q1Test:
    """Fixture object to build, check and run Q1Pulse programs."""

    def __init__(self, test_name: str, target: Target, reference: Target | None,
                 plot: bool, update_golden: bool):
        self.test_name = test_name
        self.target = target
        self.reference_target = reference
        self._plot = plot or not target.is_simulator
        self._update_golden = update_golden
        self.figures: list[tuple[str, Any]] = []
        self.listing_errors: list[str] = []
        """Listing differences. Reported after the test has been executed. See conftest.py."""
        self.runs: list[Q1TestRun] = []
        """All programs prepared in the test. Use to inspect results after run_interactive."""

    @property
    def is_simulator(self) -> bool:
        return self.target.is_simulator

    @property
    def plotting(self) -> bool:
        """True if plots are made: with option --plot or when running on hardware."""
        return self._plot

    def new_figure(self, name: str):
        """Creates a new figure that will be saved in tests/output/plots and shown with --plot."""
        fig = pt.figure(figsize=(10, 5))
        self.figures.append((name, fig))
        return fig

    def save_figures(self):
        plot_dir = OUTPUT_DIR / "plots"
        plot_dir.mkdir(parents=True, exist_ok=True)
        for name, fig in self.figures:
            file_name = re.sub(r"[^\w\-]+", "_", f"{self.test_name}_{name}") + ".png"
            fig.savefig(plot_dir / file_name)

    def prepare(self, build: BuildFunction, check_listing: bool = True) -> Q1TestRun:
        """Builds and compiles the program for the target and the reference simulator.

        Differences with the reference listing are reported as failure after
        the test function has completed, so the other checks of the test are
        executed as well.

        Args:
            build: function creating and compiling the program for a target.
            check_listing: if True compare the Q1ASM listing with the reference listing.
        """
        main = Run(self.target, *build(self.target))
        if check_listing:
            self._check_listing(main)
        reference = None
        if self.reference_target is not None:
            reference = Run(self.reference_target, *build(self.reference_target))
        test_run = Q1TestRun(main, reference, self)
        self.runs.append(test_run)
        return test_run

    def run(self, build: BuildFunction, check_listing: bool = True) -> Q1TestRun:
        """Builds, compiles and executes the program, and plots the simulator output."""
        return self.prepare(build, check_listing).execute()

    def plot(self, test_run: Q1TestRun, label: str = ""):
        if not self._plot:
            return
        sim_run = test_run.simulation
        if sim_run is None:
            return
        target = sim_run.target
        suffix = f" [{label}]" if label else ""
        if not self.target.is_simulator:
            suffix += " simulator reference"
        for module in [target.qcm, target.qrm]:
            if module.name not in sim_run.instrument.modules:
                continue
            name = f"{module.name}{suffix}"
            self.new_figure(name)
            module.plot()
            pt.title(f"{self.test_name}\n{name}")
            pt.xlabel("[ns]")
            pt.ylabel("[V]")
            pt.grid(True)
            if pt.gca().get_legend_handles_labels()[0]:
                pt.legend()

    def _check_listing(self, run: Run):
        """Compares the generated Q1ASM listings with the reference listings."""
        program_path = run.program.path
        if program_path is None:
            raise AssertionError(
                "Program has no output path. Use `t.new_instrument(listing=False)` "
                "and `check_listing=False` for tests without reference listing.")
        output_dir = Path(program_path)
        golden_dir = TESTS_DIR / run.target.isa_dir / output_dir.name
        generated = sorted(output_dir.glob("*.q1asm"))
        if not generated:
            raise AssertionError(f"No listing generated in {output_dir}. "
                                 "Compile the program with `listing=True`.")
        if self._update_golden:
            golden_dir.mkdir(parents=True, exist_ok=True)
            for file in output_dir.glob("*.q1asm"):
                shutil.copy(file, golden_dir / file.name)
            for file in output_dir.glob("*.json"):
                shutil.copy(file, golden_dir / file.name)
            return

        errors = []
        golden_files = {f.name for f in golden_dir.glob("*.q1asm")}
        for file in generated:
            golden_file = golden_dir / file.name
            if not golden_file.exists():
                errors.append(f"Missing reference listing {golden_file}")
                continue
            expected = golden_file.read_text(encoding="utf-8").splitlines()
            actual = file.read_text(encoding="utf-8").splitlines()
            if expected != actual:
                diff = list(difflib.unified_diff(
                    expected, actual,
                    fromfile=str(golden_file.relative_to(TESTS_DIR)),
                    tofile=str(file.relative_to(TESTS_DIR)),
                    lineterm="", n=2))
                if len(diff) > 60:
                    diff = diff[:60] + [f"... ({len(diff) - 60} more diff lines)"]
                errors.append("\n".join(diff))
            golden_files.discard(file.name)
        for name in sorted(golden_files):
            errors.append(f"Reference listing {golden_dir / name} not generated")
        self.listing_errors += errors

    def get_listing_error_message(self) -> str | None:
        if not self.listing_errors:
            return None
        return ("Q1ASM listing differs from reference. "
                "Run pytest with --update-golden to accept the new listing.\n"
                + "\n\n".join(self.listing_errors))


def create_simulator_target(name: str, cluster_name: str,
                            qcm_slot: int = DEFAULT_QCM_SLOT,
                            qrm_slot: int = DEFAULT_QRM_SLOT,
                            isa_version: tuple[int, int] = (2, 0)) -> Target:
    """Creates a Q1Simulator cluster. An existing instrument with the same name is replaced."""
    from qcodes.instrument import Instrument
    from q1simulator import Cluster as SimCluster
    if Instrument.exist(cluster_name):
        Instrument.find_instrument(cluster_name).close()
    cluster = SimCluster(cluster_name, {qcm_slot: "QCM", qrm_slot: "QRM"}, isa_version=isa_version)
    return _create_target(name, cluster, qcm_slot, qrm_slot, is_simulator=True)


def create_hw_target(address: str,
                     qcm_slot: int = DEFAULT_QCM_SLOT,
                     qrm_slot: int = DEFAULT_QRM_SLOT,
                     cluster_name: str = "Qblox_Cluster") -> Target:
    """Connects to a Qblox Cluster. An existing connection with the same name is reused."""
    from qcodes.instrument import Instrument
    from qblox_instruments import Cluster
    if Instrument.exist(cluster_name):
        cluster = Instrument.find_instrument(cluster_name)
    else:
        cluster = Cluster(cluster_name, address)
    return _create_target("hw", cluster, qcm_slot, qrm_slot, is_simulator=False)


def _create_target(name, cluster, qcm_slot, qrm_slot, is_simulator):
    qcm = getattr(cluster, f"module{qcm_slot}")
    qrm = getattr(cluster, f"module{qrm_slot}")
    try:
        isa_version = tuple(qcm.sequencers[0].isa_version())
    except Exception:
        isa_version = (1, 0)
    return Target(name, cluster, qcm, qrm, is_simulator, isa_version)


def run_interactive(test_function: Callable, *,
                    hw_address: str | None = ...,
                    isa_version: tuple[int, int] = ...,
                    reference: bool = ...,
                    qcm_slot: int = DEFAULT_QCM_SLOT,
                    qrm_slot: int = DEFAULT_QRM_SLOT,
                    **params) -> Q1Test:
    """Runs one test function without pytest and shows the plots.

    Use in IPython or Spyder, e.g. at the end of a test file::

        if __name__ == "__main__":
            run_interactive(test_if_rt, a=0, c=1, d=3)

    Settings that are not passed are taken from INTERACTIVE_HW_ADDRESS,
    INTERACTIVE_ISA_VERSION and INTERACTIVE_REFERENCE.

    Args:
        test_function: test function with fixture argument `q1`.
        hw_address: IP address of the Cluster. None: run on simulator.
        isa_version: ISA version of the simulator.
        reference: on hardware also run the simulator and plot the output as reference.
        params: other arguments of the test function, e.g. parametrized values.
            `tmp_path` is created when the test function has this argument.

    Returns:
        Q1Test object. The executed programs are in `q1.runs`, e.g. `q1.runs[-1].instrument`.
    """
    if hw_address is ...:
        hw_address = INTERACTIVE_HW_ADDRESS
    if isa_version is ...:
        isa_version = INTERACTIVE_ISA_VERSION
    if reference is ...:
        reference = INTERACTIVE_REFERENCE

    if hw_address is None:
        target = create_simulator_target("sim", "Q1Sim", qcm_slot, qrm_slot, isa_version)
        reference_target = None
    else:
        target = create_hw_target(hw_address, qcm_slot, qrm_slot)
        reference_target = None
        if reference:
            reference_target = create_simulator_target(
                "reference", "Q1SimReference", qcm_slot, qrm_slot, target.isa_version)
    for t in (target, reference_target):
        if t is not None:
            t.reset()

    test_name = test_function.__name__
    q1 = Q1Test(test_name, target, reference_target, plot=True, update_golden=False)
    if "tmp_path" in inspect.signature(test_function).parameters and "tmp_path" not in params:
        tmp_path = OUTPUT_DIR / "interactive" / test_name
        tmp_path.mkdir(parents=True, exist_ok=True)
        params["tmp_path"] = tmp_path

    try:
        test_function(q1, **params)
    finally:
        message = q1.get_listing_error_message()
        if message:
            print(message)
        pt.show()
    print(f"{test_name}: done")
    return q1
