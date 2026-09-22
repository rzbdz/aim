"""Which revision of the program answered you.

`design/12` §1.6: a measurement that cannot state which revision it measured is
not a measurement. Today that was not theoretical -- a stale bundle was probed
twice and nearly produced a finding against the wrong build, and a peer served a
bundle built from uncommitted source with no way to tell.

Two revisions are reported, not one, because they can differ and the difference
is the finding:

  * `fabric` -- the working tree the *server* is running from. Answers "what code
    read the record".
  * `bundle` -- the front-end build that produced `web/dist`, recorded by the
    build itself. Answers "what code drew the page".

When they disagree, `stale` is true and the payload says so. Neither is inferred
from the other: `bundle` is written at build time and never recomputed at serve
time, because a revision computed from the current tree is a claim about the tree
and not about the bytes the browser is executing.
"""
import hashlib
import json
import subprocess
from pathlib import Path


def _git(root, *argv):
    try:
        out = subprocess.run(("git", "-C", str(root)) + argv, capture_output=True,
                             text=True, timeout=5)
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0:
        return None
    return out.stdout.strip()


def tree_revision(root):
    """`<short sha>` or `<short sha>+dirty`, or '' when this is not a checkout.

    Dirty is scoped to the paths that produce the program (`bin`, `aimboard`,
    `web`), not the whole tree: a fabric that writes records and mail next to its
    own source is dirty on every message, and a dirty flag that is always true
    says nothing.
    """
    sha = _git(root, "rev-parse", "--short", "HEAD")
    if not sha:
        return ""
    try:
        status = subprocess.run(
            ["git", "-C", str(root), "status", "--porcelain", "--", "bin", "aimboard", "web"],
            capture_output=True, text=True, timeout=5)
        dirt = [line for line in status.stdout.splitlines() if line.strip()]
    except (OSError, subprocess.SubprocessError):
        dirt = []
    return sha + ("+dirty" if dirt else "")


def source_hash(*paths):
    """A content hash of the inputs that produce the served bytes.

    A revision string is not enough here, and today proved it: the tree was dirty
    at build time and still dirty when the server answered, so `sha+dirty` compared
    equal while the browser could have been running older bytes. Hashing the
    *contents* means a stale bundle is detectable while a tree is dirty -- which is
    the normal state of a tree under development, and therefore the only state in
    which the check is worth having.

    Order and relative names are part of the hash, so a file moving is a change.
    """
    h = hashlib.sha256()
    for base in paths:
        base = Path(base)
        if not base.exists():
            continue
        entries = [base] if base.is_file() else sorted(base.rglob("*"))
        for path in entries:
            if not path.is_file():
                continue
            rel = path.relative_to(base.parent if base.is_file() else base)
            h.update(f"{rel}\0".encode())
            try:
                h.update(path.read_bytes())
            except OSError:
                h.update(b"<unreadable>")
            h.update(b"\0")
    return h.hexdigest()


def front_end_hash():
    """The front-end inputs, from the repo, as the build sees them."""
    web = Path(__file__).resolve().parent.parent / "web"
    parts = [web / "src", web / "index.html", web / "vite.config.js"]
    return source_hash(*[p for p in parts if p.exists()])


def bundle_revision(dist):
    """What the front-end build recorded about itself, or None if it did not.

    `None` is a real answer and is not the same as `''`: it means the bundle was
    built by a tool that does not write this file, so a consumer must not read a
    missing revision as "up to date".
    """
    path = Path(dist) / "revision.json"
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(doc, dict):
        return None
    return {"revision": doc.get("revision", ""), "built_at": doc.get("built_at", ""),
            "dirty": bool(doc.get("dirty")), "source": doc.get("source", "build"),
            "source_sha256": doc.get("source_sha256", "")}


def describe(root, dist, front_end=None):
    """What answered, and whether the bytes on the wire match the source.

    Three states, and they are not interchangeable:
      stale=True   the source changed since the bundle was built -- the page is
                   drawing code that no longer exists.
      stale=False  the bundle's recorded hash equals the current source hash.
      stale=None   the bundle did not record one. Unknown is not equal: a bundle
                   built by an older tool must not be reported as fresh.
    """
    fabric = tree_revision(root)
    bundle = bundle_revision(dist)
    current = front_end if front_end is not None else front_end_hash()
    if bundle is None or not bundle.get("source_sha256"):
        stale = None
    else:
        stale = bundle["source_sha256"] != current
    return {"fabric": fabric, "bundle": bundle, "stale": stale,
            "front_end_sha256": current}


def default_dist():
    """The front-end build this package serves. Same path `cli.serve` uses.

    Kept here so the build record and the serve path cannot drift apart: two
    copies of "where dist lives" is how a revision ends up reporting a bundle
    that is not the one on the wire.
    """
    return Path(__file__).resolve().parent.parent / "web" / "dist"
