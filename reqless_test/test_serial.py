"""Test the serial worker"""

import json
import time
from os import path
from tempfile import NamedTemporaryFile
from threading import Thread
from typing import Generator, Optional, Tuple

from reqless import logger
from reqless.abstract import AbstractJob
from reqless.listener import Listener
from reqless.workers.serial import SerialWorker
from reqless_test.common import TestReqless


class SerialJob:
    """Dummy class"""

    @staticmethod
    def foo(job: AbstractJob) -> None:
        """Dummy job"""
        data_dict = json.loads(job.data)
        blocker_file = data_dict.get("blocker_file")
        if blocker_file:
            while path.exists(blocker_file):
                time.sleep(0.1)
        try:
            job.complete()
        except Exception:
            logger.exception("Unable to complete job %s" % job.jid)


class Worker(SerialWorker):
    """A worker that limits the number of jobs it runs"""

    def jobs(self) -> Generator[Optional[AbstractJob], None, None]:
        """Yield only a few jobs"""
        generator = SerialWorker.jobs(self)
        for _ in range(5):
            yield next(generator)

    def kill(self, jid: str) -> None:
        """We'll push a message to redis instead of falling on our sword"""
        self.client.redis.rpush("foo", jid)
        raise KeyboardInterrupt()

    def signals(self, signals: Tuple[str, ...] = ()) -> None:
        """Do not set any signal handlers"""
        pass


class NoListenWorker(Worker):
    """A worker that just won't listen"""

    def listen(self, listener: Listener) -> None:
        """Don't listen for lost locks"""
        pass


class TestWorker(TestReqless):
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
        jids = [self.queue.put(SerialJob, "{}") for _ in range(5)]
        NoListenWorker(["foo"], self.client, interval=0.2).run()
        states = []
        for jid in jids:
            job = self.client.jobs[jid]
            assert job is not None and isinstance(job, AbstractJob)
            states.append(job.state)
        self.assertEqual(states, ["complete"] * 5)

    def test_jobs(self) -> None:
        """The jobs method yields None if there are no jobs"""
        worker = NoListenWorker(["foo"], self.client, interval=0.2)
        self.assertEqual(next(worker.jobs()), None)

    def test_sleeps(self) -> None:
        """Make sure the client sleeps if there aren't jobs to be had"""
        for _ in range(4):
            self.queue.put(SerialJob, "{}")
        before = time.time()
        NoListenWorker(["foo"], self.client, interval=0.2).run()
        self.assertGreater(time.time() - before, 0.2)

    def test_lost_locks(self) -> None:
        """The worker should be able to stop processing if need be"""
        temp_file = NamedTemporaryFile()
        jid = self.queue.put(SerialJob, json.dumps({"blocker_file": temp_file.name}))
        self.thread = Thread(target=Worker(["foo"], self.client, interval=0.2).run)
        self.thread.start()
        job = self.client.jobs[jid]
        assert job is not None and isinstance(job, AbstractJob)
        # Now, we'll timeout one of the jobs and ensure that kill is invoked
        while job.state != "running":
            time.sleep(0.01)
            job = self.client.jobs[jid]
            assert job is not None and isinstance(job, AbstractJob)
        job.timeout()
        temp_file.close()
        self.assertEqual(self.client.redis.brpop(["foo"], 1), ("foo", jid))

    def test_kill(self) -> None:
        """Should be able to fall on its sword if need be"""
        worker = SerialWorker([], self.client)
        worker.jid = "foo"
        thread = Thread(target=worker.kill, args=(worker.jid,))
        thread.start()
        thread.join()
        self.assertFalse(thread.is_alive())

    def test_kill_dead(self) -> None:
        """If we've moved on to another job, say so"""
        # If this tests runs to completion, it has succeeded
        worker = SerialWorker([], self.client)
        worker.kill("foo")

    def test_shutdown(self) -> None:
        """We should be able to shutdown a serial worker"""
        # If this test finishes, it passes
        worker = SerialWorker([], self.client, interval=0.1)
        worker.stop()
        worker.run()
