from qblox_instruments import Cluster
from qblox_instruments.ieee488_2 import Ieee488_2, IpTransport
from qblox_instruments.pnp import resolve


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
        super().__init__(name, identifier, port, debug=2)

    def add_submodule(self, name, module):
        """Overwrite of qcodes add_submodule to create tcp connection for this module.
        """
        slot = module.slot_idx
        ip_config = resolve(f"{self._ip_address}/{slot}")
        transport = IpTransport(ip_config.address, ip_config.scpi_port)
        self._connections[slot] = Ieee488_2(transport)
        super().add_submodule(name, module)

    def _write(self, cmd_str):
        conn, cmd = self._get_connection_and_remove_slot(cmd_str)
        conn._write(cmd)

    def _write_bin(self, cmd_str, bin_block):
        conn, cmd = self._get_connection_and_remove_slot(cmd_str)
        conn._write_bin(cmd, bin_block)

    def _read_bin(self, cmd_str, flush_line_end=True):
        conn, cmd = self._get_connection_and_remove_slot(cmd_str)
        return conn._read_bin(cmd, flush_line_end)

    def _read(self, cmd_str: str) -> str:
        conn, cmd = self._get_connection_and_remove_slot(cmd_str)
        return conn._read(cmd)

    def _get_connection_and_remove_slot(self, cmd: str) -> tuple[Ieee488_2, str]:
        if cmd.startswith("SLOT"):
            slot_str, module_cmd = cmd.split(":", maxsplit=1)
            try:
                slot = int(slot_str[5:])
            except ValueError:
                raise Exception(f"Connect extract slot index from '{cmd}'")
            return self._connections[slot], module_cmd
        return super(), cmd

    def get_system_error(self, slot: int | None = None) -> str:
        if slot is None:
            return super().get_system_error()
        else:
            return self._connections[slot]._read("SYSTem:ERRor:NEXT?")

    def get_num_system_error(self, slot: int | None = None) -> int:
        if slot is None:
            return super().get_num_system_error()
        else:
            return int(self._read("SYSTem:ERRor:COUNt?"))

    def arm_sequencer(self, slot: int | None = None, sequencer: int | None = None) -> None:
        if slot is None:
            raise Exception("Specify slot for arm_sequencer of TurboCluster")
        super().arm_sequencer(slot, sequencer)

    def start_sequencer(self, slot: int | None = None, sequencer: int | None = None) -> None:
        if slot is None:
            raise Exception("Specify slot for start_sequencer of TurboCluster")
        super().start_sequencer(slot, sequencer)

    def stop_sequencer(self, slot: int | None = None, sequencer: int | None = None) -> None:
        if slot is None:
            raise Exception("Specify slot for stop_sequencer of TurboCluster")
        super().stop_sequencer(slot, sequencer)

    def clear_sequencer_flags(self, slot: int | None = None, sequencer: int | None = None) -> None:
        if slot is None:
            raise Exception("Specify slot for clear_sequencer_flags of TurboCluster")
        super().clear_sequencer_flags(slot, sequencer)

    def arm_scope_trigger(self, slot: int | None = None) -> None:
        if slot is None:
            raise Exception("Specify slot for arm_scope_trigger of TurboCluster")
        super().arm_scope_trigger(slot)

    def _get_acq_acquisitions(self, slot: int, sequencer: int) -> dict:
        # not implemented because native implementation uses _flush_line_end without slot
        raise NotImplementedError("Not implemented for TurboCluster")

    def _get_awg_waveforms(self, slot: int, sequencer: int) -> dict:
        # not implemented because native implementation uses _flush_line_end without slot
        raise NotImplementedError("Not implemented for TurboCluster")

    def _get_acq_weights(self, slot: int, sequencer: int) -> dict:
        # not implemented because native implementation uses _flush_line_end without slot
        raise NotImplementedError("Not implemented for TurboCluster")
