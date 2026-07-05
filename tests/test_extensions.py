"""Tests for the extension discovery layer (dysonsphere/discovery.py + package __getattr__)."""

import importlib.metadata
import types

import pytest

import dysonsphere as ds
from dysonsphere import discovery as ext


def _fake_entry_point(name, module):
    """An EntryPoint whose .load() returns ``module``.

    A real EntryPoint.load() imports the dotted path in ``value``; registering the module in
    sys.modules under a unique name lets load() resolve to our stand-in without a real install.
    """
    import sys

    sys.modules[module.__name__] = module
    return importlib.metadata.EntryPoint(name=name, value=module.__name__, group=ext._ENTRY_POINT_GROUP)


@pytest.fixture
def fake_biology(monkeypatch):
    """Register a fake ``biology`` extension via monkeypatched entry-point discovery."""
    module = types.ModuleType("_fake_dysonsphere_biology")
    module.volcano = lambda: "volcano!"  # ty: ignore[unresolved-attribute]
    ep = _fake_entry_point("biology", module)
    monkeypatch.setattr(ext, "_extension_entry_points", lambda: {"biology": ep})
    yield module
    # __getattr__ caches the resolved module in the package namespace; drop it so it can't leak.
    ds.__dict__.pop("biology", None)


def test_extensions_empty(monkeypatch):
    monkeypatch.setattr(ext, "_extension_entry_points", dict)
    assert ext.extensions() == []


def test_extensions_lists_installed_sorted(monkeypatch):
    monkeypatch.setattr(ext, "_extension_entry_points", lambda: {"physics": object(), "biology": object()})
    assert ext.extensions() == ["biology", "physics"]


def test_load_extension_returns_module(fake_biology):
    assert ext.load_extension("biology") is fake_biology


def test_load_extension_missing_raises_with_available(monkeypatch):
    monkeypatch.setattr(ext, "_extension_entry_points", dict)
    with pytest.raises(ImportError, match="no dysonsphere extension named 'biology'.*no extensions are installed"):
        ext.load_extension("biology")


def test_load_extension_missing_lists_installed(monkeypatch):
    monkeypatch.setattr(ext, "_extension_entry_points", lambda: {"physics": object()})
    with pytest.raises(ImportError, match="installed extensions: physics"):
        ext.load_extension("astronomy")


def test_getattr_resolves_extension(fake_biology):
    assert ds.biology is fake_biology
    assert ds.biology.volcano() == "volcano!"


def test_getattr_caches_resolved_extension(fake_biology):
    ds.biology  # trigger resolution + cache
    assert ds.__dict__["biology"] is fake_biology


def test_getattr_unknown_raises_attributeerror(monkeypatch):
    monkeypatch.setattr(ext, "_extension_entry_points", dict)
    with pytest.raises(AttributeError, match="has no attribute 'definitely_not_installed'"):
        ds.definitely_not_installed


def test_extensions_public_via_namespace():
    # extensions() / load_extension() are exported on the top-level namespace.
    assert callable(ds.extensions)
    assert callable(ds.load_extension)
