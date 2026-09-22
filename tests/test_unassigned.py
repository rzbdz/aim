#!/usr/bin/env python3
"""T-0226: work is unowned until someone picks it up.

The card, in its own words:

  `aim task new` without `--owner` records owner "" (unassigned) instead of the
  creator; `aim task claim --as X --channel ch --id T-nnnn` assigns X and is
  recorded as an assigned event with `from ""`; any participant of the channel
  can claim an unowned item, and releasing one (assign to "") is recorded with
  actor and reason; an unowned item is readable by every participant even in a
  divergence phase, while an owned draft keeps the rule that only its owner and
  its creator may read it. `tests/test_unassigned.py` fails on the current build.

Why the assertions have the shape they have:

  * The unowned state is read out of `channels/ch/tasks.jsonl`, not out of the
    human line `T-0001 created (backlog, draft) — …  [unowned — …]`. The line is
    a rendering; the event is the record, and a card is unowned exactly when the
    `created` event says `owner: ""`.
  * The claim is asserted on its `assigned` event with `from: ""` and
    `via: "claim"`, because "I took this" is a claim about the *absence* of a
    prior owner, and only the record can make it survive a disagreement.
  * An owned draft is checked in the same divergence phase as the unowned one,
    so "unowned is readable" cannot pass because the phase happened to be open.
  * Releasing is checked from the record too: a release with no reason is
    refused, and the reason that is accepted lands on the event.

Revision measured: `fac2a0ce9ead85da7533d378087a96f748d3080b` (HEAD) with
`bin/aim` **dirty** -- `git diff --numstat bin/aim` = 585 insertions / 90
deletions, and `/api/revision` reports `stale: true`. The behaviour asserted here
comes from the **uncommitted** lines of that diff: it removes `"owner":
args.owner or who` in favour of `"owner": args.owner or ""` and adds
`cmd_task_claim`, `cmd_task_assign`'s release branch, and the unowned clause in
`_visible_to`. Against the committed revision this file fails (HEAD has no
`task claim` verb and every `created` event carries the creator as owner).

Run: python3 tests/test_unassigned.py     (exit code = number of failures)
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


def aim(root, *argv):
    env = dict(os.environ, AIM_ROOT=str(root))
    return subprocess.run([sys.executable, str(AIM), *[str(a) for a in argv]],
                          capture_output=True, text=True, env=env, timeout=120)


def events(root, ch):
    path = root / "channels" / ch / "tasks.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def created_id(proc):
    m = re.search(r"(T-\d+) created", proc.stdout)
    return m.group(1) if m else None


class UnassignedTest(unittest.TestCase):
    """A throwaway fabric under /tmp, driven only through bin/aim."""

    @classmethod
    def setUpClass(cls):
        cls.root = Path(tempfile.mkdtemp(prefix="aim-t0226-", dir="/tmp"))
        setup = [
            ("init",),
            ("register", "--as", "alpha", "--kind", "codex"),
            ("register", "--as", "beta", "--kind", "claude"),
            ("register", "--as", "human", "--kind", "human"),
            ("register", "--as", "gamma", "--kind", "codex"),      # registered, in no channel
            ("new-channel", "--id", "ch", "--topic", "ownership", "--participants", "alpha,beta",
             "--leader", "human"),
            ("new-channel", "--id", "pool", "--topic", "an open pool", "--participants",
             "alpha,beta", "--leader", "human"),
            # `open` exists so the held-card refusal can be read in a phase where
            # the peer-read gate is not the thing that fires first: in
            # SEALED_DIVERGENT the claim is refused by _visible_to, not by the
            # owner check, and the remedy the tool advertises is then unproven.
            ("new-channel", "--id", "open", "--topic", "past the barrier",
             "--participants", "alpha,beta", "--leader", "human"),
            ("register", "--as", "syth", "--kind", "other"),
        ]
        for argv in setup:
            p = aim(cls.root, *argv)
            assert p.returncode == 0, f"setup aim {' '.join(argv)} -> {p.returncode}: {p.stderr}"

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.root, ignore_errors=True)

    def new_card(self, channel="ch", owner=None, title="a card"):
        argv = ["task", "new", "--as", "alpha", "--channel", channel, "--title", title]
        if owner:
            argv += ["--owner", owner]
        p = aim(self.root, *argv)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        tid = created_id(p)
        self.assertIsNotNone(tid, f"no id in output: {p.stdout!r}")
        return tid

    def test_created_event_without_owner_carries_an_empty_owner(self):
        tid = self.new_card(title="nobody holds this yet")
        rows = [e for e in events(self.root, "ch") if e.get("task") == tid
                and e.get("event") == "created"]
        self.assertEqual(len(rows), 1, f"created rows: {rows}")
        self.assertIn("owner", rows[0], f"the record has no owner field: {rows[0]}")
        self.assertEqual(rows[0]["owner"], "",
                         "the creator was recorded as the owner of a card nobody assigned")
        self.assertEqual(rows[0]["actor"], "alpha", "the creator is still the actor")

    def test_task_list_calls_an_unowned_card_unclaimed(self):
        self.new_card(channel="pool", title="readable by the pool")
        p = aim(self.root, "task", "list", "--as", "beta", "--channel", "pool")
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn("unclaimed", p.stdout,
                      f"an unowned card was not reported as unclaimed: {p.stdout!r}")

    def test_a_participant_claims_an_unowned_card_with_an_empty_from(self):
        tid = self.new_card(title="beta will take this")
        p = aim(self.root, "task", "claim", "--as", "beta", "--channel", "ch", "--id", tid)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        rows = [e for e in events(self.root, "ch") if e.get("task") == tid
                and e.get("event") == "assigned"]
        self.assertEqual(len(rows), 1, f"assigned rows: {rows}")
        self.assertEqual(rows[0]["owner"], "beta", rows[0])
        self.assertEqual(rows[0]["from"], "", "a claim is not a reassignment and has no prior owner")
        self.assertEqual(rows[0]["actor"], "beta", rows[0])
        self.assertEqual(rows[0].get("via"), "claim", rows[0])

    def test_a_stranger_cannot_claim_work_in_the_channel(self):
        tid = self.new_card(title="gamma may not take this")
        p = aim(self.root, "task", "claim", "--as", "gamma", "--channel", "ch", "--id", tid)
        self.assertNotEqual(p.returncode, 0,
                            f"a non-participant claimed a card: {p.stdout!r}")
        self.assertIn("participant", (p.stdout + p.stderr).lower(), p.stdout + p.stderr)

    def test_a_claim_on_a_held_card_is_refused_and_records_nothing(self):
        tid = self.new_card(owner="alpha", title="already held")
        before = [e for e in events(self.root, "ch") if e.get("task") == tid]
        p = aim(self.root, "task", "claim", "--as", "beta", "--channel", "ch", "--id", tid)
        self.assertNotEqual(p.returncode, 0, f"beta took alpha's card: {p.stdout!r}")
        after = [e for e in events(self.root, "ch") if e.get("task") == tid]
        self.assertEqual(before, after, "a refused claim still wrote an event")

    def test_the_held_card_refusal_names_the_verb_that_can_move_it(self):
        # The owner check is behind the phase gate, so this is measured in
        # CROSS_EXAMINE, where a peer may read drafts. `claim`'s own contract is
        # that it refuses a held card *and* names `assign`, because an agent whose
        # claim is refused needs the verb that will work for it.
        tid = self.new_card(channel="open", owner="alpha", title="held past the barrier")
        step = [("say", "--as", "alpha", "--channel", "open", "--private", "--body", "alpha position"),
                ("say", "--as", "beta", "--channel", "open", "--private", "--body", "beta position"),
                ("seal", "--as", "alpha", "--channel", "open", "--summary", "alpha is here"),
                ("seal", "--as", "beta", "--channel", "open", "--summary", "beta is here"),
                ("advance", "--as", "human", "--channel", "open", "--to", "COMMIT"),
                ("advance", "--as", "human", "--channel", "open", "--to", "SYNTHESIS",
                 "--synthesizer", "syth"),
                ("advance", "--as", "human", "--channel", "open", "--to", "CROSS_EXAMINE")]
        for argv in step:
            p = aim(self.root, *argv)
            self.assertEqual(p.returncode, 0, f"aim {' '.join(argv)} -> {p.stderr}")
        p = aim(self.root, "task", "claim", "--as", "beta", "--channel", "open", "--id", tid)
        self.assertNotEqual(p.returncode, 0, f"beta took alpha's card: {p.stdout!r}")
        self.assertIn("assign", p.stdout + p.stderr,
                      "the refusal must name the verb that can move a held card")

    def test_an_unowned_draft_is_readable_by_a_peer_in_a_divergence_phase(self):
        tid = self.new_card(channel="pool", title="an offer of work, not a position")
        phase = aim(self.root, "status", "--channel", "pool").stdout
        self.assertIn("SEALED_DIVERGENT", phase,
                      f"the channel is not in a divergence phase, so the read proves nothing: {phase}")
        p = aim(self.root, "task", "list", "--as", "beta", "--channel", "pool")
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn(tid, p.stdout, f"beta cannot see the unowned card: {p.stdout!r}")

    def test_an_owned_draft_keeps_the_peer_read_refusal(self):
        tid = self.new_card(owner="alpha", title="alpha's position, unsealed")
        p = aim(self.root, "task", "list", "--as", "beta", "--channel", "ch")
        self.assertNotEqual(p.returncode, 0,
                            f"beta read a peer's owned draft in SEALED_DIVERGENT: {p.stdout!r}")
        self.assertNotIn("alpha's position, unsealed", p.stdout)
        own = aim(self.root, "task", "list", "--as", "alpha", "--channel", "ch")
        self.assertIn("alpha's position, unsealed", own.stdout,
                      "the owner cannot read their own draft")

    def test_release_is_recorded_with_actor_and_reason(self):
        tid = self.new_card(title="taken then given back")
        p = aim(self.root, "task", "claim", "--as", "beta", "--channel", "ch", "--id", tid)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        p = aim(self.root, "task", "assign", "--as", "beta", "--channel", "ch",
                "--id", tid, "--owner", "", "--reason", "measured: no longer mine")
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        rows = [e for e in events(self.root, "ch") if e.get("task") == tid
                and e.get("event") == "assigned"]
        self.assertEqual(len(rows), 2, f"assigned rows: {rows}")
        release = rows[-1]
        self.assertEqual(release["owner"], "", release)
        self.assertEqual(release["from"], "beta", "the release must name the owner it released")
        self.assertEqual(release["actor"], "beta", release)
        self.assertEqual(release.get("reason"), "measured: no longer mine", release)
        back = aim(self.root, "task", "claim", "--as", "alpha", "--channel", "ch", "--id", tid)
        self.assertEqual(back.returncode, 0,
                         f"a released card is not claimable again: {back.stdout}{back.stderr}")

    def test_a_release_without_a_reason_is_refused(self):
        tid = self.new_card(title="must not be dropped silently")
        p = aim(self.root, "task", "claim", "--as", "beta", "--channel", "ch", "--id", tid)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        p = aim(self.root, "task", "assign", "--as", "beta", "--channel", "ch",
                "--id", tid, "--owner", "")
        self.assertNotEqual(p.returncode, 0, f"a reasonless release was accepted: {p.stdout!r}")
        self.assertIn("reason", (p.stdout + p.stderr).lower(), p.stdout + p.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
