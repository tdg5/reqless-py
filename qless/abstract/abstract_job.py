from abc import ABC, abstractmethod
from typing import List, Optional, Type, Union


class AbstractBaseJob(ABC):
    @abstractmethod
    def cancel(self) -> List[str]:  # pragma: no cover
        pass

    @property
    @abstractmethod
    def data(self) -> str:  # pragma: no cover
        pass

    @data.setter
    @abstractmethod
    def data(self, value: str) -> None:  # pragma: no cover
        pass

    @property
    @abstractmethod
    def jid(self) -> str:  # pragma: no cover
        pass

    @property
    @abstractmethod
    def klass(self) -> Type:  # pragma: no cover
        pass

    @property
    @abstractmethod
    def klass_name(self) -> str:  # pragma: no cover
        pass

    @property
    @abstractmethod
    def queue_name(self) -> str:  # pragma: no cover
        pass

    @abstractmethod
    def tag(self, *tags: str) -> List[str]:  # pragma: no cover
        pass

    @property
    @abstractmethod
    def tags(self) -> List[str]:  # pragma: no cover
        pass

    @property
    @abstractmethod
    def throttles(self) -> List[str]:  # pragma: no cover
        pass

    @throttles.setter
    @abstractmethod
    def throttles(self, value: List[str]) -> None:  # pragma: no cover
        pass

    @abstractmethod
    def untag(self, *tags: str) -> List[str]:  # pragma: no cover
        pass


class AbstractJob(AbstractBaseJob):
    @abstractmethod
    def complete(
        self,
        nextq: Optional[str] = None,
        delay: Optional[int] = None,
        depends: Optional[List[str]] = None,
    ) -> bool:  # pragma: no cover
        pass

    @property
    @abstractmethod
    def dependencies(self) -> List[str]:  # pragma: no cover
        pass

    @dependencies.setter
    @abstractmethod
    def dependencies(self, value: List[str]) -> None:  # pragma: no cover
        pass

    @abstractmethod
    def fail(self, group: str, message: str) -> Union[bool, str]:  # pragma: no cover
        pass

    @abstractmethod
    def heartbeat(self) -> float:  # pragma: no cover
        pass

    @property
    @abstractmethod
    def klass(self) -> Type:  # pragma: no cover
        pass

    @klass.setter
    @abstractmethod
    def klass(self, value: Type) -> None:  # pragma: no cover
        pass

    @abstractmethod
    def process(self) -> None:  # pragma: no cover
        pass

    @abstractmethod
    def retry(
        self,
        delay: int = 0,
        group: Optional[str] = None,
        message: Optional[str] = None,
    ) -> int:  # pragma: no cover
        pass

    @property
    @abstractmethod
    def sandbox(self) -> Optional[str]:  # pragma: no cover
        pass

    @sandbox.setter
    @abstractmethod
    def sandbox(self, value: Optional[str]) -> None:  # pragma: no cover
        pass

    @property
    @abstractmethod
    def state(self) -> str:  # pragma: no cover
        pass

    @abstractmethod
    def timeout(self) -> None:  # pragma: no cover
        """Time out this job"""
        pass

    @abstractmethod
    def track(self) -> bool:  # pragma: no cover
        """Begin tracking this job"""
        pass

    @property
    @abstractmethod
    def tracked(self) -> bool:  # pragma: no cover
        pass

    @property
    @abstractmethod
    def ttl(self) -> float:  # pragma: no cover
        pass

    @abstractmethod
    def untrack(self) -> bool:  # pragma: no cover
        pass

    @property
    @abstractmethod
    def worker_name(self) -> str:  # pragma: no cover
        pass


class AbstractRecurringJob(AbstractBaseJob):
    @property
    @abstractmethod
    def next(self) -> Optional[float]:  # pragma: no cover
        pass
