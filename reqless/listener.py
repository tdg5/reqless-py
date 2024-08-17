"""A class that listens to pubsub channels and can unlisten"""

import logging
from typing import Any, Dict, Generator, List

from redis import Redis
from redis.client import PubSub


logger = logging.getLogger("reqless")


class Listener:
    """A class that listens to pubsub channels and can unlisten"""

    def __init__(self, database: Redis, channels: List[str]):
        self._pubsub: PubSub = database.pubsub()
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
