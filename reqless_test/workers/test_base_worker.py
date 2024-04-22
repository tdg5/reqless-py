"""Test worker"""

from typing import List

import reqless
from reqless.abstract import AbstractClient, AbstractJob
from reqless.queue_resolvers.transforming_queue_resolver import (
    TransformingQueueResolver,
)
from reqless.workers.base_worker import BaseWorker
from reqless_test.common import TestReqless


class TestBaseWorker(TestReqless):
    """Test the worker"""

    def setUp(self) -> None:
        TestReqless.setUp(self)
        self.client.worker_name = "worker"
        self.worker = BaseWorker(["foo"], self.client)

    def test_halt_job_processing(self) -> None:
        """The base worker class' halt_job_processing method should raise an
        exception"""
        self.assertRaises(NotImplementedError, self.worker.halt_job_processing, 1)

    def test_resume(self) -> None:
        """We should be able to resume jobs"""
        queue = self.worker.client.queues["foo"]
        queue.put("reqless_test.common.NoopJob", "{}")
        job = self.pop_one(self.client, "foo")
        # Now, we'll create a new worker and make sure it gets that job first
        worker = BaseWorker(["foo"], self.client, resume=[job])
        job_from_worker = next(worker.jobs())
        assert job_from_worker is not None and isinstance(job_from_worker, AbstractJob)
        self.assertEqual(job_from_worker.jid, job.jid)

    def test_unresumable(self) -> None:
        """If we can't heartbeat jobs, we should not try to resume it"""
        queue = self.worker.client.queues["foo"]
        queue.put("reqless_test.common.NoopJob", "{}")
        # Pop from another worker
        other = reqless.Client(hostname="other")
        job = self.pop_one(other, "foo")
        # Now, we'll create a new worker and make sure it gets that job first
        job_again = self.client.jobs[job.jid]
        assert job_again is not None and isinstance(job_again, AbstractJob)
        worker = BaseWorker(["foo"], self.client, resume=[job_again])
        self.assertEqual(next(worker.jobs()), None)

    def test_resumable(self) -> None:
        """We should be able to find all the jobs that can be resumed"""
        # We're going to put some jobs into some queues, and pop them.
        jid = self.client.queues["foo"].put("reqless_test.common.NoopJob", "{}")
        self.client.queues["bar"].put("reqless_test.common.NoopJob", "{}")
        self.pop_one(self.client, "foo")
        self.pop_one(self.client, "bar")

        # Now, we should be able to see a resumable job in 'foo', but we should
        # not see the job that we popped from 'bar'
        worker = BaseWorker(["foo"], self.client, resume=True)
        jids = [job.jid for job in worker.resume]
        self.assertEqual(jids, [jid])

    def test_queue_resolver_when_list_of_queues_given(self) -> None:
        """When given a list of queues, it wraps them in a queue resolver"""
        queue_names = ["foo"]
        worker = BaseWorker(queue_names, self.client)
        self.assertEqual(queue_names, worker.queue_resolver.resolve())

    def test_queue_resolver_when_queue_resolver_given(self) -> None:
        """When given a queue resolver, it takes it without modification"""
        queue_names = ["foo"]
        queue_resolver = TransformingQueueResolver(queue_identifiers=queue_names)
        worker = BaseWorker(client=self.client, queues=queue_resolver)
        self.assertEqual(queue_resolver, worker.queue_resolver)
        self.assertEqual(queue_names, worker.queue_resolver.resolve())

    def pop_one(self, client: AbstractClient, queue_name: str) -> AbstractJob:
        job = client.queues[queue_name].pop()
        assert job is not None and not isinstance(job, List)
        return job
