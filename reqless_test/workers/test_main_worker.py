import json
import time
from tempfile import NamedTemporaryFile
from threading import Thread
from typing import Generator, Optional
from unittest.mock import patch

import pytest

from reqless.abstract import AbstractJob
from reqless.workers.main_worker import MainWorker
from reqless_test.common import BlockingJob, TestReqless


class ShortLivedMainWorker(MainWorker):
    """A worker that limits the number of jobs it runs"""

    def jobs(self) -> Generator[Optional[AbstractJob], None, None]:
        """Yield only a few jobs"""
        generator = MainWorker.jobs(self)
        for _ in range(5):
            yield next(generator)


class TestMainWorker(TestReqless):
    """Test the worker"""

    def setUp(self) -> None:
        TestReqless.setUp(self)
        self.queue = self.client.queues["foo"]

    def tearDown(self) -> None:
        TestReqless.tearDown(self)

    def test_signal_handlers_are_registered(self) -> None:
        """Test signal handler would be registered"""
        jids = [self.queue.put(BlockingJob, "{}") for _ in range(5)]
        with patch(
            "reqless.workers.main_worker.register_signal_handler",
        ) as register_signal_handler_mock:
            ShortLivedMainWorker(["foo"], self.client, interval=0.1).run()
        states = []
        for jid in jids:
            job = self.client.jobs[jid]
            assert job is not None and isinstance(job, AbstractJob)
            states.append(job.state)
        self.assertEqual(states, ["complete"] * 5)
        register_signal_handler_mock.assert_called_once()

    def test_halt_job_processing(self) -> None:
        """The worker should be able to stop processing if need be"""
        temp_file = NamedTemporaryFile()
        jid = self.queue.put(BlockingJob, json.dumps({"blocker_file": temp_file.name}))

        def job_killer() -> None:
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

        thread = Thread(target=job_killer)
        thread.start()
        with pytest.raises(KeyboardInterrupt) as exinfo:
            ShortLivedMainWorker(["foo"], self.client, interval=0.2).run()
        assert KeyboardInterrupt == exinfo.type
        thread.join()
