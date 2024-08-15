import json
from typing import Dict, List

from reqless.abstract import AbstractClient, AbstractQueuePatterns
from reqless.models import QueuePriorityPattern


class QueuePatterns(AbstractQueuePatterns):
    def __init__(self, client: AbstractClient):
        self.client: AbstractClient = client

    def get_queue_identifier_patterns(self) -> Dict[str, List[str]]:
        serialized_patterns: str = self.client("queueIdentifierPatterns.getAll")
        identifiers_with_serialized_values = json.loads(serialized_patterns)
        patterns = {
            identifier: json.loads(json_patterns)
            for identifier, json_patterns in identifiers_with_serialized_values.items()
        }
        return patterns

    def set_queue_identifier_patterns(
        self,
        identifier_patterns: Dict[str, List[str]],
    ) -> None:
        args: List[str] = [
            item
            for identifier, patterns in identifier_patterns.items()
            for item in [identifier, json.dumps(patterns)]
        ]
        self.client("queueIdentifierPatterns.setAll", *args)

    def get_queue_priority_patterns(self) -> List[QueuePriorityPattern]:
        serialized_priority_patterns_json = self.client("queuePriorityPatterns.getAll")
        serialized_priority_patterns = json.loads(serialized_priority_patterns_json)
        queue_priority_patterns: List[QueuePriorityPattern] = []
        for serialized_priority_pattern in serialized_priority_patterns:
            priority_pattern_data = json.loads(serialized_priority_pattern)
            queue_priority_pattern = QueuePriorityPattern(
                patterns=priority_pattern_data["pattern"],
                should_distribute_fairly=bool(
                    priority_pattern_data.get("fairly", False)
                ),
            )
            queue_priority_patterns.append(queue_priority_pattern)
        return queue_priority_patterns

    def set_queue_priority_patterns(
        self,
        queue_priority_patterns: List[QueuePriorityPattern],
    ) -> None:
        serialized_patterns = [
            json.dumps(
                {
                    "fairly": queue_priority_pattern.should_distribute_fairly,
                    "pattern": queue_priority_pattern.patterns,
                }
            )
            for queue_priority_pattern in queue_priority_patterns
        ]
        self.client("queuePriorityPatterns.setAll", *serialized_patterns)
