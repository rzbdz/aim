"""A small kernel: services and views, in the shape of a plugin framework.

This is the one idea worth borrowing from a plugin framework generally (and
specifically from the shape cordis uses): the *context* owns what exists, a
plugin is a function that receives the context and registers what it provides,
and nothing reaches across to a concrete sibling. Concretely, for a dashboard:

  * a **service** is a thing that answers questions about the world - the fabric
    loaders, the fold, the gate. Registered by name, so a view asks for
    `page` and never for a module path.
  * a **view** is a pane. It registers a key, a bilingual title, a render
    function and an order. The shell renders whatever is registered, in order.

What that buys, stated as a testable property: **no view imports another view.**
`aimboard/views/board.py` does not know `timeline.py` exists. A pane can be
deleted, reordered or replaced without touching the others, and a third party can
add one without editing the shell - which is the whole of the extensibility story
this file is here to provide.

It is deliberately about 60 lines. A framework big enough to need its own
documentation would be a second thing to maintain, and this project has already
learned what happens when a second implementation of a rule appears (design/05
section 3).
"""


class Page:
    """Everything a view is given. Not a dict, so a typo is an AttributeError."""

    __slots__ = ("state", "viewer", "risks", "generated_at", "lang", "labels",
                 "tasks", "hidden", "milestones", "as_of", "channels", "phase",
                 "digest", "poll_ms")

    def __init__(self, **kw):
        for key in self.__slots__:
            setattr(self, key, kw.get(key))


class Context:
    def __init__(self, name="aimboard"):
        self.name = name
        self.services = {}
        self.views = []
        self.plugins = []

    # -- services ---------------------------------------------------------
    def provide(self, name, value):
        if name in self.services:
            raise RuntimeError(f"service '{name}' is already provided by the context")
        self.services[name] = value
        return value

    def service(self, name):
        try:
            return self.services[name]
        except KeyError:
            raise KeyError(f"no service '{name}'; provided: {', '.join(sorted(self.services))}")

    # -- plugins ----------------------------------------------------------
    def use(self, plugin, **options):
        """Load a plugin. A plugin is a callable taking (context, **options)."""
        plugin(self, **options)
        self.plugins.append(getattr(plugin, "__module__", repr(plugin)))
        return self

    # -- views ------------------------------------------------------------
    def register_view(self, key, title, title_zh, render, order=50):
        if any(v["key"] == key for v in self.views):
            raise RuntimeError(f"view '{key}' is already registered")
        self.views.append({"key": key, "title": title, "title_zh": title_zh,
                           "render": render, "order": order})
        self.views.sort(key=lambda v: (v["order"], v["key"]))
        return render

    def render_view(self, key, page):
        for view in self.views:
            if view["key"] == key:
                return view["render"](page)
        return f'<p class="empty">no view registered as "{key}"</p>'
