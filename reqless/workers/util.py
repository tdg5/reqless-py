import os
import shutil
from contextlib import contextmanager
from itertools import zip_longest
from typing import Callable, Generator, Iterable, List, Optional

from reqless.abstract import AbstractJob
from reqless.logger import logger
from reqless.proctitle import getproctitle, setproctitle


def divide(jobs: Iterable[AbstractJob], count: int) -> List[List[AbstractJob]]:
    """Divide up the provided jobs into count evenly-sized groups"""
    job_groups = list(zip(*zip_longest(*[iter(jobs)] * count)))
    # If we had no jobs to resume, then we get an empty list
    job_groups = job_groups or [()] * count
    for index in range(count):
        # Filter out the items in jobs that are None
        job_groups[index] = [j for j in job_groups[index] if j is not None]
    return job_groups


def clean(path: str) -> None:
    """Clean up all the files in a provided path"""
    for pth in os.listdir(path):
        pth = os.path.abspath(os.path.join(path, pth))
        if os.path.isdir(pth):
            logger.debug("Removing directory %s" % pth)
            shutil.rmtree(pth)
        else:
            logger.debug("Removing file %s" % pth)
            os.remove(pth)


@contextmanager
def create_sandbox(
    path: str,
    clean_fn: Optional[Callable[[str], None]] = None,
) -> Generator[None, None, None]:
    """Ensures path exists before yielding, cleans up after"""
    _clean_fn = clean_fn or clean
    # Ensure the path exists and is clean
    try:
        os.makedirs(path)
        logger.debug("Making %s" % path)
    except OSError:
        if not os.path.isdir(path):
            raise
    finally:
        _clean_fn(path)
    # Then yield, but make sure to clean up the directory afterwards
    try:
        yield
    finally:
        _clean_fn(path)


def get_title() -> str:
    """Get the title of the process"""
    return getproctitle()


def set_title(message: str) -> None:
    """Set the title of the process"""
    setproctitle("reqless-py-worker %s" % message)
