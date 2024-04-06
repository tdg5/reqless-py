"""Our base worker"""

import json
import os
import signal
import sys
import threading
import traceback
from code import InteractiveConsole
from contextlib import contextmanager
from types import FrameType
from typing import Any, Dict, Generator, Iterable, List, Optional, Tuple, Union

from reqless import exceptions, logger
from reqless.abstract import (
    AbstractClient,
    AbstractJob,
    AbstractQueue,
    AbstractQueueResolver,
)
from reqless.listener import Listener
from reqless.queue_resolvers import TransformingQueueResolver


class Worker:
    """Worker. For doing work"""

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
        listener = Listener(self.client.redis, channels)
        thread = threading.Thread(target=self.listen, args=(listener,))
        thread.start()
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
                    self.kill(data["jid"])
            except Exception:
                logger.exception("Pubsub error")

    def kill(self, jid: str) -> None:
        """Stop processing the provided jid"""
        raise NotImplementedError('Derived classes must override "kill"')

    def run(self) -> None:
        """Run this worker"""
        raise NotImplementedError('Derived classes must override "run"')

    def signals(self, signals: Tuple[str, ...] = ("QUIT", "USR1", "USR2")) -> None:
        """Register our signal handler"""
        for sig in signals:
            signal.signal(getattr(signal, "SIG" + sig), self.handler)

    def stop(self) -> None:
        """Mark this for shutdown"""
        self.shutdown = True

    def handler(
        self, signum: int, frame: Optional[FrameType]
    ) -> None:  # pragma: no cover
        """Signal handler for this process"""
        if signum == signal.SIGQUIT:
            # QUIT - Finish processing, but don't do any more work after that
            self.stop()
        elif signum == signal.SIGUSR1:
            # USR1 - Print the backtrace
            message = "".join(traceback.format_stack(frame))
            message = "Signaled traceback for %s:\n%s" % (os.getpid(), message)
            print(message, file=sys.stderr)
            logger.warn(message)
        elif signum == signal.SIGUSR2:
            # USR2 - Enter a debugger
            # Much thanks to http://stackoverflow.com/questions/132058
            data = {"_frame": frame}  # Allow access to frame object.
            if frame:
                data.update(frame.f_globals)  # Unless shadowed by global
                data.update(frame.f_locals)
                # Build up a message with a traceback
                message = "".join(traceback.format_stack(frame))
            message = "Traceback:\n%s" % message
            InteractiveConsole(data).interact(message)
