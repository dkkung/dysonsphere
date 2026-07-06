---
title: "Statistics registry"
description: "Statistics report queue management."
sidebar:
  order: 12
---

<!-- Generated from docstrings by website/scripts/gen_api.py - do not edit by hand. -->

Pure statistical computation (no Altair).

Backs the chart-annotation constructors in ``layers.py`` (notably
``add_comparisons``).  Holds the omnibus tests, hand-rolled post-hoc tests,
effect-size functions, and the descriptive report builder.  Nothing here
imports Altair, so it is unit-testable in isolation.

The post-hoc tests scipy does not ship (Dunn, Nemenyi, Games-Howell) are
implemented here from scipy primitives (``rankdata``, ``norm``,
``studentized_range``) rather than taking a dependency on ``scikit-posthocs``
(which would drag in statsmodels + seaborn + matplotlib).

## `clear_stats`

```python
clear_stats() -> None
```

Discard all pending statistical records queued by ``add_comparisons`` /
``add_correlation``.

``save()`` embeds only the records whose annotations appear in the chart being saved, so
stale records never contaminate a save.  But they do accumulate in memory across a long
session — e.g. a notebook where you build many stats charts and display them without
saving each.  Call this to drop the pending queue.
