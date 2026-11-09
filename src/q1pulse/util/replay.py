from __future__ import annotations
import glob
import json
import logging
import os
import time
from dataclasses import dataclass
from typing import Any

from qblox_instruments import Cluster

from q1pulse.util.delayedkeyboardinterrupt import DelayedKeyboardInterrupt


logger = logging.getLogger(__name__)


def replay_program(
        cluster: Cluster,
        path: str | None = None,
        *,
        snapshot_name: str | None = None,
        module_mapping: dict[int, int] | None = None,
        sequencers: list[str] | None = None,
        sync_en_only: bool = True,
        ):
    """Replays a 'dumped' program on a cluster.

    The dumped program is a directory with snapshot and a sequence.json per sequencer.
    The program will be loaded in the cluster and played.

    Snapshot file name should match "*snapshot*.json".
    Sequence files should be named "q1seq_{name}.json" where `name` is the label of the sequencer
    if the label is not "sequencer<i>" else the sequencer name "<cluster_name>_module<slot>_sequencer<i>"
    is used.

    Args:
        cluster: Cluster (or Q1Simulator) to load the program in.
        path: directory containing the snapshot and sequence files.
        snapshot_name: filename of snapshot. Defaults to first match on "*snapshot*.json".
        module_mapping: renumbering of modules in case program is loaded on a different cluster.
        sequencers: names of sequencers to load. Defaults to all.
        sync_en_only: if True only loads and starts sequencers with `sync_en == True`.
    """
    if path is None:
        path = os.getcwd()

    path = os.path.expanduser(path)

    replayer = Replay(cluster, path,
                      module_mapping=module_mapping,
                      sequencers=sequencers,
                      sync_en_only=sync_en_only,
                      )
    replayer.read_sequences()
    replayer.load()
    replayer.play()
    replayer.check_sequencers()


class Replay:

    def __init__(
            self,
            cluster: Cluster,
            path: str,
            *,
            snapshot_name: str | None = None,
            module_mapping: dict[str, str] | None = None,
            sequencers: list[str] | None = None,
            sync_en_only: bool = True,
            ):
        self.cluster = cluster
        self.path = path

        self._module_mapping = module_mapping

        self.snapshot = self._load_snapshot(snapshot_name)

        # Ignore module settings...

        self._all_sequencers = self._get_sequencer_config()
        self._selected_sequencers = self._filter_sequencers(sequencers, sync_en_only)

    def read_sequences(self):
        for config in self._selected_sequencers:
            # find file... use label if it is specific otherwise use sequencer.name
            if config.label and config.label != f"sequencer{config.seq_num}":
                name = config.label
            else:
                name = config.name
            filename = f"q1seq_{name}.json"
            path = os.path.join(self.path, filename)
            if not os.path.exists(path):
                print("Sequence file '{filename}' not found")
            with open(path) as fp:
                config.sequence = json.load(fp)

    def load(self):
        for config in self._selected_sequencers:
            sequencer = self._get_sequencer_for_cluster(config)
            # configure sequencer
            for param_name in config.parameters_snapshot:
                if param_name == "sequence":
                    continue
                value = config.get(param_name)
                if value is not None:
                    sequencer.parameters[param_name].set(value)

            if config.sequence:
                sequencer.sequence(config.sequence)

    def play(self):
        for config in self._selected_sequencers:
            sequencer = self._get_sequencer_for_cluster(config)
            sequencer.arm_sequencer()

        self._check_system_errors()
        self.cluster.start_sequencer()
        self._check_system_errors()

    def check_sequencers(self):
        for config in self._selected_sequencers:
            sequencer = self._get_sequencer_for_cluster(config)
            status = self._get_sequencer_status(sequencer, timeout_minutes=15/60)
            print(status)

    def _load_snapshot(self, snapshot_name: str | None):
        if snapshot_name is None:
            names = glob.glob(os.path.join(self.path, "*snapshot*.json"))
            if not names:
                raise Exception("No snapshot found. Specify filename of snapshot to use.")
            filename = names[0]
            print(f"loading snapshot from {filename}")
        else:
            filename = os.path.join(self.path, snapshot_name)
        with open(filename) as fp:
            return json.load(fp)

    def _get_sequencer_config(self):
        # Assume Cluster is root of snapshot

        all_sequencers: list[SequencerConfig] = []

        # cluster_name = self.snapshot["name"]
        submodules = self.snapshot["submodules"]
        for slot_idx in range(1, 21):
            module = submodules.get(f"module{slot_idx}")
            if not module or not get_value(module["parameters"], "present"):
                continue
            module_name = module["name"]
            # module_parameters = module["parameters"]
            seq_modules = module["submodules"]
            for i in range(6):
                sequencer = seq_modules[f"sequencer{i}"]
                parameters = sequencer["parameters"]
                config = SequencerConfig(
                    name=sequencer["name"],
                    label=sequencer.get("label"),
                    module_name=module_name,
                    slot_idx=slot_idx,
                    seq_num=i,
                    parameters_snapshot=parameters,
                    )

                all_sequencers.append(config)
        return all_sequencers

    def _filter_sequencers(self, sequencers: list[str] | None, sync_en_only: bool):
        selected: list[SequencerConfig] = []

        for config in self._all_sequencers:
            sync_en = config.get("sync_en")
            if sync_en_only and not sync_en:
                continue
            if sequencers and config.name not in sequencers and config.label not in sequencers:
                continue
            selected.append(config)

        return selected

    def _get_sequencer_for_cluster(self, config: SequencerConfig):
        cluster = self.cluster
        slot_idx = config.slot_idx
        if self._module_mapping:
            slot_idx = self._module_mapping[slot_idx]
        module = cluster.modules[slot_idx-1]
        sequencer = module.sequencers[config.seq_num]
        return sequencer

    def _check_system_errors(self):
        cluster = self.cluster
        errors = []

        if hasattr(cluster, "get_system_errors"):
            # Get all errors from TurboCluster
            errors += cluster.get_system_errors()
        else:
            while cluster.get_num_system_error() != 0:
                errors.append(cluster.get_system_error())

        if len(errors) > 0:
            msg = "\n".join(errors)
            logger.error(msg)
            raise RuntimeError(msg)

    def _get_sequencer_status(self, sequencer, timeout_minutes: float):
        """Get sequencer status in a interrupt safe way.
        Only intercept the keyboard interrupt during communication,
        not when sleeping.
        """
        expiration_time = time.perf_counter() + timeout_minutes*60.0
        # timeout_poll_res = 0.001
        with DelayedKeyboardInterrupt("check status"):
            status = sequencer.get_sequencer_status(0.0)
        while (status.state == "RUNNING"
                or status.state == "Q1_STOPPED"
                or status.state == "ARMED"
               ) and time.perf_counter() < expiration_time:
            # time.sleep(timeout_poll_res)
            with DelayedKeyboardInterrupt("check status"):
                status = sequencer.get_sequencer_status(0.0)
        return status


def get_value(parameter_dict: dict[str, Any], name: str):
    return parameter_dict[name]["value"]


@dataclass
class SequencerConfig:
    name: str
    label: str
    module_name: str
    slot_idx: int
    seq_num: int
    parameters_snapshot: dict[str, Any]
    sequence: dict[str, Any] | None = None

    def get(self, name: str):
        if name not in self.parameters_snapshot:
            return None
        return self.parameters_snapshot[name]["value"]
