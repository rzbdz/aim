#!/usr/bin/env python3
"""T-0213: the phase owns the rules, and `advance` must say which rule it moved.

The card, in its own words:

  `aim advance` names which of read_others/channel_say/private_say it changed,
  and labels an advance that changes no rule as such; the barrier pane states
  which phase next opens reading.

The card's evidence is `design/12-architecture-review.md` §1.2, measured today:
`aim status --channel hello` reports `phase COMMIT rules {'read_others': False,
'channel_say': False, 'private_say': True}`, and the leader advanced to COMMIT
expecting cross-examination to open. Only CROSS_EXAMINE sets `read_others=True`,
so the advance moved a label and changed nothing — and nothing said so.

Why the assertions have the shape they have:

  * The two advances are run in the same throwaway fabric and compared: one that
    changes no rule (SEALED_DIVERGENT -> COMMIT) and one that does (SYNTHESIS ->
    CROSS_EXAMINE). A test that only asserted the second could not tell "the
    diff is printed" from "the diff is printed only when it is non-empty".
  * The three rule names are read from `PHASE_RULES` as the tool prints them in
    `aim status`, not from the design note: §1.2 says "five rules", the tool has
    three, and the card is authoritative for which three.
  * `test_the_advance_to_commit_changes_no_rule` is not decorated, and it exists
    so the failing methods cannot pass by the phase table having quietly changed
    underneath them.
  * The card's third clause is about the barrier *pane* (`web/**`, which this
    file does not touch). The sentence the pane must carry is the sentence its
    own acceptance quotes — "CROSS_EXAMINE is the next phase that opens it" — so
    it is pinned here on the CLI's copy of the same fact.

Revision measured: `abb177f` with `bin/aim` clean, since re-measured -- the file
was written against `fac2a0ce9ead85da7533d378087a96f748d3080b`, where `cmd_advance`
printed only `ch: SEALED_DIVERGENT -> COMMIT (round 0, by human)` and all three
methods below were `@unittest.expectedFailure`. The acceptance landed afterwards
and nothing re-ran the file, so the markers outlived the defect: two of them now
pass, and the third fails on the *value* the tool prints rather than on the
sentence it prints. Re-measured one method at a time with the decorators stripped
before any of them was removed -- a marker is evidence only until someone checks
what is under it.

What the third one found. The advance that opens `read_others` and `channel_say`
printed

    this advance changed 2: read_others: open -> open; channel_say: open -> open

because the `was` side of the arrow was inverted (`'closed' if was else 'open'`).
The fix is in `bin/aim` and not here: this file asserts on the tool's own
vocabulary rather than on the words `True`/`False`, because the line exists to be
read by a person and `read_others: closed -> open` is what it has to say. Pinning
`True` would have pinned a rendering and let the inversion through.

Run: python3 tests/test_advance_rule_diff.py     (exit code = number of failures)
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

AIM = Path(__file__).resolve().parent.parent / "bin" / "aim"
RULES = ("read_others", "channel_say", "private_say")


def aim(root, *argv):
    env = dict(os.environ, AIM_ROOT=str(root))
    return subprocess.run([sys.executable, str(AIM), *[str(a) for a in argv]],
                          capture_output=True, text=True, env=env, timeout=120)


def rules_line(root, channel):
    """The rule dict `aim status` prints, as a dict, not as a substring."""
    out = aim(root, "status", "--channel", channel).stdout
    for line in out.splitlines():
        if line.startswith("rules"):
            return {k: v for k, v in re.findall(r"'(\w+)': (\w+)", line)}
    return {}


class AdvanceRuleDiffTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.root = Path(tempfile.mkdtemp(prefix="aim-t0213-", dir="/tmp"))
        for argv in (("init",),
                     ("register", "--as", "alpha", "--kind", "codex"),
                     ("register", "--as", "beta", "--kind", "claude"),
                     ("register", "--as", "human", "--kind", "human"),
                     ("register", "--as", "syth", "--kind", "other"),
                     ("new-channel", "--id", "ch", "--topic", "the rule diff",
                      "--participants", "alpha,beta", "--leader", "human")):
            p = aim(cls.root, *argv)
            assert p.returncode == 0, f"setup aim {' '.join(argv)} -> {p.returncode}: {p.stderr}"

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.root, ignore_errors=True)

    def fresh_channel(self):
        """A channel per test, so a phase one test advances cannot move another."""
        cls = type(self)
        cls._seq = getattr(cls, "_seq", 0) + 1
        ch = f"ch{cls._seq}"
        p = aim(self.root, "new-channel", "--id", ch, "--topic", "the rule diff",
                "--participants", "alpha,beta", "--leader", "human")
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        return ch

    def advance(self, ch, to, expect=0, *extra):
        p = aim(self.root, "advance", "--as", "human", "--channel", ch, "--to", to, *extra)
        self.assertEqual(p.returncode, expect, p.stdout + p.stderr)
        return p.stdout + p.stderr

    def seal_everyone(self, ch):
        for who in ("alpha", "beta"):
            p = aim(self.root, "seal", "--as", who, "--channel", ch,
                    "--summary", f"{who} committed a position before reading a peer")
            self.assertEqual(p.returncode, 0, p.stdout + p.stderr)

    def test_the_advance_to_commit_changes_no_rule(self):
        ch = self.fresh_channel()
        before = rules_line(self.root, ch)
        self.assertEqual(before, {"read_others": "False", "channel_say": "False",
                                  "private_say": "True"},
                         "the phase table this file measures has changed")
        self.advance(ch, "COMMIT")
        self.assertEqual(rules_line(self.root, ch), before,
                         "COMMIT now changes a rule; the no-rule-change case must be re-measured")

    def test_an_advance_that_changes_no_rule_is_labelled(self):
        ch = self.fresh_channel()
        out = self.advance(ch, "COMMIT")
        for rule in RULES:
            self.assertIn(rule, out, f"advance did not name the rule it applied: {out!r}")
        self.assertRegex(out, r"(?i)no rule|nothing|unchanged|changed no rule",
                         f"an advance that changed no rule was reported as progress: {out!r}")
        self.assertIn("CROSS_EXAMINE", out,
                      f"the output must name the phase that next opens reading: {out!r}")

    def test_an_advance_that_opens_a_rule_names_the_rule_and_the_values(self):
        ch = self.fresh_channel()
        self.seal_everyone(ch)
        self.advance(ch, "COMMIT")
        self.advance(ch, "SYNTHESIS", 0, "--synthesizer", "syth")
        out = self.advance(ch, "CROSS_EXAMINE")
        for rule in ("read_others", "channel_say"):
            self.assertIn(rule, out, f"advance did not name the rule it opened: {out!r}")
        # Both arrows, not only the new value. `read_others[^\n]*True` passed on a
        # line that read `read_others: open -> open` -- the *old* side was the
        # inverted one -- so the assertion that catches it has to be about the
        # transition, which is the thing the line is for.
        for rule in ("read_others", "channel_say"):
            self.assertRegex(out, rf"{rule}: closed -> open",
                             f"{rule} is opened by this advance and the line does not say "
                             f"what it moved from: {out!r}")

    def test_the_three_rules_are_printed_with_their_values(self):
        ch = self.fresh_channel()
        out = self.advance(ch, "COMMIT")
        self.assertRegex(out, r"read_others[^\n]*(False|closed)",
                         f"read_others is not printed with its value: {out!r}")
        self.assertRegex(out, r"channel_say[^\n]*(False|closed)",
                         f"channel_say is not printed with its value: {out!r}")
        self.assertRegex(out, r"private_say[^\n]*(True|open)",
                         f"private_say is not printed with its value: {out!r}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
