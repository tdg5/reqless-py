import json
from typing import Dict, List, Union

from reqless.models import QueuePriorityPattern
from reqless.queue_patterns import QueuePatterns
from reqless_test.common import TestReqless


QUEUE_IDENTIFIER_PATTERNS_KEY = "ql:qp:identifiers"
QUEUE_PRIORITY_PATTERNS_KEY = "ql:qp:priorities"


class TestQueuePatterns(TestReqless):
    def setUp(self) -> None:
        TestReqless.setUp(self)
        self.subject = QueuePatterns(client=self.client)

    def test_get_queue_identifier_patterns(self) -> None:
        """It fetches the expected queue identifier patterns"""
        mapping = {"one": ["one", "two*", "!three"], "four": ["four", "five"]}
        json_mapping: Dict[Union[bytes, str], Union[bytes, float, int, str]] = {
            key: json.dumps(value) for key, value in mapping.items()
        }
        self.database.hset(QUEUE_IDENTIFIER_PATTERNS_KEY, mapping=json_mapping)
        fetched_mapping = self.subject.get_queue_identifier_patterns()
        self.assertEqual({"default": ["*"], **mapping}, fetched_mapping)

    def test_set_queue_identifier_patterns(self) -> None:
        """It sets the expected queue identifier patterns"""
        mapping = {"not_three": ["one", "two*", "!three"], "five": ["four", "five"]}
        self.subject.set_queue_identifier_patterns(mapping)
        serialized_patterns = self.database.hgetall(QUEUE_IDENTIFIER_PATTERNS_KEY)
        patterns = {
            identifier.decode("utf-8"): json.loads(json_patterns)
            for identifier, json_patterns in serialized_patterns.items()
        }
        expected_mapping = {"default": ["*"], **mapping}
        self.assertEqual(expected_mapping, patterns)

    def test_set_queue_identifier_patterns_with_no_patterns(self) -> None:
        """It clears any existing patterns"""
        # Make sure there's something there to clear out
        mapping = {
            "default": ["something"],
            "not_three": ["one", "two*", "!three"],
            "five": ["four", "five"],
        }
        self.subject.set_queue_identifier_patterns(mapping)
        serialized_patterns = self.subject.get_queue_identifier_patterns()
        self.assertEqual(len(mapping), len(serialized_patterns))

        default_mapping: Dict[str, List[str]] = {"default": ["*"]}
        self.subject.set_queue_identifier_patterns({})
        remote_serialized_patterns: Dict[bytes, str] = self.database.hgetall(
            QUEUE_IDENTIFIER_PATTERNS_KEY
        )
        patterns = {
            identifier.decode("utf-8"): json.loads(json_patterns)
            for identifier, json_patterns in remote_serialized_patterns.items()
        }
        self.assertEqual(default_mapping, patterns)

    def test_get_queue_priority_patterns(self) -> None:
        """It fetches the expected queue identifier patterns"""
        given_queue_priorities = [
            QueuePriorityPattern(patterns=["*"], should_distribute_fairly=True),
        ]
        serialized_queue_priorities = [
            json.dumps(
                {
                    "fairly": queue_priority.should_distribute_fairly,
                    "pattern": queue_priority.patterns,
                }
            )
            for queue_priority in given_queue_priorities
        ]
        pipeline = self.database.pipeline()
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
        serialized_queue_priorities = self.database.lrange(
            QUEUE_PRIORITY_PATTERNS_KEY, 0, -1
        )
        queue_priorities = []
        for serialized_queue_priority in serialized_queue_priorities:
            queue_priority_data = json.loads(serialized_queue_priority)
            queue_priorities.append(
                QueuePriorityPattern(
                    patterns=queue_priority_data["pattern"],
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
