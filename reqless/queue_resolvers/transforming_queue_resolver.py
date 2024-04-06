from typing import List, Optional

from reqless.abstract import AbstractQueueIdentifiersTransformer, AbstractQueueResolver


class TransformingQueueResolver(AbstractQueueResolver):
    def __init__(
        self,
        queue_identifiers: List[str],
        transformers: Optional[List[AbstractQueueIdentifiersTransformer]] = None,
    ):
        self._queue_identifiers: List[str] = queue_identifiers
        self._transformers: Optional[List[AbstractQueueIdentifiersTransformer]] = (
            transformers
        )

    def resolve(self) -> List[str]:
        if not self._transformers:
            return self._queue_identifiers

        resolved_identifiers = self._queue_identifiers
        for transformer in self._transformers:
            resolved_identifiers = transformer.transform(resolved_identifiers)

        return resolved_identifiers
