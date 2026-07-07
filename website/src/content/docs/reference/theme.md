---
title: "Theming"
description: "Register the dysonsphere Altair theme and scaffold config files."
sidebar:
  order: 8
---

<!-- Generated from docstrings by website/scripts/gen_api.py - do not edit by hand. -->

## `theme`

```python
def theme(style: str | None = None, **kwargs) -> None: ...
```

Configure and register the dysonsphere Altair theme.

All parameters are optional — pass only the ones you want to change.
Everything else uses the dysonsphere built-in defaults.

A TOML config file can provide persistent per-project or per-user
overrides. See the README for the config file format and search path.
Named styles in the config file are selected with ``style=``.

## `create_config`

```python
def create_config(
    directory: str | Path | None = None,
    *,
    persist: bool = False,
) -> None: ...
```

Write a dysonsphere.toml template to *directory* (default: current working directory).

Pass persist=True to write to the platform user config directory instead
(~/.config/dysonsphere/ on macOS/Linux, %APPDATA%/dysonsphere/ on Windows).
This file applies across all your projects.

The file is not overwritten if it already exists. Edit the values in each
section, rename [my_style] to your own style name, and load it with
ds.theme(style="name").
