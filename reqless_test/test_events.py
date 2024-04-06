"""Tests about events"""

from typing import Dict, List

from reqless.abstract import AbstractJob
from reqless_test.common import TestReqless


class TestEvents(TestReqless):
    """Tests about events"""

    def setUp(self) -> None:
        TestReqless.setUp(self)
        self.client.queues["foo"].put("reqless_test.common.NoopJob", "{}", jid="jid")
        job = self.client.jobs["jid"]
        assert job is not None and isinstance(job, AbstractJob)
        job.track()

    def test_basic(self) -> None:
        """Ensure we can get a basic event"""

        count = 0

        def func(event: Dict) -> None:
            """No docstring"""
            nonlocal count
            count += 1

        self.client.events.on("popped", func)
        with self.client.events.thread():
            self.client.queues["foo"].pop()
        self.assertEqual(count, 1)

    def test_off(self) -> None:
        """Ensure we can turn off callbacks"""

        popped_count = 0

        def popped(event: Dict) -> None:
            """No docstring"""
            nonlocal popped_count
            popped_count += 1

        completed_count = 0

        def completed(event: Dict) -> None:
            """No docstring"""
            nonlocal completed_count
            completed_count += 1

        self.client.events.on("popped", popped)
        self.client.events.on("completed", completed)
        self.client.events.off("popped")
        with self.client.events.thread():
            job = self.client.queues["foo"].pop()
            assert job is not None and not isinstance(job, List)
            job.complete()
        self.assertEqual(popped_count, 0)
        self.assertEqual(completed_count, 1)

    def test_not_implemented(self) -> None:
        """Ensure missing events throw errors"""
        self.assertRaises(NotImplementedError, self.client.events.on, "foo", int)
