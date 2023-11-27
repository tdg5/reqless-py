"""Test the serial worker"""

import time
from os import path
from tempfile import NamedTemporaryFile
from threading import Thread

from qless import logger
from qless.workers.serial import SerialWorker
from qless_test.common import TestQless


class SerialJob:
    """Dummy class"""

    @staticmethod
    def foo(job):
        """Dummy job"""
        blocker_file = job.data.get("blocker_file")
        if blocker_file:
            while path.exists(blocker_file):
                time.sleep(0.1)
        try:
            job.complete()
        except Exception:
            logger.exception("Unable to complete job %s" % job.jid)


class Worker(SerialWorker):
    """A worker that limits the number of jobs it runs"""

    def jobs(self):
        """Yield only a few jobs"""
        generator = SerialWorker.jobs(self)
        for _ in range(5):
            yield next(generator)

    def kill(self, jid):
        """We'll push a message to redis instead of falling on our sword"""
        self.client.redis.rpush("foo", jid)
        raise KeyboardInterrupt()

    def signals(self):
        """Do not set any signal handlers"""
        pass


class NoListenWorker(Worker):
    """A worker that just won't listen"""

    def listen(self, _):
        """Don't listen for lost locks"""
        pass


class TestWorker(TestQless):
    """Test the worker"""

    def setUp(self):
        TestQless.setUp(self)
        self.queue = self.client.queues["foo"]
        self.thread = None

    def tearDown(self):
        if self.thread:
            self.thread.join()
        TestQless.tearDown(self)

    def test_basic(self):
        """Can complete jobs in a basic way"""
        jids = [self.queue.put(SerialJob, {}) for _ in range(5)]
        NoListenWorker(["foo"], self.client, interval=0.2).run()
        states = []
        for jid in jids:
            job = self.client.jobs[jid]
            assert job is not None
            states.append(job.state)
        self.assertEqual(states, ["complete"] * 5)

    def test_jobs(self):
        """The jobs method yields None if there are no jobs"""
        worker = NoListenWorker(["foo"], self.client, interval=0.2)
        self.assertEqual(next(worker.jobs()), None)

    def test_sleeps(self):
        """Make sure the client sleeps if there aren't jobs to be had"""
        for _ in range(4):
            self.queue.put(SerialJob, {})
        before = time.time()
        NoListenWorker(["foo"], self.client, interval=0.2).run()
        self.assertGreater(time.time() - before, 0.2)

    def test_lost_locks(self):
        """The worker should be able to stop processing if need be"""
        temp_file = NamedTemporaryFile()
        jid = self.queue.put(SerialJob, {"blocker_file": temp_file.name})
        self.thread = Thread(target=Worker(["foo"], self.client, interval=0.2).run)
        self.thread.start()
        job = self.client.jobs[jid]
        assert job is not None
        # Now, we'll timeout one of the jobs and ensure that kill is invoked
        while job.state != "running":
            time.sleep(0.01)
            job = self.client.jobs[jid]
            assert job is not None
        job.timeout()
        temp_file.close()
        self.assertEqual(self.client.redis.brpop(["foo"], 1), ("foo", jid))

    def test_kill(self):
        """Should be able to fall on its sword if need be"""
        worker = SerialWorker([], self.client)
        worker.jid = "foo"
        thread = Thread(target=worker.kill, args=(worker.jid,))
        thread.start()
        thread.join()
        self.assertFalse(thread.is_alive())

    def test_kill_dead(self):
        """If we've moved on to another job, say so"""
        # If this tests runs to completion, it has succeeded
        worker = SerialWorker([], self.client)
        worker.kill("foo")

    def test_shutdown(self):
        """We should be able to shutdown a serial worker"""
        # If this test finishes, it passes
        worker = SerialWorker([], self.client, interval=0.1)
        worker.stop()
        worker.run()
