from typing import Generator, Optional
from unittest.mock import patch

from reqless.abstract import AbstractJob
from reqless.workers.main_worker import MainWorker
from reqless_test.common import NoopJob, TestReqless


class ShortLivedMainWorker(MainWorker):
    """A worker that limits the number of jobs it runs"""

    def jobs(self) -> Generator[Optional[AbstractJob], None, None]:
        """Yield only a few jobs"""
        generator = MainWorker.jobs(self)
        for _ in range(5):
            yield next(generator)

    def kill(self, jid: str) -> None:
        raise KeyboardInterrupt()


class TestMainWorker(TestReqless):
    """Test the worker"""

    def setUp(self) -> None:
        TestReqless.setUp(self)
        self.queue = self.client.queues["foo"]

    def tearDown(self) -> None:
        TestReqless.tearDown(self)

    def test_signal_handlers_are_registered(self) -> None:
        """Test signal handler would be registered"""
        jids = [self.queue.put(NoopJob, "{}") for _ in range(5)]
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
