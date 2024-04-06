"""A worker that forks child processes"""

import multiprocessing
import os
import signal
from types import FrameType
from typing import Any, Dict, Iterable, List, Optional, Type, Union

from reqless import logger, util
from reqless.abstract import (
    AbstractClient,
    AbstractJob,
    AbstractQueue,
    AbstractQueueResolver,
)
from reqless.workers.serial import SerialWorker
from reqless.workers.util import create_sandbox, divide
from reqless.workers.worker import Worker


try:
    NUM_CPUS = multiprocessing.cpu_count()
except NotImplementedError:
    NUM_CPUS = 1


class ForkingWorker(Worker):
    """A worker that forks child processes"""

    def __init__(
        self,
        queues: Union[Iterable[Union[str, AbstractQueue]], AbstractQueueResolver],
        client: AbstractClient,
        interval: Optional[float] = None,
        resume: Optional[Union[bool, List[AbstractJob]]] = None,
        **kwargs: Any,
    ):
        super().__init__(
            queues,
            client,
            interval,
            resume,
            **kwargs,
        )
        # Worker class to use
        _klass = self.kwargs.pop("klass", SerialWorker)
        self.klass: Type[Worker] = (
            util.import_class(_klass) if isinstance(_klass, str) else _klass
        )
        # How many children to launch
        self.count: int = self.kwargs.pop("workers", 0) or NUM_CPUS
        # A dictionary of child pids to information about them
        self.sandboxes: Dict[int, str] = {}

    def stop(self, sig: int = signal.SIGINT) -> None:
        """Stop all the workers, and then wait for them"""
        for cpid in self.sandboxes:
            logger.warn("Stopping %i..." % cpid)
            try:
                os.kill(cpid, sig)
            except OSError:  # pragma: no cover
                logger.exception("Error stopping %s..." % cpid)

        # While we still have children running, wait for them
        # We edit the dictionary during the loop, so we need to copy its keys
        for cpid in list(self.sandboxes):
            try:
                logger.info("Waiting for %i..." % cpid)
                pid, status = os.waitpid(cpid, 0)
                logger.warn("%i stopped with status %i" % (pid, status >> 8))
            except OSError:  # pragma: no cover
                logger.exception("Error waiting for %i..." % cpid)
            finally:
                self.sandboxes.pop(cpid, None)

    def spawn(self, **kwargs: Any) -> Worker:
        """Return a new worker for a child process"""
        copy = dict(self.kwargs)
        copy.update(kwargs)
        return self.klass(self.queues, self.client, **copy)

    def run(self) -> None:
        """Run this worker"""
        self.signals(("TERM", "INT", "QUIT"))
        # Divide up the jobs that we have to divy up between the workers. This
        # produces evenly-sized groups of jobs
        resume = divide(self.resume, self.count)
        for index in range(self.count):
            # The sandbox for the child worker
            sandbox = os.path.join(
                os.getcwd(), "reqless-py-workers", "sandbox-%s" % index
            )
            cpid = os.fork()
            if cpid:
                logger.info("Spawned worker %i" % cpid)
                self.sandboxes[cpid] = sandbox
            else:  # pragma: no cover
                # Move to the sandbox as the current working directory
                with create_sandbox(sandbox):
                    os.chdir(sandbox)
                    try:
                        self.spawn(resume=resume[index], sandbox=sandbox).run()
                    except Exception:
                        logger.exception("Exception in spawned worker")
                    finally:
                        os._exit(0)

        try:
            while not self.shutdown:
                pid, status = os.wait()
                logger.warn(
                    "Worker %i died with status %i from signal %i"
                    % (pid, status >> 8, status & 0xFF)
                )
                sandbox = self.sandboxes.pop(pid)
                cpid = os.fork()
                if cpid:
                    logger.info("Spawned replacement worker %i" % cpid)
                    self.sandboxes[cpid] = sandbox
                else:  # pragma: no cover
                    with create_sandbox(sandbox):
                        os.chdir(sandbox)
                        try:
                            self.spawn(sandbox=sandbox).run()
                        except Exception:
                            logger.exception("Exception in spawned worker")
                        finally:
                            os._exit(0)
        finally:
            self.stop(signal.SIGKILL)

    def handler(
        self, signum: int, frame: Optional[FrameType]
    ) -> None:  # pragma: no cover
        """Signal handler for this process"""
        if signum in (signal.SIGTERM, signal.SIGINT, signal.SIGQUIT):
            self.stop(signum)
            os._exit(0)
