import io
import json
import logging
import re
from functools import partial
from typing import Any

from qblox_instruments import Cluster
from qblox_instruments.scpi import Cluster as ClusterScpi
from qblox_instruments.ieee488_2 import Ieee488_2, IpTransport
from qblox_instruments.pnp import resolve
from q1pulse.util.qblox_version import check_qblox_instrument_version

from qblox_instruments import (
    SequencerStatus,
    SequencerStatuses,
    SequencerStates,
    SequencerStatusFlags,
    )


logger = logging.getLogger(__name__)


class TurboCluster(Cluster):
    """
    `TurboCluster` is modified version of `qblox_instruments.Cluster` that speeds up communication
    with a factor 2 to 10.

    TurboCluster is compatible with qblox_instruments v0.11 to v0.17 and can be used as a drop-in
    replacement for Cluster when Q1Pulse is used.

    Other control code only needs some minor modifications.
    TurboCluster a TCP connection per module and therefore `get_num_system_error(slot)` should be called for
    every module. Or better, `get_system_errors()` should be called to collect the errors for
    all connections with a concurrent operation.
    The status of many sequencers can be requested with the fast concurrent call `get_sequencer_status_multiple`.

    The speedup is realized by:
        * Using a TCP/IP connection per module allowing commands to be sent to multiple modules concurrently.
        * Sending batches of commands and requests to a module and then read the batch of responses.
        * Caching module and sequencer configuration.
    """

    use_configuration_cache = True
    """If true use configuration cache. This makes configuration changes must
    faster, but could fail in scenarios where other Cluster objects can modify the configuration.
    """

    def __init__(
            self,
            name: str,
            identifier: str | None = None,
            port: int | None = None,
            debug: int | None = None,
    ):
        check_qblox_instrument_version()
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
        self._init_batching()
        self._clear_cache()
        for slot in range(1, 21):
            ip_config = resolve(f"{self._ip_address}/{slot}")
            transport = IpTransport(ip_config.address, ip_config.scpi_port, timeout=5.0)
            self._connections[slot] = Ieee488_2(transport)
        super().__init__(name, identifier, port, debug=debug)
        for slot in range(1, 21):
            module = self.modules[slot-1]
            if module.present():
                for seq_nr in range(6):
                    seq = module.sequencers[seq_nr]
                    # disable slow validators
                    seq.sequence._vals = []
        # Disable continuous error checking
        self._debug = 2
        self._init_configuration_cache()

    def _init_batching(self):
        self._is_batching: list[bool] = [False]*21
        self._write_buffer: list[bytearray] = [bytearray() for _ in range(21)]

    def start_batching(self, slot):
        if self._is_batching[slot]:
            raise Exception(f"Batching already active for slot {slot}")
        buffer = self._write_buffer[slot]
        if len(buffer) > 0:
            raise Exception(f"Internal error in batching: {buffer}")
        self._is_batching[slot] = True

    def stop_batching(self, slot):
        self._flush_buffer(slot)
        self._is_batching[slot] = False

    def _add_to_buffer(self, slot, data):
        buffer = self._write_buffer[slot]
        if len(buffer) + len(data) > 1400:
            self._flush_buffer(slot)
        buffer += data

    def _flush_buffer(self, slot):
        buffer = self._write_buffer[slot]
        if not self._is_batching[slot] or len(buffer) == 0:
            return
        conn = self._connections[slot]
        conn._transport.write_binary(buffer)
        buffer.clear()

    def _write(self, cmd_str):
        conn, cmd, slot = self._get_connection_and_remove_slot(cmd_str)
        if slot is not None and self._is_batching[slot]:
            # convert to binary like done by Ieee488_2 and IpTransport.
            self._add_to_buffer(slot, (cmd_str + " \n").encode("ascii"))
            return
        conn._write(cmd)
        # logger.debug(f"write {cmd_str}")

    def _write_bin(self, cmd_str, bin_block):
        conn, cmd, slot = self._get_connection_and_remove_slot(cmd_str)
        if slot is not None and self._is_batching[slot]:
            # convert to binary like done by Ieee488_2 and IpTransport.
            header = cmd_str + " " + Ieee488_2._build_header_string(len(bin_block))
            data = bytearray(header.encode("ascii")) + bin_block + "\n".encode("ascii")
            self._add_to_buffer(slot, data)
            return
        conn._write_bin(cmd, bin_block)
        # logger.debug(f"write_bin {cmd_str}")

    def _read_bin(self, cmd_str, flush_line_end=True):
        conn, cmd, slot = self._get_connection_and_remove_slot(cmd_str)
        if slot is not None and self._is_batching[slot]:
            self._flush_buffer(slot)
        res = conn._read_bin(cmd, flush_line_end)
        # logger.debug(f"read_bin {cmd_str}")
        return res

    def _read(self, cmd_str: str) -> str:
        conn, cmd, slot = self._get_connection_and_remove_slot(cmd_str)
        if slot is not None and self._is_batching[slot]:
            self._flush_buffer(slot)
        res = conn._read(cmd)
        # logger.debug(f"read {cmd_str}")
        return res

    def _get_connection_and_remove_slot(self, cmd: str) -> tuple[Ieee488_2, str]:
        if cmd.startswith("SLOT"):
            slot_str, module_cmd = cmd.split(":", maxsplit=1)
            if len(slot_str) > 4:
                try:
                    slot = int(slot_str[4:])
                except ValueError:
                    raise Exception(f"Connect extract slot index from '{cmd}'")
                self._needs_check[slot] = True
                return self._connections[slot], module_cmd, slot
        return super(), cmd, None

    # ------------------------------------------------------------------
    # Versions <= v0.16 call arm_sequencer start_sequencer and stop_sequencer directly on the original
    # `_write ` method of ClusterScpi. Thus, all calls will go to CMM. See `ClusterNative._create_module_funcrefs`.
    # It's better and safer to have all calls to a module go directly to the module
    # using the same socket and not some calls via another socket.
    # ------------------------------------------------------------------

    def arm_sequencer(self, slot: int | None = None, sequencer: int | None = None) -> None:
        """
        Prepare the indexed sequencer to start by putting it in the armed state.
        If no sequencer index is given, all sequencers are armed. Any sequencer
        that was already running is stopped and rearmed. If an invalid sequencer
        index is given, an error is set in system error.

        Parameters
        ----------
        slot : Optional[int]
            Slot number
        sequencer : Optional[int]
            Sequencer index.

        Returns
        ----------

        Raises
        ----------
        RuntimeError
            An error is reported in system error and debug <= 1.
            All errors are read from system error and listed in the exception.
        """
        if slot is None:
            slot = ""  # Arm sequencers across all modules

        if sequencer is None:
            sequencer = ""  # Arm all sequencers within a module

        return self._write(f"SLOT{slot}:SEQuencer{sequencer}:ARM")

    def start_sequencer(self, slot: int | None = None, sequencer: int | None = None) -> None:
        """
        Start the indexed sequencer, thereby putting it in the running state.
        If an invalid sequencer index is given or the indexed sequencer was not
        yet armed, an error is set in system error. If no sequencer index is
        given, all armed sequencers are started and any sequencer not in the armed
        state is ignored. However, if no sequencer index is given and no
        sequencers are armed, and error is set in system error.

        Parameters
        ----------
        slot : Optional[int]
            Slot number
        sequencer : Optional[int]
            Sequencer index.

        Returns
        ----------

        Raises
        ----------
        RuntimeError
            An error is reported in system error and debug <= 1.
            All errors are read from system error and listed in the exception.
        """
        if slot is None:
            slot = ""  # Arm sequencers across all modules

        if sequencer is None:
            sequencer = ""  # Arm all sequencers within a module

        return self._write(f"SLOT{slot}:SEQuencer{sequencer}:START")

    def stop_sequencer(self, slot: int | None = None, sequencer: int | None = None) -> None:
        """
        Stop the indexed sequencer, thereby putting it in the stopped state. If
        an invalid sequencer index is given, an error is set in system error. If
        no sequencer index is given, all sequencers are stopped.

        Parameters
        ----------
        slot : Optional[int]
            The slot index of the module being referred to.
        sequencer : Optional[int]
            Sequencer index.

        Raises
        ----------
        RuntimeError
            An error is reported in system error and debug <= 1.
            All errors are read from system error and listed in the exception.
        """
        if slot is None:
            slot = ""  # Stop sequencers across all modules

        if sequencer is None:
            sequencer = ""  # Stop all sequencers within a module

        self._write(f"SLOT{slot}:SEQuencer{sequencer}:STOP")

    # ----------------------------------------------------------------
    # System error is a state per connection. Therefore TurboCluster has added the optional
    # slot argument to get the error count and message per connection.
    # ----------------------------------------------------------------

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
            if self._is_batching[slot]:
                self._flush_buffer(slot)
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
            if self._is_batching[slot]:
                self._flush_buffer(slot)
            if not self._needs_check.get(slot, False):
                return 0
            cnt = int(self._connections[slot]._read("SYSTem:ERRor:COUNt?"))
            if cnt == 0:
                self._needs_check[slot] = False
            return cnt

    def get_system_errors(self, exclude: list[int] = []) -> list[str]:
        """
        Returns all the system errors for all connections.
        Error counts are requested simultaneously on all connections to speed up communication.
        Error messages are requested sequentially, because there is no need to hurry when there are errors.

        Note:
            The simultaneous requests save ~1 ms per module
        """
        errors = []
        # use 0 for CMM. (actually it is in slot 0)
        slots = [0] + [slot for slot, check in self._needs_check.items() if check]
        for slot in exclude:
            try:
                slots.remove(slot)
            except Exception:
                pass
        err_count_request = "SYSTem:ERRor:COUNt?"
        get_error = "SYSTem:ERRor:NEXT?"

        # write all requests
        for slot in slots:
            if self._is_batching[slot]:
                self._flush_buffer(slot)
            conn = self._connections.get(slot, self)
            conn._write(err_count_request)
        # read all responses
        for slot in slots:
            conn = self._connections.get(slot, self)
            # read without writing command.
            response = conn._transport.readline().rstrip()
            num_err = int(response)
            for _ in range(num_err):
                error = conn._read(get_error)
                if slot:
                    error = f"slot {slot}: " + error
                errors.append(error)
            self._needs_check[slot] = False

        return errors

    # ----------------------------------------------------------------
    # Polling the sequencer status for every sequencer in a sequential way takes a lot of time.
    # The method below sends all the status requests for all the sequencers and
    # then reads all the responses.
    # Note that the implementation uses a local implementation of `readline` that can
    # read a sequence of responses in a safe way without losing data.
    # socket.makefile creates a buffer. So all responses should be read using the
    # same buffer.
    # ----------------------------------------------------------------

    def get_sequencer_status_multiple(self, sequencers: dict[int, list[int]]) -> tuple[int, int, object]:
        """
        Returns the status for multiple sequencers using parallel requests.
        Parameters
        ----------
        sequencers : dict[int, list[int]]
            Per slot a list with sequencers to request status from.

        Note:
            The simultaneous requests save ~1 ms per sequencer
        """
        results = []
        # write all requests
        for slot, seq_nums in sequencers.items():
            if len(seq_nums) == 0:
                continue
            if self._is_batching[slot]:
                self._flush_buffer(slot)
            conn = self._connections[slot]
            for sequencer in seq_nums:
                conn._write(f"SEQuencer{sequencer}:STATE?")

        # read all responses
        for slot, seq_nums in sequencers.items():
            conn = self._connections[slot]
            filereader = conn._transport._socket.makefile()

            for sequencer in seq_nums:
                status_str = filereader.readline()
                status = _convert_sequencer_status(status_str)
                results.append((slot, sequencer, status))
            filereader.close()
        return results

    # --------------------------------------------------------------------------------
    # The following methods are added to cache the sequencer configuration and
    # reduce the amount of configuration requests every time a setting is changed.
    #
    # The methods explictly call ClusterScpi, because in versions <= v0.16 the
    # super class (ClusterNative) calls the methods via func_refs.
    # Calls are mode to `ClusterScpi.method_xxx(self, ...)`, because method invocation on
    # super() will result in infinite recursion (for versions <= v0.16).
    # --------------------------------------------------------------------------------

    def _init_configuration_cache(self):
        if TurboCluster.use_configuration_cache:
            # NOTE: A simple override of the methods does not work for versions <= v0.16.
            #       These versions use Funcs to call the operations on ClusterScpi from
            #       multiple methods in ClusterNative.
            attr_names = [
                "_get_sequencer_config",
                "_set_sequencer_config",
                "_get_sequencer_channel_map",
                "_set_sequencer_channel_map",
                "_get_pre_distortion_config",
                "_set_pre_distortion_config",
                ]
            mod_handles = self._mod_handles
            for slot_id in range(1, 21):
                if slot_id in mod_handles and "func_refs" in mod_handles[slot_id]:
                    func_refs = self._mod_handles[slot_id]["func_refs"]
                    for name in attr_names:
                        if name in func_refs._funcs:
                            func_refs.register(partial(getattr(self, name), slot_id), name)
                            # logger.debug(f"Registered {slot_id}: {name}")
        self._clear_cache()

    def reset(self):
        self._clear_cache()
        super().reset()

    def _clear_cache(self):
        self._channel_map_cache: dict[tuple[int, int], str] = {}
        self._sequencer_config_cache: dict[tuple[int, int], str] = {}
        self._slot_predistortion_cache: dict[int, str] = {}

    def _set_sequencer_channel_map(
        self, slot: int, sequencer: int, sequencer_channel_map: Any
    ) -> None:
        """
        Set channel map of the indexed sequencer. The channel map consists of a list with two elements representing
        the components of the complex signal to be acquired, each mapping to a list of DAC indices.
        Index i maps to output i+1. If an invalid sequencer index is given or the channel map is not valid,
        an error is set in system error.

        Parameters
        ----------
        slot : int
            slot index.
        sequencer : int
            Sequencer index.
        sequencer_channel_map : Any
            Current Sequencer index Any.

        Returns
        -------
        None

        Raises
        ------
        Exception
            Invalid input parameter type.
        Exception
            An error is reported in system error and debug <= 1.
            All errors are read from system error and listed in the exception.
        """
        if TurboCluster.use_configuration_cache:
            self._channel_map_cache[(slot, sequencer)] = json.dumps(sequencer_channel_map)
        ClusterScpi._set_sequencer_channel_map(self, slot, sequencer, sequencer_channel_map)

    def _get_sequencer_channel_map(self, slot: int, sequencer: int) -> Any:
        """
        Get channel map of the indexed sequencer. The channel map consists of a list with two elements representing
        the components of the complex signal to be acquired, each mapping to a list of DAC indices.
        Index i maps to output i+1. If an invalid sequencer index is given or the channel map is not valid,
        an error is set in system error.

        Parameters
        ----------
        slot : int
            slot index.
        sequencer : int
            Sequencer index.

        Returns
        -------
        Any
            Current Sequencer index.

        Raises
        ------
        Exception
            Invalid input parameter type.
        Exception
            An error is reported in system error and debug <= 1.
            All errors are read from system error and listed in the exception.
        """
        if TurboCluster.use_configuration_cache:
            try:
                cached_str = self._channel_map_cache[(slot, sequencer)]
                return json.loads(cached_str)
            except KeyError:
                logger.info(f"cache miss channel_map {slot}, {sequencer}")
                pass
            result = ClusterScpi._get_sequencer_channel_map(self, slot, sequencer)
            self._channel_map_cache[(slot, sequencer)] = json.dumps(result)
            return result
        else:
            return ClusterScpi._get_sequencer_channel_map(self, slot, sequencer)

    def _set_sequencer_config(
        self, slot: int, sequencer: int, sequencer_config: Any
    ) -> None:
        """
        Set configuration of the indexed sequencer. The configuration consists of multiple parameters in a JSON format.
        If an invalid sequencer index is given, an error is set in system error.

        Parameters
        ----------
        slot : int
            slot index.
        sequencer : int
            Sequencer index.
        sequencer_config : Any
            Current Configuration struct Any.

        Returns
        -------
        None

        Raises
        ------
        Exception
            Invalid input parameter type.
        Exception
            An error is reported in system error and debug <= 1.
            All errors are read from system error and listed in the exception.
        """

        if TurboCluster.use_configuration_cache:
            self._sequencer_config_cache[(slot, sequencer)] = json.dumps(sequencer_config)
        ClusterScpi._set_sequencer_config(self, slot, sequencer, sequencer_config)

    def _get_sequencer_config(self, slot: int, sequencer: int) -> Any:
        """
        Get configuration of the indexed sequencer. The configuration consists of multiple parameters in a JSON format.
        If an invalid sequencer index is given, an error is set in system error.

        Parameters
        ----------
        slot : int
            slot index.
        sequencer : int
            Sequencer index.

        Returns
        -------
        Any
            Current Configuration struct.

        Raises
        ------
        Exception
            Invalid input parameter type.
        Exception
            An error is reported in system error and debug <= 1.
            All errors are read from system error and listed in the exception.
        """
        if TurboCluster.use_configuration_cache:
            try:
                cached_str = self._sequencer_config_cache[(slot, sequencer)]
                return json.loads(cached_str)
            except KeyError:
                logger.info(f"cache miss sequencer_config {slot}, {sequencer}")
                pass
            result = ClusterScpi._get_sequencer_config(self, slot, sequencer)
            self._sequencer_config_cache[(slot, sequencer)] = json.dumps(result)
            return result
        else:
            return ClusterScpi._get_sequencer_config(self, slot, sequencer)

    def _set_pre_distortion_config(self, slot: int, pre_distortion_config: Any) -> None:
        """
        Set pre-distortion configuration. The configuration consists of multiple parameters in a JSON format.
        If the configation does not have the correct format, an error is set in system error..

        Parameters
        ----------
        slot : int
            slot index.
        pre_distortion_config : Any
            Current pre-distortion config Any.

        Returns
        -------
        None

        Raises
        ------
        Exception
            Invalid input parameter type.
        Exception
            An error is reported in system error and debug <= 1.
            All errors are read from system error and listed in the exception.
        """
        if TurboCluster.use_configuration_cache:
            self._slot_predistortion_cache[slot] = json.dumps(pre_distortion_config)
        ClusterScpi._set_pre_distortion_config(self, slot, pre_distortion_config)

    def _get_pre_distortion_config(self, slot: int) -> Any:
        """
        Get pre-distortion configuration. The configuration consists of multiple parameters in a JSON format.
        If the configation does not have the correct format, an error is set in system error..

        Parameters
        ----------
        slot : int
            slot index.

        Returns
        -------
        Any
            Current pre-distortion config.

        Raises
        ------
        Exception
            Invalid input parameter type.
        Exception
            An error is reported in system error and debug <= 1.
            All errors are read from system error and listed in the exception.
        """
        if TurboCluster.use_configuration_cache:
            try:
                cached_str = self._slot_predistortion_cache[slot]
                return json.loads(cached_str)
            except KeyError:
                logger.info(f"cache miss predistortion {slot}")
                pass
            result = ClusterScpi._get_pre_distortion_config(self, slot)
            self._slot_predistortion_cache[slot] = json.dumps(result)
            return result
        else:
            return ClusterScpi._get_pre_distortion_config(self, slot)


def readline(conn) -> str:
    """Safe implementation of readline on socket without buffering.

    The trivial solution `socket.makefile().readline()` is wrong, because
    it uses a buffer. If there is more data available on the socket, then
    some if it will be loaded into the buffer and discarded after the statement.
    Dataloss is likely with `makefile` combined with binary reads on the socket.
    """

    socket = conn._transport._socket
    buffer = io.BytesIO()
    b = None
    while True:
        b = socket.recv(1)
        buffer.write(b)
        if b == b'\n':
            break
    return buffer.getvalue().decode().rstrip()


def _convert_sequencer_status(state_str: str):
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
