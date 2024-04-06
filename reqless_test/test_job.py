"""Basic tests about the Job class"""

import json
from typing import List

from reqless.abstract import AbstractJob
from reqless.job import Job, RecurringJob
from reqless_test.common import TestReqless


class Foo:
    """A dummy job"""

    @staticmethod
    def bar(job: AbstractJob) -> None:
        """A dummy method"""
        data_dict = json.loads(job.data)
        data_dict["foo"] = "bar"
        job.data = json.dumps(data_dict)
        job.complete()

    def nonstatic(self, job: AbstractJob) -> None:
        """A nonstatic method"""
        pass


class TestJob(TestReqless):
    """Test the Job class"""

    def get_job(self, jid: str) -> Job:
        job = self.client.jobs[jid]
        assert isinstance(job, Job)
        return job

    def test_attributes(self) -> None:
        """Has all the basic attributes we'd expect"""
        data = {"whiz": "bang"}
        self.client.queues["foo"].put(
            "reqless_test.test_job.Foo",
            json.dumps(data),
            jid="jid",
            tags=["foo"],
            retries=3,
            throttles=["throttle"],
        )
        job = self.get_job("jid")
        atts = [
            "data",
            "jid",
            "priority",
            "klass_name",
            "queue_name",
            "tags",
            "expires_at",
            "original_retries",
            "retries_left",
            "worker_name",
            "dependents",
            "dependencies",
            "throttles",
        ]
        values = [getattr(job, att) for att in atts]
        self.assertEqual(
            dict(zip(atts, values)),
            {
                "data": json.dumps(data),
                "dependencies": [],
                "dependents": [],
                "expires_at": 0,
                "jid": "jid",
                "klass_name": "reqless_test.test_job.Foo",
                "original_retries": 3,
                "priority": 0,
                "queue_name": "foo",
                "retries_left": 3,
                "tags": ["foo"],
                "worker_name": "",
                "throttles": ["throttle", "ql:q:foo"],
            },
        )

    def test_set_priority(self) -> None:
        """We can set a job's priority"""
        self.client.queues["foo"].put(
            "reqless_test.test_job.Foo", "{}", jid="jid", priority=0
        )
        job = self.get_job("jid")
        self.assertEqual(job.priority, 0)
        job.priority = 10
        job = self.get_job("jid")
        self.assertEqual(job.priority, 10)

    def test_queue(self) -> None:
        """Exposes a queue object"""
        self.client.queues["foo"].put("reqless_test.test_job.Foo", "{}", jid="jid")
        job = self.client.jobs["jid"]
        job = self.get_job("jid")
        self.assertEqual(job.queue.name, "foo")

    def test_klass(self) -> None:
        """Exposes the class for a job"""
        self.client.queues["foo"].put(Job, "{}", jid="jid")
        job = self.get_job("jid")
        self.assertEqual(job.klass, Job)

    def test_ttl(self) -> None:
        """Exposes the ttl for a job"""
        self.client.config["heartbeat"] = 10
        self.client.queues["foo"].put(Job, "{}", jid="jid")
        self.client.queues["foo"].pop()
        job = self.get_job("jid")
        self.assertTrue(job.ttl < 10)
        self.assertTrue(job.ttl > 9)

    def test_attribute_error(self) -> None:
        """Raises an attribute error for nonexistent attributes"""
        self.client.queues["foo"].put(Job, "{}", jid="jid")
        job = self.get_job("jid")
        self.assertRaises(
            AttributeError,
            lambda: job.foo,  # type: ignore[attr-defined]
        )

    def test_cancel(self) -> None:
        """Exposes the cancel method"""
        self.client.queues["foo"].put("reqless_test.test_job.Foo", "{}", jid="jid")
        job = self.get_job("jid")
        job.cancel()
        self.assertEqual(self.client.jobs["jid"], None)

    def test_tag_untag(self) -> None:
        """Exposes a way to tag and untag a job"""
        self.client.queues["foo"].put("reqless_test.test_job.Foo", "{}", jid="jid")
        job = self.get_job("jid")
        job.tag("foo")
        job = self.get_job("jid")
        self.assertEqual(job.tags, ["foo"])
        job.untag("foo")
        job = self.get_job("jid")
        self.assertEqual(job.tags, [])

    def test_move(self) -> None:
        """Able to move jobs through the move method"""
        self.client.queues["foo"].put(
            "reqless_test.test_job.Foo", "{}", jid="jid", throttles=["throttle"]
        )
        job = self.get_job("jid")
        job.move("bar")
        job = self.get_job("jid")
        queue = self.client.queues["bar"]
        self.assertEqual(queue.name, "bar")
        queue_throttle = queue.throttle.name
        self.assertEqual(job.throttles, ["throttle", queue_throttle])

    def test_complete(self) -> None:
        """Able to complete a job"""
        self.client.queues["foo"].put("reqless_test.test_job.Foo", "{}", jid="jid")
        job = self.client.queues["foo"].pop()
        assert job is not None and not isinstance(job, List)
        job.complete()
        job = self.get_job("jid")
        self.assertEqual(job.state, "complete")

    def test_advance(self) -> None:
        """Able to advance a job to another queue"""
        self.client.queues["foo"].put("reqless_test.test_job.Foo", "{}", jid="jid")
        job = self.client.queues["foo"].pop()
        assert job is not None and not isinstance(job, List)
        job.complete("bar")
        job = self.get_job("jid")
        self.assertEqual(job.state, "waiting")

    def test_heartbeat(self) -> None:
        """Provides access to heartbeat"""
        self.client.config["heartbeat"] = 10
        self.client.queues["foo"].put("reqless_test.test_job.Foo", "{}", jid="jid")
        job = self.client.queues["foo"].pop()
        assert job is not None and not isinstance(job, List)
        before = job.ttl
        self.client.config["heartbeat"] = 20
        job.heartbeat()
        self.assertTrue(job.ttl > before)

    def test_heartbeat_fail(self) -> None:
        """Failed heartbeats raise an error"""
        from reqless.exceptions import LostLockError

        self.client.queues["foo"].put("reqless_test.test_job.Foo", "{}", jid="jid")
        job = self.get_job("jid")
        self.assertRaises(LostLockError, job.heartbeat)

    def test_track_untrack(self) -> None:
        """Exposes a track, untrack method"""
        self.client.queues["foo"].put("reqless_test.test_job.Foo", "{}", jid="jid")
        job = self.get_job("jid")
        self.assertFalse(job.tracked)
        job.track()
        job = self.get_job("jid")
        self.assertTrue(job.tracked)
        job.untrack()
        job = self.get_job("jid")
        self.assertFalse(job.tracked)

    def test_depend_undepend(self) -> None:
        """Exposes a depend, undepend methods"""
        self.client.queues["foo"].put("reqless_test.test_job.Foo", "{}", jid="a")
        self.client.queues["foo"].put("reqless_test.test_job.Foo", "{}", jid="b")
        self.client.queues["foo"].put(
            "reqless_test.test_job.Foo", "{}", jid="c", depends=["a"]
        )
        job = self.get_job("c")
        self.assertEqual(job.dependencies, ["a"])
        job.depend("b")
        job = self.get_job("c")
        actual_dependencies = job.dependencies
        # Redis sets have an undefined order
        actual_dependencies.sort()
        self.assertEqual(actual_dependencies, ["a", "b"])
        job.undepend("a")
        job = self.get_job("c")
        self.assertEqual(job.dependencies, ["b"])
        job.undepend(all=True)
        job = self.get_job("c")
        self.assertEqual(job.dependencies, [])

    def test_retry_fail(self) -> None:
        """Retry raises an error if retry fails"""
        from reqless.exceptions import ReqlessError

        self.client.queues["foo"].put("reqless_test.test_job.Foo", "{}", jid="jid")
        job = self.get_job("jid")
        self.assertRaises(ReqlessError, job.retry)

    def test_retry_group_and_message(self) -> None:
        """Can supply a group and message when retrying."""
        self.client.queues["foo"].put(
            "reqless_test.test_job.Foo", "{}", jid="jid", retries=0
        )
        job = self.client.queues["foo"].pop()
        assert job is not None and not isinstance(job, List)
        job.retry(group="group", message="message")
        job = self.get_job("jid")
        assert job.failure is not None
        self.assertEqual(job.failure["group"], "group")
        assert job.failure is not None
        self.assertEqual(job.failure["message"], "message")

    def test_repr(self) -> None:
        """Has a reasonable repr"""
        self.client.queues["foo"].put(Job, "{}", jid="jid")
        job = self.get_job("jid")
        self.assertEqual(repr(job), "<reqless.job.Job jid>")

    def test_no_method(self) -> None:
        """Raises an error if the class doesn't have the method"""
        self.client.queues["foo"].put(Foo, "{}", jid="jid")
        job = self.client.queues["foo"].pop()
        assert job is not None and not isinstance(job, List)
        job.process()
        job = self.get_job("jid")
        self.assertEqual(job.state, "failed")
        assert job.failure is not None
        self.assertEqual(job.failure["group"], "foo-method-missing")

    def test_no_import(self) -> None:
        """Raises an error if it can't import the class"""
        self.client.queues["foo"].put("foo.Foo", "{}", jid="jid")
        job = self.client.queues["foo"].pop()
        assert job is not None and not isinstance(job, List)
        job.process()
        job = self.get_job("jid")
        self.assertEqual(job.state, "failed")
        assert job.failure is not None
        self.assertEqual(job.failure["group"], "foo-ModuleNotFoundError")

    def test_nonstatic(self) -> None:
        """Rasises an error if the relevant function's not static"""
        self.client.queues["nonstatic"].put(Foo, "{}", jid="jid")
        job = self.client.queues["nonstatic"].pop()
        assert job is not None and not isinstance(job, List)
        job.process()
        job = self.get_job("jid")
        self.assertEqual(job.state, "failed")
        assert job.failure is not None
        self.assertEqual(job.failure["group"], "nonstatic-TypeError")


