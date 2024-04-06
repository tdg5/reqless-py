"""Basic tests about the client"""

from typing import List

from reqless import retry
from reqless.abstract import AbstractClient, AbstractJob
from reqless.workers.worker import Worker
from reqless_test.common import TestReqless


def pop_one(client: AbstractClient, queue_name: str) -> AbstractJob:
    job = client.queues[queue_name].pop()
    assert job is not None and not isinstance(job, List)
    return job


class TestClient(TestReqless):
    """Test the client"""

    def test_track(self) -> None:
        """Gives us access to track and untrack jobs"""
        self.client.queues["foo"].put("reqless_test.common.NoopJob", "{}", jid="jid")
        self.assertTrue(self.client.track("jid"))
        self.assertFalse(self.client.track("jid"))
        self.assertEqual(self.client.jobs.tracked()["jobs"][0].jid, "jid")
        self.assertTrue(self.client.untrack("jid"))
        self.assertFalse(self.client.untrack("jid"))
        self.assertEqual(self.client.jobs.tracked(), {"jobs": [], "expired": {}})

    def test_attribute_error(self) -> None:
        """Throws AttributeError for non-attributes"""
        self.assertRaises(
            AttributeError,
            lambda: self.client.foo,  # type: ignore[attr-defined]
        )

    def test_tags(self) -> None:
        """Provides access to top tags"""
        self.assertEqual(self.client.tags(), {})
        for _ in range(10):
            self.client.queues["foo"].put(
                "reqless_test.common.NoopJob", "{}", tags=["foo"]
            )
        self.assertEqual(self.client.tags(), ["foo"])

    def test_unfail(self) -> None:
        """Provides access to unfail"""
        job_count = 10
        jids = map(str, range(job_count))
        for jid in jids:
            self.client.queues["foo"].put("reqless_test.common.NoopJob", "{}", jid=jid)
            pop_one(self.client, "foo").fail("foo", "bar")
        for jid in jids:
            job = self.client.jobs[jid]
            assert job is not None and isinstance(job, AbstractJob)
            self.assertEqual(job.state, "failed")
        unfail_count = self.client.unfail("foo", "foo")
        self.assertEqual(job_count, unfail_count)
        for jid in jids:
            job = self.client.jobs[jid]
            assert job is not None and isinstance(job, AbstractJob)
            self.assertEqual(job.state, "waiting")


class TestJobs(TestReqless):
    """Test the Jobs class"""

    def test_basic(self) -> None:
        """Can give us access to jobs"""
        self.assertEqual(self.client.jobs["jid"], None)
        self.client.queues["foo"].put("reqless_test.common.NoopJob", "{}", jid="jid")
        self.assertNotEqual(self.client.jobs["jid"], None)

    def test_recurring(self) -> None:
        """Can give us access to recurring jobs"""
        self.assertEqual(self.client.jobs["jid"], None)
        self.client.queues["foo"].recur(
            "reqless_test.common.NoopJob", "{}", 60, jid="jid"
        )
        self.assertNotEqual(self.client.jobs["jid"], None)

    def test_complete(self) -> None:
        """Can give us access to complete jobs"""
        self.assertEqual(self.client.jobs.complete(), [])
        self.client.queues["foo"].put("reqless_test.common.NoopJob", "{}", jid="jid")
        pop_one(self.client, "foo").complete()
        self.assertEqual(self.client.jobs.complete(), ["jid"])

    def test_tracked(self) -> None:
        """Gives us access to tracked jobs"""
        self.assertEqual(self.client.jobs.tracked(), {"jobs": [], "expired": {}})
        self.client.queues["foo"].put("reqless_test.common.NoopJob", "{}", jid="jid")
        self.client.track("jid")
        self.assertEqual(self.client.jobs.tracked()["jobs"][0].jid, "jid")

    def test_tagged(self) -> None:
        """Gives us access to tagged jobs"""
        self.assertEqual(self.client.jobs.tagged("foo"), {"total": 0, "jobs": {}})
        self.client.queues["foo"].put(
            "reqless_test.common.NoopJob", "{}", jid="jid", tags=["foo"]
        )
        self.assertEqual(self.client.jobs.tagged("foo")["jobs"][0], "jid")

    def test_failed(self) -> None:
        """Gives us access to failed jobs"""
        self.assertEqual(self.client.jobs.failed("foo"), {"total": 0, "jobs": []})
        self.client.queues["foo"].put("reqless_test.common.NoopJob", "{}", jid="jid")
        pop_one(self.client, "foo").fail("foo", "bar")
        self.assertEqual(self.client.jobs.failed("foo")["jobs"][0].jid, "jid")

    def test_failures(self) -> None:
        """Gives us access to failure types"""
        self.assertEqual(self.client.jobs.failed(), {})
        self.client.queues["foo"].put("reqless_test.common.NoopJob", "{}", jid="jid")
        pop_one(self.client, "foo").fail("foo", "bar")
        self.assertEqual(self.client.jobs.failed(), {"foo": 1})


