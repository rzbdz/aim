#!/usr/bin/env python3
"""T-0232: nothing states which project a session is on, and a scratch channel is
indistinguishable from a real one.

T-0232's acceptance, in its own words:

  Given a session id, one command says which project/channel it is currently
  working on, derived from the store and not from a hand-maintained field.
  Observable: a session that moves from channel A to channel B changes the
  answer with no hand edit. Separately, a channel records whether it is a real
  project or a throwaway, so aim status can hide scratch channels and a leaked
  probe channel is visible.

T-0216's acceptance, quoted from the card's own `accept` field (the card's comment
restates it): each channel states its purpose and its owning work; the development
conversation lives in dev; a channel with no traffic for a milestone is closed or
deleted rather than left at SEALED_DIVERGENT.

Both cards name no command, and T-0232 says so explicitly -- "do not invent a
second roster ... Prefer a derived view plus one field that is written by an act".
So this file discovers the surface instead of guessing one: it reads the
subcommand list out of `aim --help`, probes each subcommand's own `--help` for the
cards' vocabulary, and probes a list of plausible names that are *not*
subcommands (`project`, `session`, `whereami`, ...) to prove they are absent
rather than merely unnamed. The discovery runs once, in `setUpClass`, and its
result is asserted before anything else runs, so on a build with no such surface
the failure names the search rather than a missing flag.

Why the assertions have the shape they have:

  * `test_the_move_is_one_recorded_act_and_edits_no_field` is not decorated. The
    move is `aim channel remove` + `aim channel add` today, and the card's
    observable requires that the *only* thing the move changes is the answer.
    So the test asserts what exists -- the two ledger rows, the participants the
    manifests now carry, and a byte-identical `registry.json` across the move --
    and it is the baseline the failing methods are compared against, not a claim
    that T-0232 passes.
  * The derivation is proven by comparison, not by inspection: the fixture is
    snapshotted before the move and the same candidate command is run against
    both roots. A surface that reads a stored "current project" field would print
    the same thing twice, and the two outputs are required to differ.
  * `answers()` accepts any argv shape that answers, and the tests check that the
    answer *names the channel*. The card says "given a session id"; an agent id is
    the sound derived key and the session string is not (`design/17` §2), so this
    file does not prescribe which of the two the command must take -- only that
    the answer may not be a stored field.
  * The two CLI-half assertions match a *labelled line*, not a substring, on
    purpose: `cmd_status` prints the topic verbatim (`bin/aim` 3762) and a
    topic-derived scratch channel's topic begins with the very word the test
    looks for, so `assertIn("scratch", out)` would pass on the topic alone and
    certify nothing.
  * Each test asserts the model half first where one exists, so a failure
    measures the missing surface rather than a missing derivation: `channel_kind`
    and `channel_lifecycle` are asserted to answer, and only then is the CLI
    asked to say the same thing.

Revision measured: `63faae0d9a340f3203e350d260aa563c4b9b58d8` (HEAD when this file
was written) and `c61e3b8cef7f6269208d6ea08fb1a870842fe6cd` (HEAD a few minutes
later; a peer committed `web(reports)` mid-run and the reported output was re-run
at the later revision). `bin/aim` is **clean** at both -- `git diff --stat bin/aim`
is empty, so the absence is in committed lines: `aim --help` lists
`{init,card,register,new-channel,channel,say,seal,inbox,wait,advance,
request-advance,synthesis-input,task,reveal,push,pull,confirm,outbox,nudge,room,
search,tension,status,verify,friction,doctor}`, no subcommand's help text matches
the vocabulary regex below, and every probed name (`project`, `session`,
`whereami`, `working-on`, ...) exits 2 with `argument cmd: invalid choice`. The
one adjacent mechanism that exists is `register --session` (`bin/aim` 4321), and
it is a free-text note rather than an identity: T-0242's own measurement is that
two live sessions can carry one agent id, and this file measures the mirror of it
-- two agent ids carrying one session string. `aimboard/exporters.py` is dirty at
the second revision (83 insertions by another hand); nothing here reads it.

Measured while writing this, and not asserted on: the derivation half of both
cards already exists in the board. `aimboard/fabric.py:49 channel_kind()` and
`:58 channel_lifecycle()` derive kind and state, and `load_fabric` spreads the
lifecycle onto every channel dict at `aimboard/fabric.py:257` (`**lifecycle`; the
manifest echo is the line above it, `:254`). `cmd_status` (`bin/aim` 3757) prints
topic, phase, leader, rules, participants, history and the log count -- and
neither `kind` nor `state`. The gap is the CLI, so that is where the assertions
land, with the model asserted beside them so a failure cannot be read as "the
derivation is missing".

Also measured, and a discrepancy worth recording rather than asserting: T-0216's
comment says "AGENTS.md tells every new session to start at `hello`". `grep -n
hello AGENTS.md` returns nothing today; the surviving `hello` in the docs is a
copy-paste example at `README.md:524`. The store half of that card is a surgery
(rename or retire `hello`, update the docs) and is not encoded here; what this
file encodes is the capability whose absence let the store reach that shape --
nothing at the CLI says a channel is empty, so the channel named for the
development work and the channel the development happened in print the same
declaration block.

Run: python3 tests/test_channel_project.py     (exit code = number of failures)
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))

from aimboard.fabric import (DORMANT_AFTER_DAYS, channel_kind,  # noqa: E402
                             channel_lifecycle)

AIM = HERE / "bin" / "aim"

# The vocabulary the cards are written in. `session` is deliberately *not* here:
# the word occurs in `register --session`, and that flag is the thing this file
# measures as not-an-answer (see the revision paragraph above).
PROJECT_WORDS = re.compile(
    r"\b(projects?|working[- ]on|which channel|whose channel|current channel|"
    r"unassigned|whereabouts|where am i|lifecycle|scratch)\b", re.I)
# Names that are not subcommands today; probed so "absent" is measured, not assumed.
ABSENT_PROBES = ("project", "projects", "session", "sessions", "where",
                 "whereami", "whoami", "current", "working-on", "context",
                 "doing", "assignment", "lifecycle")
# Every shape a candidate surface might take: with the session string, with the
# agent id, with either alone, and with nothing.
ARGV_FORMS = (("--as", "alpha", "--session", "SESSION"),
              ("--as", "alpha"),
              ("--session", "SESSION"),
              ("alpha",),
              ())

ATLAS, PROBE = "atlas", "probe"
EMPTY_CH, LIVE_CH = "no-traffic", "has-traffic"
ANCHOR, ALIAS = "alpha", "beta"
# Two agent ids, one session string: the live registry holds two ids whose entry
# reads `pts/7 claude pid 1697672`, and T-0242 is the reason `session_of` exists
# (`bin/aim` 768). A surface handed "a session id" must therefore answer through
# the agent id, or say which id it means.
SESSION = "pts/9 t0232 fixture 4242"


def aim(root, *argv):
    env = dict(os.environ, AIM_ROOT=str(root))
    argv = [SESSION if a == "SESSION" else a for a in argv]
    return subprocess.run([sys.executable, str(AIM), *[str(a) for a in argv]],
                          capture_output=True, text=True, env=env, timeout=120)


def help_of(root, *argv):
    p = aim(root, *argv, "--help")
    return p.stdout + p.stderr


def subcommands(root):
    m = re.search(r"\{([a-z0-9,\-]+)\}", help_of(root))
    return m.group(1).split(",") if m else []


def project_surfaces(root):
    """Every surface that could answer the card, found, not named by this file.

    The probes run in parallel: a help page is one `python3 bin/aim` process, and
    the 26 subcommands plus the 13 absent names would be 39 of them in series,
    most of a minute for a discovery that must be cheap enough to run on every
    suite. Measured: the whole file is under 7s.
    """
    subs = subcommands(root)
    names = list(subs) + [n for n in ABSENT_PROBES if n not in subs]
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=8) as pool:
        probes = dict(zip(names, pool.map(lambda n: help_of(root, n), names)))
    found = [n for n in subs if PROJECT_WORDS.search(probes[n])]
    found += [n for n in ABSENT_PROBES
              if n not in subs and "invalid choice" not in probes[n]]
    return subs, found


def answers(root, name):
    """{argv shape: what it printed} for every shape this surface answers to."""
    out = {}
    for argv in ARGV_FORMS:
        p = aim(root, name, *argv)
        text = (p.stdout + p.stderr).strip()
        if p.returncode == 0 and text:
            out[argv] = text
    return out


def labelled(out, word):
    """Is `word` stated as a field value, rather than mentioned inside a topic?

    `cmd_status` prints the topic verbatim (`bin/aim` 3762) and the topic of a
    topic-derived scratch channel *begins* with the discriminator, so a substring
    test passes on the channel's own name for itself and measures nothing.
    """
    return bool(re.search(rf"(?im)^\s*[a-z][\w ]*?\s+{re.escape(word)}\s*$", out))


def manifest(root, cid):
    return json.loads((root / "channels" / cid / "manifest.json").read_text())


class ProjectIdentityTest(unittest.TestCase):
    """T-0232: which project is a session on, and is this channel a real one."""

    @classmethod
    def setUpClass(cls):
        cls.root = Path(tempfile.mkdtemp(prefix="aim-t0232-", dir="/tmp"))
        cls.before = Path(tempfile.mkdtemp(prefix="aim-t0232-before-", dir="/tmp"))
        for argv in (("init",),
                     ("register", "--as", "human", "--kind", "human",
                      "--session", "team leader"),
                     ("register", "--as", ANCHOR, "--kind", "codex",
                      "--session", SESSION),
                     ("register", "--as", ALIAS, "--kind", "claude",
                      "--session", SESSION),
                     ("new-channel", "--id", ATLAS, "--topic",
                      "aim development: the real work", "--participants",
                      f"human,{ANCHOR}", "--leader", "human"),
                     ("new-channel", "--id", PROBE, "--topic",
                      "scratch: does aim authenticate --as?", "--participants",
                      "human", "--leader", "human")):
            p = aim(cls.root, *argv)
            assert p.returncode == 0, f"setup aim {' '.join(argv)} -> {p.returncode}: {p.stderr}"
        # The move happens once, after the snapshot, so the two roots differ by
        # the recorded act and by nothing else.
        shutil.rmtree(cls.before)
        shutil.copytree(cls.root, cls.before)
        for argv in (("channel", "remove", "--as", "human", "--channel", ATLAS,
                      "--agent", ANCHOR, "--reason", "T-0232: the session moves"),
                     ("channel", "add", "--as", "human", "--channel", PROBE,
                      "--agent", ANCHOR, "--reason", "T-0232: the session moves")):
            p = aim(cls.root, *argv)
            assert p.returncode == 0, f"setup aim {' '.join(argv)} -> {p.returncode}: {p.stderr}"
        cls.subs, cls.surfaces = project_surfaces(cls.root)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.root, ignore_errors=True)
        shutil.rmtree(cls.before, ignore_errors=True)

    def test_the_move_is_one_recorded_act_and_edits_no_field(self):
        left = (self.root / "channels" / ATLAS / "ledger.jsonl").read_text()
        joined = (self.root / "channels" / PROBE / "ledger.jsonl").read_text()
        self.assertIn("channel_member_removed", left, "the leaving is not in the ledger")
        self.assertIn("channel_member_added", joined, "the joining is not in the ledger")
        for ledger in (left, joined):
            self.assertIn(ANCHOR, ledger, "the membership record does not name the session")
            self.assertIn("T-0232: the session moves", ledger,
                          "the record does not say why the membership changed")
        self.assertEqual(manifest(self.root, ATLAS)["participants"], ["human"])
        self.assertEqual(manifest(self.root, PROBE)["participants"], ["human", ANCHOR])
        # The card's "no hand edit": the move edits the manifests and the ledgers
        # and nothing else. The registry is where a hand-maintained field would
        # have to live, so it is compared byte for byte across the move.
        self.assertEqual(
            (self.before / "registry.json").read_bytes(),
            (self.root / "registry.json").read_bytes(),
            "the move rewrote the registry: there is a field being maintained by hand")
        # And the session string is not a key: one string, two registered ids.
        reg = json.loads((self.root / "registry.json").read_text())["agents"]
        self.assertEqual(reg[ANCHOR]["session"], reg[ALIAS]["session"])
        self.assertNotEqual(ANCHOR, ALIAS)

    @unittest.expectedFailure
    def test_one_command_answers_which_project_a_session_is_on(self):
        self.assertTrue(
            self.surfaces,
            "no `aim` surface says which project a session is on. Probed subcommands "
            f"{self.subs} for help text matching {PROJECT_WORDS.pattern!r}, and probed "
            f"the absent names {list(ABSENT_PROBES)}; none matched and none exists.")
        missing = []
        for name in self.surfaces:
            hits = [argv for argv, out in answers(self.root, name).items()
                    if PROBE in out]
            if not hits:
                missing.append(f"{name}: nothing it prints names the channel `{PROBE}`, "
                               f"which {ANCHOR} is a participant of")
        self.assertEqual(missing, [], "the project surface does not answer: "
                                      + "; ".join(missing))

    @unittest.expectedFailure
    def test_the_answer_follows_the_move_with_no_field_edited(self):
        self.assertTrue(
            self.surfaces,
            "no surface exists to compare across the move. Probed subcommands "
            f"{self.subs} and the absent names {list(ABSENT_PROBES)}.")
        self.assertEqual(
            (self.before / "registry.json").read_bytes(),
            (self.root / "registry.json").read_bytes())
        broken = []
        for name in self.surfaces:
            was, now = answers(self.before, name), answers(self.root, name)
            shared = sorted(set(was) & set(now))
            if not shared:
                broken.append(f"{name}: answered nothing on one of the two roots")
                continue
            argv = shared[0]
            if ATLAS not in was[argv]:
                broken.append(f"{name} {list(argv)}: before the move it did not name "
                              f"`{ATLAS}` (got {was[argv]!r})")
            if PROBE not in now[argv]:
                broken.append(f"{name} {list(argv)}: after the move it did not name "
                              f"`{PROBE}` (got {now[argv]!r})")
            if was[argv] == now[argv]:
                broken.append(f"{name} {list(argv)}: the same answer on both roots, so "
                              f"it is a stored field and not a derived one")
        self.assertEqual(broken, [], "the answer does not follow the move: "
                                     + "; ".join(broken))

    @unittest.expectedFailure
    def test_a_channel_says_whether_it_is_a_real_project_or_a_throwaway(self):
        # The model half is asserted first: the derivation exists (`channel_kind`,
        # `aimboard/fabric.py:49`) and this failure is the CLI not printing it.
        self.assertEqual(channel_kind(manifest(self.root, PROBE)), "scratch")
        self.assertEqual(channel_kind(manifest(self.root, ATLAS)), "project")
        scratch = aim(self.root, "status", "--channel", PROBE).stdout
        real = aim(self.root, "status", "--channel", ATLAS).stdout
        self.assertTrue(
            labelled(scratch, "scratch"),
            f"`aim status --channel {PROBE}` does not state that the channel is a "
            f"throwaway; it prints the same declaration block as a real project. "
            f"Got: {scratch!r}")
        self.assertFalse(
            labelled(real, "scratch"),
            f"`aim status --channel {ATLAS}` calls a real project a throwaway: {real!r}")


class ChannelLifecycleSurfaceTest(unittest.TestCase):
    """T-0216, the half a capability can be held to: nothing says a channel is
    empty, so `dev` and the transport test print the same declaration block."""

    @classmethod
    def setUpClass(cls):
        cls.root = Path(tempfile.mkdtemp(prefix="aim-t0216-", dir="/tmp"))
        for argv in (("init",),
                     ("register", "--as", "human", "--kind", "human",
                      "--session", "team leader"),
                     ("register", "--as", ANCHOR, "--kind", "codex",
                      "--session", SESSION),
                     ("new-channel", "--id", EMPTY_CH, "--topic",
                      "aim development: task store, rooms, dashboard",
                      "--participants", f"human,{ANCHOR}", "--leader", "human"),
                     ("new-channel", "--id", LIVE_CH, "--topic",
                      "Transport test: can two sessions reach each other",
                      "--participants", f"human,{ANCHOR}", "--leader", "human"),
                     # One recorded act, so the second channel has traffic and the
                     # first has none. `aim say` cannot do this in
                     # SEALED_DIVERGENT (`bin/aim` 52: channel_say=False).
                     ("task", "new", "--as", ANCHOR, "--channel", LIVE_CH,
                      "--title", "the work that actually happened")):
            p = aim(cls.root, *argv)
            assert p.returncode == 0, f"setup aim {' '.join(argv)} -> {p.returncode}: {p.stderr}"
        cls.subs, cls.surfaces = project_surfaces(cls.root)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.root, ignore_errors=True)

    @unittest.expectedFailure
    def test_a_channel_says_whether_anything_ever_happened_in_it(self):
        # The derivation answers both states already -- asserted, so this measures
        # the surface that does not print them (`cmd_status`, `bin/aim` 3757).
        zero = {"messages": 0, "ledger": 0, "tasks": 0, "rooms": 0, "friction": 0,
                "seals": 0}
        empty = channel_lifecycle(manifest(self.root, EMPTY_CH), zero, "", None)
        busy = channel_lifecycle(manifest(self.root, LIVE_CH), dict(zero, tasks=1),
                                 "2026-09-22T00:00:00Z", None)
        self.assertEqual(empty["state"], "empty", empty)
        self.assertEqual(busy["state"], "active", busy)
        self.assertEqual(DORMANT_AFTER_DAYS, 2)
        empty_out = aim(self.root, "status", "--channel", EMPTY_CH).stdout
        live_out = aim(self.root, "status", "--channel", LIVE_CH).stdout
        self.assertTrue(
            labelled(empty_out, "empty"),
            f"`aim status --channel {EMPTY_CH}` does not say the channel has had no "
            f"traffic, so an operator cannot see that the channel named for the work "
            f"is the empty one. Got: {empty_out!r}")
        self.assertFalse(
            labelled(live_out, "empty"),
            f"`aim status --channel {LIVE_CH}` calls a channel with recorded work "
            f"empty: {live_out!r}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
