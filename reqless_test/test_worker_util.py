import itertools
import os

from reqless.job import Job
from reqless.workers.util import clean, create_sandbox, divide, get_title, set_title
from reqless_test.common import TestReqless


class TestWorkerUtil(TestReqless):
    """Test the worker utils"""

    def setUp(self) -> None:
        TestReqless.setUp(self)
        self.client.worker_name = "worker"

    def test_proctitle(self) -> None:
        """Make sure we can get / set the process title"""
        try:
            import setproctitle  # noqa: F401

            before = get_title()
            set_title("Foo")
            self.assertNotEqual(before, get_title())
        except ImportError:
            self.skipTest("setproctitle not available")

    def test_clean(self) -> None:
        """Should be able to clean a directory"""
        if not os.path.exists("reqless_test/tmp"):
            os.makedirs("reqless_test/tmp")
        self.assertEqual(os.listdir("reqless_test/tmp"), [])
        os.makedirs("reqless_test/tmp/foo/bar")
        with open("reqless_test/tmp/file.out", "w+"):
            pass
        self.assertNotEqual(os.listdir("reqless_test/tmp"), [])
        clean("reqless_test/tmp")
        self.assertEqual(os.listdir("reqless_test/tmp"), [])

    def test_sandbox(self) -> None:
        """The sandbox utility should work"""
        path = "reqless_test/tmp/foo"
        self.assertFalse(os.path.exists(path))
        try:
            with create_sandbox(path):
                self.assertTrue(os.path.exists(path))
                for name in ["whiz", "widget", "bang"]:
                    with open(os.path.join(path, name), "w+"):
                        pass
                # Now raise an exception
                raise ValueError("foo")
        except ValueError:
            pass
        # Make sure the directory has been cleaned
        self.assertEqual(os.listdir(path), [])
        os.rmdir(path)

    def test_sandbox_exists(self) -> None:
        """Sandbox creation should not throw an error if the path exists"""
        path = "reqless_test/tmp"
        self.assertEqual(os.listdir(path), [])
        with create_sandbox(path):
            pass
        # If we get to this point, the test succeeds
        self.assertTrue(True)

    def test_dirty_sandbox(self) -> None:
        """If a sandbox is dirty on arrival, clean it first"""
        path = "reqless_test/tmp/foo"
        with create_sandbox(path):
            for name in ["whiz", "widget", "bang"]:
                with open(os.path.join(path, name), "w+"):
                    pass
            # Now it's sullied. Clean it up
            self.assertNotEqual(os.listdir(path), [])
            with create_sandbox(path):
                self.assertEqual(os.listdir(path), [])
        os.rmdir(path)

    def test_divide(self) -> None:
        """We should be able to divide resumable jobs evenly"""
        jobs = [
            Job(
                client=self.client,
                data="{}",
                dependencies=[],
                dependents=[],
                expires=0,
                failure={},
                history=[],
                jid=index,
                klass="reqless_test.common.NoopJob",
                priority=0,
                remaining=1,
                retries=1,
                queue="queue",
                state="waiting",
                tracked=False,
                worker="worker",
            )
            for index in range(100)
        ]
        items = divide(jobs, 7)
        # Make sure we have the same items as output as input
        divided_jids = sorted([job.jid for job in itertools.chain(*items)])
        self.assertEqual(list(range(100)), divided_jids)
        lengths = [len(batch) for batch in items]
        self.assertLessEqual(max(lengths) - min(lengths), 1)
