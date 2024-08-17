import time
from typing import Callable


def wait_for_condition(
    condition: Callable[[], bool],
    wait_time_between_checks_seconds: float = 0.1,
    attempt_count: int = 25,
) -> None:
    attempts = 0
    condition_result = False

    while not (condition_result := condition()) and attempts < attempt_count:
        attempts += 1
        time.sleep(wait_time_between_checks_seconds)

    assert condition_result, "Condition was not met after {attempt_count} attempts."
