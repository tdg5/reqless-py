from abc import ABC, abstractmethod
from typing import List, Optional, Type, Union


class AbstractBaseJob(ABC):
    @abstractmethod
    def cancel(self) -> List[str]:  # pragma: no cover
        ...

    @property
    @abstractmethod
    def data(self) -> str:  # pragma: no cover
        ...

    @data.setter
    @abstractmethod
    def data(self, value: str) -> None:  # pragma: no cover
        ...

    @property
    @abstractmethod
    def jid(self) -> str:  # pragma: no cover
        ...

    @property
    @abstractmethod
    def klass(self) -> Type:  # pragma: no cover
        ...

    @property
    @abstractmethod
    def klass_name(self) -> str:  # pragma: no cover
        ...

    @property
    @abstractmethod
    def queue_name(self) -> str:  # pragma: no cover
        ...

    @abstractmethod
    def tag(self, *tags: str) -> List[str]:  # pragma: no cover
        ...

    @property
    @abstractmethod
    def tags(self) -> List[str]:  # pragma: no cover
        ...

    @property
    @abstractmethod
    def throttles(self) -> List[str]:  # pragma: no cover
        ...

    @throttles.setter
    @abstractmethod
    def throttles(self, value: List[str]) -> None:  # pragma: no cover
        ...

    @abstractmethod
    def untag(self, *tags: str) -> List[str]:  # pragma: no cover
        ...


class AbstractJob(AbstractBaseJob):
    @abstractmethod
    def complete(
        self,
        nextq: Optional[str] = None,
        delay: Optional[int] = None,
        depends: Optional[List[str]] = None,
    ) -> bool:  # pragma: no cover
        ...

    @property
    @abstractmethod
    def dependencies(self) -> List[str]:  # pragma: no cover
        ...

    @dependencies.setter
    @abstractmethod
    def dependencies(self, value: List[str]) -> None:  # pragma: no cover
        ...

    @abstractmethod
    def fail(self, group: str, message: str) -> Union[bool, str]:  # pragma: no cover
        ...

    @abstractmethod
    def heartbeat(self) -> float:  # pragma: no cover
        ...

    @property
    @abstractmethod
    def klass(self) -> Type:  # pragma: no cover
        ...

    @klass.setter
    @abstractmethod
    def klass(self, value: Type) -> None:  # pragma: no cover
        ...

    @abstractmethod
    def process(self) -> None:  # pragma: no cover
        ...

    @abstractmethod
    def retry(
        self,
        delay: int = 0,
        group: Optional[str] = None,
        message: Optional[str] = None,
    ) -> int:  # pragma: no cover
        ...

    @property
    @abstractmethod
    def sandbox(self) -> Optional[str]:  # pragma: no cover
        ...

    @sandbox.setter
    @abstractmethod
    def sandbox(self, value: Optional[str]) -> None:  # pragma: no cover
        ...

    @property
    @abstractmethod
    def state(self) -> str:  # pragma: no cover
        ...

    @abstractmethod
    def timeout(self) -> None:  # pragma: no cover
        """Time out this job"""
        ...

    @abstractmethod
    def track(self) -> bool:  # pragma: no cover
        """Begin tracking this job"""
        ...

    @property
    @abstractmethod
    def tracked(self) -> bool:  # pragma: no cover
        ...

    @property
    @abstractmethod
    def ttl(self) -> float:  # pragma: no cover
        ...

    @abstractmethod
    def untrack(self) -> bool:  # pragma: no cover
        ...

    @property
    @abstractmethod
    def worker_name(self) -> str:  # pragma: no cover
        ...


class AbstractRecurringJob(AbstractBaseJob):
    @property
    @abstractmethod
    def next(self) -> Optional[float]:  # pragma: no cover
        ...
