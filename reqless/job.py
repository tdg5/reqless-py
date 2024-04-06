"""Both the regular Job and RecurringJob classes"""

import json
import time
import traceback
import types
from typing import Any, Dict, List, Optional, Type, Union

from reqless.abstract import (
    AbstractBaseJob,
    AbstractClient,
    AbstractJob,
    AbstractQueue,
    AbstractRecurringJob,
)
from reqless.exceptions import LostLockError, ReqlessError
from reqless.importer import Importer
from reqless.logger import logger


class BaseJob(AbstractBaseJob):
    def __init__(self, client: AbstractClient, **kwargs: Any):
        self.client: AbstractClient = client
        self._data: str = kwargs["data"]
        self._jid: str = kwargs["jid"]
        self._klass: Optional[Type] = None
        self._klass_name: str = kwargs["klass"]
        self._priority: int = kwargs["priority"]
        self._queue: Optional[AbstractQueue] = None
        self._queue_name: str = kwargs["queue"]
        self._sandbox: Optional[str] = None
        # Because of how Lua parses JSON, empty tags comes through as {}
        self._tags: List[str] = kwargs.get("tags") or []
        self._throttles: List[str] = kwargs.get("throttles") or []

    @property
    def data(self) -> str:
        return self._data

    @data.setter
    def data(self, value: str) -> None:
        self._data = value

    @property
    def jid(self) -> str:
        return self._jid

    @jid.setter
    def jid(self, value: str) -> None:
        self._jid = value

    @property
    def klass(self) -> Type:
        if self._klass is None:
            self._klass = Importer.import_class(class_name=self.klass_name)

        return self._klass

    @klass.setter
    def klass(self, value: Type) -> None:
        self._klass = value
        name = value.__module__ + "." + value.__name__
        self._klass_name = name

    @property
    def klass_name(self) -> str:
        return self._klass_name

    @klass_name.setter
    def klass_name(self, value: str) -> None:
        self._klass_name = value

    @property
    def priority(self) -> int:
        return self._priority

    @priority.setter
    def priority(self, value: int) -> None:
        self.client("priority", self.jid, value)
        self._priority = value

    @property
    def queue(self) -> AbstractQueue:
        if self._queue is None:
            self._queue = self.client.queues[self.queue_name]
        return self._queue

    @property
    def queue_name(self) -> str:
        return self._queue_name

    @queue_name.setter
    def queue_name(self, value: str) -> None:
        self._queue_name = value

    @property
    def sandbox(self) -> Optional[str]:
        return self._sandbox

    @sandbox.setter
    def sandbox(self, value: Optional[str]) -> None:
        self._sandbox = value

    @property
    def tags(self) -> List[str]:
        return self._tags

    @tags.setter
    def tags(self, value: List[str]) -> None:
        self._tags = value

    @property
    def throttles(self) -> List[str]:
        return self._throttles

    @throttles.setter
    def throttles(self, value: List[str]) -> None:
        self._throttles = value

    def cancel(self) -> List[str]:
        """Cancel a job. It will be deleted from the system, the thinking
        being that if you don't want to do any work on it, it shouldn't be in
        the queuing system."""
        response: List[str] = self.client("cancel", self.jid)
        return response

    def tag(self, *tags: str) -> List[str]:
        """Tag a job with additional tags"""
        response: List[str] = self.client("tag", "add", self.jid, *tags)
        return response

    def untag(self, *tags: str) -> List[str]:
        """Remove tags from a job"""
        response: List[str] = self.client("tag", "remove", self.jid, *tags)
        return response


