import os
import signal
import sys
import traceback
from code import InteractiveConsole
from types import FrameType
from typing import Callable, Optional, Tuple

from reqless import logger


def register_signal_handler(
    handler: Callable[[int, Optional[FrameType]], None],
    signals: Tuple[str, ...] = ("QUIT", "USR1", "USR2"),
) -> None:
    """Register signal handlers"""
    for sig in signals:
        signal.signal(getattr(signal, "SIG" + sig), handler)


def basic_signal_handler(
    on_quit: Callable[[], None],
) -> Callable[[int, Optional[FrameType]], None]:
    def signal_handler(
        signum: int, frame: Optional[FrameType]
    ) -> None:  # pragma: no cover
        """Signal handler for this process"""
        if signum == signal.SIGQUIT:
            on_quit()
        elif signum == signal.SIGUSR1:
            # USR1 - Print the backtrace
            message = "".join(traceback.format_stack(frame))
            message = "Signaled traceback for %s:\n%s" % (os.getpid(), message)
            print(message, file=sys.stderr)
            logger.warning(message)
        elif signum == signal.SIGUSR2:
            # USR2 - Enter a debugger
            # Much thanks to http://stackoverflow.com/questions/132058
            data = {"_frame": frame}  # Allow access to frame object.
            if frame:
                data.update(frame.f_globals)  # Unless shadowed by global
                data.update(frame.f_locals)
                # Build up a message with a traceback
                message = "".join(traceback.format_stack(frame))
            message = "Traceback:\n%s" % message
            InteractiveConsole(data).interact(message)

    return signal_handler
