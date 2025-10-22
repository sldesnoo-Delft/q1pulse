import logging
import time
from dataclasses import dataclass

from q1pulse.lang.exceptions import Q1MemoryError
from q1pulse.turbo_cluster import TurboCluster
from q1pulse.util.delayedkeyboardinterrupt import DelayedKeyboardInterrupt
from q1pulse.util.q1configuration import Q1Configuration
from q1pulse.util.qblox_version import qblox_version, Version

from .sequencer_states import translate_seq_status


logger = logging.getLogger(__name__)


@dataclass
class Sequencer:
    module_name: str
    seq_nr: int
    channels: list[int]
    max_output_voltage: float
    nco_frequency: float | None = None
    in_channels: list[int] | None = None
    label: str | None = None

    @property
    def enabled_paths(self) -> list[int]:
        n = len(self.channels)
        if n == 0:
            return []
        if n == 1:
            return [0]
        return [0, 1]


class QbloxModule:
    verbose = False
    n_sequencers = 6

    def __init__(self, pulsar):
        self.name = pulsar.name
        # check module is present in slot.
        if hasattr(pulsar, "present"):
            if not pulsar.present():
                raise Exception("No module in slot {pulsar.slot_idx}")
        self.pulsar = pulsar
        self._allocated_seq = 0
        with DelayedKeyboardInterrupt("module.__init__"):
            self.disable_all_out()
            # disable all sequencers
            for seq_nr in range(0, self.n_sequencers):
                self.enable_sync(seq_nr, False)

    @property
    def slot_idx(self):
        return self.pulsar.slot_idx

    @property
    def root_instrument(self):
        return self.pulsar.root_instrument

    def get_num_system_error(self):
        if isinstance(self.root_instrument, TurboCluster):
            return self.root_instrument.get_num_system_error(self.slot_idx)
        else:
            return 0

    def get_system_error(self):
        if isinstance(self.root_instrument, TurboCluster):
            return self.root_instrument.get_system_error(self.slot_idx)
        else:
            raise Exception("Standard Cluster has no `get_system_error` per module.")

    def get_sequencer(self, channels: list[int]) -> Sequencer:
        available_channels = list(range(self.n_channels))
        if any(ch not in available_channels for ch in channels):
            raise Exception(f"Illegal channel number(s) {channels}")
        seq_nr = self._allocate_seq_number()
        return Sequencer(self.name, seq_nr, channels, self.max_output_voltage)

    def _allocate_seq_number(self):
        if self._allocated_seq == self.n_sequencers:
            raise Exception(f"Module {self.name} is out of sequencers. "
                            f"All {self.n_sequencers} are already allocated.")
        sequencer_nr = self._allocated_seq
        self._allocated_seq += 1
        return sequencer_nr

    def disable_all_out(self):
        for seq_nr in range(0, self.n_sequencers):
            # Note: RF module connect outputs in pairs.
            n_out_ch = self.n_channels // 2 if self.pulsar.is_rf_type else self.n_channels
            for out in range(0, n_out_ch):
                self._sset(seq_nr, f"connect_out{out}", "off")

    def set_label(self, seq_nr, label):
        self.pulsar.sequencers[seq_nr].label = label

    def upload(self, seq_nr, sequence):
        if isinstance(sequence, str):
            # don't cache sequence. The contents of the file might have changed.
            filename = sequence
            # print(f"Loading {filename} to sequencer {self.pulsar.name}:{seq_nr}")
            self._sset(seq_nr, "sequence", filename, cache=False)
        else:
            for key in ["waveforms", "weights", "acquisitions"]:
                self._check_size(seq_nr, sequence, key)

            if qblox_version >= Version("0.18.0"):
                # Smart update
                self._update_sequence(seq_nr, sequence)
            else:
                self._sset(seq_nr, "sequence", sequence)

    def arm_sequencers(self):
        for seq_nr in range(0, self.n_sequencers):
            if self.enabled(seq_nr):
                self.pulsar.arm_sequencer(seq_nr)

    def start_sequencers(self):
        enabled = [self.enabled(seq_nr) for seq_nr in range(0, self.n_sequencers)]
        if any(enabled):
            self.pulsar.start_sequencer()

    def stop_sequencers(self):
        self.pulsar.stop_sequencer()

    def get_sequencer_status(self, seq_nr, timeout=0):
        status = self.pulsar.get_sequencer_status(seq_nr, timeout)
        return translate_seq_status(status)

    def enable_sync(self, seq_nr, enable):
        self._sset(seq_nr, "sync_en", enable)

    def enable_out(self, seq_nr: int, channels: list[int]) -> None:
        n = len(channels)
        if n > 0:
            self._sset(seq_nr, f"connect_out{channels[0]}", "I")
        if n == 2:
            self._sset(seq_nr, f"connect_out{channels[1]}", "Q")

    def enable_out_iq(self, seq_nr: int, channels: list[int]) -> None:
        if len(channels) == 0:
            return
        if len(channels) != 2 or channels[0] // 2 != channels[1] // 2:
            raise Exception(f"Incorrect channels {channels}. RF output must be enabled in pairs")
        ch = channels[0] // 2
        self._sset(seq_nr, f"connect_out{ch}", "IQ")

    def set_nco(self, seq_nr, nco_frequency):
        self._sset(seq_nr, "mod_en_awg", nco_frequency is not None)
        if nco_frequency is not None:
            self._sset(seq_nr, "nco_freq", nco_frequency)

    def set_mixer_gain_ratio(self, seq_nr, value):
        self._sset(seq_nr, "mixer_corr_gain_ratio", value)

    def set_mixer_phase_offset_degree(self, seq_nr, value):
        self._sset(seq_nr, "mixer_corr_phase_offset_degree", value)

    def configure_trigger_counter(self, seq_nr, address, threshold, invert):
        self._sset(seq_nr, f"trigger{address}_count_threshold", threshold)
        self._sset(seq_nr, f"trigger{address}_threshold_invert", invert)

    def set_awg_offsets(self, seq_nr, offset0, offset1):
        self._sset(seq_nr, "offset_awg_path0", offset0)
        self._sset(seq_nr, "offset_awg_path1", offset1)

    def enabled(self, seq_nr):
        seq = getattr(self.pulsar, f"sequencer{seq_nr}")
        param = seq.parameters["sync_en"]
        return param.cache()

    def disable_seq(self, sequencer):
        seq_nr = sequencer.seq_nr
        self.enable_sync(seq_nr, False)

    def enable_seq(self, sequencer):
        seq_nr = sequencer.seq_nr
        self.enable_sync(seq_nr, True)
        if self.pulsar.is_rf_type:
            self.enable_out_iq(seq_nr, sequencer.channels)
        else:
            self.enable_out(seq_nr, sequencer.channels)

    def _sset(self, seq_nr, name, value, cache=True):
        full_name = f"sequencer{seq_nr}.{name}"
        seq = getattr(self.pulsar, f"sequencer{seq_nr}")
        param = seq.parameters[name]
        try:
            if cache and param.cache.valid and param.cache() == value:
                if QbloxModule.verbose:
                    logger.debug(f"# {full_name}={value} -- cached")
                return
        except Exception:
            logger.debug(f"No cache value for {full_name}")
        result = param(value)
        if QbloxModule.verbose:
            logger.info(f"{full_name}={value}")
        return result

    def invalidate_cache(self, seq_nr, param_name):
        seq = getattr(self.pulsar, f"sequencer{seq_nr}")
        param = seq.parameters[param_name]
        param.cache.invalidate()

    def set_out_offset(self, channel, offset_mV):
        if self.pulsar.is_rf_type:
            name = f"out{channel//2}_offset_path{channel % 2}"
            value = offset_mV
        else:
            name = f"out{channel}_offset"
            value = offset_mV/1000

        param = self.pulsar.parameters[name]
        if param.cache() == value:
            if QbloxModule.verbose:
                logger.debug(f"# {name}={value} -- cached")
            return
        param(value)

    def set_marker_invert(self, number: int, invert: bool):
        name = f"marker{number}_inv_en"
        param = self.pulsar.parameters[name]
        if param.cache() != invert:
            param(invert)

    def _update_sequence(self, seq_nr, sequence):
        seq = getattr(self.pulsar, f"sequencer{seq_nr}")
        param = seq.parameters["sequence"]
        if not param.cache.valid:
            # update all.
            self._sset(seq_nr, "sequence", sequence)
            return

        # compare sequence with cached value.
        # note: changes to loaded are immediately changed in cache.
        loaded = param.cache()

        program = sequence["program"]
        if loaded["program"] != program:
            loaded["program"] = program
            seq.update_sequence(program=program)

        for key in ["waveforms", "weights", "acquisitions"]:
            updates = {}
            loaded_entries = loaded[key]
            new_entries = sequence[key]
            if len(new_entries) == 0:
                continue
            for name, entry in new_entries.items():
                if name in loaded_entries and entry == loaded_entries[name]:
                    logger.debug(f"{self.slot_idx}.{seq_nr} Reuse {key}: {name}, index:{entry['index']}")
                    continue
                else:
                    # remove entries with same index.
                    index_name = {name: entry["index"] for name, entry in loaded_entries.items()}
                    try:
                        del loaded_entries[index_name[entry["index"]]]
                    except KeyError:
                        pass
                    loaded_entries[name] = entry
                    updates[name] = entry

            erase = self._check_size(seq_nr, loaded, key, raise_exception=False) is False
            if QbloxModule.verbose and len(updates) and not erase:
                logger.debug(f"{self.slot_idx}.{seq_nr} Update {key}: {len(new_entries)} entries, "
                             f"write {[entry['index'] for entry in updates.values()]}")
            if erase:
                logger.debug(f"{self.slot_idx}.{seq_nr} Erase {key}: {len(new_entries)} new entries")
                # overwrite cached entries
                loaded[key] = new_entries
                seq.update_sequence(waveforms=new_entries, erase_existing=True)
            elif len(updates) > 0:
                # loaded entries is already updated.
                seq.update_sequence(**{key: updates}, erase_existing=False)

    def _check_size(self, seq_nr: int, sequence: dict, key: str, raise_exception: bool = True) -> bool:
        entries = sequence[key]
        if len(entries) == 0:
            return True

        if key == "acquisitions":
            max_bins = [131072, 131072, 131072, 65536, 65536, 63536]
            size = sum(entry["num_bins"] for entry in entries.values())
            max_size = max_bins[seq_nr]
            max_entries = 32 # TODO Verify
        else:
            size = sum(len(entry["data"]) for entry in entries.values())
            if key == "waveforms":
                max_size = Q1Configuration.WAVEFORM_MEM_SIZE
                max_entries = Q1Configuration.MAX_NUM_WAVEFORMS
            else:
                max_size = Q1Configuration.WEIGHTS_MEM_SIZE
                max_entries = Q1Configuration.MAX_NUM_WEIGHTS
        if QbloxModule.verbose:
            logger.debug(f"{self.slot_idx}.{seq_nr} {key}: {len(entries)} entries, {size} total")
        if size > max_size:
            if raise_exception:
                raise Q1MemoryError(f"Too much {key} data ({size}) for memory of sequencer {seq_nr}")
            return False
        if len(entries) > max_entries:
            if raise_exception:
                raise Q1MemoryError(f"Too many {key} entries ({len(entries)}) for memory of sequencer {seq_nr}")
            return False
        return True


