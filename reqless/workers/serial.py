"""A worker that serially pops and complete jobs"""

import os
import time
from typing import Any, Iterable, List, Optional, Union

from reqless.abstract import (
    AbstractClient,
    AbstractJob,
    AbstractQueue,
    AbstractQueueResolver,
)
from reqless.workers.util import create_sandbox, set_title
from reqless.workers.worker import Worker


class SerialWorker(Worker):
    """A worker that just does serial work"""

    def __init__(
        self,
        queues: Union[Iterable[Union[str, AbstractQueue]], AbstractQueueResolver],
        client: AbstractClient,
        interval: Optional[float] = None,
        resume: Optional[Union[bool, List[AbstractJob]]] = None,
        **kwargs: Any,
    ):
        super().__init__(
            queues,
            client,
            interval,
            resume,
            **kwargs,
        )
        # The jid that we're working on at the moment
        self.jid: Optional[str] = None
        # This is the sandbox we use
        self._sandbox: str = kwargs.pop(
            "sandbox", os.path.join(os.getcwd(), "reqless-py-workers")
        )

    def kill(self, jid: str) -> None:
        """The best way to do this is to fall on our sword"""
        if jid == self.jid:
            exit(1)

    def run(self) -> None:
        """Run jobs, popping one after another"""
        # Register our signal handlers
        self.signals()

        with self.listener():
            for job in self.jobs():
                # If there was no job to be had, we should sleep a little bit
                if not job:
                    self.jid = None
                    set_title("Sleeping for %fs" % self.interval)
                    time.sleep(self.interval)
                else:
                    self.jid = job.jid
                    set_title("Working on %s (%s)" % (job.jid, job.klass_name))
                    with create_sandbox(self._sandbox):
                        job.sandbox = self._sandbox
                        job.process()
                if self.shutdown:
                    break
