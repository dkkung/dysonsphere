"""Shared export choices, exposed publicly as dysonsphere.export.SAVE_FORMATS."""

from typing import Final

SAVE_FORMATS: Final[tuple[str, ...]] = ("svg", "png", "tiff", "json", "html")
