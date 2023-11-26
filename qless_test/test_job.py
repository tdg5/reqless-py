"""Basic tests about the Job class"""

import mock

from qless.job import Job, RecurringJob
from qless_test.common import TestQless


class Foo:
    """A dummy job"""

    @staticmethod
    def bar(job):
        """A dummy method"""
        job["foo"] = "bar"
        job.complete()

    def nonstatic(self, job):
        """A nonstatic method"""
        pass


class TestJob(TestQless):
    """Test the Job class"""

    def get_job(self, jid: str) -> Job:
        job = self.client.jobs[jid]
        assert isinstance(job, Job)
        return job

    def test_attributes(self):
        """Has all the basic attributes we'd expect"""
        self.client.queues["foo"].put(
            "Foo",
            {"whiz": "bang"},
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
                "data": {"whiz": "bang"},
                "dependencies": [],
                "dependents": [],
                "expires_at": 0,
                "jid": "jid",
                "klass_name": "Foo",
                "original_retries": 3,
                "priority": 0,
                "queue_name": "foo",
                "retries_left": 3,
                "tags": ["foo"],
                "worker_name": "",
                "throttles": ["throttle", "ql:q:foo"],
            },
        )

    def test_set_priority(self):
        """We can set a job's priority"""
        self.client.queues["foo"].put("Foo", {}, jid="jid", priority=0)
        job = self.get_job("jid")
        self.assertEqual(job.priority, 0)
        job.priority = 10
        job = self.get_job("jid")
        self.assertEqual(job.priority, 10)

    def test_queue(self):
        """Exposes a queue object"""
        self.client.queues["foo"].put("Foo", {}, jid="jid")
        job = self.client.jobs["jid"]
        job = self.get_job("jid")
        self.assertEqual(job.queue.name, "foo")

    def test_klass(self):
        """Exposes the class for a job"""
        self.client.queues["foo"].put(Job, {}, jid="jid")
        job = self.get_job("jid")
        self.assertEqual(job.klass, Job)

    def test_ttl(self):
        """Exposes the ttl for a job"""
        self.client.config["heartbeat"] = 10
        self.client.queues["foo"].put(Job, {}, jid="jid")
        self.client.queues["foo"].pop()
        job = self.get_job("jid")
        self.assertTrue(job.ttl < 10)
        self.assertTrue(job.ttl > 9)

    def test_attribute_error(self):
        """Raises an attribute error for nonexistent attributes"""
        self.client.queues["foo"].put(Job, {}, jid="jid")
        job = self.get_job("jid")
        self.assertRaises(
            AttributeError,
            lambda: job.foo,  # type: ignore[attr-defined]
        )

    def test_cancel(self):
        """Exposes the cancel method"""
        self.client.queues["foo"].put("Foo", {}, jid="jid")
        job = self.get_job("jid")
        job.cancel()
        self.assertEqual(self.client.jobs["jid"], None)

    def test_tag_untag(self):
        """Exposes a way to tag and untag a job"""
        self.client.queues["foo"].put("Foo", {}, jid="jid")
        job = self.get_job("jid")
        job.tag("foo")
        job = self.get_job("jid")
        self.assertEqual(job.tags, ["foo"])
        job.untag("foo")
        job = self.get_job("jid")
        self.assertEqual(job.tags, [])

    def test_getitem(self):
        """Exposes job data through []"""
        self.client.queues["foo"].put("Foo", {"foo": "bar"}, jid="jid")
        job = self.get_job("jid")
        self.assertEqual(job["foo"], "bar")

    def test_setitem(self):
        """Sets jobs data through []"""
        self.client.queues["foo"].put("Foo", {}, jid="jid")
        job = self.get_job("jid")
        job["foo"] = "bar"
        self.assertEqual(job["foo"], "bar")

    def test_move(self):
        """Able to move jobs through the move method"""
        self.client.queues["foo"].put("Foo", {}, jid="jid", throttles=["throttle"])
        job = self.get_job("jid")
        job.move("bar")
        job = self.get_job("jid")
        queue = self.client.queues["bar"]
        self.assertEqual(queue.name, "bar")
        queue_throttle = queue.throttle.name
        self.assertEqual(job.throttles, ["throttle", queue_throttle])

    def test_complete(self):
        """Able to complete a job"""
        self.client.queues["foo"].put("Foo", {}, jid="jid")
        self.client.queues["foo"].pop().complete()
        job = self.get_job("jid")
        self.assertEqual(job.state, "complete")

    def test_advance(self):
        """Able to advance a job to another queue"""
        self.client.queues["foo"].put("Foo", {}, jid="jid")
        self.client.queues["foo"].pop().complete("bar")
        job = self.get_job("jid")
        self.assertEqual(job.state, "waiting")

    def test_heartbeat(self):
        """Provides access to heartbeat"""
        self.client.config["heartbeat"] = 10
        self.client.queues["foo"].put("Foo", {}, jid="jid")
        job = self.client.queues["foo"].pop()
        before = job.ttl
        self.client.config["heartbeat"] = 20
        job.heartbeat()
        self.assertTrue(job.ttl > before)

    def test_heartbeat_fail(self):
        """Failed heartbeats raise an error"""
        from qless.exceptions import LostLockError

        self.client.queues["foo"].put("Foo", {}, jid="jid")
        job = self.get_job("jid")
        self.assertRaises(LostLockError, job.heartbeat)

    def test_track_untrack(self):
        """Exposes a track, untrack method"""
        self.client.queues["foo"].put("Foo", {}, jid="jid")
        job = self.get_job("jid")
        self.assertFalse(job.tracked)
        job.track()
        job = self.get_job("jid")
        self.assertTrue(job.tracked)
        job.untrack()
        job = self.get_job("jid")
        self.assertFalse(job.tracked)

    def test_depend_undepend(self):
        """Exposes a depend, undepend methods"""
        self.client.queues["foo"].put("Foo", {}, jid="a")
        self.client.queues["foo"].put("Foo", {}, jid="b")
        self.client.queues["foo"].put("Foo", {}, jid="c", depends=["a"])
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

    def test_retry_fail(self):
        """Retry raises an error if retry fails"""
        from qless.exceptions import QlessError

        self.client.queues["foo"].put("Foo", {}, jid="jid")
        job = self.get_job("jid")
        self.assertRaises(QlessError, job.retry)

    def test_retry_group_and_message(self):
        """Can supply a group and message when retrying."""
        self.client.queues["foo"].put("Foo", {}, jid="jid", retries=0)
        self.client.queues["foo"].pop().retry(group="group", message="message")
        job = self.get_job("jid")
        self.assertEqual(job.failure["group"], "group")
        self.assertEqual(job.failure["message"], "message")

    def test_repr(self):
        """Has a reasonable repr"""
        self.client.queues["foo"].put(Job, {}, jid="jid")
        job = self.get_job("jid")
        self.assertEqual(repr(job), "<qless.job.Job jid>")

    def test_no_method(self):
        """Raises an error if the class doesn't have the method"""
        self.client.queues["foo"].put(Foo, {}, jid="jid")
        self.client.queues["foo"].pop().process()
        job = self.get_job("jid")
        self.assertEqual(job.state, "failed")
        self.assertEqual(job.failure["group"], "foo-method-missing")

    def test_no_import(self):
        """Raises an error if it can't import the class"""
        self.client.queues["foo"].put("foo.Foo", {}, jid="jid")
        self.client.queues["foo"].pop().process()
        job = self.get_job("jid")
        self.assertEqual(job.state, "failed")
        self.assertEqual(job.failure["group"], "foo-ModuleNotFoundError")

    def test_nonstatic(self):
        """Rasises an error if the relevant function's not static"""
        self.client.queues["nonstatic"].put(Foo, {}, jid="jid")
        self.client.queues["nonstatic"].pop().process()
        job = self.get_job("jid")
        self.assertEqual(job.state, "failed")
        self.assertEqual(job.failure["group"], "nonstatic-TypeError")

    def test_reload(self):
        """Ensure that nothing blows up if we reload a class"""
        self.client.queues["foo"].put(Foo, {}, jid="jid")
        job = self.get_job("jid")
        self.assertEqual(job.klass, Foo)
        Job.reload(job.klass_name)
        job = self.get_job("jid")
        self.assertEqual(job.klass, Foo)

    def test_no_mtime(self):
        """Don't blow up we cannot check the modification time of a module."""
        exc = OSError("Could not stat file")
        with mock.patch("qless.job.os.stat", side_effect=exc):
            Job._import("qless_test.test_job.Foo")
            Job._import("qless_test.test_job.Foo")


