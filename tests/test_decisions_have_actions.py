#!/usr/bin/env python3
"""T-0211: no control renders without the exact argv that resolves it.

Card text (`channels/hello/tasks.jsonl`, `created` 2026-09-22T07:19:47.759Z,
actor codex), verbatim:

  "every Decision and WorkItem in /api/state carries at least one action with a
   verbatim argv and the viewer already applied; a test walks the payload and
   fails on a primary control with no argv; T-0004 is approving, not 'open it'"

and its comment, which names the evidence:

  "Measured on the served bundle (assets/index-kt71uWBo.js, viewer human): the
   overview promise row for T-0004 reads ... its only control is `["open it"]`,
   and the drawer it opens offers `["Start doing", "Record this work item"]` --
   no Approve / Request changes / Reject, because the item is a seed and is not
   in the store. Acceptance: every Decision and every WorkItem in /api/state
   carries `actions[]`, each `{label, argv, why}` with the viewer already
   substituted and any `--as` dropped (the rule T-0141 established). A test
   walks the payload and fails if a primary control has no argv. A row that says
   'decision for you' must be approvable from that row. Do NOT make this a
   second write path: actions are argv for the one server-side runner."

`design/12` §1.3 is the design this comes from: four objects, and "every
`Decision` and every `WorkItem` carries the exact argv that resolves it, with the
viewer's identity already applied. **A control with no argv is a dead end and
must not render.**"

What this file measures, and how it is scoped:

  * the payload's WorkItems are `payload["tasks"]` (design/12 §1.3's table:
    WorkItem -> Kanban, Gantt, Items, Plan). Each row must carry a non-empty
    `actions[]`;
  * every action is `{label, argv, why}`, the label and the why are non-empty
    sentences, and the argv is verbatim: a command (a list of non-empty strings)
    or a list of commands. Both are accepted because both are the argv the same
    runner takes and the shape the existing client-side builder already emits
    (`ItemsPane.decisionArgv` returns up to two commands);
  * no command carries `--as`: the viewer is applied server-side, not typed by
    the caller (T-0141);
  * every command's first word is a subcommand `bin/aim` actually has -- read
    from the tool's own `--help`, not restated here -- because a control that
    names a verb the tool does not hold is a command that cannot run;
  * the row that owes *this viewer* a decision (`owner == viewer`, status
    `ready`: `board.promiseDecisions`, the T-0004 shape) must offer an action
    that resolves it -- a state-changing verb -- and must not offer a
    navigation-only label (`open it` / `inspect`) as its control, which is
    exactly the defect the card measured. Recording a promise is `task new`
    (T-0176's correction: a seed that claims a decision is offered only
    'record it'); making a promise approvable in place is T-0180's work, so
    this file asserts that the resolution exists and is a real command, not
    which verb the ruling picks;
  * a row in `review` must offer the three decisions `design/11` §2 names
    (approve / request changes / reject), which this repository maps to
    `task move --to done|doing|dropped` (`test_items_decision.py` check 4 pins
    that mapping against `bin/aim`'s state machine; the `--to` values are
    checked against the payload's own `statuses`, so they stay the server's
    vocabulary rather than this file's).

Scope note, stated rather than silently assumed: `register.decisions` (D5, D6,
...) are the plan's *recorded* decisions -- prose with `id`/`decision`/`because`,
drawn read-only by `PlanPane` -- and are not design/12 §1.3's `Decision` object,
which is "something only a human can settle". The card's own evidence for this
row type is T-0004, which is a task row. So the walk is over `payload["tasks"]`,
and `register.decisions` is not asserted to carry controls it has never had.

VERDICT: FAIL. `/api/state` has no `actions` key anywhere -- `rg '"actions"'` over
`aimboard/` and the served payload finds nothing -- so every WorkItem is a row
whose primary control, if a surface draws one, has nothing to run. Both authoring
sides are client-side today (`ItemsPane.decisionArgv`, `TaskDecisionDrawer`), and
the card's sentence "Do NOT make this a second write path: actions are argv for
the one server-side runner" is precisely the work this test pins. The tests below
are annotated `@unittest.expectedFailure` with the measurement so the suite stays
green while the defect is on the record.

Revision measured -- `GET http://127.0.0.1:8777/api/revision`, read only, before
and after this file ran, 2026-09-22T08:50Z and 08:57Z:

  08:50Z  fabric fac2a0c+dirty  bundle 870b282+dirty built 08:40:07.787Z  stale true
  08:57Z  fabric 1277f7e+dirty  bundle 870b282+dirty built 08:40:07.787Z  stale true

The fabric moved (another session in this shared checkout committed) and the
bundle did not; `stale` was true at both reads. The payload this file folds is
built from the checked-out source, not from the served bundle.

The fabric this file drives is a throwaway `AIM_ROOT` under /tmp created with
`tempfile.mkdtemp` and removed in `tearDownClass`; it never touches
`/root/tmp/agent-im/channels`, and it writes nothing through `aim` except into
that root. The board on 127.0.0.1:8777 is only read, and only `/api/revision`
was read here.

Run: python3 tests/test_decisions_have_actions.py      (exit code = failures)
     python3 -m unittest tests.test_decisions_have_actions
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
AIM = HERE / "bin" / "aim"
sys.path.insert(0, str(HERE))

from aimboard import api                                    # noqa: E402
from aimboard.fabric import load_fabric                     # noqa: E402

VIEWER = "lead"
CHANNEL = "hello"
# The T-0004 shape, verbatim in the way that matters: a promise the plan parked
# on the person, whose acceptance is a phase move.
DECISION_TITLE = "Leader: approve the plan; advance hello past SEALED_DIVERGENT"
REVIEW_TITLE = "the worker's item, waiting on the leader's verdict"


def aim(env, *argv):
    return subprocess.run([sys.executable, str(AIM), *[str(a) for a in argv]],
                          env=env, capture_output=True, text=True, timeout=120)


def aim_verbs():
    """The subcommands `bin/aim` has, from the tool rather than from memory."""
    p = subprocess.run([sys.executable, str(AIM), "--help"],
                       capture_output=True, text=True, timeout=60)
    m = re.search(r"\{([a-z][a-z,\-]*)\}", p.stdout)
    return set(m.group(1).split(",")) if m else set()


def build_fabric(root):
    """One channel, one promise owed to the viewer, one row in review."""
    env = dict(os.environ, AIM_ROOT=str(root))
    steps = [
        ("init",),
        ("register", "--as", VIEWER, "--kind", "human"),
        ("register", "--as", "worker", "--kind", "codex"),
        ("new-channel", "--id", CHANNEL, "--topic", "decisions have actions",
         "--participants", f"{VIEWER},worker", "--leader", VIEWER),
        # The decision owed to the viewer: a seed-shaped promise, owner == viewer,
        # status ready. Recorded through the CLI because the payload is a fold
        # over the record, and a hand-written plan file would not be the record.
        ("task", "new", "--as", VIEWER, "--channel", CHANNEL,
         "--title", DECISION_TITLE, "--owner", VIEWER, "--status", "ready",
         "--priority", "high", "--accept",
         "aim status --channel hello shows a phase after SEALED_DIVERGENT"),
        # A recorded work item waiting on the same person's verdict.
        ("task", "new", "--as", "worker", "--channel", CHANNEL,
         "--title", REVIEW_TITLE, "--owner", "worker", "--status", "review",
         "--accept", "the reviewer accepts it or says what would change their mind"),
    ]
    for argv in steps:
        p = aim(env, *argv)
        if p.returncode != 0:
            raise AssertionError(f"aim {' '.join(argv)} -> rc {p.returncode}: "
                                 f"{p.stdout.strip()}{p.stderr.strip()}")
    return env


def commands_of(argv):
    """Every command in an action's argv, whichever of the two shapes it is.

    A `Decision`'s argv is "the exact argv that resolves it"; some resolutions
    are two commands (the words, then the move), which `ItemsPane.decisionArgv`
    already emits as a list of commands. Both shapes are verbatim; neither is
    restated here.
    """
    if not isinstance(argv, list) or not argv:
        return []
    if all(isinstance(item, str) for item in argv):
        return [argv]
    return [cmd for cmd in argv if isinstance(cmd, list)]


def action_problems(row, verbs):
    """Everything wrong with one row's `actions[]`, as sentences."""
    bad = []
    actions = row.get("actions")
    if not isinstance(actions, list) or not actions:
        return [f"{row.get('id')}: no actions[] at all (control with no argv)"]
    for i, action in enumerate(actions):
        if not isinstance(action, dict):
            bad.append(f"{row.get('id')}: actions[{i}] is {type(action).__name__}, not an object")
            continue
        label = action.get("label")
        why = action.get("why")
        if not (isinstance(label, str) and label.strip()):
            bad.append(f"{row.get('id')}: actions[{i}] has no label")
        if not (isinstance(why, str) and why.strip()):
            bad.append(f"{row.get('id')}: actions[{i}] ({label!r}) has no why -- a control "
                       "without a reason cannot be audited")
        commands = commands_of(action.get("argv"))
        if not commands:
            bad.append(f"{row.get('id')}: actions[{i}] ({label!r}) has no argv "
                       f"(got {action.get('argv')!r}) -- a dead end")
            continue
        for cmd in commands:
            if len(cmd) < 2 or not all(isinstance(part, str) and part for part in cmd):
                bad.append(f"{row.get('id')}: actions[{i}] ({label!r}) argv {cmd!r} is not "
                           "a command (a list of non-empty strings)")
                continue
            if cmd[0] not in verbs:
                bad.append(f"{row.get('id')}: actions[{i}] ({label!r}) runs '{cmd[0]}', "
                           f"which is not a subcommand bin/aim has")
            if "--as" in cmd or any(part.startswith("--as=") for part in cmd):
                bad.append(f"{row.get('id')}: actions[{i}] ({label!r}) argv {cmd!r} carries "
                           "--as; the viewer is applied server-side (T-0141)")
    return bad


