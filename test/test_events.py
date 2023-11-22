"""Tests about events"""

from common import TestQless


class TestEvents(TestQless):
    """Tests about events"""

    def setUp(self):
        TestQless.setUp(self)
        self.client.queues["foo"].put("Foo", {}, jid="jid")
        self.client.jobs["jid"].track()

    def test_basic(self):
        """Ensure we can get a basic event"""

        count = 0

        def func(_):
            """No docstring"""
            nonlocal count
            count += 1

        self.client.events.on("popped", func)
        with self.client.events.thread():
            self.client.queues["foo"].pop()
        self.assertEqual(count, 1)

    def test_off(self):
        """Ensure we can turn off callbacks"""

        popped_count = 0

        def popped(_):
            """No docstring"""
            nonlocal popped_count
            popped_count += 1

        completed_count = 0

        def completed(_):
            """No docstring"""
            nonlocal completed_count
            completed_count += 1

        self.client.events.on("popped", popped)
        self.client.events.on("completed", completed)
        self.client.events.off("popped")
        with self.client.events.thread():
            self.client.queues["foo"].pop().complete()
        self.assertEqual(popped_count, 0)
        self.assertEqual(completed_count, 1)

    def test_not_implemented(self):
        """Ensure missing events throw errors"""
        self.assertRaises(NotImplementedError, self.client.events.on, "foo", int)
