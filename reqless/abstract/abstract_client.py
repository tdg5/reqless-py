from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

from reqless.abstract.abstract_config import AbstractConfig
from reqless.abstract.abstract_jobs import AbstractJobs
from reqless.abstract.abstract_queues import AbstractQueues
from reqless.abstract.abstract_throttles import AbstractThrottles
from reqless.abstract.abstract_workers import AbstractWorkers


if TYPE_CHECKING:  # pragma: no cover
    from redis import Redis


class AbstractClient(ABC):
    @abstractmethod
    def __call__(self, command: str, *args: Any) -> Any:  # pragma: no cover
        pass

    @property
    @abstractmethod
    def config(self) -> AbstractConfig:  # pragma: no cover
        pass

    @property
    @abstractmethod
    def jobs(self) -> AbstractJobs:  # pragma: no cover
        pass

    @property
    @abstractmethod
    def queues(self) -> AbstractQueues:  # pragma: no cover
        pass

    @property
    @abstractmethod
    def redis(self) -> "Redis":  # pragma: no cover
        pass

    @property
    @abstractmethod
    def throttles(self) -> AbstractThrottles:  # pragma: no cover
        pass

    @property
    @abstractmethod
    def worker_name(self) -> str:  # pragma: no cover
        pass

    @property
    @abstractmethod
    def workers(self) -> AbstractWorkers:  # pragma: no cover
        pass
