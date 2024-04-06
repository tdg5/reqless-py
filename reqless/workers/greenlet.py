"""A Gevent-based worker"""

import os
from typing import Any, Dict, Iterable, List, Optional, Union

import gevent
from gevent import Greenlet
from gevent.pool import Pool

from reqless import logger
from reqless.abstract import (
    AbstractClient,
    AbstractJob,
    AbstractQueue,
    AbstractQueueResolver,
)
from reqless.workers.util import create_sandbox
from reqless.workers.worker import Worker


class GeventWorker(Worker):
    """A Gevent-based worker"""

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
        # Should we shut down after this?
        self.shutdown = False
        # A mapping of jids to the greenlets handling them
        self.greenlets: Dict[str, Greenlet] = {}
        count = kwargs.pop("greenlets", 10)
        self.pool = Pool(count)
        # A list of the sandboxes that we'll use
        sandbox_path = kwargs.pop(
            "sandbox_path", os.path.join(os.getcwd(), "reqless-py-workers")
        )
        self.sandboxes: List[str] = [
            os.path.join(sandbox_path, "greenlet-%i" % i) for i in range(count)
        ]

    def process(self, job: AbstractJob) -> None:
        """Process a job"""
        sandbox = self.sandboxes.pop(0)
        try:
            with create_sandbox(sandbox):
                job.sandbox = sandbox
                job.process()
        finally:
            # Delete its entry from our greenlets mapping
            self.greenlets.pop(job.jid, None)
            self.sandboxes.append(sandbox)

    def kill(self, jid: str) -> None:
        """Stop the greenlet processing the provided jid"""
        greenlet = self.greenlets.get(jid)
        if greenlet is not None:
            logger.warn("Lost ownership of %s" % jid)
            greenlet.kill()

    def run(self) -> None:
        """Work on jobs"""
        # Register signal handlers
        self.signals()

        # Start listening
        with self.listener():
            try:
                generator = self.jobs()
                while not self.shutdown:
                    self.pool.wait_available()
                    job = next(generator)
                    if job:
                        # For whatever reason, doing imports within a greenlet
                        # (there's one implicitly invoked in job.process), was
                        # throwing exceptions. The simplest way to get around
                        # this is to force the import to happen before the
                        # greenlet is spawned.
                        job.klass
                        greenlet = Greenlet(self.process, job)
                        self.greenlets[job.jid] = greenlet
                        self.pool.start(greenlet)
                    else:
                        logger.debug("Sleeping for %fs" % self.interval)
                        gevent.sleep(self.interval)
            except StopIteration:
                logger.info("Exhausted jobs")
            finally:
                logger.info("Waiting for greenlets to finish")
                self.pool.join()
