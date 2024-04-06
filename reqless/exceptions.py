"""Some exception classes"""


class ReqlessError(Exception):
    """Any and all reqless exceptions"""

    pass


class LostLockError(ReqlessError):
    """Lost lock on a job"""

    pass
