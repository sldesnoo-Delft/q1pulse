from __future__ import annotations

import logging
import signal
import threading
from collections.abc import Callable
from typing import Any, cast

from types import FrameType, TracebackType

logger = logging.getLogger(__name__)


class DelayedKeyboardInterrupt:
    signal_received: tuple[int, FrameType | None] | None = None
    # the handler type is seemingly only defined in typesheeed so copy it here
    # manually https://github.com/python/typeshed/blob/main/stdlib/signal.pyi
    old_handler: Callable[[int, FrameType | None], Any] | int | None = None

    def __init__(self, where: str = "") -> None:
        """
        A context manager to wrap a piece of code to ensure that a
        KeyboardInterrupt is not triggered by a SIGINT during the execution of
        this context. A second SIGINT will trigger the KeyboardInterrupt
        immediately.

        Inspired by https://stackoverflow.com/questions/842557/how-to-prevent-a-block-of-code-from-being-interrupted-by-keyboardinterrupt-in-py
        """
        self._where_msg = f"Section: {where}" if where != "" else ""

    def __enter__(self) -> None:
        is_main_thread = threading.current_thread() is threading.main_thread()
        if not is_main_thread:
            logger.debug(
                "Not on main thread. Cannot intercept interrupts. " + self._where_msg
            )
            return
        handler = signal.getsignal(signal.SIGINT)
        try:
            is_delayed_sig_handler = handler.__self__.__class__ == DelayedKeyboardInterrupt
        except Exception:
            is_delayed_sig_handler = False
            logger.debug("Not setting delayed keyboard interrupt. "
                         f"Current handler {repr(handler)}", exc_info=True)
        if not is_delayed_sig_handler:
            self.old_handler = signal.signal(signal.SIGINT, self._handler)

    def _handler(self, sig: int, frame: FrameType | None) -> None:

        self.signal_received = (sig, frame)
        print(
            "Received SIGINT, Will interrupt at first suitable time. "
            "Send second SIGINT to interrupt immediately."
        )
        # now that we have gotten one SIGINT make the signal
        # trigger a keyboard interrupt normally
        signal.signal(signal.SIGINT, self._forceful_handler)
        logger.info("SIGINT received. Delaying KeyboardInterrupt." + self._where_msg)

    def _forceful_handler(self, sig: int, frame: FrameType | None) -> None:
        print("Second SIGINT received. Triggering KeyboardInterrupt immediately.")
        logger.info(
            "Second SIGINT received. Triggering KeyboardInterrupt immediately. "
        )
        # The typing of signals seems to be inconsistent
        # since handlers must be types to take an optional frame
        # but default_int_handler does not take None.
        # see https://github.com/python/typeshed/pull/6599
        frame = cast("FrameType", frame)
        signal.default_int_handler(sig, frame)

    def __exit__(
        self,
        exception_type: type[BaseException] | None,
        value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if self.old_handler is not None:
            signal.signal(signal.SIGINT, self.old_handler)
        if self.signal_received is not None:
            if self.old_handler is not None and not isinstance(self.old_handler, int):
                self.old_handler(*self.signal_received)
