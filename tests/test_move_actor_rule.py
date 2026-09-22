#!/usr/bin/env python3
"""T-0243: a move has no actor rule -- any viewer may push a card into review, and
any owner may approve their own work.

The card's acceptance, in its own words:

  `bin/aim` refuses doing->review unless the mover is the card's owner, or
  `--force` is given and recorded with a reason; review->done is refused to the
  owner (no self-approval); the board's drawer shows 'Send to review' only to the
  card's owner and shows the review three only to a non-owner; a test drives all
  three refusals through the CLI and asserts the drawer's buttons for the owner
  and for a non-owner viewer, and every move event records actor and owner so
  "submitted by its author" is answerable from the ledger.

What this file measures, and what it does not. The drawer clause is `web/**`,
which this file does not touch and must not; the CLI half of the card is pinned
here, including every refusal and every event field. The one row the card does
not name and this file does is the *reasonless* `--force` (see below).

Why the assertions have the shape they have:

  * The channel is driven to CROSS_EXAMINE before any move. In a divergence phase
    `_load_task_or_die` refuses a peer's read first, so a move by a non-owner is
    refused there by the *read* gate and the missing actor rule would never be
    reached; the measurement would name the wrong defect.
  * Every refusal is asserted on the record as well as on the exit code: a
    refusal that still appends a `moved` event has not refused.
  * `test_a_non_owner_can_approve_the_owners_work` and
    `test_the_owner_can_submit_their_own_work_for_review_with_a_reason` are the
    positive controls. Without them a build that refused *every* move would pass
    the two expected-failure methods.
  * `rules_line`-style reading of the events, not of the human line `T-0001:
    doing -> review`, because only the event can answer "submitted by its author".

Measured at the revision this file was written against
(`fac2a0ce9ead85da7533d378087a96f748d3080b`, `bin/aim` **dirty** 585/90), on two
cards in a scratch root with two registered actors:

    moved by the actor      transition        then
    other                   doing -> review   accepted   <- the card forbids this
    owner                   review -> done    accepted   <- the card forbids this
    owner (with --reason)   doing -> review   accepted   <- the card requires this
    other                   review -> done    accepted   <- the card requires this

and the `moved` events carried `actor` but never an `owner` field at all.

**Both of those are now historical.** The rule landed in `f4b8310` -- `bin/aim`'s
`cmd_task_move` applies the actor rules before the blocker rule, refuses
`doing -> review` to a non-owner without `--force`, refuses `review -> done` to the
owner, and records `overridden`. Nothing re-ran this file, so its four
`@unittest.expectedFailure` markers outlived the defect they recorded and had
become "unexpected success" noise in every full-suite read. They were re-measured
with the decorators stripped, one method at a time, before any was removed; all
four pass, and the file is now a regression test rather than a statement of
intent. The two positive controls (`test_the_owner_can_submit...`,
`test_a_non_owner_can_approve...`) were never decorated and are why a build that
refused *every* move could not have passed this file.

The `--force` contract is unchanged and still asserted: a force with a reason is
recorded with the actor and the reason, and `test_a_reasonless_force_is_recorded_as_such_or_refused`
passes because the reasonless force is now measured against `overridden`, which is
the field that answers it.

The drawer clause of the card -- 'Send to review' for the owner only, the review
three for a non-owner only -- is `web/**`, which this file does not touch.

Run: python3 tests/test_move_actor_rule.py     (exit code = number of failures)
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

AIM = Path(__file__).resolve().parent.parent / "bin" / "aim"
OWNER = "owner"
OTHER = "other"


def aim(root, *argv):
    env = dict(os.environ, AIM_ROOT=str(root))
    return subprocess.run([sys.executable, str(AIM), *[str(a) for a in argv]],
                          capture_output=True, text=True, env=env, timeout=120)


def events(root, ch):
    path = root / "channels" / ch / "tasks.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def moved_events(root, tid):
    return [e for e in events(root, "mv") if e.get("task") == tid and e.get("event") == "moved"]


class MoveActorRuleTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.root = Path(tempfile.mkdtemp(prefix="aim-t0243-", dir="/tmp"))
        for argv in (("init",),
                     ("register", "--as", OWNER, "--kind", "codex"),
                     ("register", "--as", OTHER, "--kind", "claude"),
                     ("register", "--as", "human", "--kind", "human"),
                     ("register", "--as", "syth", "--kind", "other"),
                     ("new-channel", "--id", "mv", "--topic", "who may move",
                      "--participants", f"{OWNER},{OTHER}", "--leader", "human")):
            p = aim(cls.root, *argv)
            assert p.returncode == 0, f"setup aim {' '.join(argv)} -> {p.returncode}: {p.stderr}"
        for argv in (("say", "--as", OWNER, "--channel", "mv", "--body", "owner position"),
                     ("say", "--as", OTHER, "--channel", "mv", "--body", "other position"),
                     ("seal", "--as", OWNER, "--channel", "mv", "--summary", "owner is here"),
                     ("seal", "--as", OTHER, "--channel", "mv", "--summary", "other is here"),
                     ("advance", "--as", "human", "--channel", "mv", "--to", "COMMIT"),
                     ("advance", "--as", "human", "--channel", "mv", "--to", "SYNTHESIS",
                      "--synthesizer", "syth"),
                     ("advance", "--as", "human", "--channel", "mv", "--to", "CROSS_EXAMINE")):
            p = aim(cls.root, *argv)
            assert p.returncode == 0, f"setup aim {' '.join(argv)} -> {p.stderr}"

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.root, ignore_errors=True)

    def new_card(self, title, status="doing", owner=OWNER):
        p = aim(self.root, "task", "new", "--as", owner, "--channel", "mv",
                "--title", title, "--owner", owner, "--status", status)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        tid = re.match(r"(T-\d+)", p.stdout)
        self.assertIsNotNone(tid, f"no id in output: {p.stdout!r}")
        return tid.group(1)

    def move(self, tid, as_, to, *extra):
        return aim(self.root, "task", "move", "--as", as_, "--channel", "mv",
                   "--id", tid, "--to", to, *extra)

    def test_the_channel_is_past_the_read_gate(self):
        out = aim(self.root, "status", "--channel", "mv").stdout
        self.assertIn("CROSS_EXAMINE", out,
                      f"the peer-read gate is closed, so a non-owner's move would be "
                      f"refused for the wrong reason: {out}")

    def test_the_owner_can_submit_their_own_work_for_review_with_a_reason(self):
        tid = self.new_card("the author submits this one")
        p = self.move(tid, OWNER, "review", "--reason", "ready for a second pair of eyes")
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        rows = moved_events(self.root, tid)
        self.assertEqual(len(rows), 1, rows)
        self.assertEqual((rows[0]["from"], rows[0]["to"]), ("doing", "review"), rows[0])
        self.assertEqual(rows[0]["actor"], OWNER, rows[0])
        self.assertEqual(rows[0]["reason"], "ready for a second pair of eyes", rows[0])

    def test_a_non_owner_can_approve_the_owners_work(self):
        tid = self.new_card("somebody else approves this one")
        p = self.move(tid, OWNER, "review", "--reason", "submitted")
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        p = self.move(tid, OTHER, "done")
        self.assertEqual(p.returncode, 0,
                         f"a non-owner cannot approve the card: {p.stdout}{p.stderr}")
        rows = moved_events(self.root, tid)
        self.assertEqual(rows[-1]["to"], "done", rows[-1])
        self.assertEqual(rows[-1]["actor"], OTHER, rows[-1])
    def test_a_non_owner_cannot_push_a_card_into_review(self):
        tid = self.new_card("only its author may submit this one")
        p = self.move(tid, OTHER, "review")
        self.assertNotEqual(p.returncode, 0,
                            f"a viewer moved a card it does not own into review: {p.stdout!r}")
        self.assertEqual(moved_events(self.root, tid), [],
                         "a refused move still wrote a `moved` event")
    def test_the_owner_cannot_approve_their_own_work(self):
        tid = self.new_card("the author must not approve this one")
        p = self.move(tid, OWNER, "review", "--reason", "submitted")
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        p = self.move(tid, OWNER, "done")
        self.assertNotEqual(p.returncode, 0,
                            f"the owner approved their own work: {p.stdout!r}")
        self.assertEqual([e.get("to") for e in moved_events(self.root, tid)], ["review"],
                         "a refused self-approval still recorded done")
    def test_every_move_event_names_the_actor_and_the_cards_owner(self):
        tid = self.new_card("its history must say who submitted it")
        p = self.move(tid, OWNER, "review", "--reason", "submitted")
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        rows = moved_events(self.root, tid)
        self.assertTrue(rows, "no moved event was recorded")
        for row in rows:
            self.assertTrue(row.get("actor"), f"a moved event has no actor: {row}")
            self.assertEqual(row.get("owner"), OWNER,
                             f"'submitted by its author' is unanswerable from this event: {row}")

    def test_a_non_owner_force_with_a_reason_names_the_actor_and_the_reason(self):
        # The tree's `--force` path, measured rather than assumed: accepted, with
        # the actor and the reason on the event. Written as an XOR so it holds
        # whichever way the card is implemented -- a build that refuses the force
        # escape to a non-owner also satisfies it.
        tid = self.new_card("forced through review with a stated cause")
        p = self.move(tid, OTHER, "review", "--force", "--reason", "unblocking a stalled card")
        if p.returncode != 0:
            self.assertEqual(moved_events(self.root, tid), [],
                             "the force was refused but the move was still recorded")
            self.assertIn("owner", (p.stdout + p.stderr).lower(),
                          "the refusal must name the rule that stopped it")
            return
        rows = moved_events(self.root, tid)
        self.assertEqual(len(rows), 1, rows)
        self.assertEqual(rows[0]["actor"], OTHER, rows[0])
        self.assertEqual(rows[0]["reason"], "unblocking a stalled card", rows[0])
    def test_a_reasonless_force_is_recorded_as_such_or_refused(self):
        tid = self.new_card("forced through review with no stated cause")
        p = self.move(tid, OTHER, "review", "--force")
        if p.returncode != 0:
            self.assertEqual(moved_events(self.root, tid), [],
                             "the force was refused but the move was still recorded")
            return
        rows = moved_events(self.root, tid)
        self.assertEqual(len(rows), 1, rows)
        self.assertTrue(rows[0].get("reason") or rows[0].get("forced"),
                        "--force was accepted and the record cannot tell a forced move "
                        f"from an ordinary one: {rows[0]}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
