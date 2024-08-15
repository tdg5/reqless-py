import json
from typing import Dict, List, Mapping, Union

from redis import Redis

from reqless.models import QueuePriorityPattern


QUEUE_IDENTIFIER_PATTERNS_KEY = "qmore:dynamic"
QUEUE_PRIORITY_PATTERNS_KEY = "qmore:priority"


class QmoreClient:
    def __init__(self, database: Redis):
        self.database: Redis = database

    def get_queue_identifier_patterns(self) -> Dict[str, List[str]]:
        serialized_patterns = self.database.hgetall(QUEUE_IDENTIFIER_PATTERNS_KEY)
        patterns = {
            identifier: json.loads(json_patterns)
            for identifier, json_patterns in serialized_patterns.items()
        }
        if "default" not in patterns:
            patterns["default"] = ["*"]
        return patterns

    def set_queue_identifier_patterns(
        self,
        identifier_patterns: Dict[str, List[str]],
    ) -> None:
        json_patterns: Mapping[Union[bytes, str], Union[bytes, float, int, str]] = {
            identifier: json.dumps(patterns)
            for identifier, patterns in identifier_patterns.items()
        }
        pipeline = self.database.pipeline()
        pipeline.delete(QUEUE_IDENTIFIER_PATTERNS_KEY)
        if json_patterns:
            pipeline.hset(QUEUE_IDENTIFIER_PATTERNS_KEY, mapping=json_patterns)
        pipeline.execute()

    def get_queue_priority_patterns(self) -> List[QueuePriorityPattern]:
        serialized_priority_patterns = self.database.lrange(
            QUEUE_PRIORITY_PATTERNS_KEY, 0, -1
        )
        queue_priority_patterns: List[QueuePriorityPattern] = []
        for serialized_priority_pattern in serialized_priority_patterns:
            priority_pattern_data = json.loads(serialized_priority_pattern)
            queue_priority_pattern = QueuePriorityPattern(
                patterns=[
                    pattern.strip()
                    for pattern in str(priority_pattern_data["pattern"]).split(",")
                ],
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
        pipeline = self.database.pipeline()
        pipeline.delete(QUEUE_PRIORITY_PATTERNS_KEY)
        for queue_priority_pattern in queue_priority_patterns:
            serialized_queue_priority_pattern = json.dumps(
                {
                    "fairly": queue_priority_pattern.should_distribute_fairly,
                    "pattern": ",".join(queue_priority_pattern.patterns),
                }
            )
            pipeline.rpush(
                QUEUE_PRIORITY_PATTERNS_KEY,
                serialized_queue_priority_pattern,
            )
        pipeline.execute()
