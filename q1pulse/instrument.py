import json
import os
import time
import logging
from collections import defaultdict
from pathlib import Path
from tempfile import TemporaryDirectory


from q1pulse.program import Program
from q1pulse.lang.exceptions import Q1InputOverloaded, Q1InternalError
from q1pulse.sequencer.sequencer import SequenceBuilder
from q1pulse.sequencer.control import ControlBuilder
from q1pulse.sequencer.readout import ReadoutBuilder
from q1pulse.turbo_cluster import TurboCluster
from q1pulse.modules.modules import QcmModule, QrmModule, QbloxModule, Sequencer
from q1pulse.modules.sequencer_states import translate_seq_status
from q1pulse.util.delayedkeyboardinterrupt import DelayedKeyboardInterrupt
from q1pulse.util.qblox_version import check_qblox_instrument_version

logger = logging.getLogger(__name__)


class Q1Instrument:
    verbose = False
    concurrent_communication = True
    ignore_acq_binning_done = False

    # Postpone error checking till the end to save communication overhead.
    # System errors are only reported for SCPI errors. It's higly unlikely to
    # get an error, because everything is already checked in qblox-instruments code.
    # Note on v0.16: Default cluster behavior is like _i_feel_lucky = True.
    _i_feel_lucky = True

    _exception_on_overload = True

    def __init__(self, path=None, add_traceback=True):
        check_qblox_instrument_version()
        if path:
            self.path = path
        else:
            q1dir = Path.home() / ".q1"
            q1dir.mkdir(exist_ok=True)
            self.temp_dir = TemporaryDirectory(dir=q1dir)
            self.path = self.temp_dir.name
            logger.info("Instrument upload temp dir: " + self.path)
        self.root_instruments = set()
        self.modules: dict[str, QbloxModule] = {}
        self.controllers: dict[int, Sequencer] = {}
        self.readouts: dict[int, Sequencer] = {}
        self._loaded_q1asm: dict[str, dict] = {}
        self._loaded_program_uuid = None
        SequenceBuilder.add_traceback_to_instructions = add_traceback

    def add_qcm(self, module):
        logger.info(f"Add {module.name}")
        self.modules[module.name] = QcmModule(module)
        self._add_root_instrument(module.root_instrument)

    def add_qrm(self, module):
        logger.info(f"Add {module.name}")
        self.modules[module.name] = QrmModule(module)
        self._add_root_instrument(module.root_instrument)

    def add_control(self, name, module_name, channels, nco_frequency=None):
        sequencer = self.modules[module_name].get_sequencer(channels)
        sequencer.nco_frequency = nco_frequency
        sequencer.label = name
        self.controllers[name] = sequencer

    def add_readout(self, name, module_name, out_channels=[],
                    nco_frequency=None, in_channels=[0, 1]):
        module = self.modules[module_name]
        if not isinstance(module, QrmModule):
            raise Exception(f"Module {module_name} is not a QRM")
        sequencer = module.get_sequencer(out_channels)
        sequencer.nco_frequency = nco_frequency
        sequencer.in_channels = in_channels
        sequencer.label = name
        self.readouts[name] = sequencer

    def _add_root_instrument(self, root_instrument):
        self.root_instruments.add(root_instrument)

    def new_program(self, prog_name):
        program = Program(path=os.path.join(self.path, prog_name))
        for name, seq in self.controllers.items():
            seq_builder = ControlBuilder(name, seq.enabled_paths,
                                         seq.max_output_voltage,
                                         seq.nco_frequency)
            program.add_sequence_builder(seq_builder)

        for name, seq in self.readouts.items():
            seq_builder = ReadoutBuilder(name, seq.enabled_paths,
                                         seq.max_output_voltage,
                                         seq.nco_frequency)
            program.add_sequence_builder(seq_builder)

        return program

    def save_program(self, program: Program, path: str):
        """Stores program including current settings of the sequence builders,
        like nco_frequency.

        Args:
            program: program to save.
            path: path to store the program.
        """
        os.makedirs(path, exist_ok=True)
        config = {}
        for builder in program.sequence_builders.values():
            name = builder.name
            q1asm = program.q1asm(name)
            if q1asm is not None:
                filename = f"q1seq_{name}.json"
                with open(os.path.join(path, filename), "w", encoding="utf-8") as f:
                    json.dump(q1asm, f, indent=1, separators=(",", ":"))
            else:
                filename = None
            sequencer = self.controllers.get(name)
            if sequencer is not None:
                seq_type = "controller"
            else:
                sequencer = self.readouts.get(name)
                seq_type = "readout"
                if sequencer is None:
                    raise Q1InternalError(f"Sequencer {name} not found in instrument")
            builder_config = {
                "module": sequencer.module_name,
                "seq_nr": sequencer.seq_nr,
                "seq_type": seq_type,
                "out_channels": sequencer.channels,
                "nco": builder.nco_frequency,
                "paths": builder.enabled_paths,
                "sequence": filename,
                "duration": builder.end_time if q1asm is not None else None,
                }
            if seq_type == "readout":
                builder_config["in_channels"] = sequencer.in_channels
            config[name] = builder_config
        with open(os.path.join(path, "q1program.json"), "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)

    def run_program(self, program):
        self.start_program(program)
        self.wait_stopped()

    def load_program(self, program):
        # TODO @@@@ add global state?
        t_start = time.perf_counter()

        for instrument in self.root_instruments:
            if Q1Instrument._i_feel_lucky and hasattr(instrument, "_debug"):
                # Change the debug level to speed up communication.
                # Errors will be checked before start of the sequence.
                instrument._debug = 2

        sequencers = {**self.controllers, **self.readouts}

        # sort on (seq_num, slot)
        sequencers = dict(sorted(sequencers.items(),
                                 key=lambda kv: (kv[1].seq_nr, self.modules[kv[1].module_name].slot_idx)))

        for name, seq in sequencers.items():
            module = self.modules[seq.module_name]
            with DelayedKeyboardInterrupt("upload sequences"):
                q1asm = program.q1asm(name)
                self._loaded_q1asm[name] = q1asm
                if q1asm is None:
                    continue
                module.upload(seq.seq_nr, q1asm)

        # TODO @@@@ Check errors? This gives some delay!

        t = (time.perf_counter() - t_start) * 1000
        logger.info(f"Duration (async) upload: ({t:5.3f}ms)")

        self._loaded_program_uuid = program.uuid

    def start_program(self, program):
        if program.uuid != self._loaded_program_uuid:
            self.load_program(program)

        t_start = time.perf_counter()

        for instrument in self.root_instruments:
            with DelayedKeyboardInterrupt("check status"):
                check_instrument_status(instrument)

        instruments_with_sequence = set()
        sequencers = {**self.controllers, **self.readouts}
        n_configured = 0

        # sort on (seq_num, slot)
        sequencers = dict(sorted(sequencers.items(),
                                 key=lambda kv: (kv[1].seq_nr, self.modules[kv[1].module_name].slot_idx)))

        for name, seq in sequencers.items():
            t_start_seq = time.perf_counter()
            module = self.modules[seq.module_name]
            with DelayedKeyboardInterrupt("configure sequencers"):
                q1asm = program.q1asm(name)
                self._loaded_q1asm[name] = q1asm
                if q1asm is None:
                    module.disable_seq(seq)
                    module.set_awg_offsets(seq.seq_nr, 0.0, 0.0)
                    logger.debug(f"Sequencer {name} no sequence")
                    continue
                n_configured += 1
                instruments_with_sequence.add(module.root_instrument)
                module.set_label(seq.seq_nr, name)
                # module.upload(seq.seq_nr, q1asm) @@@ Already loaded.
                module.invalidate_cache(seq.seq_nr, "offset_awg_path0")
                module.invalidate_cache(seq.seq_nr, "offset_awg_path1")
                module.enable_seq(seq)
                prog_seq = program[name]
                module.set_nco(seq.seq_nr, prog_seq.nco_frequency)
                if prog_seq.modifies_frequency:
                    module.invalidate_cache(seq.seq_nr, "nco_freq")
                if prog_seq.mixer_gain_ratio is not None:
                    module.set_mixer_gain_ratio(seq.seq_nr, prog_seq.mixer_gain_ratio)
                if prog_seq.mixer_phase_offset_degree is not None:
                    module.set_mixer_phase_offset_degree(seq.seq_nr, prog_seq.mixer_phase_offset_degree)
                # configure trigger counters
                for counter in prog_seq.trigger_counters:
                    module.configure_trigger_counter(seq.seq_nr, counter.trigger.address,
                                                     counter.threshold, counter.invert)
            if Q1Instrument.verbose:
                duration = time.perf_counter() - t_start_seq
                logger.debug(f"Configured {name} in {duration*1000.0:3.1f} ms")

        for name, seq in self.readouts.items():
            t_start_seq = time.perf_counter()
            module = self.modules[seq.module_name]
            if not module.enabled(seq.seq_nr):
                continue
            with DelayedKeyboardInterrupt("configure readout"):
                readout = program[name]
                module.thresholded_acq_rotation(seq.seq_nr, readout.thresholded_acq_rotation)
                module.thresholded_acq_threshold(seq.seq_nr, readout.thresholded_acq_threshold)
                module.integration_length_acq(seq.seq_nr, int(readout.integration_length_acq))
                module.nco_prop_delay(seq.seq_nr, int(readout.nco_prop_delay))
                module.delete_acquisition_data(seq.seq_nr)
                trigger = readout.trigger
                if trigger is not None:
                    module.set_trigger(seq.seq_nr, trigger.address, trigger.invert)
                else:
                    module.set_trigger(seq.seq_nr, None)
                module.set_ttl(
                    seq.seq_nr,
                    readout.ttl_acq_input_select,
                    readout.ttl_acq_threshold,
                    readout.ttl_acq_auto_bin_incr_en
                    )

            if Q1Instrument.verbose:
                duration = time.perf_counter() - t_start_seq
                logger.debug(f"Configured QRM {name} in {duration*1000.0:3.1f} ms")

        with DelayedKeyboardInterrupt("arm and start"):
            t_start_arm = time.perf_counter()
            # Note: arm per sequencer. Arm on the cluster still gives red leds on the modules.
            for module in self.modules.values():
                module.arm_sequencers()
            if Q1Instrument.verbose:
                duration = time.perf_counter() - t_start_arm
                logger.debug(f"Armed {n_configured} sequencers in {duration*1000.0:3.1f} ms")

            # Error check implicitly waits for the module to process all previous commands.
            # Exclude CMM (slot=0)
            self.check_system_errors(exclude=[0])

            for module in self.modules.values():
                module.start_sequencers()
            self.check_system_errors()
            self._t_start = time.perf_counter()

        t = (time.perf_counter() - t_start) * 1000
        logger.info(f"Duration upload/start: ({t:5.3f}ms)")

    def wait_stopped(self, timeout_minutes: float = 1):
        try:
            # Wait for completion
            errors = {}
            msg_level = 0
            # list[tuple[module, sequencer]]
            active_sequencers: list[tuple[QbloxModule, Sequencer]] = []
            sequencers = {**self.controllers, **self.readouts}
            for name, seq in sequencers.items():
                module = self.modules[seq.module_name]
                if not module.enabled(seq.seq_nr):
                    continue
                active_sequencers.append((module, seq))

            statuses = self._get_sequencer_status_multiple(active_sequencers, timeout_minutes)
            for (module, seq), status in zip(active_sequencers, statuses):
                # status = self._get_sequencer_status(module, seq.seq_nr, timeout_minutes)
                if "ACQ BINNING DONE" in status.debug_msgs:
                    module.mark_acq_ready(seq.seq_nr)
                logger.log(status.level, f"Status {module.slot_idx}:{seq.seq_nr} ({seq.label}): {status}")
                msg_level = max(msg_level, status.level)
                if status.status != "OKAY" or status.state != "STOPPED" or status.level >= logging.WARNING:
                    errors[seq.label] = str(status)
                    # reset awg offsets in case of any error.
                    with DelayedKeyboardInterrupt("set offsets"):
                        module.set_awg_offsets(seq.seq_nr, 0.0, 0.0)
                if status.input_overloaded:
                    if Q1Instrument._exception_on_overload:
                        raise Q1InputOverloaded(
                                f"INPUT OVERLOAD on {seq.label}."
                                "\nException can be suppressed with q1pulse.set_exception_on_overload(False)")
                    else:
                        print(f"WARNING: input overload on {seq.label}")

            if msg_level == logging.ERROR:
                logger.error("*** Program errors ***")
                for name, state in errors.items():
                    logger.error(f"  {name}: {state}")
                raise Exception(f"Q1 failures (see logging):\n {errors}")
            duration = time.perf_counter() - self._t_start
            logger.debug(f"Ready after {duration*1000:.1f} ms")
        except Exception:
            logger.error("Exception", exc_info=True)
            raise
        finally:
            with DelayedKeyboardInterrupt("stop sequencers"):
                logger.debug("Stop sequencers")
                # for instrument in self.root_instruments:
                #     instrument.stop_sequencer()
                for module in self.modules.values():
                    module.stop_sequencers()

    def _get_sequencer_status(self, module, seq_nr, timeout_minutes):
        """Get sequencer status in a interrupt safe way.
        Only intercept the keyboard interrupt during communication,
        not when sleeping.
        """
        expiration_time = time.perf_counter() + timeout_minutes*60.0
        # timeout_poll_res = 0.001
        with DelayedKeyboardInterrupt("check status"):
            status = module.get_sequencer_status(seq_nr, 0.0)
        while (status.state == "RUNNING"
                or status.state == "Q1_STOPPED"
                or status.state == "ARMED"
               ) and time.perf_counter() < expiration_time:
            # time.sleep(timeout_poll_res)
            with DelayedKeyboardInterrupt("check status"):
                status = module.get_sequencer_status(seq_nr, 0.0)
        return status

    def _get_sequencer_status_multiple(
            self,
            active_sequencers: list[tuple[QbloxModule, SequenceBuilder]],
            timeout_minutes):
        """Get sequencer status in a interrupt safe way.
        Only intercept the keyboard interrupt during communication,
        not when sleeping.
        """
        not_ready = ["ARMED", "RUNNING", "Q1_STOPPED"]
        statuses = []
        expiration_time = time.perf_counter() + timeout_minutes*60.0
        # timeout_poll_res = 0.001
        if not Q1Instrument.concurrent_communication:
            for module, seq in active_sequencers:
                statuses.append(self._get_sequencer_status(module, seq.seq_nr, timeout_minutes))
        else:
            statuses = [None]*len(active_sequencers)
            # reverse lookup in statuses
            index: dict[tuple[TurboCluster, int, int], int] = {}
            turbo_sequencers: dict[TurboCluster, dict[QbloxModule, list[int]]] = {}
            # group by instrument. Keep index in list.
            # if not TurboCluster use normal. sequential method.
            for idx, (module, seq) in enumerate(active_sequencers):
                instrument = module.root_instrument
                if not isinstance(instrument, TurboCluster):
                    statuses[idx] = self._get_sequencer_status(module, seq.seq_nr, timeout_minutes)
                else:
                    module_sequencers = turbo_sequencers.setdefault(instrument, defaultdict(list))
                    module_sequencers[module].append(seq.seq_nr)
                    index[(instrument, module.slot_idx, seq.seq_nr)] = idx

            while any(status is None or status.state in not_ready for status in statuses):
                for instrument, mod_seqs in turbo_sequencers.items():
                    # collect sequencers that are not yet ready
                    sequencers = {}
                    for module, seqs in mod_seqs.items():
                        seq_nums = []
                        slot = module.slot_idx
                        for seq_num in seqs:
                            status = statuses[index[(instrument, slot, seq_num)]]
                            if status is None or status.state in not_ready:
                                seq_nums.append(seq_num)
                        sequencers[slot] = seq_nums

                    try:
                        res = None
                        with DelayedKeyboardInterrupt("check status"):
                            res = instrument.get_sequencer_status_multiple(sequencers)
                    except KeyboardInterrupt:
                        logger.info(f"Interrupted during get_sequencer_status_multiple. Statusses: {res}")
                        raise

                    for slot, seq_num, status in res:
                        status = translate_seq_status(status)
                        statuses[index[(instrument, slot, seq_num)]] = status
                if time.perf_counter() > expiration_time:
                    break
                # if any(status.state in not_ready for status in statuses):
                #     time.sleep(timeout_poll_res)

        return statuses

    def check_system_errors(self, exclude: list[int] = []):
        t_start_check = time.perf_counter()
        errors = []

        for instrument in self.root_instruments:
            if Q1Instrument.concurrent_communication and isinstance(instrument, TurboCluster):
                errors += instrument.get_system_errors(exclude)
            else:
                while instrument.get_num_system_error() != 0:
                    errors.append(instrument.get_system_error())

        if not Q1Instrument.concurrent_communication:
            for module in self.modules.values():
                while module.get_num_system_error() != 0:
                    errors.append(module.get_system_error())

        if len(errors) > 0:
            if Q1Instrument._i_feel_lucky:
                logger.error("You're not lucky. One of the previous calls failed...")
            msg = instrument.name + ":" + "\n".join(errors)
            logger.error(msg)
            raise RuntimeError(msg)

        if Q1Instrument.verbose:
            duration = time.perf_counter() - t_start_check
            logger.debug(f"Checked errors in {duration*1000.0:3.1f} ms")

    def get_acquisition_bins(self, sequencer_name, acq_name):
        acq_data = self._get_acquisitions(sequencer_name, acq_name)
        if acq_data is None:
            return None
        return acq_data["acquisition"]["bins"]

    def get_scope_data(self, sequencer_name: str, acq_name: str):
        acq_data = self._get_acquisitions(sequencer_name, acq_name)
        if acq_data is None:
            return None
        return acq_data["acquisition"]["scope"]

    def _get_acquisitions(self, sequencer_name, acq_name):
        seq = self.readouts[sequencer_name]
        q1asm = self._loaded_q1asm[sequencer_name]
        if q1asm is None or len(q1asm["acquisitions"]) == 0:
            logger.warning(f"No acquisitions for {sequencer_name}")
            return None
        module = self.modules[seq.module_name]
        if self.ignore_acq_binning_done:
            finished = module.get_acquisition_status(seq.seq_nr, 0)
            if not finished:
                logger.info("Acquisition not finished (according to QRM)")
        else:
            # check if module is ready.
            timeout = 0.1  # wait max 6 s.
            finished = module.get_acquisition_status(seq.seq_nr, timeout)
            if not finished:
                logger.error("Acquisition not finished (according to QRM)")
        with DelayedKeyboardInterrupt("get_acquisitions"):
            return module.get_acquisitions(seq.seq_nr, acq_name)

    def get_input_ranges(self, sequencer_name):
        """ Returns input range for both channels of sequencer.
        Value is in Vpp.
        """
        seq = self.readouts[sequencer_name]
        module = self.modules[seq.module_name]
        if module.pulsar.is_rf_type:
            att_db = module.pulsar.in0_att.cache()
            in_range = 1.0 * 10**(att_db/20)
            in_range = (in_range, in_range)
        else:
            in0_gain = module.pulsar.in0_gain.cache()
            in1_gain = module.pulsar.in1_gain.cache()
            in_range = tuple(
                    1.0 * 10**(-dB/20)
                    for dB in [in0_gain, in1_gain])
        return in_range


def set_exception_on_overload(enable: bool):
    """
    Setting set_exception_on_overload to False suppresses Exception
    when the QRM input is overloaded.
    """
    Q1Instrument._exception_on_overload = enable


def check_instrument_status(instrument, print_status=False):
    t = time.perf_counter()
    sys_state = instrument.get_system_status()
    if Q1Instrument.verbose:
        d = time.perf_counter() - t
        logger.debug(f"Status {sys_state.status} {d*1000:.1f} ms")

    if sys_state.status != "OKAY":
        if getattr(instrument, "is_dummy", False):
            print(f"Status (Dummy) {instrument.name}:", sys_state)
        elif instrument.get_idn()["serial_number"] == "whatever":
            # looks like dummy cluster
            print(f"Status (Dummy) {instrument.name}:", sys_state)
        else:
            raise Exception(f"{instrument.name} status not OKAY: {sys_state}")