class Job(BaseJob, AbstractJob):
    """The Job class"""

    def __init__(self, client: AbstractClient, **kwargs: Any):
        super().__init__(client, **kwargs)
        self.client: AbstractClient = client
        self._state: str = kwargs["state"]
        self._failure: Optional[Dict] = kwargs["failure"]
        # Because of how Lua parses JSON, empty lists come through as {}
        self._dependents: List[str] = kwargs["dependents"] or []
        self._dependencies: List[str] = kwargs["dependencies"] or []
        self._tracked: bool = kwargs["tracked"]
        self._worker_name: str = kwargs["worker"]
        self._retries_left: int = kwargs["remaining"]
        self._expires_at: float = kwargs["expires"]
        self._original_retires: int = kwargs["retries"]
        self._history: List[Dict] = kwargs["history"] or []

    @property
    def dependencies(self) -> List[str]:
        return self._dependencies

    @dependencies.setter
    def dependencies(self, value: List[str]) -> None:
        self._dependencies = value

    @property
    def dependents(self) -> List[str]:
        return self._dependents

    @property
    def expires_at(self) -> float:
        return self._expires_at

    @expires_at.setter
    def expires_at(self, value: float) -> None:
        self._expires_at = value

    @property
    def failure(self) -> Optional[Dict]:
        return self._failure

    @failure.setter
    def failure(self, value: Optional[Dict]) -> None:
        self._failure = value

    @property
    def history(self) -> List[Dict]:
        return self._history

    @property
    def original_retries(self) -> int:
        return self._original_retires

    @property
    def retries_left(self) -> int:
        return self._retries_left

    @property
    def state(self) -> str:
        return self._state

    @property
    def ttl(self) -> float:
        return self.expires_at - time.time()

    @property
    def tracked(self) -> bool:
        return self._tracked

    @property
    def worker_name(self) -> str:
        return self._worker_name

    def __repr__(self) -> str:
        return "<%s %s>" % (self.klass_name, self.jid)

    def process(self) -> None:
        """Load the module containing your class, and run the appropriate
        method. For example, if this job was popped from the queue
        ``testing``, then this would invoke the ``testing`` staticmethod of
        your class."""
        try:
            method = getattr(
                self.klass, self.queue_name, getattr(self.klass, "process", None)
            )
        except Exception as exc:
            # We failed to import the module containing this class
            logger.exception("Failed to import %s", self.klass_name)
            self.fail(
                self.queue_name + "-" + exc.__class__.__name__,
                "Failed to import %s" % self.klass_name,
            )
            return

        if not method:
            logger.error(
                'Failed %s : %s is missing a method "%s" or "process"',
                self.jid,
                self.klass_name,
                self.queue_name,
            )
            self.fail(
                self.queue_name + "-method-missing",
                self.klass_name
                + ' is missing a method "'
                + self.queue_name
                + '" or "process"',
            )
            return

        if not isinstance(method, types.FunctionType):
            logger.error(
                "Failed %s in %s : %s is not static",
                self.jid,
                self.queue_name,
                repr(method),
            )
            self.fail(self.queue_name + "-method-type", repr(method) + " is not static")
            return

        try:
            logger.info("Processing %s in %s", self.jid, self.queue_name)
            method(self)
            logger.info("Completed %s in %s", self.jid, self.queue_name)
        except Exception as exc:
            # Make error type based on exception type
            logger.exception(
                "Failed %s in %s: %s", self.jid, self.queue_name, repr(method)
            )
            self.fail(
                self.queue_name + "-" + exc.__class__.__name__,
                traceback.format_exc(),
            )

    def move(
        self,
        queue: str,
        delay: Optional[int] = 0,
        depends: Optional[List[str]] = None,
    ) -> str:
        """Move this job out of its existing state and into another queue. If
        a worker has been given this job, then that worker's attempts to
        heartbeat that job will fail. Like ``Queue.put``, this accepts a
        delay, and dependencies"""
        logger.info("Moving %s to %s from %s", self.jid, queue, self.queue_name)
        response: str = self.client(
            "put",
            self.worker_name,
            queue,
            self.jid,
            self.klass_name,
            self.data,
            delay,
            "depends",
            json.dumps(depends or []),
            "throttles",
            json.dumps(self.throttles or []),
        )
        return response

    def complete(
        self,
        nextq: Optional[str] = None,
        delay: Optional[int] = None,
        depends: Optional[List[str]] = None,
    ) -> bool:
        """Turn this job in as complete, optionally advancing it to another
        queue. Like ``Queue.put`` and ``move``, it accepts a delay, and
        dependencies"""
        if nextq:
            logger.info("Advancing %s to %s from %s", self.jid, nextq, self.queue_name)
            return (
                self.client(
                    "complete",
                    self.jid,
                    self.client.worker_name,
                    self.queue_name,
                    self.data,
                    "next",
                    nextq,
                    "delay",
                    delay or 0,
                    "depends",
                    json.dumps(depends or []),
                )
                or False
            )
        else:
            logger.info("Completing %s", self.jid)
            return (
                self.client(
                    "complete",
                    self.jid,
                    self.client.worker_name,
                    self.queue_name,
                    self.data,
                )
                or False
            )

    def heartbeat(self) -> float:
        """Renew the heartbeat, if possible, and optionally update the job's
        user data."""
        logger.debug("Heartbeating %s (ttl = %s)", self.jid, self.ttl)
        try:
            self.expires_at = float(
                self.client(
                    "heartbeat",
                    self.jid,
                    self.client.worker_name,
                    self.data,
                )
                or 0
            )
        except ReqlessError:
            raise LostLockError(self.jid)
        logger.debug("Heartbeated %s (ttl = %s)", self.jid, self.ttl)
        return self.expires_at

    def fail(self, group: str, message: str) -> Union[bool, str]:
        """Mark the particular job as failed, with the provided type, and a
        more specific message. By `type`, we mean some phrase that might be
        one of several categorical modes of failure. The `message` is
        something more job-specific, like perhaps a traceback.

        This method should __not__ be used to note that a job has been dropped
        or has failed in a transient way. This method __should__ be used to
        note that a job has something really wrong with it that must be
        remedied.

        The motivation behind the `type` is so that similar errors can be
        grouped together. Optionally, updated data can be provided for the job.
        A job in any state can be marked as failed. If it has been given to a
        worker as a job, then its subsequent requests to heartbeat or complete
        that job will fail. Failed jobs are kept until they are canceled or
        completed. __Returns__ the id of the failed job if successful, or
        `False` on failure."""
        logger.warn("Failing %s (%s): %s", self.jid, group, message)
        response: bool = self.client(
            "fail",
            self.jid,
            self.client.worker_name,
            group,
            message,
            self.data,
        )
        return response or False

    def track(self) -> bool:
        """Begin tracking this job"""
        response: str = self.client("track", "track", self.jid)
        return response == "1"

    def untrack(self) -> bool:
        """Stop tracking this job"""
        response: str = self.client("track", "untrack", self.jid)
        return response == "1"

    def retry(
        self,
        delay: int = 0,
        group: Optional[str] = None,
        message: Optional[str] = None,
    ) -> int:
        """Retry this job in a little bit, in the same queue. This is meant
        for the times when you detect a transient failure yourself"""
        args: List[str] = [
            "retry",
            self.jid,
            self.queue_name,
            self.worker_name,
            str(delay),
        ]
        if group is not None and message is not None:
            args.append(group)
            args.append(message)
        response: int = self.client(*args)
        return response

    def depend(self, *args: str) -> bool:
        """If and only if a job already has other dependencies, this will add
        more jids to the list of this job's dependencies."""
        return self.client("depends", self.jid, "on", *args) or False

    def undepend(self, *args: str, **kwargs: bool) -> bool:
        """Remove specific (or all) job dependencies from this job:

        job.remove(jid1, jid2)
        job.remove(all=True)"""
        if kwargs.get("all", False):
            return self.client("depends", self.jid, "off", "all") or False
        else:
            return self.client("depends", self.jid, "off", *args) or False

    def timeout(self) -> None:
        """Time out this job"""
        self.client("timeout", self.jid)


