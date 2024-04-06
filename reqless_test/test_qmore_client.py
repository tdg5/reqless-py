import json
from typing import Dict, List, Mapping, Union

from qmore.client import (
    QUEUE_IDENTIFIER_PATTERNS_KEY,
    QUEUE_PRIORITY_PATTERNS_KEY,
    QmoreClient,
    QueuePriorityPattern,
)
from reqless_test.common import TestReqless


class TestQmoreClient(TestReqless):
    def setUp(self) -> None:
        TestReqless.setUp(self)
        self.redis = self.client.redis
        self.subject = QmoreClient(redis=self.client.redis)

    def test_get_queue_identifier_patterns(self) -> None:
        """It fetches the expected queue identifier patterns"""
        mapping = {"one": ["one", "two*", "!three"], "four": ["four", "five"]}
        json_mapping: Mapping[Union[bytes, str], Union[bytes, float, int, str]] = {
            key: json.dumps(value) for key, value in mapping.items()
        }
        self.redis.hset(QUEUE_IDENTIFIER_PATTERNS_KEY, mapping=json_mapping)
        fetched_mapping = self.subject.get_queue_identifier_patterns()
        self.assertEqual({"default": "*", **mapping}, fetched_mapping)

    def test_set_queue_identifier_patterns(self) -> None:
        """It sets the expected queue identifier patterns"""
        mapping = {"not_three": ["one", "two*", "!three"], "five": ["four", "five"]}
        self.subject.set_queue_identifier_patterns(mapping)
        serialized_patterns = self.redis.hgetall(QUEUE_IDENTIFIER_PATTERNS_KEY)
        patterns = {
            identifier: json.loads(json_patterns)
            for identifier, json_patterns in serialized_patterns.items()
        }
        self.assertEqual(mapping, patterns)

    def test_set_queue_identifier_patterns_with_no_patterns(self) -> None:
        """It clears any existing patterns and does not try to hset without a mapping"""
        # Make sure there's something there to clear out
        mapping = {"not_three": ["one", "two*", "!three"], "five": ["four", "five"]}
        self.subject.set_queue_identifier_patterns(mapping)
        serialized_patterns = self.redis.hgetall(QUEUE_IDENTIFIER_PATTERNS_KEY)
        self.assertEqual(2, len(serialized_patterns))

        empty_mapping: Dict[str, List[str]] = {}
        self.subject.set_queue_identifier_patterns(empty_mapping)
        serialized_patterns = self.redis.hgetall(QUEUE_IDENTIFIER_PATTERNS_KEY)
        patterns = {
            identifier: json.loads(json_patterns)
            for identifier, json_patterns in serialized_patterns.items()
        }
        self.assertEqual(empty_mapping, patterns)

    def test_get_queue_priority_patterns(self) -> None:
        """It fetches the expected queue identifier patterns"""
        given_queue_priorities = [
            QueuePriorityPattern(patterns=["*"], should_distribute_fairly=True),
        ]
        serialized_queue_priorities = [
            json.dumps(
                {
                    "fairly": queue_priority.should_distribute_fairly,
                    "pattern": ",".join(queue_priority.patterns),
                }
            )
            for queue_priority in given_queue_priorities
        ]
        pipeline = self.redis.pipeline()
        pipeline.delete(QUEUE_PRIORITY_PATTERNS_KEY)
        for serialized_queue_priority in serialized_queue_priorities:
            pipeline.rpush(QUEUE_PRIORITY_PATTERNS_KEY, serialized_queue_priority)
        pipeline.execute()
        queue_priorities = self.subject.get_queue_priority_patterns()
        zipped_queue_priorities = zip(given_queue_priorities, queue_priorities)
        for given_queue_priority, queue_priority in zipped_queue_priorities:
            self.assertEqual(given_queue_priority.patterns, queue_priority.patterns)
            self.assertEqual(
                given_queue_priority.should_distribute_fairly,
                queue_priority.should_distribute_fairly,
            )

    def test_set_queue_priority_patterns(self) -> None:
        """It sets the expected queue identifier patterns"""
        given_queue_priorities = [
            QueuePriorityPattern(patterns=["*"], should_distribute_fairly=True),
        ]
        self.subject.set_queue_priority_patterns(given_queue_priorities)
        serialized_queue_priorities = self.redis.lrange(
            QUEUE_PRIORITY_PATTERNS_KEY, 0, -1
        )
        queue_priorities = []
        for serialized_queue_priority in serialized_queue_priorities:
            queue_priority_data = json.loads(serialized_queue_priority)
            patterns = [
                pattern.strip() for pattern in queue_priority_data["pattern"].split(",")
            ]
            queue_priorities.append(
                QueuePriorityPattern(
                    patterns=patterns,
                    should_distribute_fairly=queue_priority_data["fairly"],
                )
            )
        zipped_queue_priorities = zip(given_queue_priorities, queue_priorities)
        for given_queue_priority, queue_priority in zipped_queue_priorities:
            self.assertEqual(given_queue_priority.patterns, queue_priority.patterns)
            self.assertEqual(
                given_queue_priority.should_distribute_fairly,
                queue_priority.should_distribute_fairly,
            )
