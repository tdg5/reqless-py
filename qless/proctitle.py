"""Utils for getting and setting the process title"""

try:
    from setproctitle import getproctitle, setproctitle
except ImportError:  # pragma: no cover

    def setproctitle(title: str) -> None:
        pass

    def getproctitle() -> str:
        return ""


__all__ = [
    "getproctitle",
    "setproctitle",
]
