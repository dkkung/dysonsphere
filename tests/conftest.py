import pytest

from dysonsphere.statistics import _REPORTS


@pytest.fixture(autouse=True)
def _clear_report_queue():
    """Isolate the add_statistics() report registry between tests.

    add_statistics() queues a report on every call (for export metadata); without
    clearing it, reports from one test leak into another test's ds.save() output.
    """
    _REPORTS.clear()
    yield
    _REPORTS.clear()
