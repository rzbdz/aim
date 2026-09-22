#!/usr/bin/env python3
"""T-0230: `aim say` must not become a private note and call that success.

The card, in its own words:

  When `channel_say` is false, `aim say` either refuses and says why, or writes
  the public message; it never reports success while the message reached nobody
  but the writer. Observable: run `aim say` in a channel whose rules show
  `channel_say False`, then `aim status --channel <ch>` -- the public count must
  move, or the command must exit non-zero naming the rule that stopped it.

Why the assertions have the shape they have:

  * The public count is read from `channels/<ch>/log.jsonl` -- the same file
    `aim status` counts -- so "the count moved" cannot pass because a *private*
    file was appended to. `aim status`'s `log N public messages` line is checked
    as well, because that is the surface the card names.
  * The decision rule the card states is XOR, encoded as XOR: a non-zero exit
    that names `channel_say`, or exactly one new public record. Success with the
    message filed privately satisfies neither.
  * `test_say_reaches_the_public_log_when_the_phase_opens_the_channel` is the
    positive control: CROSS_EXAMINE has `channel_say=True`, and if `say` did not
    deliver there, the failing method would be measuring a broken verb rather
    than a silent one.
  * `test_the_status_rule_is_the_one_the_gate_is_measured_against` fails fast if
    the phase table moved underneath the measurement.

The private routing itself is documented (`README.md`: `aim say ... # private,
pre-barrier`); what the card calls a defect is that the command exits 0, moves
no public count, and never names the rule that sent the message to the writer's
own log.

Revision measured: `fac2a0ce9ead85da7533d378087a96f748d3080b` (HEAD) with
`bin/aim` **dirty** (585 insertions / 90 deletions vs HEAD) and `/api/revision`
`stale: true`. This behaviour came from **committed** lines --

    to_public = kind_of == "synthesis" or phase not in ("SEALED_DIVERGENT", "COMMIT", "SYNTHESIS")
    print(f"[private/{who}] {kind_of} recorded ({len(body)} chars)")

Measured in COMMIT on that build:

    $ aim say --as alpha --channel gated --body "..."
    [private/alpha] note recorded (71 chars)        (exit 0; public log still 0)

which was the failing row, and `test_say_moves_the_public_count_or_refuses_by_name`
was `@unittest.expectedFailure`.

**T-0230 landed the fix, and the decorator was removed deliberately.** Here is the
measurement that removed it, and the two behaviours it has to keep.

`to_public` was a second copy of `PHASE_RULES[phase]["channel_say"]`, spelled as a
list of phase *names*. That is the drift `bin/aim:135-139` forbids: the expression
answers "is the public channel open" and was being read as "where does this
message go". So a `note` -- a member of the *public* vocabulary,
`COMMITMENT_KINDS` -- was filed privately because the phase happened to be closed,
and the command reported that as success. Measured after the fix, same channel,
same phase:

    $ aim say --as alpha --channel gated --body "a message the public count must account for"
    aim: REFUSED: channel is in COMMIT; channel_say is False — the public channel is closed.
    Write to your private log instead: `aim say --private`, or a kind with no public route (claim/position).
    exit=2

    $ aim status --channel gated | grep '^log'
    log       0 public messages      # unchanged, and the command said so instead

The destination is now derived from the rule table plus a declared intent, never
from the phase name: `synthesis` | `--public` | (a declared `--private`, or a kind
with no public route such as `claim`/`position`) -> the private log; everything
else -> the public log, where `gate(...)` refuses by name. Two consequences are
pinned below, because a future change that refused *everything* while the channel
is shut would satisfy this card's XOR and delete the private path the fleet runs
on: `--private` still reaches the private log, and `--public` cannot downgrade.

`--private` is the old documented capability made declarable, not a new one:
`README.md` §6 has read `aim say ... # private, pre-barrier` since the first run,
and the fleet's pre-barrier traffic is private on purpose. `tests/selftest.sh`
lines 50/63/67 and `tests/conformance.py` lines 111/140/169 are that traffic and
opt in with `--private`; `test_move_actor_rule.py`, `test_unassigned.py`,
`test_a2a_conformance.py` and `attack_renderer_gate.py` carry the same calls. Those
files are outside this one's write set and are reported with the change rather
than edited here.

Run: python3 tests/test_say_channel_gate.py     (exit code = number of failures)
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

AIM = Path(__file__).resolve().parent.parent / "bin" / "aim"


def aim(root, *argv):
    env = dict(os.environ, AIM_ROOT=str(root))
    return subprocess.run([sys.executable, str(AIM), *[str(a) for a in argv]],
                          capture_output=True, text=True, env=env, timeout=120)


def public_log(root, ch):
    path = root / "channels" / ch / "log.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


class SayChannelGateTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.root = Path(tempfile.mkdtemp(prefix="aim-t0230-", dir="/tmp"))
        for argv in (("init",),
                     ("register", "--as", "alpha", "--kind", "codex"),
                     ("register", "--as", "beta", "--kind", "claude"),
                     ("register", "--as", "human", "--kind", "human"),
                     ("register", "--as", "syth", "--kind", "other"),
                     ("new-channel", "--id", "gated", "--topic", "still closed",
                      "--participants", "alpha,beta", "--leader", "human"),
                     ("new-channel", "--id", "open", "--topic", "open floor",
                      "--participants", "alpha,beta", "--leader", "human")):
            p = aim(cls.root, *argv)
            assert p.returncode == 0, f"setup aim {' '.join(argv)} -> {p.returncode}: {p.stderr}"
        # `gated` stops at COMMIT: channel_say is still False there, which is the
        # phase the card's evidence was measured in.
        p = aim(cls.root, "advance", "--as", "human", "--channel", "gated", "--to", "COMMIT")
        assert p.returncode == 0, p.stderr
        # `open` is driven to CROSS_EXAMINE for the positive control. The two
        # opening writes say `--private` because that is what they are: positions
        # formed *before* the channel opens, filed in the writer's own log. On the
        # old build they were private without saying so (`channel_say` was False
        # in SEALED_DIVERGENT and the phase decided); on this one the intent is
        # declared, which is the whole change. A fixture that relied on the silent
        # downgrade would be measuring the defect rather than the fix.
        for argv in (("say", "--as", "alpha", "--channel", "open", "--private",
                      "--body", "alpha position"),
                     ("say", "--as", "beta", "--channel", "open", "--private",
                      "--body", "beta position"),
                     ("seal", "--as", "alpha", "--channel", "open", "--summary", "alpha is here"),
                     ("seal", "--as", "beta", "--channel", "open", "--summary", "beta is here"),
                     ("advance", "--as", "human", "--channel", "open", "--to", "COMMIT"),
                     ("advance", "--as", "human", "--channel", "open", "--to", "SYNTHESIS",
                      "--synthesizer", "syth"),
                     ("advance", "--as", "human", "--channel", "open", "--to", "CROSS_EXAMINE")):
            p = aim(cls.root, *argv)
            assert p.returncode == 0, f"setup aim {' '.join(argv)} -> {p.stderr}"

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.root, ignore_errors=True)

    def test_the_status_rule_is_the_one_the_gate_is_measured_against(self):
        out = aim(self.root, "status", "--channel", "gated").stdout
        self.assertIn("phase     COMMIT", out, out)
        self.assertIn("'channel_say': False", out, "the gate under test is not closed")
        self.assertIn("'private_say': True", out, "the private log is not open")

    def test_say_moves_the_public_count_or_refuses_by_name(self):
        # `@unittest.expectedFailure` was removed here when T-0230 landed, and its
        # absence is the point of the file rather than tidying: the decorator said
        # "this method asserts a capability the build does not have", and on a
        # build where `say` refuses and names `channel_say` it reports *unexpected
        # success*, which unittest counts as a failure. The header records the
        # before/after CLI transcript the removal was measured against. It is not
        # weakened: the same XOR is asserted, unchanged, and it now passes on the
        # tool's own output rather than on a promise.
        before = public_log(self.root, "gated")
        p = aim(self.root, "say", "--as", "alpha", "--channel", "gated",
                "--body", "a message the public count must account for")
        after = public_log(self.root, "gated")
        moved = len(after) == len(before) + 1
        refused_by_name = p.returncode != 0 and "channel_say" in (p.stdout + p.stderr)
        status = aim(self.root, "status", "--channel", "gated").stdout
        self.assertTrue(
            moved or refused_by_name,
            "channel_say is False and the command neither moved the public count nor "
            f"refused by name: exit={p.returncode}, public {len(before)} -> {len(after)}, "
            f"stdout={p.stdout.strip()!r}, stderr={p.stderr.strip()!r}, "
            f"status log line={[l for l in status.splitlines() if l.startswith('log')]}")

    def test_a_declared_private_write_still_reaches_the_private_log(self):
        # The other half of the XOR, and the reason T-0230 could not be closed by
        # refusing every write while the channel is shut: `private_say` is True in
        # COMMIT, the private log is where pre-barrier reasoning goes, and
        # `--private` is that capability said out loud. A build that refused this
        # would pass the method above and delete the path the fleet runs on.
        priv = self.root / "channels" / "gated" / "private" / "alpha.jsonl"
        before = priv.read_text().count("\n") if priv.exists() else 0
        public_before = len(public_log(self.root, "gated"))
        p = aim(self.root, "say", "--as", "alpha", "--channel", "gated", "--private",
                "--body", "reasoning that is mine to hold: t0230")
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        after = priv.read_text().count("\n")
        self.assertEqual(after, before + 1, f"--private wrote nothing: {p.stdout!r}")
        self.assertIn("reasoning that is mine to hold: t0230", priv.read_text())
        # Read as a count, not as a comparison of two reads of one file: the
        # private route must leave the public log exactly as it found it.
        self.assertEqual(len(public_log(self.root, "gated")), public_before,
                         "a private write moved the public log")

    def test_the_public_route_cannot_downgrade_to_a_private_note(self):
        # `--public` is the one route that must never end in the writer's own log:
        # the message was aimed at the channel, and a run that filed it privately
        # while printing success is exactly the defect this card measured. So the
        # private log is checked for the body, not just the exit status.
        priv = self.root / "channels" / "gated" / "private" / "alpha.jsonl"
        before = priv.read_text() if priv.exists() else ""
        p = aim(self.root, "say", "--as", "alpha", "--channel", "gated", "--public",
                "--body", "aimed at the channel while it was shut: t0230")
        self.assertNotEqual(p.returncode, 0, f"--public must not succeed: {p.stdout!r}")
        self.assertIn("channel_say", p.stdout + p.stderr)
        self.assertEqual(priv.read_text() if priv.exists() else "", before,
                         "--public downgraded to a private note, which is the defect")

    def test_say_reaches_the_public_log_when_the_phase_opens_the_channel(self):
        before = public_log(self.root, "open")
        p = aim(self.root, "say", "--as", "alpha", "--channel", "open", "--kind", "note",
                "--body", "a public note with a label that appears nowhere else: t0230")
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        after = public_log(self.root, "open")
        self.assertEqual(len(after), len(before) + 1,
                         f"a say in CROSS_EXAMINE did not reach the public log: {p.stdout!r}")
        self.assertEqual(after[-1]["body"], "a public note with a label that appears nowhere else: t0230")


if __name__ == "__main__":
    unittest.main(verbosity=2)
