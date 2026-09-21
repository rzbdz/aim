"""aimboard - a read-only dashboard over an aim fabric.

Layout, and why it is split this way:

    kernel.py      a small context: services and registered views (see its docstring)
    const.py       the status vocabulary and the colour map
    primitives.py  hashing, escaping, JSON IO, chain verification, dates
    fabric.py      read-only loaders for every file the fabric keeps
    fold.py        board state as a fold over the task log
    gate.py        who may see what, and which channel's phase decides
    components.py  a card and a message, escaped on the way in
    web.py         the page shell: CSS and JavaScript
    page.py        assembles the shell out of whatever views are registered
    exporters.py   CSV, iCal, JSON for a foreign tool
    views/         one module per pane, each registered as a plugin
    cli.py         the command line

The property that makes it modular rather than merely split up: **no view imports
another view.** A pane registers itself with the kernel and receives a Page; the
shell renders whatever is registered. Adding a pane is a new module plus a line in
views/__init__.py, and it cannot break an existing one.
"""
from .kernel import Context, Page

__all__ = ["Context", "Page"]
# `render_html` lives in aimboard.page and is imported from there. Importing it
# here would make the package initialise the shell before any of its services
# exist, which is the circular import this comment exists to prevent.