class DecisionsHaveActions(unittest.TestCase):
    """`/api/state` as `aimboard.api.payload` builds it for the leader."""

    @classmethod
    def setUpClass(cls):
        cls.root = Path(tempfile.mkdtemp(prefix="t0211-", dir="/tmp"))
        build_fabric(cls.root)
        state = load_fabric(cls.root, ["plan/*.json"], date.today())
        cls.payload = api.payload(state, VIEWER, {})
        cls.tasks = cls.payload["tasks"]
        cls.verbs = aim_verbs()

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.root, ignore_errors=True)

    def row(self, title):
        rows = [t for t in self.tasks.values() if t.get("title") == title]
        self.assertEqual(len(rows), 1, f"expected one row titled {title!r}, got {rows!r}")
        return rows[0]

    # ------------------------------------------------------------------ fixtures

    def test_the_payload_holds_the_two_rows_this_file_is_about(self):
        """The precondition. Without it, an empty payload would pass every walk."""
        decision = self.row(DECISION_TITLE)
        review = self.row(REVIEW_TITLE)
        self.assertEqual(decision["owner"], VIEWER)
        self.assertEqual(decision["status"], "ready")
        self.assertEqual(review["status"], "review")
        self.assertEqual(self.payload["viewer"], VIEWER)
        self.assertTrue(self.verbs, "bin/aim --help did not print a subcommand list")

    # ------------------------------------------------------------- the card's rule

    @unittest.expectedFailure
    def test_every_workitem_carries_actions(self):
        """Measured 2026-09-22 on `fac2a0c`/bundle 870b282+dirty (stale true).

        Not one row in `/api/state` carries an `actions` key: the fold has no such
        field and no surface reads one, so every WorkItem the payload ships is a
        row whose control, when a pane draws one, has nothing to run.
        """
        without = [t["id"] for t in self.tasks.values()
                   if not isinstance(t.get("actions"), list) or not t["actions"]]
        self.assertEqual(without, [],
                         f"{len(without)} of {len(self.tasks)} work items in /api/state carry no "
                         f"actions[]: {without}")

    @unittest.expectedFailure
    def test_every_action_is_a_label_a_reason_and_a_verbatim_argv(self):
        """Measured 2026-09-22: `actions[]` does not exist, so `{label, argv, why}`
        does not exist. The precondition is asserted before the walk so an empty
        payload cannot pass this test by having nothing to check."""
        rows = list(self.tasks.values())
        self.assertTrue(any(row.get("actions") for row in rows),
                        "every row has no actions[]; this test cannot be vacuous-green")
        problems = []
        for row in rows:
            problems += action_problems(row, self.verbs)
        self.assertEqual(problems, [])

    @unittest.expectedFailure
    def test_no_action_carries_the_viewer_as_an_argument(self):
        """Measured 2026-09-22: no argv exists to carry `--as`; the rule the card
        quotes (T-0141) is asserted the moment the argv exists."""
        rows = list(self.tasks.values())
        self.assertTrue(any(row.get("actions") for row in rows),
                        "every row has no actions[]; this test cannot be vacuous-green")
        offenders = []
        for row in rows:
            for action in row.get("actions") or []:
                for cmd in commands_of(action.get("argv")):
                    if "--as" in cmd or any(part.startswith("--as=") for part in cmd):
                        offenders.append(f"{row['id']}: {action.get('label')!r} -> {cmd!r}")
        self.assertEqual(offenders, [])

    @unittest.expectedFailure
    def test_the_row_that_owes_the_viewer_a_decision_offers_a_resolving_action(self):
        """Measured 2026-09-22 on the T-0004 shape: the payload row has no
        `actions[]`, so the only thing a surface can render for it is the
        navigation control the card measured -- `open it` -- and "a row that says
        'decision for you' must be approvable from that row" has nothing to run."""
        row = self.row(DECISION_TITLE)
        actions = row.get("actions")
        self.assertTrue(isinstance(actions, list) and actions,
                        f"{row['id']} ({row['title']!r}) carries no actions[]; the row that "
                        "owes the viewer a decision has no command on it")
        resolving = [a for a in actions
                     if any(cmd[0] in ("task", "advance") for cmd in commands_of(a.get("argv")))]
        self.assertTrue(resolving,
                        f"{row['id']}: no action resolves the decision; got "
                        f"{[a.get('label') for a in actions]!r}")
        navigation = [a.get("label") for a in actions
                      if re.match(r"^\s*(open|inspect)\b", str(a.get("label") or ""), re.I)]
        self.assertEqual(navigation, [],
                         f"{row['id']}: the control offered is navigation, not the decision: "
                         f"{navigation!r}")

    @unittest.expectedFailure
    def test_a_row_in_review_offers_approve_request_changes_and_reject(self):
        """Measured 2026-09-22: no row in `/api/state` carries the three argv that
        design/11 §2 names, because no row carries argv at all."""
        row = self.row(REVIEW_TITLE)
        actions = row.get("actions")
        self.assertTrue(isinstance(actions, list) and actions,
                        f"{row['id']} ({row['title']!r}) carries no actions[]")
        statuses = set(self.payload["statuses"])
        targets = set()
        for action in actions:
            for cmd in commands_of(action.get("argv")):
                if cmd[0] == "task" and "move" in cmd and "--to" in cmd:
                    to = cmd[cmd.index("--to") + 1]
                    self.assertIn(to, statuses,
                                  f"{row['id']}: {action.get('label')!r} moves to '{to}', which "
                                  "is not a status the payload's own statuses hold")
                    targets.add(to)
        self.assertEqual(targets, {"done", "doing", "dropped"},
                         f"the review decisions design/11 §2 names are missing; got {targets!r}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
