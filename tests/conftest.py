import os
import tempfile

import pytest

from dysonsphere.statistics import _REPORTS


@pytest.fixture(autouse=True)
def _clear_report_queue():
    """Isolate the add_comparisons() report registry between tests.

    add_comparisons() queues a report on every call (for export metadata); without
    clearing it, reports from one test leak into another test's ds.save() output.
    """
    _REPORTS.clear()
    yield
    _REPORTS.clear()


@pytest.fixture(autouse=True)
def _isolate_user_config():
    """Keep tests from reading the developer's real ``~/.config/dysonsphere`` config.

    Theme/config tests assert against the built-in defaults, so a user-wide config
    (e.g. a ``[default]`` block setting ``saveBackground``) would bleed in and break them.
    Point XDG_CONFIG_HOME at an empty temp dir so no user config is found.  (Uses os.environ
    directly, not ``monkeypatch`` — requesting ``monkeypatch`` in an autouse fixture reorders
    its teardown relative to other fixtures that chdir.)
    """
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
