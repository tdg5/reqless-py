from abc import ABC, abstractmethod

from typing_extensions import Self


class AbstractJobData(ABC):
    @abstractmethod
    def to_json(self) -> str:  # pragma: no cover
        pass

    @classmethod
    @abstractmethod
    def from_json(cls, data: str) -> Self:  # pragma: no cover
        pass
