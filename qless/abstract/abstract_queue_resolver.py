from abc import ABC, abstractmethod
from typing import List


class AbstractQueueResolver(ABC):
    @abstractmethod
    def resolve(self) -> List[str]:  # pragma: no cover
        pass
