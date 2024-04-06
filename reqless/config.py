"""All our configuration operations"""

import json
from typing import Any, Dict, ItemsView, Iterable, Iterator, KeysView, ValuesView

from reqless.abstract.abstract_client import AbstractClient
from reqless.abstract.abstract_config import AbstractConfig


class Config(AbstractConfig):
    """A class that allows us to change and manipulate reqless config"""

    def __init__(self, client: AbstractClient):
        self._client: AbstractClient = client

    @property
    def all(self) -> Dict[str, Any]:
        response: Dict[str, Any] = json.loads(self._client("config.get"))
        return response

    def __len__(self) -> int:
        return len(self.all)

    def __getitem__(self, option: str) -> Any:
        result = self._client("config.get", option)
        if not result:
            return None
        try:
            return json.loads(result)
        except TypeError:
            return result

    def __setitem__(self, option: str, value: Any) -> None:
        self._client("config.set", option, value)

    def __delitem__(self, option: str) -> None:
        self._client("config.unset", option)

    def __contains__(self, option: str) -> bool:
        return option in self.all

    def __iter__(self) -> Iterator:
        return iter(self.all)

    def clear(self) -> None:
        """Remove all keys"""
        for key in self.keys():
            self._client("config.unset", key)

    def get(self, option: str, default: Any = None) -> Any:
        """Get a particular option, or the default if it's missing"""
        val = self[option]
        return (val is None and default) or val

    def items(self) -> ItemsView[str, Any]:
        """Just like `dict.items`"""
        return self.all.items()

    def keys(self) -> KeysView[str]:
        """Just like `dict.keys`"""
        return self.all.keys()

    def pop(self, option: str, default: Any = None) -> Any:
        """Just like `dict.pop`"""
        val = self[option]
        del self[option]
        return (val is None and default) or val

    def update(self, other: Iterable = (), **kwargs: Any) -> None:
        """Just like `dict.update`"""
        _kwargs = dict(kwargs)
        _kwargs.update(other)
        for key, value in _kwargs.items():
            self[key] = value

    def values(self) -> ValuesView:
        """Just like `dict.values`"""
        return self.all.values()
