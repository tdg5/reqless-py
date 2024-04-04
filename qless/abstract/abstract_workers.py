from abc import ABC, abstractmethod
from typing import Dict


class AbstractWorkers(ABC):
    @property
    @abstractmethod
    def counts(self) -> Dict:  # pragma: no cover
        pass

    @abstractmethod
    def __getitem__(self, queue_name: str) -> Dict:  # pragma: no cover
        pass
