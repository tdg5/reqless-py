from abc import ABC, abstractmethod
from typing import Dict, List

from reqless.models import QueuePriorityPattern


class AbstractQueuePatterns(ABC):
    @abstractmethod
    def get_queue_identifier_patterns(self) -> Dict[str, List[str]]:  # pragma: no cover
        pass

    @abstractmethod
    def set_queue_identifier_patterns(
        self,
        identifier_patterns: Dict[str, List[str]],
    ) -> None:  # pragma: no cover
        pass

    @abstractmethod
    def get_queue_priority_patterns(
        self,
    ) -> List[QueuePriorityPattern]:  # pragma: no cover
        pass

    @abstractmethod
    def set_queue_priority_patterns(
        self,
        queue_priority_patterns: List[QueuePriorityPattern],
    ) -> None:  # pragma: no cover
        pass
