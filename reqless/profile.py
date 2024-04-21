"""Some utilities for profiling"""

from collections import defaultdict
from types import TracebackType
from typing import Any, Dict, Optional, Type

from redis import Redis
from redis.connection import ConnectionPool, DefaultParser

from reqless.abstract import AbstractClient


class Profiler:
    """Profiling a series of requests. Initialized with a Reqless client"""

    @staticmethod
    def clone(client: AbstractClient) -> Redis:
        """Clone the data structure server client to be slowlog-compatible"""
        kwargs = client.database.connection_pool.connection_kwargs
        kwargs["parser_class"] = DefaultParser
        pool = ConnectionPool(**kwargs)
        return Redis(connection_pool=pool)

    @staticmethod
    def pretty(timings: Dict, label: str) -> None:
        """Print timing stats"""
        results = [(sum(values), len(values), key) for key, values in timings.items()]
        print(label)
        print("=" * 65)
        print(
            "%20s => %13s | %8s | %13s"
            % ("Command", "Average", "# Calls", "Total time")
        )
        print("-" * 65)
        for total, length, key in sorted(results, reverse=True):
            print(
                "%20s => %10.5f us | %8i | %10i us"
                % (key, float(total) / length, length, total)
            )

    def __init__(self, client: AbstractClient):
        self._database: Redis = self.clone(client)
        self._configs: Optional[Dict] = None
        self._timings: Dict = defaultdict(list)
        self._commands: Dict = {}

    def start(self) -> None:
        """Get ready for a profiling run"""
        self._configs = self._database.config_get("slow-*")
        self._database.config_set("slowlog-max-len", 100000)
        self._database.config_set("slowlog-log-slower-than", 0)
        self._database.execute_command("slowlog", "reset")

    def stop(self) -> None:
        """Set everything back to normal and collect our data"""
        if self._configs:
            for key, value in self._configs.items():
                self._database.config_set(key, value)
        logs = self._database.execute_command("slowlog", "get", 100000)
        current: Dict[str, Any] = {"name": None, "accumulated": defaultdict(list)}
        for _, _, duration, request in logs:
            command = request[0]
            if command == "slowlog":
                continue
            if "eval" in command.lower():
                subcommand = request[3]
                self._timings["reqless-%s" % subcommand].append(duration)
                if current["name"]:
                    if current["name"] not in self._commands:
                        self._commands[current["name"]] = defaultdict(list)
                    for key, values in current["accumulated"].items():
                        self._commands[current["name"]][key].extend(values)
                current = {"name": subcommand, "accumulated": defaultdict(list)}
            else:
                self._timings[command].append(duration)
                if current["name"]:
                    current["accumulated"][command].append(duration)
        # Include the last
        if current["name"]:
            if current["name"] not in self._commands:
                self._commands[current["name"]] = defaultdict(list)
            for key, values in current["accumulated"].items():
                self._commands[current["name"]][key].extend(values)

    def display(self) -> None:
        """Print the results of this profiling"""
        self.pretty(self._timings, "Raw Data Structure Server Commands")
        print()
        for key, value in self._commands.items():
            self.pretty(value, 'Reqless "%s" Command' % key)
            print()

    def __enter__(self) -> "Profiler":
        self.start()
        return self

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_value: Optional[BaseException],
        exc_trace: Optional[TracebackType],
    ) -> None:
        self.stop()
        self.display()
