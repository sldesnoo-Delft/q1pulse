import re

from qblox_instruments import Cluster
from qblox_instruments.ieee488_2 import Ieee488_2, IpTransport
from qblox_instruments.pnp import resolve
from q1pulse.util.qblox_version import qblox_version, Version

if qblox_version >= Version('0.12'):
    from qblox_instruments import (
        SequencerStatuses,
        SequencerStates,
        )
else:
    from qblox_instruments import SequencerState

from qblox_instruments import SequencerStatus, SequencerStatusFlags


class TurboCluster(Cluster):

    def __init__(
            self,
            name: str,
            identifier: str | None = None,
            port: int | None = None,
            debug: int | None = None,
    ):
        self._identifier = identifier
        addr_info = resolve(identifier)
        if addr_info.protocol != "ip":
            raise RuntimeError(
                f"Instrument cannot be reached due to invalid IP configuration. "
                f"Use qblox-pnp tool to rectify; serial number is {addr_info.address}"
            )
        self._ip_address = addr_info.address
        self._connections: dict[int, Ieee488_2] = {}
        self._needs_check: dict[int, bool] = {}
        for slot in range(1, 21):
            ip_config = resolve(f"{self._ip_address}/{slot}")
            transport = IpTransport(ip_config.address, ip_config.scpi_port)
            self._connections[slot] = Ieee488_2(transport)
        super().__init__(name, identifier, port, debug=2)

    def _write(self, cmd_str):
        conn, cmd = self._get_connection_and_remove_slot(cmd_str)
        conn._write(cmd)

    def _write_bin(self, cmd_str, bin_block):
        conn, cmd = self._get_connection_and_remove_slot(cmd_str)
        conn._write_bin(cmd, bin_block)

    def _read_bin(self, cmd_str, flush_line_end=True):
        conn, cmd = self._get_connection_and_remove_slot(cmd_str)
        res = conn._read_bin(cmd, flush_line_end)
        return res

    def _read(self, cmd_str: str) -> str:
        conn, cmd = self._get_connection_and_remove_slot(cmd_str)
        res = conn._read(cmd)
        return res

    def _get_connection_and_remove_slot(self, cmd: str) -> tuple[Ieee488_2, str]:
        if cmd.startswith("SLOT"):
            slot_str, module_cmd = cmd.split(":", maxsplit=1)
            try:
                slot = int(slot_str[4:])
            except ValueError:
                raise Exception(f"Connect extract slot index from '{cmd}'")
            self._needs_check[slot] = True
            return self._connections[slot], module_cmd
        return super(), cmd

    def get_system_error(self, slot: int | None = None) -> str:
        """
        Get system error from queue (see `SCPI <https://www.ivifoundation.org/downloads/SCPI/scpi-99.pdf>`_).

        Parameters
        ----------
        slot : Optional[int]
            Slot number

        Returns
        -------
        str
            System error description string.

        """
        if slot is None:
            return super().get_system_error()
        else:
            return f"slot{slot}: " + self._connections[slot]._read("SYSTem:ERRor:NEXT?")

    def get_num_system_error(self, slot: int | None = None) -> int:
        """
        Get number of system errors (see `SCPI <https://www.ivifoundation.org/downloads/SCPI/scpi-99.pdf>`_).

        Parameters
        ----------
        slot : Optional[int]
            Slot number

        Returns
        -------
        int
            Current number of system errors.

        """
        if slot is None:
            return super().get_num_system_error()
        else:
            if not self._needs_check.get(slot, False):
                return 0
            cnt = int(self._connections[slot]._read("SYSTem:ERRor:COUNt?"))
            if cnt == 0:
                self._needs_check[slot] = False
            return cnt

    def get_system_errors(self) -> list[str]:
        """
        Returns all the system errors for all connections.
        Error counts are requested simultaneously on all connections to speed up communication.
        Error messages are requested sequentially, because there is not need to hurry when there are errors.
        """
        errors = []
        # use 0 for CMM. (bit hacky)
        slots = [0] + [slot for slot, check in self._needs_check.items() if check]
        err_count_request = "SYSTem:ERRor:COUNt?"
        get_error = "SYSTem:ERRor:NEXT?"

        # write all requests
        for slot in slots:
            conn = self._connections.get(slot, super())
            conn._write(err_count_request)
        # read all responses
        for slot in slots:
            conn = self._connections.get(slot, super())
            # read without writing command.
            response = conn._transport.readline().rstrip()
            num_err = int(response)
            for _ in range(num_err):
                error = conn._read(get_error)
                if slot:
                    error = f"slot {slot}: " + error
                errors.append(error)

        return errors

    def get_sequencer_status_multiple(self, sequencers: dict[int, list[int]]) -> tuple[int, int, object]:
        """
        Returns the status for multiple sequencers using parallel requests.
        Parameters
        ----------
        sequencers : dict[int, list[int]]
            Per slot a list with sequencers to request status from.
        """
        # write all requests
        for slot, seq_nums in sequencers.items():
            conn = self._connections[slot]
            for sequencer in seq_nums:
                conn._write(f"SEQuencer{sequencer}:STATE?")

        results = []
        # read all responses
        for slot, seq_nums in sequencers.items():
            conn = self._connections.get[slot]
            for sequencer in seq_nums:
                # read without writing command.
                status_str = conn._transport.readline().rstrip()
                if qblox_version >= Version('0.12'):
                    status = _convert_sequencer_status(status_str)
                else:
                    status = _convert_sequencer_state_v11(status_str)
                results.append((slot, sequencer, status))
        return results


if qblox_version >= Version('0.12'):
    def _convert_sequencer_status(self, state_str: str):
        status, state, info_flags, warn_flags, err_flags, log = _parse_sequencer_status(state_str)

        state_tuple = SequencerStatus(
            SequencerStatuses[status],
            SequencerStates[state],
            [SequencerStatusFlags[flag] for flag in info_flags],
            [SequencerStatusFlags[flag] for flag in warn_flags],
            [SequencerStatusFlags[flag] for flag in err_flags],
            log,
        )
        return state_tuple

    def _parse_sequencer_status(full_status_str: str) -> tuple([list, list, list, list]):
        full_status_list = re.sub(" |-", "_", full_status_str).split(";")

        # STATUS;STATE;INFO_FLAGS;WARN_FLAGS;ERR_FLAGS;LOG
        status = full_status_list[0]  # They are always present
        state = full_status_list[1]  # They are always present

        if full_status_list[2] != "":
            info_flag_list = full_status_list[2].split(",")[:-1]
        else:
            info_flag_list = []

        if full_status_list[3] != "":
            warn_flag_list = full_status_list[3].split(",")[:-1]
        else:
            warn_flag_list = []

        if full_status_list[4] != "":
            err_flag_list = full_status_list[4].split(",")[:-1]
        else:
            err_flag_list = []

        if full_status_list[5] != "":
            log = full_status_list[5]
        else:
            log = []

        return status, state, info_flag_list, warn_flag_list, err_flag_list, log

else:
    def _convert_sequencer_state_v11(self, state_str: str):
        state_elem_list = re.sub(" |-", "_", state_str).split(";")
        if state_elem_list[-1] != "":
            state_flag_list = state_elem_list[-1].split(",")[:-1]
        else:
            state_flag_list = []

        state_tuple = SequencerState(
            SequencerStatus[state_elem_list[0]],
            [SequencerStatusFlags[flag] for flag in state_flag_list],
        )
        return state_tuple
