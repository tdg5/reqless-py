"""Some exception classes"""


class QlessError(Exception):
    """Any and all qless exceptions"""

    pass


class LostLockError(QlessError):
    """Lost lock on a job"""

    pass
