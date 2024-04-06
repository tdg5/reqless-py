import re
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from qmore.client import QmoreClient
from reqless import Client
from reqless.abstract import AbstractQueueIdentifiersTransformer


class QmoreDynamicMappingQueueIdentifiersTransformer(
    AbstractQueueIdentifiersTransformer
):
    def __init__(
        self,
        client: Client,
        dynamic_queue_mapping_refresh_frequency_milliseconds: Optional[int] = None,
    ):
        self.reqless_client: Client = client
        self.qmore_client: QmoreClient = QmoreClient(redis=self.reqless_client.redis)

        self._dynamic_queue_mapping: Optional[Dict[str, List[str]]] = None
        self._dynamic_queue_mapping_ttl_time_delta: timedelta = timedelta(
            milliseconds=(
                dynamic_queue_mapping_refresh_frequency_milliseconds or 5 * 60 * 1000
            ),
        )
        self._dynamic_queue_mapping_expires_at: datetime = datetime.now(tz=timezone.utc)

    def _get_dynamic_queue_mapping(self) -> Dict[str, List[str]]:
        if (
            self._dynamic_queue_mapping is None
            or self._dynamic_queue_mapping_expires_at <= datetime.now(tz=timezone.utc)
        ):
            self._dynamic_queue_mapping = (
                self.qmore_client.get_queue_identifier_patterns()
            )
            self._dynamic_queue_mapping_expires_at = (
                datetime.now(tz=timezone.utc)
                + self._dynamic_queue_mapping_ttl_time_delta
            )
        return self._dynamic_queue_mapping

    @staticmethod
    def resolve_queue_names(
        dynamic_queue_mapping: Dict[str, List[str]],
        known_queue_names: List[str],
        patterns: List[str],
    ) -> List[str]:
        # First, resolve dynamic identifiers to patterns, negating where appropriate
        expanded_patterns: List[str] = []
        for queue_pattern in patterns:
            negated = queue_pattern.startswith("!")
            _queue_pattern = queue_pattern[1:] if negated else queue_pattern
            if _queue_pattern.startswith("@"):
                dynamic_patterns = dynamic_queue_mapping.get(_queue_pattern[1:], [])
                for pattern in dynamic_patterns:
                    if negated:
                        _pattern = (
                            pattern[1:] if pattern.startswith("!") else f"!{pattern}"
                        )
                    else:
                        _pattern = pattern
                    expanded_patterns.append(_pattern)
            else:
                expanded_patterns.append(queue_pattern)

        # Next, resolve patterns to actual queue names
        matched_queues: List[str] = []
        for pattern in expanded_patterns:
            is_static_pattern = "!" not in pattern and "*" not in pattern
            # Always include static queue names even if the queue doesn't exist
            if is_static_pattern and pattern not in matched_queues:
                matched_queues.append(pattern)
                continue

            negated = pattern.startswith("!")
            pattern_without_negate = pattern[1:] if negated else pattern
            regex = re.compile(pattern_without_negate.replace("*", ".*"))
            for known_queue_name in known_queue_names:
                if regex.fullmatch(known_queue_name):
                    if negated:
                        matched_queues.remove(known_queue_name)
                    else:
                        # Only add queue name if it hasn't been added already
                        # In this way, a given match will maintain its earliest
                        # position unless fully removed
                        if known_queue_name not in matched_queues:
                            matched_queues.append(known_queue_name)

        return matched_queues

    def transform(self, queue_identifiers: List[str]) -> List[str]:
        return QmoreDynamicMappingQueueIdentifiersTransformer.resolve_queue_names(
            dynamic_queue_mapping=self._get_dynamic_queue_mapping(),
            known_queue_names=[
                count["name"] for count in self.reqless_client.queues.counts
            ],
            patterns=queue_identifiers,
        )
