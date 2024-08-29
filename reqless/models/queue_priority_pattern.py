from typing import Any, List


class QueuePriorityPattern:
    def __init__(
        self,
        patterns: List[str],
        should_distribute_fairly: bool,
    ):
        self.patterns: List[str] = patterns
        self.should_distribute_fairly: bool = should_distribute_fairly

    def __eq__(self, other: Any) -> bool:
        return (
            isinstance(other, QueuePriorityPattern)
            and other.patterns == self.patterns
            and other.should_distribute_fairly == self.should_distribute_fairly
        )

    def __repr__(self) -> str:
        return (
            f"<QueuePriorityPattern patterns={self.patterns}"
            f" should_distribute_fairly={self.should_distribute_fairly}>"
        )
