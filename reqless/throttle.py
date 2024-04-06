import json
from typing import Any, Dict, List, Optional

from reqless.abstract import AbstractClient, AbstractThrottle


class Throttle(AbstractThrottle):
    def __init__(self, client: AbstractClient, name: str):
        self.client: AbstractClient = client
        self._name: str = name

    def delete(self) -> None:
        self.client("throttle.delete", self.name)

    @property
    def name(self) -> str:
        return self._name

    def locks(self) -> List[str]:
        response: List[str] = self.client("throttle.locks", self.name)
        return response

    def maximum(self) -> int:
        json_state = self.client("throttle.get", self.name)
        state: Dict[str, Any] = json.loads(json_state) if json_state else {}
        maximum: int = state.get("maximum", 0)
        return maximum

    def set_maximum(
        self,
        maximum: Optional[int] = None,
        expiration: Optional[int] = None,
    ) -> None:
        _maximum = maximum if maximum is not None else self.maximum()
        self.client("throttle.set", self.name, _maximum, expiration or 0)

    def pending(self) -> List[str]:
        response: List[str] = self.client("throttle.pending", self.name)
        return response

    def ttl(self) -> int:
        response: int = self.client("throttle.ttl", self.name)
        return response
