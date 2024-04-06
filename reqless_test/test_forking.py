"""Test the forking worker"""

import json
import os
import signal
import time
from threading import Thread
from typing import Optional, Tuple

from reqless.abstract import AbstractJob
from reqless.workers.forking import ForkingWorker
from reqless.workers.worker import Worker
from reqless_test.common import TestReqless


class Foo:
    """Dummy class"""

    @staticmethod
    def foo(job: AbstractJob) -> None:
        """Fall on your sword!"""
        os.kill(os.getpid(), signal.SIGKILL)


class CWD:
    """Completes with our current working directory"""

    @staticmethod
    def foo(job: AbstractJob) -> None:
        """Puts your current working directory in the job data"""
        data_dict = json.loads(job.data)
        data_dict["cwd"] = os.getcwd()
        job.data = json.dumps(data_dict)
        job.complete()
        os.kill(os.getpid(), signal.SIGKILL)


class PatchedForkingWorker(ForkingWorker):
    """A forking worker that doesn't register signal handlers"""

    def signals(self, signals: Tuple[str, ...] = ()) -> None:
        """Do not actually register signal handlers"""
        pass


class TestWorker(TestReqless):
    """Test the worker"""

    def setUp(self) -> None:
        TestReqless.setUp(self)
        self.client.worker_name = "worker"
        self.worker = PatchedForkingWorker(["foo"], self.client, workers=1, interval=1)
        self.queue = self.client.queues["foo"]
        self.thread: Optional[Thread] = None

    def tearDown(self) -> None:
        if self.thread:
            self.thread.join()
        TestReqless.tearDown(self)

    def test_respawn(self) -> None:
        """It respawns workers as needed"""
        self.thread = Thread(target=self.worker.run)
        self.thread.start()
        time.sleep(0.1)
        self.worker.shutdown = True
        self.queue.put(Foo, "{}")
        self.thread.join(1)
        self.assertFalse(self.thread.is_alive())

    def test_cwd(self) -> None:
        """Should set the child's cwd appropriately"""
        self.thread = Thread(target=self.worker.run)
        self.thread.start()
        time.sleep(0.1)
        self.worker.shutdown = True
        jid = self.queue.put(CWD, "{}")
        self.thread.join(1)
        self.assertFalse(self.thread.is_alive())
        expected = os.path.join(os.getcwd(), "reqless-py-workers/sandbox-0")
        job = self.client.jobs[jid]
        assert isinstance(job, AbstractJob)
        self.assertEqual(json.loads(job.data)["cwd"], expected)

    def test_spawn_klass_string(self) -> None:
        """Should be able to import by class string"""
        worker = PatchedForkingWorker(
            client=self.client,
            klass="reqless.workers.serial.SerialWorker",
            queues=["foo"],
        )
        self.assertIsInstance(worker.spawn(), Worker)

    def test_spawn(self) -> None:
        """It gives us back a worker instance"""
        self.assertIsInstance(self.worker.spawn(), Worker)
