from abc import ABC, abstractmethod
from typing import List


class AbstractQueueIdentifiersTransformer(ABC):
    @abstractmethod
    def transform(self, queue_identifiers: List[str]) -> List[str]:  # pragma: no cover
        pass
