"""A base class for all of our common tests"""

import json
import logging
import time
import unittest
from os import path
from typing import List

from redis import Redis

import reqless
from reqless import logger
from reqless.abstract import AbstractJob


class BlockingJob:
    """Job that can block until a given file is removed from the file system"""

    @staticmethod
    def process(job: AbstractJob) -> None:
        """Dummy job"""
        data_dict = json.loads(job.data)
        blocker_file = data_dict.get("blocker_file")
        if blocker_file:
            while path.exists(blocker_file):
                time.sleep(0.1)
        try:
            job.complete()
        except Exception:
            logger.exception("Unable to complete job %s" % job.jid)


class NoopJob:
    @staticmethod
    def process(job: AbstractJob) -> None:
        job.complete()


class TestReqless(unittest.TestCase):
    """Base class for all of our tests"""

    database: Redis

    @classmethod
    def setUpClass(cls) -> None:
        reqless.logger.setLevel(logging.CRITICAL)
        cls.database = Redis()
        # Clear the script cache, and nuke everything
        cls.database.execute_command("script", "flush")

    def setUp(self) -> None:
        all_keys: List = self.database.keys("*")
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
        self.database.flushdb()
