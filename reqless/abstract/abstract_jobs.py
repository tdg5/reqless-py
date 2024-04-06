from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Union

from reqless.abstract.abstract_job import AbstractJob, AbstractRecurringJob


class AbstractJobs(ABC):
    @abstractmethod
    def complete(
        self,
        offset: int = 0,
        count: int = 25,
    ) -> List[str]:  # pragma: no cover
        pass

    @abstractmethod
    def failed(
        self,
        group: Optional[str] = None,
        start: int = 0,
        limit: int = 25,
    ) -> Dict:  # pragma: no cover
        pass

    @abstractmethod
    def get(self, *jids: str) -> List[AbstractJob]:  # pragma: no cover
        pass

    @abstractmethod
    def tagged(
        self, tag: str, offset: int = 0, count: int = 25
    ) -> Dict:  # pragma: no cover
        pass

    @abstractmethod
    def tracked(self) -> Dict[str, List[AbstractJob]]:  # pragma: no cover
        pass

    @abstractmethod
    def __getitem__(
        self,
        jid: str,
    ) -> Optional[Union[AbstractJob, AbstractRecurringJob]]:  # pragma: no cover
        pass
