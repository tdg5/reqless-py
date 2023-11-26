"""Main qless business"""

import json
import pkgutil
import socket
import time
from typing import Any, Callable, Dict, List, Optional, Type, Union

import decorator
import redis
from redis import Redis
from redis.commands.core import Script

from qless.config import Config
from qless.exceptions import QlessError
from qless.job import Job, RecurringJob
from qless.listener import Events
from qless.logger import logger
from qless.queue import Queue
from qless.throttle import Throttle


def retry(*excepts: Type[Exception]) -> Callable:
    """A decorator to specify a bunch of exceptions that should be caught
    and the job retried. It turns out this comes up with relative frequency"""

    @decorator.decorator
    def wrapper(func: Callable[[Job], None], job: Job):
        """No docstring"""
        try:
            func(job)
        except tuple(excepts):
            job.retry()

    return wrapper


class Jobs:
    """Class for accessing jobs and job information lazily"""

    def __init__(self, client: "Client"):
        self.client: Client = client

    def complete(self, offset: int = 0, count: int = 25) -> List[str]:
        """Return the paginated jids of complete jobs"""
        return self.client("jobs", "complete", offset, count)

    def tracked(self) -> Dict[str, List[Job]]:
        """Return an array of job objects that are being tracked"""
        results = json.loads(self.client("track"))
        results["jobs"] = [Job(self, **job) for job in results["jobs"]]
        return results

    def tagged(self, tag: str, offset: int = 0, count: int = 25) -> Dict:
        """Return the paginated jids of jobs tagged with a tag"""
        return json.loads(self.client("tag", "get", tag, offset, count))

    def failed(
        self,
        group: Optional[str] = None,
        start: int = 0,
        limit: int = 25,
    ) -> Dict:
        """If no group is provided, this returns a JSON blob of the counts of
        the various types of failures known. If a type is provided, returns
        paginated job objects affected by that kind of failure."""
        if not group:
            return json.loads(self.client("failed"))
        else:
            results = json.loads(self.client("failed", group, start, limit))
            results["jobs"] = self.get(*results["jobs"])
            return results

    def get(self, *jids: str) -> List[Job]:
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


class Workers:
    """Class for accessing worker information lazily"""

    def __init__(self, client: "Client"):
        self.client: Client = client

    @property
    def counts(self) -> Dict:
        return json.loads(self.client("workers"))

    def __getitem__(self, worker_name: str) -> Dict:
        """Which jobs does a particular worker have running"""
        result = json.loads(self.client("workers", worker_name))
        result["jobs"] = result["jobs"] or []
        result["stalled"] = result["stalled"] or []
        return result


class Queues:
    """Class for accessing queues lazily"""

    def __init__(self, client: "Client"):
        self.client: Client = client

    @property
    def counts(self) -> Dict:
        return json.loads(self.client("queues"))

    def __getitem__(self, queue_name: str) -> Queue:
        """Get a queue object associated with the provided queue name"""
        return Queue(queue_name, self.client, self.client.worker_name)


class Throttles:
    def __init__(self, client: "Client"):
        self.client: Client = client

    def __getitem__(self, throttle_name: str) -> Throttle:
        return Throttle(
            client=self.client,
            name=throttle_name,
        )


class Client:
    """Basic qless client object."""

    def __init__(
        self,
        url: str = "redis://localhost:6379",
        hostname: Optional[str] = None,
        **kwargs,
    ):
        # This is our unique identifier as a worker
        self.worker_name: str = hostname or socket.gethostname()
        kwargs["decode_responses"] = True
        # This is just the redis instance we're connected to conceivably
        # someone might want to work with multiple instances simultaneously.
        self.redis: Redis = redis.Redis.from_url(url, **kwargs)
        self.jobs: Jobs = Jobs(self)
        self.queues: Queues = Queues(self)
        self.throttles: Throttles = Throttles(self)
        self.config: Config = Config(self)
        self.workers: Workers = Workers(self)
        self._events: Optional[Events] = None

        # We now have a single unified core script.
        data = pkgutil.get_data("qless", "lua/qless.lua")
        if data is None:
            raise RuntimeError("Failed to load qless lua!")
        self._lua: Script = self.redis.register_script(data)

    @property
    def events(self) -> Events:
        if self._events is None:
            self._events = Events(self.redis)
        return self._events

    def __call__(self, command: str, *args) -> Any:
        lua_args = [command, repr(time.time())]
        lua_args.extend(args)
        try:
            return self._lua(keys=[], args=lua_args)
        except redis.ResponseError as exc:
            raise QlessError(str(exc))

    def track(self, jid: str) -> bool:
        """Begin tracking this job"""
        return self("track", "track", jid) == "1"

    def untrack(self, jid: str) -> bool:
        """Stop tracking this job"""
        return self("track", "untrack", jid) == "1"

    def tags(self, offset: int = 0, count: int = 100) -> List[str]:
        """The most common tags among jobs"""
        return json.loads(self("tag", "top", offset, count))

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
    "QlessError",
    "Queue",
    "Queues",
    "RecurringJob",
    "Throttle",
    "Throttles",
    "Workers",
    "logger",
    "retry",
]
