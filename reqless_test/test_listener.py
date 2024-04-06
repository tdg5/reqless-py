import time
from threading import Thread
from typing import Dict

from reqless.abstract import AbstractJob
from reqless.listener import Listener
from reqless_test.common import TestReqless


class TestListener(TestReqless):
    def setUp(self) -> None:
        super().setUp()
        self.client.queues["foo"].put("reqless_test.common.NoopJob", "{}", jid="jid")
        job = self.client.jobs["jid"]
        assert job is not None and isinstance(job, AbstractJob)
        job.track()

    def test_basic(self) -> None:
        """Ensure we can get a basic message"""

        count = 0

        def func(message: Dict) -> None:
            nonlocal count
            count += 1
            self.assertEqual("ql:popped", message["channel"])
            self.assertEqual("message", message["type"])
            self.assertEqual("jid", message["data"])

        listener = Listener(channels=["ql:popped"], redis=self.client.redis)

        def publish() -> None:
            for message in listener.listen():
                func(message)

        thread = Thread(target=publish)
        thread.start()
        self.client.queues["foo"].pop()

        # Give the thread a second to process the message
        attempts = 0
        while count == 0 and attempts < 10:
            attempts += 1
            time.sleep(0.1)
        listener.unlisten()
        thread.join()
        self.assertEqual(count, 1)