class TestRecurring(TestQless):
    def get_job(self, jid: str) -> RecurringJob:
        job = self.client.jobs[jid]
        assert isinstance(job, RecurringJob)
        return job

    def test_attributes(self):
        """We can access all the recurring attributes"""
        self.client.queues["foo"].recur(
            "Foo", {"whiz": "bang"}, 60, jid="jid", tags=["foo"], retries=3
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
                "data": {"whiz": "bang"},
                "interval": 60,
                "jid": "jid",
                "klass_name": "Foo",
                "priority": 0,
                "queue_name": "foo",
                "retries": 3,
                "tags": ["foo"],
            },
        )

    def test_set_priority(self):
        """We can set priority on recurring jobs"""
        self.client.queues["foo"].recur("Foo", {}, 60, jid="jid", priority=0)
        job = self.get_job("jid")
        job.priority = 10
        job = self.get_job("jid")
        self.assertEqual(job.priority, 10)

    def test_set_retries(self):
        """We can set retries"""
        self.client.queues["foo"].recur("Foo", {}, 60, jid="jid", retries=2)
        job = self.get_job("jid")
        job.retries = 2
        job = self.get_job("jid")
        self.assertEqual(job.retries, 2)

    def test_set_interval(self):
        """We can set the interval"""
        self.client.queues["foo"].recur("Foo", {}, 60, jid="jid")
        job = self.get_job("jid")
        job.interval = 10
        job = self.get_job("jid")
        self.assertEqual(job.interval, 10)

    def test_set_data(self):
        """We can set the job data"""
        self.client.queues["foo"].recur("Foo", {}, 60, jid="jid")
        job = self.get_job("jid")
        job.data = {"foo": "bar"}
        job = self.get_job("jid")
        self.assertEqual(job.data, {"foo": "bar"})

    def test_set_klass(self):
        """We can set the klass"""
        self.client.queues["foo"].recur("Foo", {}, 60, jid="jid")
        job = self.get_job("jid")
        job.klass = Foo
        job = self.get_job("jid")
        self.assertEqual(job.klass, Foo)

    def test_get_next(self):
        """Exposes the next time a job will run"""
        self.client.queues["foo"].recur("Foo", {}, 60, jid="jid")
        job = self.get_job("jid")
        nxt = job.next
        self.client.queues["foo"].pop()
        job = self.get_job("jid")
        self.assertTrue(abs(job.next - nxt - 60) < 1)

    def test_attribute_error(self):
        """Raises attribute errors for non-attributes"""
        self.client.queues["foo"].recur("Foo", {}, 60, jid="jid")
        job = self.get_job("jid")
        self.assertRaises(
            AttributeError,
            lambda: job.foo,  # type: ignore[attr-defined]
        )

    def test_move(self):
        """Exposes a way to move a job"""
        self.client.queues["foo"].recur(
            "Foo", {}, 60, jid="jid", throttles=["throttle"]
        )
        job = self.get_job("jid")
        job.move("bar")

        job = self.get_job("jid")
        queue = self.client.queues["bar"]
        self.assertEqual(queue.name, "bar")
        queue_throttle = queue.throttle.name
        self.assertEqual(job.throttles, ["throttle", queue_throttle])

    def test_cancel(self):
        """Exposes a way to cancel jobs"""
        self.client.queues["foo"].recur("Foo", {}, 60, jid="jid")
        job = self.get_job("jid")
        job.cancel()
        self.assertEqual(self.client.jobs["jid"], None)

    def test_tag_untag(self):
        """Exposes a way to tag jobs"""
        self.client.queues["foo"].recur("Foo", {}, 60, jid="jid")
        job = self.get_job("jid")
        job.tag("foo")
        job = self.get_job("jid")
        self.assertEqual(job.tags, ["foo"])
        job = self.get_job("jid")
        job.untag("foo")
        job = self.get_job("jid")
        self.assertEqual(job.tags, [])
