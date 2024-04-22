"""Test the serial worker"""

import json
import time
from tempfile import NamedTemporaryFile
from threading import Thread
from typing import Generator, Optional

from reqless.abstract import AbstractJob
from reqless.listener import Listener
from reqless.workers.serial_worker import SerialWorker
from reqless_test.common import BlockingJob, TestReqless


class ShortLivedSerialWorker(SerialWorker):
    def jobs(self) -> Generator[Optional[AbstractJob], None, None]:
        generator = SerialWorker.jobs(self)
        for _ in range(5):
            yield next(generator)

    def halt_job_processing(self, jid: str) -> None:
        self.client.database.rpush("foo", jid)


class NoListenSerialWorker(ShortLivedSerialWorker):
    def listen(self, listener: Listener) -> None:
        pass


class TestSerialWorker(TestReqless):
    """Test the worker"""

    def setUp(self) -> None:
        TestReqless.setUp(self)
        self.queue = self.client.queues["foo"]
        self.thread: Optional[Thread] = None

    def tearDown(self) -> None:
        if self.thread:
            self.thread.join()
        TestReqless.tearDown(self)

    def test_basic(self) -> None:
        """Can complete jobs in a basic way"""
        jids = [self.queue.put(BlockingJob, "{}") for _ in range(5)]
        NoListenSerialWorker(["foo"], self.client, interval=0.2).run()
        states = []
        for jid in jids:
            job = self.client.jobs[jid]
            assert job is not None and isinstance(job, AbstractJob)
            states.append(job.state)
        self.assertEqual(states, ["complete"] * 5)

    def test_jobs(self) -> None:
        """The jobs method yields None if there are no jobs"""
        worker = NoListenSerialWorker(["foo"], self.client, interval=0.2)
        self.assertEqual(next(worker.jobs()), None)

    def test_sleeps(self) -> None:
        """Make sure the client sleeps if there aren't jobs to be had"""
        for _ in range(4):
            self.queue.put(BlockingJob, "{}")
        before = time.time()
        NoListenSerialWorker(["foo"], self.client, interval=0.2).run()
        self.assertGreater(time.time() - before, 0.2)

    def test_lost_locks(self) -> None:
        """The worker should be able to stop processing if need be"""
        temp_file = NamedTemporaryFile()
        jid = self.queue.put(BlockingJob, json.dumps({"blocker_file": temp_file.name}))
        self.thread = Thread(
            target=ShortLivedSerialWorker(["foo"], self.client, interval=0.2).run
        )
        self.thread.start()
        job = self.client.jobs[jid]
        assert job is not None and isinstance(job, AbstractJob)
        # Now, we'll timeout one of the jobs and ensure that
        # halt_job_processing is invoked
        while job.state != "running":
            time.sleep(0.01)
            job = self.client.jobs[jid]
            assert job is not None and isinstance(job, AbstractJob)
        job.timeout()
        temp_file.close()
        self.assertEqual(self.client.database.brpop(["foo"], 1), ("foo", jid))

    def test_halt_job_processing(self) -> None:
        """Should be able to fall on its sword if need be"""
        worker = SerialWorker([], self.client)
        worker.jid = "foo"
        thread = Thread(target=worker.halt_job_processing, args=(worker.jid,))
        thread.start()
        thread.join()
        self.assertFalse(thread.is_alive())

    def test_halt_job_processing_dead(self) -> None:
        """If we've moved on to another job, say so"""
        # If this tests runs to completion, it has succeeded
        worker = SerialWorker([], self.client)
        worker.halt_job_processing("foo")

    def test_shutdown(self) -> None:
        """We should be able to shutdown a serial worker"""
        # If this test finishes, it passes
        worker = SerialWorker([], self.client, interval=0.1)
        worker.stop()
        worker.run()
