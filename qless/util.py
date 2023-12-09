"""Some utility functions"""

from typing import Type


def import_class(klass: str) -> Type:
    """Import the named class and return that class"""
    mod = __import__(klass.rpartition(".")[0])
    for segment in klass.split(".")[1:-1]:
        mod = getattr(mod, segment)
    cls: Type = getattr(mod, klass.rpartition(".")[2])
    return cls
