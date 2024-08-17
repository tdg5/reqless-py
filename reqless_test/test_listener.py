from threading import Thread
from typing import Dict

from reqless.abstract import AbstractJob
from reqless.listener import Listener
from reqless_test.common import TestReqless
from reqless_test.test_helpers import wait_for_condition


class TestListener(TestReqless):
    def setUp(self) -> None:
        super().setUp()
        self.client.queues["foo"].put("reqless_test.common.NoopJob", "{}", jid="jid")
        job = self.client.jobs["jid"]
        assert job is not None and isinstance(job, AbstractJob)
        job.track()

    def test_wait_until_listening_waits_for_listening(self) -> None:
        thread_is_waiting = False
        thread_is_done_waiting = False
        listener = Listener(channels=["ql:popped"], database=self.client.database)

        def wait_until_listening() -> None:
            nonlocal listener
            nonlocal thread_is_waiting
            nonlocal thread_is_done_waiting

            thread_is_waiting = True
            listener.wait_until_listening()
            thread_is_done_waiting = True

        def listen() -> None:
            for message in listener.listen():
                break

        waiter_thread = Thread(target=wait_until_listening)
        waiter_thread.start()

        # Give the thread a chance to get started
        wait_for_condition(lambda: thread_is_waiting)

        assert thread_is_waiting
        assert not thread_is_done_waiting

        listener_thread = Thread(target=listen)
        listener_thread.start()

        listener.wait_until_listening()
        listener.unlisten()

    def test_basic(self) -> None:
        """Ensure we can get a basic message"""

        count = 0

        def on_popped(message: Dict) -> None:
            nonlocal count
            count += 1
            self.assertEqual("ql:popped", message["channel"])
            self.assertEqual("message", message["type"])
            self.assertEqual("jid", message["data"])

        listener = Listener(channels=["ql:popped"], database=self.client.database)

        def publish() -> None:
            for message in listener.listen():
                on_popped(message)

        thread = Thread(target=publish)
        thread.start()
        # Wait for listening to begin so we don't unlisten too soon.
        listener.wait_until_listening()
        self.client.queues["foo"].pop()

        listener.unlisten()
        thread.join()
        self.assertEqual(count, 1)
