"""A small kernel: services and views, in the shape of a plugin framework.

This is the one idea worth borrowing from a plugin framework generally (and
specifically from the shape cordis uses): the *context* owns what exists, a
plugin is a function that receives the context and registers what it provides,
and nothing reaches across to a concrete sibling. Concretely, for a dashboard:

  * a **service** is a thing that answers questions about the world - the fabric
    loaders, the fold, the gate. Registered by name, so a view asks for
    `page` and never for a module path.
  * a **view** is a pane. It registers a key, a bilingual title, a render
    function, an order, and the payload scopes it reads. The shell renders
    whatever is registered, in order.

What that buys, stated as a testable property: **no view imports another view.**
`aimboard/views/board.py` does not know `timeline.py` exists. A pane can be
deleted, reordered or replaced without touching the others, and a third party can
add one without editing the shell - which is the whole of the extensibility story
this file is here to provide.

It is deliberately small: a framework big enough to need its own documentation
would be a second thing to maintain, and this project has already learned what
happens when a second implementation of a rule appears (design/05 section 3).
The sentence here used to read "about 60 lines" and this file is 79 at HEAD
(`git show HEAD:aimboard/kernel.py | wc -l`); a count in a comment is a
measurement that decays, so what is written down is the property.
"""


class Page:
    """Everything a view is given. Not a dict, so a typo is an AttributeError."""

    __slots__ = ("state", "viewer", "risks", "generated_at", "lang", "labels",
                 "tasks", "hidden", "milestones", "as_of", "channels", "phase",
                 "phase_channel", "digest", "poll_ms")

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
    def register_view(self, key, title, title_zh, render, order=50, reads=()):
        """A pane, and the payload scopes it draws (T-0215).

        `reads` is a declaration the *pane* makes, passed through untouched: the
        kernel never interprets a scope name, because the vocabulary is the wire
        layer's (`aimboard/api.py:276 scoped_digests` produces it, `:538`
        publishes it) and a second copy of a vocabulary is the defect
        `aimboard/api.py:23` names. What is missing without this parameter is the
        other end of the same fact: the producer knows six scopes exist and
        nothing recorded *which pane reads which*, so a consumer holding all six
        digests still cannot answer "has the page in front of me moved".

        `()` means the pane declared nothing, which a consumer must read as
        unknown and not as stable -- the same reading `aimboard/revision.py`
        takes of a bundle that recorded no revision. Reordering or deleting a
        pane still costs the others nothing: this is a keyword with a default.

        The consumer this is for does not exist yet, and the shape it would need
        is one line: `aimboard/cli.py:779` strips the query string before
        dispatch, so `/api/digest?view=<key>` already reaches the branch at
        `aimboard/cli.py:820`, which today answers with `fabric_digest(root)`
        alone. `web/src/stores/board.js:490` polls exactly that route. None of
        those three files is this card's.
        """
        if any(v["key"] == key for v in self.views):
            raise RuntimeError(f"view '{key}' is already registered")
        self.views.append({"key": key, "title": title, "title_zh": title_zh,
                           "render": render, "order": order, "reads": tuple(reads)})
        self.views.sort(key=lambda v: (v["order"], v["key"]))
        return render

    def reads_of(self, key):
        """What the pane registered as `key` draws, by the names it declared."""
        for view in self.views:
            if view["key"] == key:
                return view["reads"]
        raise KeyError(f"no view registered as '{key}'; "
                       f"registered: {', '.join(sorted(v['key'] for v in self.views))}")

    def render_view(self, key, page):
        for view in self.views:
            if view["key"] == key:
                return view["render"](page)
        return f'<p class="empty">no view registered as "{key}"</p>'
