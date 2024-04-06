"""A class that listens to pubsub channels and can unlisten"""

import logging
import threading
from contextlib import contextmanager
from typing import Any, Callable, Dict, Generator, List, Optional, Tuple

from redis import Redis
from redis.client import PubSub


# Our logger
logger = logging.getLogger("reqless")


class Listener:
    """A class that listens to pubsub channels and can unlisten"""

    def __init__(self, redis: Redis, channels: List[str]):
        self._pubsub: PubSub = redis.pubsub()
        self._channels: List[str] = channels

    def listen(self) -> Generator[Dict[str, Any], None, None]:
        """Listen for events as they come in"""
        try:
            self._pubsub.subscribe(*self._channels)
            for message in self._pubsub.listen():  # type: ignore[no-untyped-call]
                if message["type"] == "message":
                    yield message
        finally:
            self._channels = []

    def unlisten(self) -> None:
        """Stop listening for events"""
        self._pubsub.unsubscribe(*self._channels)


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

    def __init__(self, redis: Redis):
        self._listener = Listener(
            channels=[self.namespace + event for event in self.events],
            redis=redis,
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
        try:
            yield self
        finally:
            self.unlisten()
            thread.join()
