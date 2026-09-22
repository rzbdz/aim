#!/usr/bin/env python3
"""T-0204 -- "Fix the store schema drift: the note and the record must agree on one spelling".

The card's acceptance, verbatim:

    design/05 section 3 and the store agree, and the renderer's tolerance is either
    documented or deleted

Three measurements, run against the tool rather than against a description of it:

  1. every event name the store *writes* is the event name design/05 section 3
     *names*. The note says `task.created`, `task.moved`, ...; the store froze as
     `created`, `moved`, ... -- `aimboard/fold.py:18` says so in a comment, and that
     comment is the only place the disagreement is written down.
  2. every key section 3 says an event carries is a key the store's own rows carry.
     The note lists `id`; the store writes `task`.
  3. the read tolerance that hides the drift -- `fold.py:20` strips a `task.` prefix
     so a log written in the note's spelling still folds -- is either named in
     section 3 or gone from the renderer. It is neither today, which is why the
     drift has survived: the tool absorbs the note's spelling silently, so a fixture
     written from the note looks like it works while the board it produces is empty
     (measured in `tests/attack_renderer_gate.py:170`).

Everything below runs on a throwaway fabric under /tmp (`tempfile.mkdtemp`), so the
real `channels/hello` is never touched.

Run: python3 tests/test_schema_drift.py
Exit code is 0 while the failures are annotated; an *unexpected success* means the
note was fixed and the annotation should be deleted.
"""
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
AIM = ROOT / "bin" / "aim"
DESIGN = ROOT / "design" / "05-project-management.md"
FOLD = ROOT / "aimboard" / "fold.py"
CH = "schema-drift"


def section(text, number):
    """The body of `## <number>. ...` up to the next `## ` heading."""
    m = re.search(r"^## %d\..*?$(.*?)(?=^## |\Z)" % number, text, re.S | re.M)
    if not m:
        raise AssertionError("design/05 has no section %d" % number)
    return m.group(1)


def backticked(chunk):
    return re.findall(r"`([^`]+)`", chunk)


def declared_events():
    """The event spellings section 3 names: the backticked tokens that carry the
    note's `task.` prefix (the sentence's other backticks are key names)."""
    sec = section(DESIGN.read_text(encoding="utf-8"), 3)
    m = re.search(r"Event types:(.*?),?\s+Each carries", sec, re.S)
    chunk = m.group(1) if m else sec
    return {t for t in backticked(chunk) if "." in t}


def declared_keys():
    """The keys section 3 says every event carries."""
    sec = section(DESIGN.read_text(encoding="utf-8"), 3)
    m = re.search(r"Each carries (.{0,300}?)\.", sec, re.S)
    return set(backticked(m.group(1))) if m else set()


class Store:
    """A throwaway fabric. The store is exercised, never described."""

    def __init__(self):
        self.root = pathlib.Path(tempfile.mkdtemp(prefix="schema-drift-"))
        self.env = dict(os.environ, AIM_ROOT=str(self.root))

    def aim(self, *args):
        return subprocess.run([sys.executable, str(AIM), *[str(a) for a in args]],
                              env=self.env, capture_output=True, text=True, timeout=120)

    def rows(self):
        path = self.root / "channels" / CH / "tasks.jsonl"
        if not path.exists():
            return []
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]

    def exercise_every_verb(self):
        """Run one of each `aim task` verb and collect the event names it appends.

        Ids are read back rather than assumed: `task new` allocates them under the
        channel lock, and a fixture that hardcodes T-0003 breaks the moment an
        earlier step stops consuming one.
        """
        self.aim("init")
        self.aim("register", "--as", "human", "--kind", "human")
        self.aim("register", "--as", "codex", "--kind", "codex")
        self.aim("new-channel", "--id", CH, "--topic", "schema drift",
                 "--participants", "codex")

        def new(title, *extra):
            out = self.aim("task", "new", "--as", "human", "--channel", CH,
                           "--title", title, *extra).stdout
            m = re.search(r"(T-\d+)", out)
            if not m:
                raise AssertionError("task new printed no id: %r" % out)
            return m.group(1)

        first = new("the first item")
        second = new("the second item")
        self.aim("task", "assign", "--as", "human", "--channel", CH, "--id", second, "--owner", "codex")
        self.aim("task", "move", "--as", "human", "--channel", CH, "--id", first, "--to", "ready")
        self.aim("task", "comment", "--as", "human", "--channel", CH, "--id", first, "--body", "a note")
        self.aim("task", "publish", "--as", "human", "--channel", CH, "--id", first)
        self.aim("task", "link", "--as", "human", "--channel", CH, "--id", second, "--blocked-by", first)
        self.aim("task", "claim", "--as", "human", "--channel", CH, "--id", second)
        self.aim("task", "retract", "--as", "human", "--channel", CH, "--id", second,
                 "--reason", "the verb is exercised, not the item")
        self.aim("task", "move", "--as", "human", "--channel", CH, "--id", first,
                 "--to", "dropped", "--reason", "the verb is exercised, not the item")
        return self.rows()

    def close(self):
        shutil.rmtree(self.root, ignore_errors=True)


class SchemaDrift(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.store = Store()
        cls.rows = cls.store.exercise_every_verb()

    @classmethod
    def tearDownClass(cls):
        cls.store.close()

    def store_events(self):
        return {str(row.get("event")) for row in self.rows if row.get("event")}

    def store_keys(self):
        keys = set()
        for row in self.rows:
            keys |= set(row)
        return keys

    @unittest.expectedFailure
    def test_section_3_names_every_event_the_store_writes(self):
        """The store's spelling, not the note's that the renderer tolerates."""
        measured = self.store_events()
        declared = declared_events()
        self.assertTrue(measured, "the fixture wrote no events at all: %r" % self.rows[:1])
        missing = sorted(measured - declared)
        self.assertFalse(
            missing,
            "the store writes %s; design/05 section 3 names %s. The note's spelling "
            "reaches the board only because fold.py strips a `task.` prefix, so a "
            "log written from the note folds to an empty board." % (missing, sorted(declared)))

    @unittest.expectedFailure
    def test_section_3_names_the_key_the_store_uses_for_the_id(self):
        """`task` is the store's key; `id` is the note's."""
        measured = self.store_keys()
        declared = declared_keys()
        self.assertTrue(declared, "section 3 lists no carried keys at all")
        missing = sorted(declared - measured)
        self.assertFalse(
            missing,
            "section 3 says each event carries %s; the store's rows carry %s. An event "
            "spelled and keyed as the note writes it is not what `aim` appends."
            % (missing, sorted(measured)))

    @unittest.expectedFailure
    def test_the_renderers_tolerance_is_documented_or_deleted(self):
        """Tolerating two spellings is a decision; an undocumented one is drift."""
        fold = FOLD.read_text(encoding="utf-8")
        tolerant = bool(re.search(r"startswith\(\s*['\"]task\.['\"]\s*\)", fold))
        sec = section(DESIGN.read_text(encoding="utf-8"), 3)
        documented = bool(re.search(
            r"(accept|tolerat|alias|both spellings|either spelling)[^.]{0,200}`task\."
            r"|`task\.[^`]*`[^.]{0,200}(accept|tolerat|alias|both spellings|either spelling)",
            sec, re.I))
        self.assertTrue(
            not tolerant or documented,
            "fold.py still strips a `task.` prefix from every event name (the tolerance "
            "that lets the note's spelling fold), and design/05 section 3 never says so. "
            "The note and the store still hold two spellings, one of them silently "
            "absorbed: the card asks for documented or deleted.")


if __name__ == "__main__":
    unittest.main(verbosity=2)
