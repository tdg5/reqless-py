import importlib
import os
import time
from typing import Dict, Type

from reqless.logger import logger


class Importer:
    """A singleton to manage importing of job processors."""

    """This is a dictionary of all the classes that we've seen, and
    the last load time for each of them. We'll use this either for
    the debug mode or the general mechanism"""
    _loaded: Dict[str, float] = {}

    @staticmethod
    def mark_for_reload_on_next_import(class_name: str) -> None:
        Importer._loaded[class_name] = 0

    @staticmethod
    def import_class(class_name: str) -> Type:
        """1) Get a reference to the module
        2) Check the file that module's imported from
        3) If that file's been updated, force a reload of that module
             return it"""
        mod = __import__(class_name.rpartition(".")[0])
        for segment in class_name.split(".")[1:-1]:
            mod = getattr(mod, segment)

        # Alright, now check the file associated with it. Note that classes
        # defined in __main__ don't have a __file__ attribute
        if class_name not in Importer._loaded:
            Importer._loaded[class_name] = time.time()
        if hasattr(mod, "__file__") and mod.__file__:
            try:
                mtime = os.stat(mod.__file__).st_mtime
                if Importer._loaded[class_name] < mtime:
                    mod = importlib.reload(mod)
            except OSError:
                logger.warn("Could not check modification time of %s", mod.__file__)

        _class: Type = getattr(mod, class_name.rpartition(".")[2])
        return _class
