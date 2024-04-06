"""Our Queue and supporting classes"""

import json
import time
import uuid
from typing import Any, Dict, List, Optional, Type, Union

from reqless.abstract import (
    AbstractClient,
    AbstractJob,
    AbstractQueue,
    AbstractQueueJobs,
    AbstractThrottle,
)
from reqless.job import Job


class Jobs(AbstractQueueJobs):
    """A proxy object for queue-specific job information"""

    def __init__(self, name: str, client: AbstractClient):
        self._name: str = name
        self.client: AbstractClient = client

    @property
    def name(self) -> str:
        return self._name

    def depends(self, offset: int = 0, count: int = 25) -> List[str]:
        """Return all the currently dependent jobs"""
        response: List[str] = self.client("jobs", "depends", self.name, offset, count)
        return response

    def recurring(self, offset: int = 0, count: int = 25) -> List[str]:
        """Return all the recurring jobs"""
        response: List[str] = self.client("jobs", "recurring", self.name, offset, count)
        return response

    def running(self, offset: int = 0, count: int = 25) -> List[str]:
        """Return all the currently-running jobs"""
        response: List[str] = self.client("jobs", "running", self.name, offset, count)
        return response

    def scheduled(self, offset: int = 0, count: int = 25) -> List[str]:
        """Return all the currently-scheduled jobs"""
        response: List[str] = self.client("jobs", "scheduled", self.name, offset, count)
        return response

    def stalled(self, offset: int = 0, count: int = 25) -> List[str]:
        """Return all the currently-stalled jobs"""
        response: List[str] = self.client("jobs", "stalled", self.name, offset, count)
        return response


class Queue(AbstractQueue):
    """The Queue class"""

    def __init__(self, name: str, client: AbstractClient, worker_name: str):
        self._name: str = name
        self.client: AbstractClient = client
        self.worker_name: str = worker_name
        self._jobs: Optional[AbstractQueueJobs] = None

    @property
    def counts(self) -> Dict[str, Any]:
        response: Dict[str, Any] = json.loads(self.client("queues", self.name))
        return response

    @property
    def heartbeat(self) -> int:
        config = self.client.config.all
        return int(config.get(self.name + "-heartbeat", config.get("heartbeat", 60)))

    @heartbeat.setter
    def heartbeat(self, value: int) -> None:
        self.client.config[self.name + "-heartbeat"] = value

    @property
    def jobs(self) -> AbstractQueueJobs:
        if self._jobs is None:
            self._jobs = Jobs(self.name, self.client)

        return self._jobs

    @property
    def name(self) -> str:
        return self._name

    @property
    def throttle(self) -> AbstractThrottle:
        return self.client.throttles[f"ql:q:{self.name}"]

    def class_string(self, klass: Union[str, Type]) -> str:
        """Return a string representative of the class"""
        if isinstance(klass, str):
            return klass
        return klass.__module__ + "." + klass.__name__

    def pause(self) -> None:
        self.client("pause", self.name)

    def unpause(self) -> None:
        self.client("unpause", self.name)

    def put(
        self,
        klass: Union[str, Type],
        data: str,
        priority: Optional[int] = None,
        tags: Optional[List[str]] = None,
        delay: Optional[int] = None,
        retries: Optional[int] = None,
        jid: Optional[str] = None,
        depends: Optional[List[str]] = None,
        throttles: Optional[List[str]] = None,
    ) -> str:
        """Either create a new job in the provided queue with the provided
        attributes, or move that job into that queue. If the job is being
        serviced by a worker, subsequent attempts by that worker to either
        `heartbeat` or `complete` the job should fail and return `false`.

        The `priority` argument should be negative to be run sooner rather
        than later, and positive if it's less important. The `tags` argument
        should be a JSON array of the tags associated with the instance and
        the `valid after` argument should be in how many seconds the instance
        should be considered actionable."""
        response: str = self.client(
            "put",
            self.worker_name,
            self.name,
            jid or uuid.uuid4().hex,
            self.class_string(klass),
            data,
            delay or 0,
            "priority",
            priority or 0,
            "tags",
            json.dumps(tags or []),
            "retries",
            retries or 5,
            "depends",
            json.dumps(depends or []),
            "throttles",
            json.dumps(throttles or []),
        )
        return response

    """Same function as above but check if the job already exists in the DB beforehand.
    You can re-queue for instance failed ones."""

    def requeue(
        self,
        klass: Union[str, Type],
        data: str,
        priority: Optional[int] = None,
        tags: Optional[List[str]] = None,
        delay: Optional[int] = None,
        retries: Optional[int] = None,
        jid: Optional[str] = None,
        depends: Optional[List[str]] = None,
        throttles: Optional[List[str]] = None,
    ) -> str:
        response: str = self.client(
            "requeue",
            self.worker_name,
            self.name,
            jid or uuid.uuid4().hex,
            self.class_string(klass),
            data,
            delay or 0,
            "priority",
            priority or 0,
            "tags",
            json.dumps(tags or []),
            "retries",
            retries or 5,
            "depends",
            json.dumps(depends or []),
            "throttles",
            json.dumps(throttles or []),
        )
        return response

    def recur(
        self,
        klass: Union[str, Type[AbstractJob]],
        data: str,
        interval: Optional[int] = None,
        offset: Optional[int] = 0,
        priority: Optional[int] = None,
        tags: Optional[List[str]] = None,
        retries: Optional[int] = None,
        jid: Optional[str] = None,
        throttles: Optional[List[str]] = None,
    ) -> str:
        """Place a recurring job in this queue"""
        response: str = self.client(
            "recur",
            self.name,
            jid or uuid.uuid4().hex,
            self.class_string(klass),
            data,
            "interval",
            interval,
            offset,
            "priority",
            priority or 0,
            "tags",
            json.dumps(tags or []),
            "retries",
            retries or 5,
            "throttles",
            json.dumps(throttles or []),
        )
        return response

    def pop(
        self, count: Optional[int] = None
    ) -> Union[AbstractJob, List[AbstractJob], None]:
        """Passing in the queue from which to pull items, the current time,
        when the locks for these returned items should expire, and the number
        of items to be popped off."""
        results: List[AbstractJob] = [
            Job(self.client, **job)
            for job in json.loads(
                self.client("pop", self.name, self.worker_name, count or 1)
            )
        ]
        if count is None:
            return (len(results) and results[0]) or None
        return results

    def peek(
        self, count: Optional[int] = None
    ) -> Union[AbstractJob, List[AbstractJob], None]:
        """Similar to the pop command, except that it merely peeks at the next
        items"""
        results: List[AbstractJob] = [
            Job(self.client, **rec)
            for rec in json.loads(self.client("peek", self.name, count or 1))
        ]
        if count is None:
            return (len(results) and results[0]) or None
        return results

    def stats(self, date: Optional[str] = None) -> Dict:
        """Return the current statistics for a given queue on a given date.
        The results are returned are a JSON blob::

            {
                'total'    : ...,
                'mean'     : ...,
                'variance' : ...,
                'histogram': [
                    ...
                ]
            }

        The histogram's data points are at the second resolution for the first
        minute, the minute resolution for the first hour, the 15-minute
        resolution for the first day, the hour resolution for the first 3
        days, and then at the day resolution from there on out. The
        `histogram` key is a list of those values."""
        response: Dict = json.loads(
            self.client("stats", self.name, date or repr(time.time()))
        )
        return response

    def __len__(self) -> int:
        response: int = self.client("length", self.name)
        return response
