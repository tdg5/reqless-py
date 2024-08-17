"""Minimal wrapper around concurrent.futures.Future since custom use of
concurrent.futures.Future is discouraged."""

from concurrent.futures import Future as _Future
from typing import Generic, Optional, TypeVar, cast


T = TypeVar("T")


class Future(Generic[T]):
    def __init__(self) -> None:
        self._future: _Future = _Future()

    def done(self) -> bool:
        """Check if the future is complete."""
        return self._future.done()

    def result(self, timeout: Optional[float] = None) -> T:
        """Fetch the result of the future if it is ready, otherwise wait for
        the result."""
        return cast(T, self._future.result(timeout=timeout))

    def set_result(self, result: T) -> None:
        """Set the result of the future."""
        self._future.set_result(result)