class TestRecurring(TestReqless):
    def get_job(self, jid: str) -> RecurringJob:
        job = self.client.jobs[jid]
        assert isinstance(job, RecurringJob)
        return job

    def test_attributes(self) -> None:
        """We can access all the recurring attributes"""
        data = {"whiz": "bang"}
        self.client.queues["foo"].recur(
            "reqless_test.test_job.Foo",
            json.dumps(data),
            60,
            jid="jid",
            tags=["foo"],
            retries=3,
        )
        job = self.get_job("jid")
        atts = [
            "data",
            "jid",
            "priority",
            "klass_name",
            "queue_name",
            "tags",
            "retries",
            "interval",
            "count",
        ]
        values = [getattr(job, att) for att in atts]
        self.assertEqual(
            dict(zip(atts, values)),
            {
                "count": 0,
                "data": json.dumps(data),
                "interval": 60,
                "jid": "jid",
                "klass_name": "reqless_test.test_job.Foo",
                "priority": 0,
                "queue_name": "foo",
                "retries": 3,
                "tags": ["foo"],
            },
        )

    def test_set_priority(self) -> None:
        """We can set priority on recurring jobs"""
        self.client.queues["foo"].recur(
            "reqless_test.test_job.Foo", "{}", 60, jid="jid", priority=0
        )
        job = self.get_job("jid")
        job.priority = 10
        job = self.get_job("jid")
        self.assertEqual(job.priority, 10)

    def test_set_retries(self) -> None:
        """We can set retries"""
        self.client.queues["foo"].recur(
            "reqless_test.test_job.Foo", "{}", 60, jid="jid", retries=2
        )
        job = self.get_job("jid")
        job.retries = 2
        job = self.get_job("jid")
        self.assertEqual(job.retries, 2)

    def test_set_interval(self) -> None:
        """We can set the interval"""
        self.client.queues["foo"].recur(
            "reqless_test.test_job.Foo", "{}", 60, jid="jid"
        )
        job = self.get_job("jid")
        job.interval = 10
        job = self.get_job("jid")
        self.assertEqual(job.interval, 10)

    def test_set_data(self) -> None:
        """We can set the job data"""
        self.client.queues["foo"].recur(
            "reqless_test.test_job.Foo", "{}", 60, jid="jid"
        )
        job = self.get_job("jid")
        job.data = json.dumps({"foo": "bar"})
        job = self.get_job("jid")
        self.assertEqual(json.loads(job.data), {"foo": "bar"})

    def test_set_klass(self) -> None:
        """We can set the klass"""
        self.client.queues["foo"].recur(
            "reqless_test.test_job.Foo", "{}", 60, jid="jid"
        )
        job = self.get_job("jid")
        job.klass = Foo
        job = self.get_job("jid")
        self.assertEqual(job.klass, Foo)

    def test_get_next(self) -> None:
        """Exposes the next time a job will run"""
        self.client.queues["foo"].recur(
            "reqless_test.test_job.Foo", "{}", 60, jid="jid"
        )
        job = self.get_job("jid")
        nxt = job.next
        assert nxt is not None
        self.client.queues["foo"].pop()
        job = self.get_job("jid")
        job_next = job.next
        assert job_next is not None
        self.assertTrue(abs(job_next - nxt - 60) < 1)

    def test_attribute_error(self) -> None:
        """Raises attribute errors for non-attributes"""
        self.client.queues["foo"].recur(
            "reqless_test.test_job.Foo", "{}", 60, jid="jid"
        )
        job = self.get_job("jid")
        self.assertRaises(
            AttributeError,
            lambda: job.foo,  # type: ignore[attr-defined]
        )

    def test_move(self) -> None:
        """Exposes a way to move a job"""
        self.client.queues["foo"].recur(
            "reqless_test.test_job.Foo", "{}", 60, jid="jid", throttles=["throttle"]
        )
        job = self.get_job("jid")
        job.move("bar")

        job = self.get_job("jid")
        queue = self.client.queues["bar"]
        self.assertEqual(queue.name, "bar")
        queue_throttle = queue.throttle.name
        self.assertEqual(job.throttles, ["throttle", queue_throttle])

    def test_cancel(self) -> None:
        """Exposes a way to cancel jobs"""
        self.client.queues["foo"].recur(
            "reqless_test.test_job.Foo", "{}", 60, jid="jid"
        )
        job = self.get_job("jid")
        job.cancel()
        self.assertEqual(self.client.jobs["jid"], None)

    def test_tag_untag(self) -> None:
        """Exposes a way to tag jobs"""
        self.client.queues["foo"].recur(
            "reqless_test.test_job.Foo", "{}", 60, jid="jid"
        )
        job = self.get_job("jid")
        job.tag("foo")
        job = self.get_job("jid")
        self.assertEqual(job.tags, ["foo"])
        job = self.get_job("jid")
        job.untag("foo")
        job = self.get_job("jid")
        self.assertEqual(job.tags, [])
