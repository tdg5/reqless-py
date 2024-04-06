from abc import ABC, abstractmethod

from reqless.abstract.abstract_throttle import AbstractThrottle


class AbstractThrottles(ABC):
    @abstractmethod
    def __getitem__(self, throttle_name: str) -> AbstractThrottle:  # pragma: no cover
        pass
