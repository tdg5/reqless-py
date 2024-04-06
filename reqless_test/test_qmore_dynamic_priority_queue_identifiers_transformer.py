import time
from typing import List

from qmore.client import QmoreClient, QueuePriorityPattern
from reqless.queue_resolvers.qmore_dynamic_priority_queue_identifiers_transformer import (  # noqa: E501
    QmoreDynamicPriorityQueueIdentifiersTransformer,
)
from reqless.queue_resolvers.transforming_queue_resolver import (
    TransformingQueueResolver,
)
from reqless_test.common import TestReqless


class TestQmoreDynamicPriorityQueueIdentifiersTransformer(TestReqless):
    def setUp(self) -> None:
        TestReqless.setUp(self)
        self.qmore_client = QmoreClient(redis=self.client.redis)
        # We use many queues to reduce the chances that we shuffle a list into
        # the same order.
        # Identifiers are [a1a, a2a, a3a, ... g1g, g2g, g3g]  # noqa: SC100
        self.queue_identifiers: List[str] = [
            f"{chr(97 + ascii_offset)}{index}{chr(97 + ascii_offset)}"
            for ascii_offset in range(7)
            for index in range(1, 4)
        ]
        self.ensure_queues_exist(self.queue_identifiers)

    def test_transform_places_default_queues_last_when_no_patterns_defined(
        self,
    ) -> None:
        """It should prioritize default queues last when no patterns defined"""
        subject = QmoreDynamicPriorityQueueIdentifiersTransformer(client=self.client)
        self.qmore_client.set_queue_priority_patterns([])
        transformed_queues = subject.transform(queue_identifiers=self.queue_identifiers)
        self.assertEqual(self.queue_identifiers, transformed_queues)

    def test_transform_places_default_queues_last_when_no_default_pattern(self) -> None:
        """It should prioritize default queues last when no default pattern"""
        subject = QmoreDynamicPriorityQueueIdentifiersTransformer(client=self.client)
        self.qmore_client.set_queue_priority_patterns(
            [
                QueuePriorityPattern(patterns=["g*"], should_distribute_fairly=False),
            ]
        )
        transformed_queues = subject.transform(queue_identifiers=self.queue_identifiers)
        expected_queues = self.queue_identifiers[-3:] + self.queue_identifiers[0:-3]
        self.assertEqual(expected_queues, transformed_queues)
        transformed_queues.sort()
        self.assertEqual(self.queue_identifiers, transformed_queues)

    def test_transform_default_unfairly(self) -> None:
        """It should handle default queues fairly"""
        subject = QmoreDynamicPriorityQueueIdentifiersTransformer(client=self.client)
        self.qmore_client.set_queue_priority_patterns(
            [
                QueuePriorityPattern(
                    patterns=["default"], should_distribute_fairly=False
                ),
            ]
        )
        transformed_queues = subject.transform(queue_identifiers=self.queue_identifiers)
        self.assertEqual(self.queue_identifiers, transformed_queues)

    def test_transform_default_fairly(self) -> None:
        """It should handle default queues fairly"""
        subject = QmoreDynamicPriorityQueueIdentifiersTransformer(client=self.client)
        self.qmore_client.set_queue_priority_patterns(
            [
                QueuePriorityPattern(
                    patterns=["default"], should_distribute_fairly=True
                ),
            ]
        )
        transformed_queues = subject.transform(queue_identifiers=self.queue_identifiers)

        self.assertNotEqual(self.queue_identifiers, transformed_queues)
        transformed_queues.sort()
        self.assertEqual(self.queue_identifiers, transformed_queues)

    def test_transform_inclusive_simple_patterns_unfairly(self) -> None:
        """It should handle simple patterns unfairly"""
        subject = QmoreDynamicPriorityQueueIdentifiersTransformer(client=self.client)
        self.qmore_client.set_queue_priority_patterns(
            [
                QueuePriorityPattern(
                    patterns=["g1g", "g2g", "g3g"], should_distribute_fairly=False
                ),
                QueuePriorityPattern(
                    patterns=["default"], should_distribute_fairly=False
                ),
                QueuePriorityPattern(
                    patterns=["a1a", "a2a", "a3a"], should_distribute_fairly=False
                ),
            ]
        )
        transformed_queues = subject.transform(queue_identifiers=self.queue_identifiers)

        expected_queues = (
            self.queue_identifiers[-3:]
            + self.queue_identifiers[3:-3]
            + self.queue_identifiers[0:3]
        )
        self.assertEqual(expected_queues, transformed_queues)
        transformed_queues.sort()
        self.assertEqual(self.queue_identifiers, transformed_queues)

    def test_transform_inclusive_wildcards_unfairly(self) -> None:
        """It should prioritize inclusive wildcard patterns unfairly"""
        subject = QmoreDynamicPriorityQueueIdentifiersTransformer(client=self.client)
        self.qmore_client.set_queue_priority_patterns(
            [
                QueuePriorityPattern(
                    patterns=["f*", "g*"], should_distribute_fairly=False
                ),
                QueuePriorityPattern(
                    patterns=["default"], should_distribute_fairly=False
                ),
            ]
        )
        transformed_queues = subject.transform(queue_identifiers=self.queue_identifiers)
        expected_queues = self.queue_identifiers[-6:] + self.queue_identifiers[0:-6]
        self.assertEqual(expected_queues, transformed_queues)
        transformed_queues.sort()
        self.assertEqual(self.queue_identifiers, transformed_queues)

    def test_transform_inclusive_wildcards_fairly(self) -> None:
        """It should prioritize inclusive wildcard patterns fairly"""
        subject = QmoreDynamicPriorityQueueIdentifiersTransformer(client=self.client)
        self.qmore_client.set_queue_priority_patterns(
            [
                QueuePriorityPattern(
                    patterns=["e*", "f*", "g*"], should_distribute_fairly=True
                ),
                QueuePriorityPattern(
                    patterns=["default"], should_distribute_fairly=False
                ),
            ]
        )
        transformed_queues = subject.transform(queue_identifiers=self.queue_identifiers)

        prioritized_queue_block = self.queue_identifiers[-9:]
        fairly_prioritized_queues = transformed_queues[0:9]
        self.assertNotEqual(prioritized_queue_block, fairly_prioritized_queues)
        fairly_prioritized_queues.sort()
        self.assertEqual(prioritized_queue_block, fairly_prioritized_queues)

        self.assertEqual(self.queue_identifiers[0:-9], transformed_queues[9:])

        transformed_queues.sort()
        self.assertEqual(self.queue_identifiers, transformed_queues)

    def test_transform_inclusive_double_ended_wildcards_unfairly(self) -> None:
        """It should prioritize inclusive double ended wildcard patterns unfairly"""
        subject = QmoreDynamicPriorityQueueIdentifiersTransformer(client=self.client)
        self.qmore_client.set_queue_priority_patterns(
            [
                QueuePriorityPattern(patterns=["*1*"], should_distribute_fairly=False),
                QueuePriorityPattern(
                    patterns=["default"], should_distribute_fairly=False
                ),
                QueuePriorityPattern(patterns=["*3*"], should_distribute_fairly=False),
            ]
        )
        transformed_queues = subject.transform(queue_identifiers=self.queue_identifiers)
        expected_queues = [
            f"{chr(97 + ascii_offset)}{index}{chr(97 + ascii_offset)}"
            for index in range(1, 4)
            for ascii_offset in range(7)
        ]
        self.assertEqual(expected_queues, transformed_queues)
        transformed_queues.sort()
        self.assertEqual(self.queue_identifiers, transformed_queues)

    def test_transform_exclusive_simple_patterns_unfairly(self) -> None:
        """It should handle simple patterns unfairly"""
        subject = QmoreDynamicPriorityQueueIdentifiersTransformer(client=self.client)
        self.qmore_client.set_queue_priority_patterns(
            [
                QueuePriorityPattern(
                    patterns=["*", "!a1a"], should_distribute_fairly=False
                ),
                QueuePriorityPattern(
                    patterns=["default"], should_distribute_fairly=False
                ),
            ]
        )
        transformed_queues = subject.transform(queue_identifiers=self.queue_identifiers)

        expected_queues = self.queue_identifiers[1:] + self.queue_identifiers[0:1]
        self.assertEqual(expected_queues, transformed_queues)
        transformed_queues.sort()
        self.assertEqual(self.queue_identifiers, transformed_queues)

    def test_transform_is_not_impacted_by_standalone_exclusive_patterns(self) -> None:
        """It should not be impacted by standalone exclusive patterns"""
        subject = QmoreDynamicPriorityQueueIdentifiersTransformer(client=self.client)
        self.qmore_client.set_queue_priority_patterns(
            [
                QueuePriorityPattern(patterns=["!a1a"], should_distribute_fairly=False),
                QueuePriorityPattern(
                    patterns=["default"], should_distribute_fairly=False
                ),
            ]
        )
        transformed_queues = subject.transform(queue_identifiers=self.queue_identifiers)
        self.assertEqual(self.queue_identifiers, transformed_queues)

    def test_transform_should_handle_no_queues_in_default_bucket(self) -> None:
        """It should be unaffected by there being no queues in the default bucket"""
        subject = QmoreDynamicPriorityQueueIdentifiersTransformer(client=self.client)
        self.qmore_client.set_queue_priority_patterns(
            [
                QueuePriorityPattern(patterns=["*"], should_distribute_fairly=False),
                QueuePriorityPattern(
                    patterns=["default"], should_distribute_fairly=False
                ),
            ]
        )
        transformed_queues = subject.transform(queue_identifiers=self.queue_identifiers)
        self.assertEqual(self.queue_identifiers, transformed_queues)

    def test_transform_exclusive_wildcard_unfairly(self) -> None:
        """It should handle exclusive wildcard patterns unfairly"""
        subject = QmoreDynamicPriorityQueueIdentifiersTransformer(client=self.client)
        self.qmore_client.set_queue_priority_patterns(
            [
                QueuePriorityPattern(
                    patterns=["*", "!a*"], should_distribute_fairly=False
                ),
                QueuePriorityPattern(
                    patterns=["default"], should_distribute_fairly=False
                ),
            ]
        )
        transformed_queues = subject.transform(queue_identifiers=self.queue_identifiers)
        expected_queues = self.queue_identifiers[3:] + self.queue_identifiers[0:3]
        self.assertEqual(expected_queues, transformed_queues)
        transformed_queues.sort()
        self.assertEqual(self.queue_identifiers, transformed_queues)

    def test_transform_evaluates_patterns_in_order(self) -> None:
        """It should allow later patterns to cancel out earlier patterns"""
        subject = QmoreDynamicPriorityQueueIdentifiersTransformer(client=self.client)
        self.qmore_client.set_queue_priority_patterns(
            [
                QueuePriorityPattern(
                    patterns=["a*", "!a*"], should_distribute_fairly=False
                ),
                QueuePriorityPattern(
                    patterns=["default"], should_distribute_fairly=False
                ),
            ]
        )
        transformed_queues = subject.transform(queue_identifiers=self.queue_identifiers)
        self.assertEqual(self.queue_identifiers, transformed_queues)

    def test_transform_does_not_repeat_queues(self) -> None:
        """It should not repeat a given queue in multiple priority buckets"""
        subject = QmoreDynamicPriorityQueueIdentifiersTransformer(client=self.client)
        self.qmore_client.set_queue_priority_patterns(
            [
                QueuePriorityPattern(patterns=["a1a"], should_distribute_fairly=False),
                QueuePriorityPattern(
                    patterns=["default"], should_distribute_fairly=False
                ),
                QueuePriorityPattern(patterns=["a1a"], should_distribute_fairly=False),
            ]
        )
        transformed_queues = subject.transform(queue_identifiers=self.queue_identifiers)
        self.assertEqual(self.queue_identifiers, transformed_queues)

    def test_get_dynamic_queue_priorities_caches_priorities_for_some_duration(
        self,
    ) -> None:
        """get dynamic queue priorities caches the priorities for some duration"""
        refresh_frequency = 500
        subject = QmoreDynamicPriorityQueueIdentifiersTransformer(
            client=self.client,
            dynamic_queue_priorities_refresh_frequency_milliseconds=refresh_frequency,
        )
        self.qmore_client.set_queue_priority_patterns([])
        priorities = subject._get_dynamic_queue_priorities()
        self.assertEqual([], priorities)

        self.qmore_client.set_queue_priority_patterns(
            [
                QueuePriorityPattern(
                    patterns=["default"], should_distribute_fairly=False
                ),
            ]
        )
        priorities = subject._get_dynamic_queue_priorities()
        self.assertEqual([], priorities)

        time.sleep(refresh_frequency / 1000.0)

        priorities = subject._get_dynamic_queue_priorities()
        self.assertEqual(1, len(priorities))
        self.assertEqual(["default"], priorities[0].patterns)
        self.assertFalse(priorities[0].should_distribute_fairly)

    def test_with_transforming_queue_resolver(self) -> None:
        """It works with TransformingQueueResolver"""
        subject = QmoreDynamicPriorityQueueIdentifiersTransformer(client=self.client)
        self.qmore_client.set_queue_priority_patterns(
            [
                QueuePriorityPattern(patterns=["*1*"], should_distribute_fairly=False),
                QueuePriorityPattern(
                    patterns=["default"], should_distribute_fairly=False
                ),
                QueuePriorityPattern(patterns=["*3*"], should_distribute_fairly=False),
            ]
        )
        subject = QmoreDynamicPriorityQueueIdentifiersTransformer(client=self.client)
        queue_resolver = TransformingQueueResolver(
            queue_identifiers=self.queue_identifiers,
            transformers=[subject],
        )

        transformed_queues = queue_resolver.resolve()
        expected_queues = [
            f"{chr(97 + ascii_offset)}{index}{chr(97 + ascii_offset)}"
            for index in range(1, 4)
            for ascii_offset in range(7)
        ]
        self.assertEqual(expected_queues, transformed_queues)
        transformed_queues.sort()
        self.assertEqual(self.queue_identifiers, transformed_queues)
