"""A class that listens to pubsub channels and can unlisten"""

import logging
from threading import RLock
from typing import Any, Dict, Generator, List

from redis import Redis
from redis.client import PubSub

from reqless.future import Future


logger = logging.getLogger("reqless")


class Listener:
    """A class that listens to pubsub channels and can unlisten"""

    def __init__(self, database: Redis, channels: List[str]):
        self._pubsub: PubSub = database.pubsub()
        self._channels: List[str] = channels
        self._lock: RLock = RLock()
        self._listening_future: Future[bool] = Future[bool]()
        self.is_listening: bool = False

    def listen(self) -> Generator[Dict[str, Any], None, None]:
        """Listen for events as they come in"""
        with self._lock:
            self._pubsub.subscribe(*self._channels)
            self._listening_future.set_result(True)
            self.is_listening = True

        for message in self._pubsub.listen():  # type: ignore[no-untyped-call]
            if message["type"] == "message":
                yield message
            if not self.is_listening:
                break

    def wait_until_listening(self) -> None:
        """Block until listening has begun. Intended for multi-thread scenarios
        where one thread is listening and another thread wants to know when
        listening has begun."""

        self._listening_future.result()

    def unlisten(self) -> None:
        """Stop listening for events"""
        with self._lock:
            if self.is_listening:
                self._pubsub.unsubscribe(*self._channels)
                self.is_listening = False
                # Reset the future so the listener can listen again.
                self._listening_future = Future[bool]()
