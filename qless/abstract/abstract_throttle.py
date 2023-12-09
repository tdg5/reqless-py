from abc import ABC, abstractmethod
from typing import List, Optional


class AbstractThrottle(ABC):
    @abstractmethod
    def delete(self) -> None:  # pragma: no cover
        ...

    @abstractmethod
    def locks(self) -> List[str]:  # pragma: no cover
        ...

    @abstractmethod
    def maximum(self) -> int:  # pragma: no cover
        ...

    @property
    @abstractmethod
    def name(self) -> str:  # pragma: no cover
        ...

    @abstractmethod
    def set_maximum(
        self,
        maximum: Optional[int] = None,
        expiration: Optional[int] = None,
    ) -> None:  # pragma: no cover
        ...

    @abstractmethod
    def pending(self) -> List[str]:  # pragma: no cover
        ...

    @abstractmethod
    def ttl(self) -> int:  # pragma: no cover
        ...
