import json
import logging
import os
from datetime import datetime
from pprint import pprint

import numpy as np
from qblox_instruments import Cluster


logger = logging.getLogger(__name__)


def q1asm_dump(cluster: Cluster, path: str | None = None, sync_en_only: bool = True):
    """Writes cluster configuration including current sequences to disk.

    All data are retrieved from the qcodes cache!
    This function only works properly if called on the Cluster object
    that was used to program the cluster.

    Args:
        cluster: cluster to get data from.
        path: path to store the program.
        sync_en_only:
            If True only save sequences of sequencers with `sync_en() = True`.
            if False try to save sequences of all sequencers.
    """
    if path is None:
        path = os.getcwd()

    path = os.path.expanduser(path)
    now = datetime.now().strftime("%Y%m%d_%H%M%S_%f")

    path = os.path.join(path, f"q1program_{now}")
    print(f"dumping cluster configuration + Q1ASM to {path}")

    dumper = Q1Dumper(cluster)
    dumper.save_program(path, sync_en_only)


class Q1Dumper:

    def __init__(self, cluster: Cluster):
        self._cluster = cluster

    def save_program(self, path: str, sync_en_only: bool = True):
        """Stores program including current settings of the sequencers.

        Args:
            path: path to store the program.
            sync_en_only:
                If True only save sequences of sequencers with `sync_en() = True`.
                if False try to save sequences of all sequencers.
        """
        os.makedirs(path, exist_ok=True)

        config = {}
        cluster = self._cluster

        for slot, module in enumerate(cluster.modules, 1):
            if not module.present():
                continue
            if module.is_qcm_type:
                mod_type = "QCM"
                seq_type = "controller"
            elif module.is_qrm_type:
                mod_type = "QRM"
                seq_type = "readout"
            else:
                logger.warning(f"unknown module type {module.module_type} in slot {slot}")
                continue

            for seq_num in range(6):
                sequencer = module.sequencers[seq_num]
                name = sequencer.label
                if name == sequencer.name:
                    name = f"{mod_type} {slot}:{seq_num}"
                sync_en = sequencer.sync_en.cache()
                if sync_en_only and not sync_en:
                    continue

                filename = self._save_sequence(sequencer, name, path)

                seq_config = self._get_seq_config(sequencer, module.is_qcm_type, module.is_rf_type)

                builder_config = {
                    "instrument": cluster.name,
                    "module": module.name,
                    "slot": module.slot_idx,
                    "seq_nr": seq_num,
                    "seq_type": seq_type,
                    "sync_en": sync_en,
                    "sequence": filename,
                    }
                builder_config.update(seq_config)
                config[name] = builder_config

        with open(os.path.join(path, "q1program.json"), "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)

        # finally save snapshot. This can fail when communication to cluster is attempted.
        try:
            filename = f"snapshot_{cluster.name}.json"
            with open(os.path.join(path, filename), "w", encoding="utf-8") as f:
                json.dump(cluster.snapshot(), f, indent=1, separators=(",", ":"))
        except Exception:
            logger.error("Failed to save snapshot", exc_info=True)

    def _save_sequence(self, sequencer, name, path) -> str:
        q1asm = sequencer.sequence.cache()
        if q1asm is None:
            logger.warning(f"Q1ASM for '{name}' cannot be loaded.")
            return None
        if not isinstance(q1asm, dict):
            seq_file = q1asm
            if not os.path.exists(seq_file):
                logger.warning(f"Cannot load sequence {seq_file}")
                return None
            with open(seq_file) as fp:
                q1asm = json.load(fp)
        if q1asm is not None:
            filename = f"q1seq_{name}.json"
            with open(os.path.join(path, filename), "w", encoding="utf-8") as f:
                json.dump(q1asm, f, indent=1, separators=(",", ":"))
            self._save_q1asm(q1asm, name, path)
        else:
            filename = None
        return filename

    def _save_q1asm(self, program, name, path):
        filename = f"q1seq_{name}.q1asm"
        with open(os.path.join(path, filename), "w", encoding="utf-8") as f:
            f.write('waveforms=')
            self._pprint_data(program['waveforms'], f)
            f.write('weights=')
            self._pprint_data(program['weights'], f)
            f.write('acquisitions=')
            pprint(program['acquisitions'], f)
            f.write('\n')
            f.write('seq_prog="""\n')
            for line in program["program"].split(r"\n"):
                f.write(f"{line}\n")
            f.write('\n"""\n\n')

    def _pprint_data(self, data_dict, f):
        prefix = ' '*12
        f.write('{\n')
        for name, wave in data_dict.items():
            f.write(f"    '{name}':{{\n")
            f.write(f"        'data':\n")
            f.write(prefix)
            # precision of 5 digits is sufficient for 16 bit numbers in range [-1, +1]
            f.write(np.array2string(np.array(wave['data']),
                                    prefix=prefix,
                                    separator=',',
                                    formatter={'float_kind': lambda x: f'{x:9.5f}'},
                                    threshold=1000_000))
            f.write(f",\n")
            f.write(f"        'index':{wave['index']},\n")
            f.write(f'        }},\n')
        f.write('    }\n\n')

    def _get_seq_config(self, sequencer, is_qcm, is_rf):
        seq_config = {}
        param_names = [
                "mod_en_awg",
                "nco_freq",
                'marker_ovr_en',
                'marker_ovr_value',
                'nco_phase_offs',
                'gain_awg_path0',
                'gain_awg_path1',
                'offset_awg_path0',
                'offset_awg_path1',
                ]

        for i in range(1, 16):
            param_names += [
                f'trigger{i}_count_threshold',
                f'trigger{i}_threshold_invert',
                ]

        n_out_ch = 4 if is_qcm else 2
        if is_rf:
            n_out_ch //= 2
        for ch in range(n_out_ch):
            param_names += [f"connect_out{ch}"]

        if not is_qcm:
            if is_rf:
                param_names += ["connect_acq"]
            else:
                param_names += ["connect_acq_I", "connect_acq_Q"]

        if not is_qcm:
            param_names += [
                "demod_en_acq",
                "integration_length_acq",
                'thresholded_acq_rotation',
                'thresholded_acq_threshold',
                'thresholded_acq_trigger_en',
                'thresholded_acq_trigger_address',
                'thresholded_acq_trigger_invert',
                ]

        for param_name in param_names:
            value = sequencer.parameters[param_name].cache()
            seq_config[param_name] = value

        out_channels = set()
        in_channels = set()
        enabled_paths = set()
        for ch in range(n_out_ch):
            out = seq_config[f"connect_out{ch}"]
            if out is None:
                continue
            if out != "off":
                out_channels.add(ch)
            if "I" in out:
                enabled_paths.add(0)
            if "Q" in out:
                enabled_paths.add(1)

        if not is_qcm:
            if is_rf:
                if seq_config["connect_acq"] == "in0":
                    in_channels.add(0)
            else:
                for param in ["connect_acq_I", "connect_acq_Q"]:
                    in_ch = seq_config[param]
                    if in_ch == "in0":
                        in_channels.add(0)
                    elif in_ch == "in1":
                        in_channels.add(1)
        seq_config["in_channels"] = sorted(in_channels)
        seq_config["out_channels"] = sorted(out_channels)
        seq_config["paths"] = sorted(enabled_paths)
        seq_config["nco"] = seq_config["nco_freq"] if seq_config["mod_en_awg"] else None

        return seq_config
