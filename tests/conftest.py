"""pytest configuration for Q1Pulse tests.

Run on the simulator (default, ISA v2):
    pytest tests
Run on the simulator with ISA v1:
    pytest tests --isa 1
Run on hardware, plotting the simulator output as reference:
    pytest tests --hw 192.168.0.2 -k ramp
Show the plots (close the windows to continue with the next test):
    pytest tests/test_ramp.py --plot
Accept changed Q1ASM listings as new reference:
    pytest tests --update-golden
"""
import shutil

import matplotlib
import pytest

from q1test import (
    OUTPUT_DIR, DEFAULT_QCM_SLOT, DEFAULT_QRM_SLOT,
    Q1Test, create_hw_target, create_simulator_target,
    )


def pytest_addoption(parser):
    group = parser.getgroup("q1pulse")
    group.addoption("--hw", metavar="IP_ADDRESS", default=None,
                    help="Run the tests on the Qblox Cluster with this IP address "
                         "instead of on the simulator.")
    group.addoption("--qcm-slot", type=int, default=DEFAULT_QCM_SLOT,
                    help=f"Slot of the QCM (default {DEFAULT_QCM_SLOT}).")
    group.addoption("--qrm-slot", type=int, default=DEFAULT_QRM_SLOT,
                    help=f"Slot of the QRM (default {DEFAULT_QRM_SLOT}).")
    group.addoption("--isa", choices=["1", "2"], default="2",
                    help="Q1ASM ISA version of the simulator (default 2). "
                         "Ignored with --hw.")
    group.addoption("--plot", action="store_true",
                    help="Show plots of the simulator output. "
                         "Plots are always saved in tests/output/plots when running on hardware.")
    group.addoption("--no-reference", action="store_true",
                    help="With --hw: do not run the simulator reference.")
    group.addoption("--update-golden", action="store_true",
                    help="Write the generated Q1ASM listings as new reference listings.")


def pytest_configure(config):
    if not config.getoption("--plot"):
        matplotlib.use("Agg")


@pytest.hookimpl(wrapper=True)
def pytest_runtest_call(item):
    """Reports differences in Q1ASM listing after the test function has been executed."""
    q1test = getattr(item, "funcargs", {}).get("q1")
    try:
        result = yield
    except BaseException as ex:
        if q1test is not None and q1test.listing_errors:
            ex.add_note(q1test.get_listing_error_message())
        raise
    if q1test is not None and q1test.listing_errors:
        raise AssertionError(q1test.get_listing_error_message())
    return result


@pytest.fixture(scope="session")
def q1_targets(pytestconfig):
    """Returns the target to test and an optional simulator reference."""
    qcm_slot = pytestconfig.getoption("--qcm-slot")
    qrm_slot = pytestconfig.getoption("--qrm-slot")
    hw_address = pytestconfig.getoption("--hw")

    shutil.rmtree(OUTPUT_DIR, ignore_errors=True)

    if hw_address is None:
        isa_version = (int(pytestconfig.getoption("--isa")), 0)
        target = create_simulator_target("sim", "Q1Sim", qcm_slot, qrm_slot, isa_version)
        reference = None
    else:
        target = create_hw_target(hw_address, qcm_slot, qrm_slot)
        if pytestconfig.getoption("--no-reference"):
            reference = None
        else:
            reference = create_simulator_target(
                "reference", "Q1SimReference", qcm_slot, qrm_slot, target.isa_version)

    yield target, reference

    for t in (target, reference):
        if t is not None:
            t.cluster.close()


@pytest.fixture
def q1(request, pytestconfig, q1_targets):
    """Fixture to build, check and run Q1Pulse programs. See q1test.py."""
    target, reference = q1_targets

    if request.node.get_closest_marker("hw_only") and target.is_simulator:
        pytest.skip("hardware only test")
    if request.node.get_closest_marker("isa_v2") and not target.isa_v2:
        pytest.skip("requires Q1ASM ISA v2")

    for t in (target, reference):
        if t is not None:
            t.reset()

    q1test = Q1Test(request.node.name, target, reference,
                    plot=pytestconfig.getoption("--plot"),
                    update_golden=pytestconfig.getoption("--update-golden"))
    yield q1test

    import matplotlib.pyplot as pt
    q1test.save_figures()
    if q1test.figures and pytestconfig.getoption("--plot"):
        pt.show()
    pt.close("all")
