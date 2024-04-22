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
from reqless.workers.base_worker import BaseWorker
from reqless.workers.util import create_sandbox, set_title


class SerialWorker(BaseWorker):
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

    def halt_job_processing(self, jid: str) -> None:
        """Since this method is most likely to be called by the listener, and
        the worker is definitely running in a different thread from the
        listenter, there's not a lot we can reliably do here. Trying to exit
        would only kill the listener thread, while the thread doing the actual
        work continued. So, in this scenario, we have to depend on the job
        doing a good job of heartbeating since that's the best way for the job
        to learn that it should halt. As such, do nothing."""
        pass

    def run(self) -> None:
        """Run jobs, popping one after another"""
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
