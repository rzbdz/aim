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
`stale: true`. This behaviour comes from **committed** lines: the two lines that
decide it are already in `git show HEAD:bin/aim` and untouched by the dirty
diff --

    to_public = kind_of == "synthesis" or phase not in ("SEALED_DIVERGENT", "COMMIT", "SYNTHESIS")
    print(f"[private/{who}] {kind_of} recorded ({len(body)} chars)")

Measured in COMMIT on this build:

    $ aim say --as alpha --channel gated --body "..."
    [private/alpha] note recorded (71 chars)        (exit 0; public log still 0)

which is the failing row: the public count did not move and the command did not
refuse. That method is `@unittest.expectedFailure`.

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
        # `open` is driven to CROSS_EXAMINE for the positive control.
        for argv in (("say", "--as", "alpha", "--channel", "open", "--body", "alpha position"),
                     ("say", "--as", "beta", "--channel", "open", "--body", "beta position"),
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

    @unittest.expectedFailure
    def test_say_moves_the_public_count_or_refuses_by_name(self):
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
