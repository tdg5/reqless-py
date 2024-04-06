"""Main reqless business"""

import json
import pkgutil
import socket
import time
from typing import Any, Callable, Dict, List, Optional, Type, Union

import decorator
import redis
from redis import Redis
from redis.commands.core import Script

from reqless.abstract import (
    AbstractClient,
    AbstractConfig,
    AbstractJob,
    AbstractJobs,
    AbstractQueue,
    AbstractQueues,
    AbstractThrottles,
    AbstractWorkers,
)
from reqless.config import Config
from reqless.exceptions import ReqlessError
from reqless.job import Job, RecurringJob
from reqless.listener import Events
from reqless.logger import logger
from reqless.queue import Queue
from reqless.throttle import Throttle


def retry(*excepts: Type[Exception]) -> Callable:
    """A decorator to specify a bunch of exceptions that should be caught
    and the job retried. It turns out this comes up with relative frequency"""

    @decorator.decorator
    def wrapper(func: Callable[[Job], None], job: Job) -> None:
        """No docstring"""
        try:
            func(job)
        except tuple(excepts):
            job.retry()

    return wrapper


class Jobs(AbstractJobs):
    """Class for accessing jobs and job information lazily"""

    def __init__(self, client: AbstractClient):
        self.client: AbstractClient = client

    def complete(self, offset: int = 0, count: int = 25) -> List[str]:
        """Return the paginated jids of complete jobs"""
        response: List[str] = self.client("jobs", "complete", offset, count)
        return response

    def tracked(self) -> Dict[str, List[Any]]:
        """Return an array of job objects that are being tracked"""
        results: Dict[str, Any] = json.loads(self.client("track"))
        results["jobs"] = [Job(self.client, **job) for job in results["jobs"]]
        return results

    def tagged(self, tag: str, offset: int = 0, count: int = 25) -> Dict[str, Any]:
        """Return the paginated jids of jobs tagged with a tag"""
        response: Dict[str, Any] = json.loads(
            self.client("tag", "get", tag, offset, count)
        )
        return response

    def failed(
        self,
        group: Optional[str] = None,
        start: int = 0,
        limit: int = 25,
    ) -> Dict[str, Any]:
        """If no group is provided, this returns a JSON blob of the counts of
        the various types of failures known. If a type is provided, returns
        paginated job objects affected by that kind of failure."""
        results: Dict[str, Any]
        if not group:
            results = json.loads(self.client("failed"))
        else:
            results = json.loads(self.client("failed", group, start, limit))
            results["jobs"] = self.get(*results["jobs"])
        return results

    def get(self, *jids: str) -> List[AbstractJob]:
        """Return jobs objects for all the jids"""
        if jids:
            return [
                Job(self.client, **j)
                for j in json.loads(self.client("multiget", *jids))
            ]
        return []

    def __getitem__(self, jid: str) -> Optional[Union[Job, RecurringJob]]:
        """Get a job object corresponding to that jid, or ``None`` if it
        doesn't exist"""
        results = self.client("get", jid)
        if not results:
            results = self.client("recur.get", jid)
            if not results:
                return None
            return RecurringJob(self.client, **json.loads(results))
        return Job(self.client, **json.loads(results))


class Workers(AbstractWorkers):
    """Class for accessing worker information lazily"""

    def __init__(self, client: AbstractClient):
        self.client: AbstractClient = client

    @property
    def counts(self) -> Dict[str, Any]:
        counts: Dict[str, Any] = json.loads(self.client("workers"))
        return counts

    def __getitem__(self, worker_name: str) -> Dict[str, Any]:
        """Which jobs does a particular worker have running"""
        result: Dict[str, Any] = json.loads(self.client("workers", worker_name))
        result["jobs"] = result["jobs"] or []
        result["stalled"] = result["stalled"] or []
        return result


class Queues(AbstractQueues):
    """Class for accessing queues lazily"""

    def __init__(self, client: AbstractClient):
        self.client: AbstractClient = client

    @property
    def counts(self) -> Dict:
        counts: Dict = json.loads(self.client("queues"))
        return counts

    def __getitem__(self, queue_name: str) -> AbstractQueue:
        """Get a queue object associated with the provided queue name"""
        return Queue(queue_name, self.client, self.client.worker_name)


class Throttles(AbstractThrottles):
    def __init__(self, client: AbstractClient):
        self.client: AbstractClient = client

    def __getitem__(self, throttle_name: str) -> Throttle:
        return Throttle(
            client=self.client,
            name=throttle_name,
        )


class Client(AbstractClient):
    """Basic reqless client object."""

    def __init__(
        self,
        url: str = "redis://localhost:6379",
        hostname: Optional[str] = None,
        **kwargs: Any,
    ):
        # This is our unique identifier as a worker
        self._worker_name: str = hostname or socket.gethostname()
        kwargs["decode_responses"] = True
        # This is just the redis instance we're connected to conceivably
        # someone might want to work with multiple instances simultaneously.
        self._redis: Redis = redis.Redis.from_url(url, **kwargs)
        self._jobs: AbstractJobs = Jobs(self)
        self._queues: AbstractQueues = Queues(self)
        self._throttles: AbstractThrottles = Throttles(self)
        self._config: AbstractConfig = Config(self)
        self._workers: AbstractWorkers = Workers(self)
        self._events: Optional[Events] = None

        # We now have a single unified core script.
        data = pkgutil.get_data("reqless", "lua/qless.lua")
        if data is None:
            raise RuntimeError("Failed to load reqless lua!")
        self._lua: Script = self.redis.register_script(data)

    @property
    def config(self) -> AbstractConfig:
        return self._config

    @property
    def jobs(self) -> AbstractJobs:
        return self._jobs

    @property
    def queues(self) -> AbstractQueues:
        return self._queues

    @property
    def redis(self) -> Redis:
        return self._redis

    @property
    def throttles(self) -> AbstractThrottles:
        return self._throttles

    @property
    def workers(self) -> AbstractWorkers:
        return self._workers

    @property
    def worker_name(self) -> str:
        return self._worker_name

    @worker_name.setter
    def worker_name(self, value: str) -> None:
        self._worker_name = value

    @property
    def events(self) -> Events:
        if self._events is None:
            self._events = Events(self.redis)
        return self._events

    def __call__(self, command: str, *args: Any) -> Any:
        lua_args = [command, repr(time.time())]
        lua_args.extend(args)
        try:
            return self._lua(keys=[], args=lua_args)
        except redis.ResponseError as exc:
            raise ReqlessError(str(exc))

    def track(self, jid: str) -> bool:
        """Begin tracking this job"""
        response: str = self("track", "track", jid)
        return response == "1"

    def untrack(self, jid: str) -> bool:
        """Stop tracking this job"""
        response: str = self("track", "untrack", jid)
        return response == "1"

    def tags(self, offset: int = 0, count: int = 100) -> List[str]:
        """The most common tags among jobs"""
        tags: List[str] = json.loads(self("tag", "top", offset, count))
        return tags

    def unfail(self, group: str, queue: str, count: int = 500) -> int:
        """Move jobs from the failed group to the provided queue"""
        unfail_count = self("unfail", queue, group, count)
        return int(unfail_count)


__all__ = [
    "Client",
    "Config",
    "Events",
    "Job",
    "Jobs",
    "Queue",
    "Queues",
    "RecurringJob",
    "ReqlessError",
    "Throttle",
    "Throttles",
    "Workers",
    "logger",
    "retry",
]
