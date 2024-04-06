"""Basic tests of TransformingQueueResolver class"""

from typing import List

from reqless.abstract import AbstractQueueIdentifiersTransformer
from reqless.queue_resolvers.transforming_queue_resolver import (
    TransformingQueueResolver,
)
from reqless_test.common import TestReqless


class OrderReversingQueueIdentifiersTransformer(AbstractQueueIdentifiersTransformer):
    def transform(self, queue_identifiers: List[str]) -> List[str]:
        _queue_identifiers = list(queue_identifiers)
        _queue_identifiers.reverse()
        return _queue_identifiers


class TestTransformingQueueResolver(TestReqless):
    def test_resolve_with_no_transformers(self) -> None:
        """It returns the given queue identifiers when no transformers"""
        given_queue_names = ["one", "two", "three"]
        queue_names = TransformingQueueResolver(
            queue_identifiers=given_queue_names,
        ).resolve()
        self.assertEqual(given_queue_names, queue_names)

    def test_resolve_with_a_transformer(self) -> None:
        """It returns the tranformed queue identifiers when given transformers"""
        given_queue_names = ["one", "two", "three"]
        queue_names = TransformingQueueResolver(
            queue_identifiers=given_queue_names,
            transformers=[
                OrderReversingQueueIdentifiersTransformer(),
            ],
        ).resolve()
        expected_queue_names = list(given_queue_names)
        expected_queue_names.reverse()
        self.assertEqual(expected_queue_names, queue_names)
