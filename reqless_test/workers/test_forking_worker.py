"""Test the forking worker"""

import json
import os
import signal
from threading import Thread
from typing import Optional

from reqless.abstract import AbstractJob
from reqless.workers.base_worker import BaseWorker
from reqless.workers.forking_worker import ForkingWorker
from reqless_test.common import TestReqless
from reqless_test.test_helpers import wait_for_condition


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

    def before_run(self) -> None:
        """Do not actually register signal handlers"""
        pass


class TestForkingWorker(TestReqless):
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
        thread_started = False

        def start_worker() -> None:
            nonlocal thread_started
            thread_started = True
            self.worker.run()

        thread = Thread(target=start_worker)
        self.thread = thread
        self.thread.start()
        wait_for_condition(lambda: thread_started)
        self.worker.shutdown = True
        self.queue.put(Foo, "{}")
        wait_for_condition(lambda: not thread.is_alive())

    def test_cwd(self) -> None:
        """Should set the child's cwd appropriately"""
        thread_started = False

        def start_worker() -> None:
            nonlocal thread_started
            thread_started = True
            self.worker.run()

        thread = Thread(target=start_worker)
        self.thread = thread
        self.thread.start()
        wait_for_condition(lambda: thread_started)
        jid = self.queue.put(CWD, "{}")

        self.worker.shutdown = True

        def job_is_complete() -> bool:
            job = self.client.jobs[jid]
            assert isinstance(job, AbstractJob)
            return job.state == "complete"

        wait_for_condition(job_is_complete)

        expected = os.path.join(os.getcwd(), "reqless-py-workers/sandbox-0")
        job = self.client.jobs[jid]
        assert isinstance(job, AbstractJob)
        wait_for_condition(lambda: not thread.is_alive())
        self.assertEqual(json.loads(job.data)["cwd"], expected)

    def test_spawn_klass_string(self) -> None:
        """Should be able to import by class string"""
        worker = PatchedForkingWorker(
            client=self.client,
            klass="reqless.workers.serial_worker.SerialWorker",
            queues=["foo"],
        )
        self.assertIsInstance(worker.spawn(), BaseWorker)

    def test_spawn(self) -> None:
        """It gives us back a worker instance"""
        self.assertIsInstance(self.worker.spawn(), BaseWorker)
