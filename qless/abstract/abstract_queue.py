from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Type, Union

from qless.abstract.abstract_job import AbstractJob
from qless.abstract.abstract_queue_jobs import AbstractQueueJobs
from qless.abstract.abstract_throttle import AbstractThrottle


class AbstractQueue(ABC):
    @property
    @abstractmethod
    def counts(self) -> Dict:  # pragma: no cover
        ...

    @property
    @abstractmethod
    def heartbeat(self) -> int:  # pragma: no cover
        ...

    @heartbeat.setter
    @abstractmethod
    def heartbeat(self, value: int) -> None:  # pragma: no cover
        ...

    @property
    @abstractmethod
    def jobs(self) -> AbstractQueueJobs:  # pragma: no cover
        ...

    @property
    @abstractmethod
    def name(self) -> str:  # pragma: no cover
        ...

    @abstractmethod
    def pause(self) -> None:  # pragma: no cover
        ...

    @abstractmethod
    def peek(
        self, count: Optional[int] = None
    ) -> Union[AbstractJob, List[AbstractJob], None]:  # pragma: no cover
        ...

    @abstractmethod
    def pop(
        self, count: Optional[int] = None
    ) -> Union[AbstractJob, List[AbstractJob], None]:  # pragma: no cover
        ...

    @abstractmethod
    def put(
        self,
        klass: Union[str, Type],
        data: str,
        priority: Optional[int] = None,
        tags: Optional[List[str]] = None,
        delay: Optional[int] = None,
        retries: Optional[int] = None,
        jid: Optional[str] = None,
        depends: Optional[List[str]] = None,
        throttles: Optional[List[str]] = None,
    ) -> str:  # pragma: no cover
        ...

    @abstractmethod
    def requeue(
        self,
        klass: Union[str, Type],
        data: str,
        priority: Optional[int] = None,
        tags: Optional[List[str]] = None,
        delay: Optional[int] = None,
        retries: Optional[int] = None,
        jid: Optional[str] = None,
        depends: Optional[List[str]] = None,
        throttles: Optional[List[str]] = None,
    ) -> str:  # pragma: no cover
        ...

    @abstractmethod
    def recur(
        self,
        klass: Union[str, Type],
        data: str,
        interval: Optional[int] = None,
        offset: Optional[int] = 0,
        priority: Optional[int] = None,
        tags: Optional[List[str]] = None,
        retries: Optional[int] = None,
        jid: Optional[str] = None,
        throttles: Optional[List[str]] = None,
    ) -> str:  # pragma: no cover
        ...

    @abstractmethod
    def stats(self, date: Optional[str] = None) -> Dict:  # pragma: no cover
        ...

    @property
    @abstractmethod
    def throttle(self) -> AbstractThrottle:  # pragma: no cover
        ...

    @abstractmethod
    def unpause(self) -> None:  # pragma: no cover
        ...

    @abstractmethod
    def __len__(self) -> int:  # pragma: no cover
        ...