class QcmModule(QbloxModule):
    n_channels = 4

    def __init__(self, pulsar):
        super().__init__(pulsar)
        self.max_output_voltage = 2.5 if not pulsar.is_rf_type else 3.3


class QrmModule(QbloxModule):
    n_channels = 2

    def __init__(self, pulsar):
        super().__init__(pulsar)
        self.max_output_voltage = 0.5 if not pulsar.is_rf_type else 3.3
        self.disable_all_inputs()
        self._acq_ready = []

    def disable_all_inputs(self):
        for seq_nr in range(0, self.n_sequencers):
            if self.pulsar.is_rf_type:
                self._sset(seq_nr, "connect_acq", "off")
            else:
                self._sset(seq_nr, "connect_acq_I", "off")
                self._sset(seq_nr, "connect_acq_Q", "off")

    def thresholded_acq_rotation(self, seq_nr, phase_rotation):
        self._sset(seq_nr, "thresholded_acq_rotation", phase_rotation)

    def thresholded_acq_threshold(self, seq_nr, threshold):
        self._sset(seq_nr, "thresholded_acq_threshold", threshold)

    def integration_length_acq(self, seq_nr, length):
        self._sset(seq_nr, "integration_length_acq", length)

    def nco_prop_delay(self, seq_nr, delay):
        if delay > 0:
            if 96 <= delay <= 245:
                self._sset(seq_nr, "nco_prop_delay_comp_en", True)
                self._sset(seq_nr, "nco_prop_delay_comp", delay - 146)
            else:
                logger.warning(f"NCO delay ({delay} ns) is out of range. NCO delay not enabled.")
                self._sset(seq_nr, "nco_prop_delay_comp_en", False)
        else:
            self._sset(seq_nr, "nco_prop_delay_comp_en", False)

    def delete_acquisition_data(self, seq_nr):
        self.pulsar.delete_acquisition_data(seq_nr, all=True)

    def enable_in(self, seq_nr, channel):
        if self.pulsar.is_rf_type:
            self._sset(seq_nr, "connect_acq", "in0")
        else:
            # Keep old convention: I on 0, Q on 1
            # TODO: change API to allow different IQ mapping.
            if channel == 0:
                self._sset(seq_nr, "connect_acq_I", "in0")
            else:
                self._sset(seq_nr, "connect_acq_Q", "in1")

    def enable_seq(self, sequencer):
        super().enable_seq(sequencer)
        if sequencer.in_channels is not None:
            seq_nr = sequencer.seq_nr
            for ch in sequencer.in_channels:
                self.enable_in(seq_nr, ch)

    def set_nco(self, seq_nr, nco_frequency):
        super().set_nco(seq_nr, nco_frequency)
        self._sset(seq_nr, "demod_en_acq", nco_frequency is not None)

    def set_trigger(self, seq_nr, address, invert=False):
        enabled = address is not None and address > 0
        self._sset(seq_nr, "thresholded_acq_trigger_en", enabled)
        if enabled:
            self._sset(seq_nr, "thresholded_acq_trigger_address", address)
            self._sset(seq_nr, "thresholded_acq_trigger_invert", invert)

    def set_ttl(self, seq_nr, ttl_acq_input_select, ttl_acq_threshold, ttl_acq_auto_bin_incr_en):
        if ttl_acq_input_select is not None:
            self._sset(seq_nr, "ttl_acq_input_select", ttl_acq_input_select)
        if ttl_acq_threshold is not None:
            self._sset(seq_nr, "ttl_acq_threshold", ttl_acq_threshold)
        if ttl_acq_auto_bin_incr_en is not None:
            self._sset(seq_nr, "ttl_acq_auto_bin_incr_en", ttl_acq_auto_bin_incr_en)

    def arm_sequencers(self):
        self._acq_ready = []
        super().arm_sequencers()

    def start_sequencers(self):
        self._acq_ready = []
        super().start_sequencers()

    def mark_acq_ready(self, seq_nr):
        self._acq_ready.append(seq_nr)

    def get_acquisition_status(self, seq_nr: int, timeout_minutes: float = 1) -> bool:
        if seq_nr in self._acq_ready:
            return True
        logger.info(f"Acquisitions of {self.slot_idx}:{seq_nr} not ready when sequencer stopped")
        expiration_time = time.perf_counter() + timeout_minutes*60.0

        completed = False
        while not completed:
            with DelayedKeyboardInterrupt("get acquisition status"):
                completed = self.pulsar.get_acquisition_status(seq_nr, 0)
                logger.debug(f"Acquisition status {self.pulsar.name}:{seq_nr} ready={completed}")
                if not completed:
                    time.sleep(0.001)
            if time.perf_counter() > expiration_time:
                break
        return completed

    def get_acquisitions(self, seq_nr: int, bin_name: str):
        if qblox_version >= Version("0.18"):
            return self.pulsar.get_acquisitions(seq_nr, as_numpy=True)[bin_name]["acquisition"]["bins"]
        else:
            return self.pulsar.get_acquisitions(seq_nr)[bin_name]["acquisition"]["bins"]
