"""dysonsphere-biology: biology chart extensions for dysonsphere.

Registered under the ``dysonsphere.extensions`` entry-point group so ``dysonsphere.biology``
resolves to this module (see dysonsphere's extension-architecture design point). Also importable
directly as ``dysonsphere_biology``.
"""

from .volcano import volcano

__all__ = ["volcano"]
