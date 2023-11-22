"""A base class for all of our common tests"""

import logging
import unittest
from typing import List, cast

import redis

import qless


class TestQless(unittest.TestCase):
    """Base class for all of our tests"""

    redis: redis.Redis

    @classmethod
    def setUpClass(cls):
        qless.logger.setLevel(logging.CRITICAL)
        cls.redis = redis.Redis()
        # Clear the script cache, and nuke everything
        cls.redis.execute_command("script", "flush")

    def setUp(self):
        all_keys = cast(List, self.redis.keys("*"))
        assert len(all_keys) == 0
        # The qless client we're using
        self.client = qless.Client()

    def tearDown(self):
        # Ensure that we leave no keys behind, and that we've unfrozen time
        self.redis.flushdb()
