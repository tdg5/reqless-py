import logging
import threading
from contextlib import contextmanager
from typing import Callable, Dict, Generator, Optional, Tuple

from redis import Redis

from reqless.listener import Listener


logger = logging.getLogger("reqless")


class Events:
    """A class for handling reqless events"""

    namespace = "ql:"
    events: Tuple[str, ...] = (
        "canceled",
        "completed",
        "failed",
        "popped",
        "put",
        "stalled",
        "track",
        "untrack",
    )

    def __init__(self, database: Redis):
        self._listener = Listener(
            channels=[self.namespace + event for event in self.events],
            database=database,
        )
        self._callbacks: Dict[str, Optional[Callable]] = {k: None for k in self.events}

    def listen(self) -> None:
        """Listen for events"""
        for message in self._listener.listen():
            logger.debug("Message: %s", message)
            # Strip off the 'namespace' from the channel
            channel = message["channel"][len(self.namespace) :]
            func = self._callbacks.get(channel)
            if func:
                func(message["data"])

    def on(self, evt: str, func: Optional[Callable]) -> None:
        """Set a callback handler for a pubsub event"""
        if evt not in self._callbacks:
            raise NotImplementedError('callback "%s"' % evt)
        else:
            self._callbacks[evt] = func

    def off(self, evt: str) -> Optional[Callable]:
        """Deactivate the callback for a pubsub event"""
        return self._callbacks.pop(evt, None)

    def unlisten(self) -> None:
        """Stop listening for events"""
        self._listener.unlisten()

    @contextmanager
    def thread(self) -> Generator["Events", None, None]:
        """Run in a thread"""
        thread = threading.Thread(target=self.listen)
        thread.start()
        # Wait for the listener to start listening to ensure we don't unlisten
        # before the listener has started listening.
        self._listener.wait_until_listening()
        try:
            yield self
        finally:
            self.unlisten()
            thread.join()
