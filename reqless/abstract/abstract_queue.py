from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Type, Union

from reqless.abstract.abstract_job import AbstractJob
from reqless.abstract.abstract_queue_jobs import AbstractQueueJobs
from reqless.abstract.abstract_throttle import AbstractThrottle


class AbstractQueue(ABC):
    @property
    @abstractmethod
    def counts(self) -> Dict:  # pragma: no cover
        pass

    @property
    @abstractmethod
    def heartbeat(self) -> int:  # pragma: no cover
        pass

    @heartbeat.setter
    @abstractmethod
    def heartbeat(self, value: int) -> None:  # pragma: no cover
        pass

    @property
    @abstractmethod
    def jobs(self) -> AbstractQueueJobs:  # pragma: no cover
        pass

    @property
    @abstractmethod
    def name(self) -> str:  # pragma: no cover
        pass

    @abstractmethod
    def pause(self) -> None:  # pragma: no cover
        pass

    @abstractmethod
    def peek(
        self, count: Optional[int] = None
    ) -> Union[AbstractJob, List[AbstractJob], None]:  # pragma: no cover
        pass

    @abstractmethod
    def pop(
        self, count: Optional[int] = None
    ) -> Union[AbstractJob, List[AbstractJob], None]:  # pragma: no cover
        pass

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
        pass

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
        pass

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
        pass

    @abstractmethod
    def stats(self, date: Optional[str] = None) -> Dict:  # pragma: no cover
        pass

    @property
    @abstractmethod
    def throttle(self) -> AbstractThrottle:  # pragma: no cover
        pass

    @abstractmethod
    def unpause(self) -> None:  # pragma: no cover
        pass

    @abstractmethod
    def __len__(self) -> int:  # pragma: no cover
        pass
