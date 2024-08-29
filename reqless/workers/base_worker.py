"""Our base worker"""

import json
import threading
from contextlib import contextmanager
from typing import Any, Dict, Generator, Iterable, List, Optional, Union

from reqless import exceptions, logger
from reqless.abstract import (
    AbstractClient,
    AbstractJob,
    AbstractQueue,
    AbstractQueueResolver,
)
from reqless.listener import Listener
from reqless.queue_resolvers import TransformingQueueResolver


class BaseWorker:
    """Base worker, for doing work"""

    def __init__(
        self,
        queues: Union[Iterable[Union[str, AbstractQueue]], AbstractQueueResolver],
        client: AbstractClient,
        interval: Optional[float] = None,
        resume: Optional[Union[bool, List[AbstractJob]]] = None,
        **kwargs: Any,
    ):
        self.client: AbstractClient = client

        queue_resolver: AbstractQueueResolver
        if isinstance(queues, AbstractQueueResolver):
            queue_resolver = queues
        else:
            queue_identifiers = [
                queue if isinstance(queue, str) else queue.name for queue in queues
            ]
            queue_resolver = TransformingQueueResolver(
                queue_identifiers=queue_identifiers
            )
        self.queue_resolver: AbstractQueueResolver = queue_resolver

        # Save our kwargs, since a common pattern to instantiate subworkers
        self.kwargs: Dict[str, Any] = {
            **kwargs,
            "interval": interval,
            "queue_resolver": queue_resolver,
            "resume": resume,
        }

        # Check for any jobs that we should resume. If 'resume' is the actual
        # value 'True', we should find all the resumable jobs we can. Otherwise,
        # we should interpret it as a list of jobs already
        self.resume: List[AbstractJob] = (
            self.resumable() if resume is True else (resume or [])
        )
        # How frequently we should poll for work
        self.interval: float = interval or 60.0
        # To mark whether or not we should shutdown after work is done
        self.shutdown: bool = False

    @property
    def queues(self) -> Iterable[AbstractQueue]:
        for queue_name in self.queue_resolver.resolve():
            yield self.client.queues[queue_name]

    def resumable(self) -> List[AbstractJob]:
        """Find all the jobs that we'd previously been working on"""
        # First, find the jids of all the jobs registered to this client.
        # Then, get the corresponding job objects
        jids = self.client.workers[self.client.worker_name]["jobs"]
        jobs = self.client.jobs.get(*jids)

        # We'll filter out all the jobs that aren't in any of the queues
        # we're working on.
        queue_names = set(self.queue_resolver.resolve())
        return [job for job in jobs if job.queue_name in queue_names]

    def jobs(
        self,
    ) -> Generator[Optional[AbstractJob], None, None]:
        """Generator for all the jobs"""
        # If we should resume work, then we should hand those out first,
        # assuming we can still heartbeat them
        for job in self.resume:
            try:
                if job.heartbeat():
                    yield job
            except exceptions.LostLockError:
                logger.exception("Cannot resume %s" % job.jid)
        while True:
            seen = False
            for queue in self.queues:
                popped_job = queue.pop()
                if popped_job:
                    assert not isinstance(popped_job, List)
                    seen = True
                    yield popped_job
            if not seen:
                yield None

    @contextmanager
    def listener(self) -> Generator[None, None, None]:
        """Listen for pubsub messages relevant to this worker in a thread"""
        channels = ["ql:w:" + self.client.worker_name]
        listener = Listener(self.client.database, channels)
        thread = threading.Thread(target=self.listen, args=(listener,))
        thread.start()
        listener.wait_until_listening()
        try:
            yield
        finally:
            listener.unlisten()
            thread.join()

    def listen(self, listener: Listener) -> None:
        """Listen for events that affect our ownership of a job"""
        for message in listener.listen():
            try:
                data = json.loads(message["data"])
                if data["event"] in ("canceled", "lock_lost", "put"):
                    self.halt_job_processing(data["jid"])
            except Exception:
                logger.exception("Pubsub error")

    def halt_job_processing(self, jid: str) -> None:  # pragma: no cover
        """Stop processing the provided jid"""
        raise NotImplementedError('Derived classes must override "halt_job_processing"')

    def run(self) -> None:  # pragma: no cover
        """Run this worker"""
        raise NotImplementedError('Derived classes must override "run"')

    def stop(self) -> None:
        """Mark this for shutdown"""
        self.shutdown = True
