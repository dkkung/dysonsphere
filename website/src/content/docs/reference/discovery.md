---
title: "Extensions"
description: "Discover and load installed dysonsphere extensions."
sidebar:
  order: 13
---

<!-- Generated from docstrings by website/scripts/gen_api.py - do not edit by hand. -->

Discovery of optional dysonsphere extension packages (e.g. ``dysonsphere-biology``).

Extensions are separate, independently released distributions - not part of core - that
register themselves under the ``dysonsphere.extensions`` entry-point group in their own
``pyproject.toml``::

    [project.entry-points."dysonsphere.extensions"]
    biology = "dysonsphere_biology"

Core discovers them lazily. Accessing ``dysonsphere.<name>`` (resolved by the package-level
``__getattr__`` in ``dysonsphere/__init__.py``) imports and returns the registered module, so
``dysonsphere.biology.volcano(df)`` works once ``dysonsphere-biology`` is pip-installed. The
extension is also importable directly (``import dysonsphere_biology``); the entry point only
adds the ``dysonsphere.<name>`` alias and lets core enumerate what is installed.

Public surface: ``extensions()`` (list installed names) and ``load_extension(name)`` (import
one by name). Both live here; ``__getattr__`` delegates to ``_extension_entry_points``.

## `extensions`

```python
def extensions() -> list[str]: ...
```

Return the sorted names of installed dysonsphere extensions.

Each name is also accessible as an attribute of the top-level ``dysonsphere`` module
(e.g. ``dysonsphere.biology`` when ``dysonsphere-biology`` is installed).

## `load_extension`

```python
def load_extension(name: str) -> ModuleType: ...
```

Import and return the extension registered under ``name``.

Equivalent to accessing ``dysonsphere.<name>`` but explicit. Raises ``ImportError`` with
the list of installed extensions if no extension is registered under ``name``.
