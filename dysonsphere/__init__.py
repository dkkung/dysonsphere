# ext is the extension-author primitive surface: exposed as the namespaced `ds.ext` (its
# contents are deliberately NOT star-imported into the top namespace).
from . import ext  # noqa: E402, F401
from .discovery import *  # noqa: F403
from .export import *  # noqa: F403
from .labels import *  # noqa: F403
from .layers import *  # noqa: F403
from .marks import *  # noqa: F403
from .metadata import *  # noqa: F403
from .multilabel import *  # noqa: F403
from .nonlinear import *  # noqa: F403
from .palettes import *  # noqa: F403
from .statistics import *  # noqa: F403
from .theme import *  # noqa: F403
from .transforms import *  # noqa: F403
from .utils import *  # noqa: F403

__all__ = [name for name in dir() if not name.startswith("_")]


def __getattr__(name: str):
    """Lazily resolve installed extensions as attributes (PEP 562).

    ``dysonsphere.biology`` imports and returns the ``dysonsphere-biology`` extension when it
    is installed (registered under the ``dysonsphere.extensions`` entry-point group); the
    resolved module is cached in the package namespace so later access skips discovery. Any
    other missing attribute raises ``AttributeError`` as usual (a plain typo and an
    uninstalled extension are indistinguishable here - use ``extensions()`` to list what is
    installed, or ``load_extension(name)`` for an ImportError that names them).
    """
    from .discovery import _extension_entry_points

    ep = _extension_entry_points().get(name)
    if ep is not None:
        module = ep.load()
        globals()[name] = module
        return module
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
