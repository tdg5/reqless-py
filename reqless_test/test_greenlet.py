"""Test the serial worker"""

import json
import time
from threading import Thread
from typing import Generator, Optional

import gevent

from reqless.abstract import AbstractJob, AbstractQueue
from reqless.listener import Listener
from reqless.workers.greenlet import GeventWorker
from reqless_test.common import TestReqless


class GeventJob:
    """Dummy class"""

    @staticmethod
    def foo(job: AbstractJob) -> None:
        """Dummy job"""
        data_dict = json.loads(job.data)
        data_dict["sandbox"] = job.sandbox
        job.data = json.dumps(data_dict)
        job.complete()


class PatchedGeventWorker(GeventWorker):
    """A worker that limits the number of jobs it runs"""

    @classmethod
    def patch(cls) -> None:
        """Don't monkey-patch anything"""
        pass

    def jobs(self) -> Generator[Optional[AbstractJob], None, None]:
        """Yield only a few jobs"""
        generator = GeventWorker.jobs(self)
        for _ in range(5):
            yield next(generator)

    def listen(self, listener: Listener) -> None:
        """Don't actually listen for pubsub events"""
        pass


class TestWorker(TestReqless):
    """Test the worker"""

    def setUp(self) -> None:
        TestReqless.setUp(self)
        self.worker = PatchedGeventWorker(
            ["foo"], self.client, greenlets=1, interval=0.2
        )
        self.queue: AbstractQueue = self.client.queues["foo"]
        self.thread: Optional[Thread] = None

    def tearDown(self) -> None:
        if self.thread:
            self.thread.join()
        TestReqless.tearDown(self)

    def test_basic(self) -> None:
        """Can complete jobs in a basic way"""
        jids = [self.queue.put(GeventJob, "{}") for _ in range(5)]
        self.worker.run()
        states = []
        for jid in jids:
            job = self.client.jobs[jid]
            assert job is not None and isinstance(job, AbstractJob)
            states.append(job.state)
        self.assertEqual(states, ["complete"] * 5)
        sandboxes = []
        for jid in jids:
            job = self.client.jobs[jid]
            assert job is not None
            sandboxes.append(json.loads(job.data)["sandbox"])
        for sandbox in sandboxes:
            self.assertIn("reqless-py-workers/greenlet-0", sandbox)

    def test_sleeps(self) -> None:
        """Make sure the client sleeps if there aren't jobs to be had"""
        for _ in range(4):
            self.queue.put(GeventJob, "{}")
        before = time.time()
        self.worker.run()
        self.assertGreater(time.time() - before, 0.2)

    def test_kill(self) -> None:
        """Can kill greenlets when it loses its lock"""
        worker = PatchedGeventWorker(["foo"], self.client)
        greenlet = gevent.spawn(gevent.sleep, 1)
        worker.greenlets["foo"] = greenlet
        worker.kill("foo")
        greenlet.join()
        self.assertIsInstance(greenlet.value, gevent.GreenletExit)

    def test_kill_dead(self) -> None:
        """Does not panic if the greenlet handling a job is no longer around"""
        # This test succeeds if it finishes without an exception
        self.worker.kill("foo")