class TestQueues(TestReqless):
    """Test the Queues class"""

    def test_basic(self) -> None:
        """Gives us access to queues"""
        self.assertNotEqual(self.client.queues["foo"], None)

    def test_counts(self) -> None:
        """Gives us access to counts"""
        self.assertEqual(self.client.queues.counts, {})
        self.client.queues["foo"].put("reqless_test.common.NoopJob", "{}")
        self.assertEqual(
            self.client.queues.counts,
            [
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
                }
            ],
        )

    def test_attribute_error(self) -> None:
        """Raises AttributeErrors for non-attributes"""
        self.assertRaises(
            AttributeError,
            lambda: self.client.queues.foo,  # type: ignore[attr-defined]
        )


class TestThrottles(TestReqless):
    """Test the Throttles class"""

    def test_basic(self) -> None:
        """Give us access to throttles"""
        self.assertNotEqual(self.client.throttles["foo"], None)

    def test_throttle_operations(self) -> None:
        throttle_name = "foo"
        throttle = self.client.throttles[throttle_name]

        self.assertEqual(throttle.name, throttle_name)
        self.assertEqual(throttle.maximum(), 0)
        # The throttle shouldn't actually exist at this time, so ttl should be -2
        self.assertEqual(throttle.ttl(), -2)

        new_maximum = 5
        throttle.set_maximum(new_maximum)
        self.assertEqual(throttle.maximum(), new_maximum)
        # Now that the throttle exists, it should not have an expiration
        self.assertEqual(throttle.ttl(), -1)

        new_expiration = 999
        throttle.set_maximum(None, new_expiration)
        self.assertEqual(throttle.maximum(), new_maximum)
        # Now that the throttle exists, it should not have an expiration
        self.assertLessEqual(throttle.ttl(), new_expiration)

        self.assertEqual(throttle.locks(), [])
        self.assertEqual(throttle.pending(), [])

        throttle.delete()
        # The throttle shouldn't actually exist at this time, so ttl should  be -2
        self.assertEqual(throttle.ttl(), -2)


class TestWorkers(TestReqless):
    """Test the Workers class"""

    def setUp(self) -> None:
        TestReqless.setUp(self)
        self.client.worker_name = "worker"
        self.worker = Worker(["foo"], self.client)

    def test_individual(self) -> None:
        """Gives us access to individual workers"""
        self.client.queues["foo"].put("reqless_test.common.NoopJob", "{}", jid="jid")
        self.assertEqual(self.client.workers["worker"], {"jobs": [], "stalled": []})
        job = next(self.worker.jobs())
        assert job is not None
        assert job.jid == "jid"
        self.assertEqual(
            self.client.workers["worker"], {"jobs": ["jid"], "stalled": []}
        )

    def test_counts(self) -> None:
        """Gives us access to worker counts"""
        self.client.queues["foo"].put("reqless_test.common.NoopJob", "{}", jid="jid")
        self.assertEqual(self.client.workers.counts, {})
        job = next(self.worker.jobs())
        assert job is not None
        self.assertEqual(
            self.client.workers.counts, [{"jobs": 1, "name": "worker", "stalled": 0}]
        )

    def test_attribute_error(self) -> None:
        """Raises AttributeErrors for non-attributes"""
        self.assertRaises(
            AttributeError,
            lambda: self.client.workers.foo,  # type: ignore[attr-defined]
        )


# This is used for TestRetry
class RetryFoo:
    @staticmethod
    @retry(ValueError)
    def process(job: AbstractJob) -> None:
        """This is supposed to raise an Exception"""
        if "valueerror" in job.tags:
            raise ValueError("Foo")
        else:
            raise Exception("Foo")


class TestRetry(TestReqless):
    """Test the retry decorator"""

    def test_basic(self) -> None:
        """Ensure the retry decorator works"""
        # The first time, it should just be retries automatically
        self.client.queues["foo"].put(RetryFoo, "{}", tags=["valueerror"], jid="jid")
        pop_one(self.client, "foo").process()
        # Now remove the tag so it should fail
        job = self.client.jobs["jid"]
        assert job is not None and isinstance(job, AbstractJob)
        job.untag("valueerror")
        pop_one(self.client, "foo").process()
        job = self.client.jobs["jid"]
        assert job is not None and isinstance(job, AbstractJob)
        self.assertEqual(job.state, "failed")

    def test_docstring(self) -> None:
        """Retry decorator should preserve docstring"""
        self.assertEqual(
            RetryFoo.process.__doc__, "This is supposed to raise an Exception"
        )
