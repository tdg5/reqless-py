"""A base class for all of our common tests"""

import logging
import unittest
from typing import List

import redis

import reqless
from reqless.abstract import AbstractJob


class NoopJob:
    @staticmethod
    def process(job: AbstractJob) -> None:
        job.complete()


class TestReqless(unittest.TestCase):
    """Base class for all of our tests"""

    redis: redis.Redis

    @classmethod
    def setUpClass(cls) -> None:
        reqless.logger.setLevel(logging.CRITICAL)
        cls.redis = redis.Redis()
        # Clear the script cache, and nuke everything
        cls.redis.execute_command("script", "flush")

    def setUp(self) -> None:
        all_keys: List = self.redis.keys("*")
        assert len(all_keys) == 0
        # The reqless client we're using
        self.client = reqless.Client()

    def ensure_queues_exist(self, queue_names: List[str]) -> None:
        for queue_name in queue_names:
            queue = self.client.queues[queue_name]
            if len(queue) == 0:
                jid = queue.put(NoopJob, "{}")
                job = self.client.jobs[jid]
                if job:
                    job.cancel()

    def tearDown(self) -> None:
        # Ensure that we leave no keys behind, and that we've unfrozen time
        self.redis.flushdb()
