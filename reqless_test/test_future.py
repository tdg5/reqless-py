from threading import Thread

from reqless.future import Future
from reqless_test.test_helpers import wait_for_condition


def test_done_returns_false_when_not_done_and_true_when_done() -> None:
    subject = Future[bool]()
    assert not subject.done()
    subject.set_result(True)
    assert subject.done()


def test_result_blocks_until_done() -> None:
    expected_result = "expected result"

    subject = Future[str]()

    thread_is_waiting = False
    validated_result = False

    def wait_for_result() -> None:
        nonlocal expected_result
        nonlocal subject
        nonlocal thread_is_waiting
        nonlocal validated_result

        thread_is_waiting = True
        result = subject.result()
        assert result == expected_result
        validated_result = True

    thread = Thread(target=wait_for_result)
    thread.start()

    # Give the thread a chance to get started.
    wait_for_condition(lambda: thread_is_waiting)
    subject.set_result(expected_result)
    # Give the thread a chance to wrap up.
    wait_for_condition(lambda: validated_result)
    assert subject.done()


def test_set_result_makes_the_result_retrievable() -> None:
    subject = Future[bool]()
    assert not subject.done()
    subject.set_result(True)
    assert subject.done()
    assert subject.result()
