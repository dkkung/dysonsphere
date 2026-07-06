---
title: "Statistics"
description: "Statistics report queue management."
sidebar:
  order: 10
---

<!-- Generated from docstrings by website/scripts/gen_api.py - do not edit by hand. -->

## `clear_stats`

```python
clear_stats()
```

Discard all pending statistical records queued by ``add_comparisons`` /
``add_correlation``.

``save()`` embeds only the records whose annotations appear in the chart being saved, so
stale records never contaminate a save.  But they do accumulate in memory across a long
session — e.g. a notebook where you build many stats charts and display them without
saving each.  Call this to drop the pending queue.
