"""Test worker"""

import qless
from qless.job import Job
from qless.workers.worker import Worker
from qless_test.common import TestQless


class TestWorker(TestQless):
    """Test the worker"""

    def setUp(self):
        TestQless.setUp(self)
        self.client.worker_name = "worker"
        self.worker = Worker(["foo"], self.client)

    def test_kill(self):
        """The base worker class' kill method should raise an exception"""
        self.assertRaises(NotImplementedError, self.worker.kill, 1)

    def test_resume(self):
        """We should be able to resume jobs"""
        queue = self.worker.client.queues["foo"]
        queue.put("foo", {})
        job = self.client.queues["foo"].peek()
        self.assertTrue(isinstance(job, Job))
        # Now, we'll create a new worker and make sure it gets that job first
        worker = Worker(["foo"], self.client, resume=[job])
        job_from_worker = next(worker.jobs())
        assert job_from_worker is not None
        self.assertEqual(job_from_worker.jid, job.jid)

    def test_unresumable(self):
        """If we can't heartbeat jobs, we should not try to resume it"""
        queue = self.worker.client.queues["foo"]
        queue.put("foo", {})
        # Pop from another worker
        other = qless.Client(hostname="other")
        job = other.queues["foo"].pop()
        self.assertTrue(isinstance(job, Job))
        # Now, we'll create a new worker and make sure it gets that job first
        job = self.client.jobs[job.jid]
        assert job is not None
        worker = Worker(["foo"], self.client, resume=[job])
        self.assertEqual(next(worker.jobs()), None)

    def test_resumable(self):
        """We should be able to find all the jobs that can be resumed"""
        # We're going to put some jobs into some queues, and pop them.
        jid = self.client.queues["foo"].put("Foo", {})
        self.client.queues["bar"].put("Foo", {})
        self.client.queues["foo"].pop()
        self.client.queues["bar"].pop()

        # Now, we should be able to see a resumable job in 'foo', but we should
        # not see the job that we popped from 'bar'
        worker = Worker(["foo"], self.client, resume=True)
        jids = [job.jid for job in worker.resume]
        self.assertEqual(jids, [jid])
