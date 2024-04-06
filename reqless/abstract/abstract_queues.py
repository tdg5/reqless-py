from abc import ABC, abstractmethod
from typing import Dict

from reqless.abstract.abstract_queue import AbstractQueue


class AbstractQueues(ABC):
    @property
    @abstractmethod
    def counts(self) -> Dict:  # pragma: no cover
        pass

    @abstractmethod
    def __getitem__(self, queue_name: str) -> AbstractQueue:  # pragma: no cover
        pass
