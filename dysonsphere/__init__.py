# ext is the extension-author primitive surface: exposed as the namespaced `ds.ext` (its
# contents are deliberately NOT star-imported into the top namespace).
from . import ext  # noqa: F401
from .annotations import *  # noqa: F403
from .discovery import *  # noqa: F403
from .export import *  # noqa: F403
from .inference import *  # noqa: F403
from .labels import *  # noqa: F403
from .marks import *  # noqa: F403
from .metadata import *  # noqa: F403
from .multilabel import *  # noqa: F403
from .nonlinear import *  # noqa: F403
from .palettes import *  # noqa: F403
from .statistics import *  # noqa: F403
from .table import *  # noqa: F403
from .theme import *  # noqa: F403
from .transforms import *  # noqa: F403
from .utils import *  # noqa: F403

# The public API - the union of the modules' __all__ lists, written out explicitly so the
# surface is documented in one place and guarded by tests (test_package_namespace). Every
# module defines its own __all__, so the star-imports above bind exactly these names and
# nothing else (no leaked stdlib/third-party imports on the dysonsphere namespace).
__all__ = [
    "BandGeometry",
    "add_beeswarm",
    "add_comparisons",
    "add_correlation",
    "add_jitter",
    "add_labels",
    "add_log_ticks",
    "add_multilabel",
    "add_pow_ticks",
    "add_rule",
    "add_shade",
    "add_text",
    "band_geometry",
    "categorical",
    "clear_stats",
    "colors",
    "count_n",
    "create_config",
    "ensure_polars",
    "export_swatches",
    "extensions",
    "frame_checksum",
    "label_expr",
    "load",
    "load_extension",
    "log_label_expr",
    "mark_strip",
    "mark_table",
    "mark_violin",
    "palette",
    "read",
    "save",
    "show",
    "theme",
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
    from .discovery import _extension_entry_points

    ep = _extension_entry_points().get(name)
    if ep is not None:
        module = ep.load()
        globals()[name] = module
        return module
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
