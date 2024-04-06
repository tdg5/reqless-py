import time
from typing import Dict, List
from uuid import uuid4

from qmore.client import QmoreClient
from reqless.queue_resolvers.qmore_dynamic_mapping_queue_identifiers_transformer import (  # noqa: E501
    QmoreDynamicMappingQueueIdentifiersTransformer,
)
from reqless.queue_resolvers.transforming_queue_resolver import (
    TransformingQueueResolver,
)
from reqless_test.common import TestReqless


class TestQmoreDynamicMappingQueueIdentifiersTransformer(TestReqless):
    def setUp(self) -> None:
        TestReqless.setUp(self)
        self.qmore_client = QmoreClient(redis=self.client.redis)

    def set_dynamic_queues(self, mapping: Dict[str, List[str]]) -> None:
        self.qmore_client.set_queue_identifier_patterns(mapping)

    def collect_queue_names(
        self,
        dynamic_queue_mapping: Dict[str, List[str]],
        known_queue_names: List[str],
        patterns: List[str],
    ) -> List[str]:
        subject = QmoreDynamicMappingQueueIdentifiersTransformer(client=self.client)
        if known_queue_names:
            self.ensure_queues_exist(known_queue_names)
        self.set_dynamic_queues(dynamic_queue_mapping)
        return subject.transform(queue_identifiers=patterns)

    def test_resolve_queue_names_exact_match(self) -> None:
        """It includes queue names by exact match"""
        patterns = ["exact_queue_name"]
        known_queue_names = ["exact_queue_name", "exact_queue_name_extended"]
        self.assertEqual(
            ["exact_queue_name"],
            self.collect_queue_names(
                dynamic_queue_mapping={},
                known_queue_names=known_queue_names,
                patterns=patterns,
            ),
        )

    def test_resolve_queue_names_exact_match_negated(self) -> None:
        """It excludes queue names by negated exact match"""
        patterns = ["*", "!exact_queue_name_extended"]
        known_queue_names = ["exact_queue_name", "exact_queue_name_extended"]
        self.assertEqual(
            ["exact_queue_name"],
            self.collect_queue_names(
                dynamic_queue_mapping={},
                known_queue_names=known_queue_names,
                patterns=patterns,
            ),
        )

    def test_resolve_queue_names_wildcard_match(self) -> None:
        """It includes queue names by wildcard"""
        known_queue_names = [
            "exact_queue_name",
            "exact_queue_name_extended",
            "other_queue_name",
        ]
        self.assertEqual(
            ["exact_queue_name", "exact_queue_name_extended"],
            self.collect_queue_names(
                dynamic_queue_mapping={},
                known_queue_names=known_queue_names,
                patterns=["exact*"],
            ),
        )
        self.assertEqual(
            known_queue_names,
            self.collect_queue_names(
                dynamic_queue_mapping={},
                known_queue_names=known_queue_names,
                patterns=["*"],
            ),
        )

    def test_resolve_queue_names_wildcard_match_negated(self) -> None:
        """It excludes queue names by negated wildcard"""
        known_queue_names = [
            "exact_queue_name",
            "exact_queue_name_extended",
            "other_queue_name",
        ]
        self.assertEqual(
            ["other_queue_name"],
            self.collect_queue_names(
                dynamic_queue_mapping={},
                known_queue_names=known_queue_names,
                patterns=["*", "!exact*"],
            ),
        )
        self.assertEqual(
            [],
            self.collect_queue_names(
                dynamic_queue_mapping={},
                known_queue_names=known_queue_names,
                patterns=["*", "!*"],
            ),
        )

    def test_resolve_queue_names_dynamic_with_exact_match(self) -> None:
        """It includes queue names from dynamic queues by identifier"""
        patterns = ["@exact", "other_queue_name"]
        known_queue_names = [
            "exact_queue_name",
            "exact_queue_name_extended",
            "other_queue_name",
        ]
        dynamic_queue_mapping = {"exact": ["exact_queue_name"]}
        self.assertEqual(
            ["exact_queue_name", "other_queue_name"],
            self.collect_queue_names(
                dynamic_queue_mapping=dynamic_queue_mapping,
                known_queue_names=known_queue_names,
                patterns=patterns,
            ),
        )

    def test_resolve_queue_names_dynamic_with_exact_match_negated(self) -> None:
        """It excludes queue names from dynamic queues by negated identifier"""
        patterns = ["exact*", "@exact"]
        known_queue_names = [
            "exact_queue_name",
            "exact_queue_name_extended",
            "other_queue_name",
        ]
        dynamic_queue_mapping = {"exact": ["!exact_queue_name_extended"]}
        self.assertEqual(
            ["exact_queue_name"],
            self.collect_queue_names(
                dynamic_queue_mapping=dynamic_queue_mapping,
                known_queue_names=known_queue_names,
                patterns=patterns,
            ),
        )

    def test_resolve_queue_names_dynamic_with_wildcard_match(self) -> None:
        """It includes queue names from dynamic queues by wildcard"""
        patterns = ["@exact"]
        known_queue_names = [
            "exact_queue_name",
            "exact_queue_name_extended",
            "other_queue_name",
        ]
        dynamic_queue_mapping = {"exact": ["exact*"]}
        self.assertEqual(
            ["exact_queue_name", "exact_queue_name_extended"],
            self.collect_queue_names(
                dynamic_queue_mapping=dynamic_queue_mapping,
                known_queue_names=known_queue_names,
                patterns=patterns,
            ),
        )

    def test_resolve_queue_names_dynamic_with_wildcard_match_negated(self) -> None:
        """It excludes queue names from dynamic queues by negated wildcard"""
        patterns = ["*", "@exact"]
        known_queue_names = [
            "exact_queue_name",
            "exact_queue_name_extended",
            "other_queue_name",
        ]
        dynamic_queue_mapping = {"exact": ["!exact*"]}
        self.assertEqual(
            ["other_queue_name"],
            self.collect_queue_names(
                dynamic_queue_mapping=dynamic_queue_mapping,
                known_queue_names=known_queue_names,
                patterns=patterns,
            ),
        )

    def test_resolve_queue_names_dynamic_negated_with_exact_match(self) -> None:
        """It excludes queue names from negated dynamic queues by exact match"""
        patterns = ["*", "!@exact"]
        known_queue_names = [
            "exact_queue_name",
            "exact_queue_name_extended",
            "other_queue_name",
        ]
        dynamic_queue_mapping = {"exact": ["exact_queue_name_extended"]}
        self.assertEqual(
            ["exact_queue_name", "other_queue_name"],
            self.collect_queue_names(
                dynamic_queue_mapping=dynamic_queue_mapping,
                known_queue_names=known_queue_names,
                patterns=patterns,
            ),
        )

    def test_resolve_queue_names_dynamic_negated_with_exact_match_negated(self) -> None:
        """It includes queue names from negated dynamic queues by exact match"""
        patterns = ["!@exact"]
        known_queue_names = [
            "exact_queue_name",
            "exact_queue_name_extended",
            "other_queue_name",
        ]
        dynamic_queue_mapping = {"exact": ["!exact_queue_name"]}
        self.assertEqual(
            ["exact_queue_name"],
            self.collect_queue_names(
                dynamic_queue_mapping=dynamic_queue_mapping,
                known_queue_names=known_queue_names,
                patterns=patterns,
            ),
        )

    def test_resolve_queue_names_dynamic_negated_with_wildcard_match(self) -> None:
        """It excludes queue names from negated dynamic queues by wildcard"""
        patterns = ["*", "!@exact"]
        known_queue_names = [
            "exact_queue_name",
            "exact_queue_name_extended",
            "other_queue_name",
        ]
        dynamic_queue_mapping = {"exact": ["exact*"]}
        self.assertEqual(
            ["other_queue_name"],
            self.collect_queue_names(
                dynamic_queue_mapping=dynamic_queue_mapping,
                known_queue_names=known_queue_names,
                patterns=patterns,
            ),
        )

    def test_resolve_queue_names_dynamic_negated_with_wildcard_match_negated(
        self,
    ) -> None:
        """It includes queue names from negated dynamic queues by wildcard"""
        patterns = ["!@exact"]
        known_queue_names = [
            "exact_queue_name",
            "exact_queue_name_extended",
            "other_queue_name",
        ]
        dynamic_queue_mapping = {"exact": ["!exact*"]}
        self.assertEqual(
            ["exact_queue_name", "exact_queue_name_extended"],
            self.collect_queue_names(
                dynamic_queue_mapping=dynamic_queue_mapping,
                known_queue_names=known_queue_names,
                patterns=patterns,
            ),
        )

    def test_resolve_queue_names_a_little_bit_of_everything(self) -> None:
        """It includes queue names when using a mix of strategies"""
        patterns = [
            "*",
            "!@exact",
            "!@inexact",
            "!exact_queue_name_extended",
            "@other",
            "!no*",
        ]
        known_queue_names = [
            "exact_queue_name",
            "exact_queue_name_extended",
            "no_match_queue_name",
            "other_queue_name",
        ]
        dynamic_queue_mapping = {
            "exact": ["exact*"],
            "inexact": ["!exact*"],
            "other": ["other*"],
        }
        self.assertEqual(
            ["other_queue_name", "exact_queue_name"],
            self.collect_queue_names(
                dynamic_queue_mapping=dynamic_queue_mapping,
                known_queue_names=known_queue_names,
                patterns=patterns,
            ),
        )

    def test_resolve_queue_names_allows_no_duplicates(self) -> None:
        """It does not return the same queue name multiple times"""
        patterns = [
            "exact_queue_name",
            "@exact",
            "!@exact",
            "exact*",
            "!other*",
            "!exact_queue_name_extended",
        ]
        known_queue_names = ["exact_queue_name", "exact_queue_name_extended"]
        self.assertEqual(
            ["exact_queue_name"],
            self.collect_queue_names(
                dynamic_queue_mapping={
                    "exact": ["exact_queue_name"],
                    "inexact": ["!exact_queue_name"],
                },
                known_queue_names=known_queue_names,
                patterns=patterns,
            ),
        )

    def test_get_dynamic_queue_mapping_handles_no_defined_mapping(self) -> None:
        """It tolerates when no dynamic queue mapping is defined"""
        subject = QmoreDynamicMappingQueueIdentifiersTransformer(client=self.client)
        mapping = subject._get_dynamic_queue_mapping()
        self.assertEqual({"default": "*"}, mapping)

    def test_get_dynamic_queue_mapping_returns_expected_mapping(self) -> None:
        """It fetches and returns the expected dynamic queue mapping"""
        default_mapping = ["*"]
        other_mapping = ["one", "two*", "th*ree", "four"]
        self.set_dynamic_queues({"default": default_mapping, "other": other_mapping})
        subject = QmoreDynamicMappingQueueIdentifiersTransformer(client=self.client)
        mapping = subject._get_dynamic_queue_mapping()
        self.assertEqual(default_mapping, mapping["default"])
        self.assertEqual(other_mapping, mapping["other"])

    def test_get_dynamic_queue_mapping_caches_mapping_for_some_duration(self) -> None:
        """It caches the dynamic queue mapping for the configured duration"""
        refresh_frequency = 500
        subject = QmoreDynamicMappingQueueIdentifiersTransformer(
            client=self.client,
            dynamic_queue_mapping_refresh_frequency_milliseconds=refresh_frequency,
        )
        mapping = subject._get_dynamic_queue_mapping()
        self.assertEqual({"default": "*"}, mapping)

        default_mapping = ["ignore"]
        other_mapping = ["one", "two*", "th*ree", "four"]
        self.set_dynamic_queues({"default": default_mapping, "other": other_mapping})
        mapping = subject._get_dynamic_queue_mapping()
        self.assertEqual({"default": "*"}, mapping)

        time.sleep(refresh_frequency / 1000.0)

        mapping = subject._get_dynamic_queue_mapping()
        self.assertEqual(
            {"default": default_mapping, "other": other_mapping},
            mapping,
        )

    def test_with_transforming_queue_resolver(self) -> None:
        """It works with TransformingQueueResolver"""
        default_mapping = ["*"]
        other_mapping = ["one", "two*", "th*ree", "four"]
        expected_queue_names = [
            "ten",
            "two",
            "tweleve",
            "eleven",
            "one",
            "thirty-three",
            "four",
        ]
        self.set_dynamic_queues({"default": default_mapping, "other": other_mapping})
        self.ensure_queues_exist(expected_queue_names)

        patterns = ["ten", "tw*", "eleven", "tweleve", "@no_exist", "@other", "!skip"]
        subject = QmoreDynamicMappingQueueIdentifiersTransformer(client=self.client)
        queue_resolver = TransformingQueueResolver(
            queue_identifiers=patterns,
            transformers=[subject],
        )

        queue_names = queue_resolver.resolve()
        self.assertEqual(expected_queue_names, queue_names)

    def test_static_queue_names_are_enumerated_even_if_they_do_not_yet_exist(
        self,
    ) -> None:
        """It includes static queue names when the queues don't exist"""
        patterns = [f"unique-queue-name-{uuid4()}"]
        self.assertEqual(
            patterns,
            self.collect_queue_names(
                dynamic_queue_mapping={},
                known_queue_names=[],
                patterns=patterns,
            ),
        )
