from abc import ABC, abstractmethod
from typing import Any, Dict, ItemsView, Iterable, Iterator, KeysView, ValuesView


class AbstractConfig(ABC):
    """Abstract interface describing a class that allows us to change and
    manipulate reqless config"""

    @property
    @abstractmethod
    def all(self) -> Dict[str, Any]:  # pragma: no cover
        pass

    @abstractmethod
    def __len__(self) -> int:  # pragma: no cover
        pass

    @abstractmethod
    def __getitem__(self, option: str) -> Any:  # pragma: no cover
        pass

    @abstractmethod
    def __setitem__(self, option: str, value: Any) -> None:  # pragma: no cover
        pass

    @abstractmethod
    def __delitem__(self, option: str) -> None:  # pragma: no cover
        pass

    @abstractmethod
    def __contains__(self, option: str) -> bool:  # pragma: no cover
        pass

    @abstractmethod
    def __iter__(self) -> Iterator:  # pragma: no cover
        pass

    @abstractmethod
    def clear(self) -> None:  # pragma: no cover
        """Remove all keys"""
        pass

    @abstractmethod
    def get(self, option: str, default: Any = None) -> Any:  # pragma: no cover
        """Get a particular option, or the default if it's missing"""
        pass

    @abstractmethod
    def items(self) -> ItemsView[str, Any]:  # pragma: no cover
        """Just like `dict.items`"""
        return self.all.items()

    @abstractmethod
    def keys(self) -> KeysView[str]:  # pragma: no cover
        """Just like `dict.keys`"""
        return self.all.keys()

    @abstractmethod
    def pop(self, option: str, default: Any = None) -> Any:  # pragma: no cover
        """Just like `dict.pop`"""
        pass

    @abstractmethod
    def update(self, other: Iterable = (), **kwargs: Any) -> None:  # pragma: no cover
        """Just like `dict.update`"""
        pass

    @abstractmethod
    def values(self) -> ValuesView:  # pragma: no cover
        """Just like `dict.values`"""
        pass
