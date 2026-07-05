"""Test isolation for dysonsphere-biology, mirroring core's tests/conftest.py.

Biology tests build on core (ds.theme/save/read), so they need the same hermeticity: a clean
theme with no developer user-config bleeding in (e.g. a user-wide saveBackground=["light",
"dark"] would make single-background saves write _light/_dark suffixes), and an isolated stats
registry.
"""

import os
import tempfile

import pytest

import dysonsphere as ds
from dysonsphere.statistics import _REPORTS


@pytest.fixture(autouse=True)
def _clear_report_queue():
    _REPORTS.clear()
    yield
    _REPORTS.clear()


@pytest.fixture(autouse=True)
def _isolate_user_config():
    prev = os.environ.get("XDG_CONFIG_HOME")
    with tempfile.TemporaryDirectory() as d:
        os.environ["XDG_CONFIG_HOME"] = d
        try:
            yield
        finally:
            if prev is None:
                os.environ.pop("XDG_CONFIG_HOME", None)
            else:
                os.environ["XDG_CONFIG_HOME"] = prev


@pytest.fixture(autouse=True)
def _theme(_isolate_user_config):
    """Reset to the built-in theme after config isolation is in place."""
    ds.theme()