class RecurringJob(BaseJob, AbstractRecurringJob):
    """Recurring Job object"""

    def __init__(self, client: AbstractClient, **kwargs: Any):
        super().__init__(client, **kwargs)
        self._retries: int = kwargs["retries"]
        self._interval: int = kwargs["interval"]
        self._count: int = kwargs["count"]

    @property
    def count(self) -> int:
        return self._count

    @count.setter
    def count(self, value: int) -> None:
        self.client("recur.update", self.jid, "count", value)

    @property
    def data(self) -> str:
        return self._data

    @data.setter
    def data(self, value: str) -> None:
        self._data = value
        self.client("recur.update", self.jid, "data", self.data)

    @property
    def interval(self) -> int:
        return self._interval

    @interval.setter
    def interval(self, value: int) -> None:
        self._interval = value
        self.client("recur.update", self.jid, "interval", value)

    @property
    def priority(self) -> int:
        return self._priority

    @priority.setter
    def priority(self, value: int) -> None:
        self.client("recur.update", self.jid, "priority", value)

    @property
    def retries(self) -> int:
        return self._retries

    @retries.setter
    def retries(self, value: int) -> None:
        self.client("recur.update", self.jid, "retries", value)

    @property
    def klass(self) -> Type:
        return super().klass

    @klass.setter
    def klass(self, value: Type) -> None:
        name = value.__module__ + "." + value.__name__
        self.client("recur.update", self.jid, "klass", name)
        self._klass = value
        self._klass_name = name

    @property
    def next(self) -> Optional[float]:
        return self.client.redis.zscore("ql:q:" + self.queue_name + "-recur", self.jid)

    def move(self, queue: str) -> bool:
        """Make this recurring job attached to another queue"""
        response: bool = self.client("recur.update", self.jid, "queue", queue)
        return response

    def cancel(self) -> List[str]:
        """Cancel all future recurring jobs"""
        self.client("unrecur", self.jid)
        return [self.jid]

    def tag(self, *tags: str) -> List[str]:
        """Add tags to this recurring job"""
        response: List[str] = self.client("recur.tag", self.jid, *tags)
        return response

    def untag(self, *tags: str) -> List[str]:
        """Remove tags from this job"""
        response: List[str] = self.client("recur.untag", self.jid, *tags)
        return response
