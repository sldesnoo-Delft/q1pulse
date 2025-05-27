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
        res =  conn._read_bin(cmd, flush_line_end)
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
            return self._connections[slot]._read("SYSTem:ERRor:NEXT?")

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
            return int(self._connections[slot]._read("SYSTem:ERRor:COUNt?"))


    def _get_acq_acquisitions(self, slot: int, sequencer: int) -> dict:
        # not implemented because native implementation uses _flush_line_end without slot
        raise NotImplementedError("Not implemented for TurboCluster")

    def _get_awg_waveforms(self, slot: int, sequencer: int) -> dict:
        # not implemented because native implementation uses _flush_line_end without slot
        raise NotImplementedError("Not implemented for TurboCluster")

    def _get_acq_weights(self, slot: int, sequencer: int) -> dict:
        # not implemented because native implementation uses _flush_line_end without slot
        raise NotImplementedError("Not implemented for TurboCluster")
