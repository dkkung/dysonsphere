from .annotations import *  # noqa: F403
from .export import *  # noqa: F403
from .inference import *  # noqa: F403
from .labels import *  # noqa: F403
from .marks import *  # noqa: F403
from .metadata import *  # noqa: F403
from .multilabel import *  # noqa: F403
from .nonlinear import *  # noqa: F403
from .palettes import *  # noqa: F403
from .statistics import *  # noqa: F403
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
    "frame_checksum",
    "label_expr",
    "load",
    "log_label_expr",
    "mark_strip",
    "mark_violin",
    "palette",
    "read",
    "save",
    "show",
    "theme",
]
