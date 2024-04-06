import re
from datetime import datetime, timedelta, timezone
from random import SystemRandom
from typing import List, Optional

from qmore.client import QmoreClient, QueuePriorityPattern
from reqless import Client
from reqless.abstract import AbstractQueueIdentifiersTransformer


class QmoreDynamicPriorityQueueIdentifiersTransformer(
    AbstractQueueIdentifiersTransformer
):
    def __init__(
        self,
        client: Client,
        dynamic_queue_priorities_refresh_frequency_milliseconds: Optional[int] = None,
    ):
        self.reqless_client: Client = client
        self.qmore_client: QmoreClient = QmoreClient(redis=self.reqless_client.redis)

        self._dynamic_queue_priorities: Optional[List[QueuePriorityPattern]] = None
        self._dynamic_queue_priorities_ttl_time_delta: timedelta = timedelta(
            milliseconds=(
                dynamic_queue_priorities_refresh_frequency_milliseconds or 5 * 60 * 1000
            ),
        )
        self._dynamic_queue_priorities_expires_at: datetime = datetime.now(
            tz=timezone.utc
        )

    def _get_dynamic_queue_priorities(self) -> List[QueuePriorityPattern]:
        if (
            self._dynamic_queue_priorities is None
            or self._dynamic_queue_priorities_expires_at
            <= datetime.now(tz=timezone.utc)
        ):
            self._dynamic_queue_priorities = (
                self.qmore_client.get_queue_priority_patterns()
            )
            self._dynamic_queue_priorities_expires_at = (
                datetime.now(tz=timezone.utc)
                + self._dynamic_queue_priorities_ttl_time_delta
            )
        return self._dynamic_queue_priorities

    @staticmethod
    def prioritize_queues(
        queue_identifiers: List[str],
        queue_priority_patterns: List[QueuePriorityPattern],
    ) -> List[str]:
        rand = SystemRandom()
        prioritized_queue_groups: List[List[str]] = []
        _queue_identifiers = list(queue_identifiers)

        default_index = -1
        default_should_distribute_fairly = False

        for queue_priority_pattern in queue_priority_patterns:
            if queue_priority_pattern.patterns == ["default"]:
                default_index = len(prioritized_queue_groups)
                default_should_distribute_fairly = (
                    queue_priority_pattern.should_distribute_fairly
                )
                continue

            priority_group_queues: List[str] = []
            for pattern in queue_priority_pattern.patterns:
                negated = pattern.startswith("!")
                _pattern = pattern[1:] if negated else pattern
                regex = re.compile(_pattern.replace("*", ".*"))

                if negated:
                    queues_to_remove = []
                    for queue in priority_group_queues:
                        if regex.fullmatch(queue):
                            queues_to_remove.append(queue)
                    for queue in queues_to_remove:
                        priority_group_queues.remove(queue)
                else:
                    for queue in _queue_identifiers:
                        if (
                            regex.fullmatch(queue)
                            and queue not in priority_group_queues
                        ):
                            priority_group_queues.append(queue)

            # Remove matched queues from remaining queue identifiers
            for queue_identifier in priority_group_queues:
                _queue_identifiers.remove(queue_identifier)

            if queue_priority_pattern.should_distribute_fairly:
                rand.shuffle(priority_group_queues)

            prioritized_queue_groups.append(priority_group_queues)

        # insert remaining queues at the position of the default item (or at the end)
        if default_should_distribute_fairly:
            rand.shuffle(_queue_identifiers)

        _default_index = (
            default_index if default_index != -1 else len(prioritized_queue_groups)
        )
        prioritized_queue_groups.insert(_default_index, _queue_identifiers)

        prioritized_queues = []
        for prioritized_queue_group in prioritized_queue_groups:
            prioritized_queues.extend(prioritized_queue_group)
        return prioritized_queues

    def transform(self, queue_identifiers: List[str]) -> List[str]:
        return QmoreDynamicPriorityQueueIdentifiersTransformer.prioritize_queues(
            queue_identifiers=queue_identifiers,
            queue_priority_patterns=self._get_dynamic_queue_priorities(),
        )
