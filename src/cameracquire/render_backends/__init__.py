from abc import ABC, abstractmethod
from types import ModuleType
from typing import Optional, List, Set, Callable

REGISTERED_BACKENDS = {}
DEFAULT_BACKENDS = set()


def register_backend(backend_name: str, backend_module: ModuleType, set_default=True):
    REGISTERED_BACKENDS[backend_name] = backend_module
    if set_default:
        DEFAULT_BACKENDS.add(backend_name)


def unregister_backend(backend_name: str):
    DEFAULT_BACKENDS.discard(backend_name)
    REGISTERED_BACKENDS.pop(backend_name, None)


def set_backend_default_state(backend_name: str, default_state: bool):
    if default_state:
        DEFAULT_BACKENDS.add(backend_name)
    else:
        DEFAULT_BACKENDS.discard(backend_name)


def get_backend(backend_name: str):
    return REGISTERED_BACKENDS[backend_name]


def get_default_backends() -> "BackendsCollection":
    return get_backends(DEFAULT_BACKENDS)


def get_backends(backend_names: Optional[Set[str] | List[str] | str] = None) -> "BackendsCollection":
    if backend_names is None:
        return get_default_backends()
    if not isinstance(backend_names, (list, set)):
        backend_names = [backend_names]
    return BackendsCollection([get_backend(backend_name) for backend_name in backend_names])


class BaseRenderer(ABC):
    @abstractmethod
    def render(self, *args, **kwargs) -> None: ...


class BackendsCollection:

    backends = []

    def __init__(self, backends: List[ModuleType]):
        self.backends = backends

    def render(self, classname: str, *args, **kwargs):
        for backend in self.backends:
            cls = self.get_class(backend, classname)
            self.render_single(cls, *args, **kwargs)

    def get_class(self, backend, classname: str) -> type[BaseRenderer]:
        return getattr(backend, classname)

    def render_single(self, cls: type[BaseRenderer], *args, **kwargs):
        renderer = cls()
        renderer.render(*args, **kwargs)
