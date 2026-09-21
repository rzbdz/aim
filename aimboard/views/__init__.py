"""The panes.

Each module here is a plugin: it exposes `build(page)` and `plugin(ctx)`, and
imports no sibling. This file is the only place that knows the set, which is why
adding a pane is a one-line change here rather than an edit to the shell.
"""
from . import audit, board, chat, items, overview, plan, reports, timeline

BUILTIN = (overview, board, timeline, items, chat, reports, audit, plan)


def load_builtin(ctx):
    for module in BUILTIN:
        ctx.use(module.plugin)
    return ctx
