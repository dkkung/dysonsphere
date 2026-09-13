# Support modules stay separate; their contents are not star-imported
# into the top namespace.
from . import ext, metadata, palettes, stats, transforms  # noqa: F401
from .annotations import *  # noqa: F403
from .assembly import *  # noqa: F403
from .display_labels import *  # noqa: F403
from .export import *  # noqa: F403
from .ext import extensions, load_extension
from .marks import *  # noqa: F403
from .multilabel import *  # noqa: F403
from .nonlinear import *  # noqa: F403
from .palettes import palette
from .table import *  # noqa: F403
from .theme import *  # noqa: F403

# Keep the root namespace explicit. Module-level __all__ values control the star imports above;
# namespace tests check that unrelated imports do not leak here.
__all__ = [
    "add_log_ticks",
    "add_multilabel",
    "add_pow_ticks",
    "assemble",
    "create_config",
    "extensions",
    "label_expr",
    "labels",
    "load",
    "load_extension",
    "log_label_expr",
    "mark_strip",
    "mark_table",
    "mark_violin",
    "metadata",
    "palette",
    "palettes",
    "rule",
    "save",
    "shade",
    "show",
    "stats",
    "text",
    "theme",
    "transforms",
]


def __getattr__(name: str):
    """Lazily resolve installed extensions as attributes (PEP 562).

    ``dysonsphere.biology`` imports and returns the ``dysonsphere-biology`` extension when it
    is installed (registered under the ``dysonsphere.extensions`` entry-point group); the
    resolved module is cached in the package namespace so later access skips discovery. Any
    other missing attribute raises ``AttributeError`` as usual (a plain typo and an
    uninstalled extension are indistinguishable here - use ``extensions()`` to list what is
    installed, or ``load_extension(name)`` for an ImportError that names them).
    """
    ep = ext._extension_entry_points().get(name)
    if ep is not None:
        module = ep.load()
        globals()[name] = module
        return module
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
