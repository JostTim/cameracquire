from types import ModuleType
from typing import Optional, Sequence, List, Set

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


def get_backends(backend_names: Optional[Set[str] | str]):
    if backend_names is None:
        return get_default_backends()
    if not isinstance(backend_names, (list, set, tuple)):
        backend_names = [backend_names]

    return [get_backend(backend_name) for backend_name in backend_names]


def get_default_backends():
    return [get_backend(backend_name) for backend_name in DEFAULT_BACKENDS]
