import json
from typing import TYPE_CHECKING, List, Optional


if TYPE_CHECKING:
    from qless import Client


class Throttle:
    def __init__(self, client: "Client", name: str):
        self.client: "Client" = client
        self.name: str = name

    def delete(self) -> None:
        self.client("throttle.delete", self.name)

    def locks(self) -> List[str]:
        return self.client("throttle.locks", self.name)

    def maximum(self) -> int:
        json_state = self.client("throttle.get", self.name)
        state = json.loads(json_state) if json_state else {}
        return state.get("maximum", 0)

    def set_maximum(
        self,
        maximum: Optional[int] = None,
        expiration: Optional[int] = None,
    ) -> None:
        _maximum = maximum if maximum is not None else self.maximum()
        self.client("throttle.set", self.name, _maximum, expiration or 0)

    def pending(self) -> List[str]:
        return self.client("throttle.pending", self.name)

    def ttl(self) -> int:
        return self.client("throttle.ttl", self.name)
