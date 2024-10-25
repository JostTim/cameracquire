from abc import ABC, abstractmethod
from types import ModuleType
from typing import Optional, List, Set, Callable, Generic, TypeVar, overload
from dataclasses import dataclass
from time import time
from warnings import warn

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
    DEBUG = False

    def __init__(self, backends: List[ModuleType]):
        self.backends = backends

    def render(self, classname: str, *args, **kwargs):
        for backend in self.backends:
            cls = self.get_class(backend, classname)
            if cls is None:
                continue
            self.render_single(cls, *args, **kwargs)

    def get_class(self, backend, classname: str) -> type[BaseRenderer] | None:
        cls = getattr(backend, classname, None)
        if cls is None and self.DEBUG:
            raise AttributeError(f"Cannot find the class {classname} in the backend  {backend}")
        return cls

    def render_single(self, cls: type[BaseRenderer], *args, **kwargs):
        try:
            renderer = cls()
            renderer.render(*args, **kwargs)
        except Exception as e:
            from inspect import getfile

            warn(
                f"Renderer {cls.__name__} ( object: {cls} from {getfile(cls)} ) could not run. "
                "Please fix your renderer. Here is the full exception error :\n"
                f"{type(e)} : {e}",
                stacklevel=3,
            )


@dataclass
class CrossInstanceCameraAttributes:

    real_fps = 0.0
    frame_times = []
    total_frames = 0
    image_shape = (-1, -1)

    def add_frame(self, image_shape):
        now = time()
        self.total_frames += 1
        self.frame_times.append(now)
        self.image_shape = image_shape

    def calculate_fps(self):
        now = max(self.frame_times)
        self.frame_times = list(filter(lambda value: value >= now - 1, self.frame_times))
        self.real_fps = len(self.frame_times)

    def update(self, image_shape):
        self.add_frame(image_shape)
        self.calculate_fps()


T = TypeVar("T")


class CrossInstanceReferencer(dict, Generic[T]):

    def __init__(self, value: Optional[T] = None):
        self.fetchkey = "value"
        super().__init__()
        if value is not None:
            self.set(value)

    def set(self, value: T) -> T:
        self[self.fetchkey] = value
        return value

    def get(self) -> T | None:
        return super().get(self.fetchkey, None)
