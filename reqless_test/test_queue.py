"""Basic tests about the Job class"""

from typing import List

from reqless_test.common import TestReqless


class TestQueue(TestReqless):
    """Test the Job class"""

    def test_jobs(self) -> None:
        """The queue.Jobs class provides access to job counts"""
        queue = self.client.queues["foo"]
        queue.put("reqless_test.common.NoopJob", "{}")
        self.assertEqual(queue.jobs.depends(), [])
        self.assertEqual(queue.jobs.running(), [])
        self.assertEqual(queue.jobs.stalled(), [])
        self.assertEqual(queue.jobs.scheduled(), [])
        self.assertEqual(queue.jobs.recurring(), [])

    def test_counts(self) -> None:
        """Provides access to job counts"""
        self.client.queues["foo"].put("reqless_test.common.NoopJob", "{}")
        self.assertEqual(
            self.client.queues["foo"].counts,
            {
                "depends": 0,
                "name": "foo",
                "paused": False,
                "recurring": 0,
                "running": 0,
                "scheduled": 0,
                "stalled": 0,
                "throttled": 0,
                "waiting": 1,
            },
        )

    def test_pause(self) -> None:
        """Pause/Unpause Queue"""
        queue = self.client.queues["foo"]

        queue.pause()
        self.assertTrue(queue.counts["paused"])

        queue.unpause()
        self.assertFalse(queue.counts["paused"])

    def test_heartbeat(self) -> None:
        """Provided access to heartbeat configuration"""
        original = self.client.queues["foo"].heartbeat
        self.client.queues["foo"].heartbeat = 10
        self.assertNotEqual(original, self.client.queues["foo"].heartbeat)

    def test_attribute_error(self) -> None:
        """Raises an attribute error if there is no attribute"""
        self.assertRaises(
            AttributeError,
            lambda: self.client.queues["foo"].foo,  # type: ignore[attr-defined]
        )

    def test_multipop(self) -> None:
        """Exposes multi-pop"""
        self.client.queues["foo"].put("reqless_test.common.NoopJob", "{}")
        self.client.queues["foo"].put("reqless_test.common.NoopJob", "{}")
        jobs = self.client.queues["foo"].pop(10)
        assert isinstance(jobs, List)
        self.assertEqual(len(jobs), 2)

    def test_peek(self) -> None:
        """Exposes queue peeking"""
        self.client.queues["foo"].put("reqless_test.common.NoopJob", "{}", jid="jid")
        job = self.client.queues["foo"].peek()
        assert job is not None and not isinstance(job, List)
        self.assertEqual(job.jid, "jid")

    def test_multipeek(self) -> None:
        """Exposes multi-peek"""
        self.client.queues["foo"].put("reqless_test.common.NoopJob", "{}")
        self.client.queues["foo"].put("reqless_test.common.NoopJob", "{}")
        jobs = self.client.queues["foo"].peek(10)
        assert isinstance(jobs, List)
        self.assertEqual(len(jobs), 2)

    def test_stats(self) -> None:
        """Exposes stats"""
        self.client.queues["foo"].stats()

    def test_len(self) -> None:
        """Exposes the length of a queue"""
        self.client.queues["foo"].put("reqless_test.common.NoopJob", "{}")
        self.assertEqual(len(self.client.queues["foo"]), 1)

    def test_throttle(self) -> None:
        """Exposes the queue's throttle"""
        queue_name = "foo"
        queue = self.client.queues[queue_name]
        throttle = queue.throttle
        self.assertEqual(throttle.name, f"ql:q:{queue_name}")

    def test_put_with_throttles(self) -> None:
        """Test put with throttles given"""
        queue = self.client.queues["foo"]
        queue.put(
            "reqless_test.common.NoopJob", "{}", jid="jid", throttles=["throttle"]
        )
        job = self.client.jobs["jid"]
        assert job is not None
        queue_throttle = queue.throttle.name
        self.assertEqual(job.throttles, ["throttle", queue_throttle])

    def test_requeue_with_throttles(self) -> None:
        """Test requeue with throttles given"""
        queue = self.client.queues["foo"]
        queue.put(
            "reqless_test.common.NoopJob", "{}", jid="jid", throttles=["throttle"]
        )
        job_to_fail = queue.pop()
        assert job_to_fail is not None and not isinstance(job_to_fail, List)
        job_to_fail.fail("foo", "bar")

        queue.requeue(
            "reqless_test.common.NoopJob", "{}", jid="jid", throttles=["other-throttle"]
        )
        job = self.client.jobs["jid"]
        assert job is not None
        queue_throttle = queue.throttle.name
        self.assertEqual(job.throttles, ["other-throttle", queue_throttle])

    def test_recur_with_throttles(self) -> None:
        """Test recur with throttles given"""
        queue = self.client.queues["foo"]
        queue.recur(
            "reqless_test.common.NoopJob", "{}", 60, jid="jid", throttles=["throttle"]
        )

        job = self.client.jobs["jid"]
        assert job is not None
        queue_throttle = queue.throttle.name
        self.assertEqual(job.throttles, ["throttle", queue_throttle])
