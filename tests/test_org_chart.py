#!/usr/bin/env python3
"""T-0231: no surface answers the org chart -- who is in the team, who may I
dispatch to, to whom do I report.

The card's acceptance, in its own words:

  One command answers all three questions for a named agent without reading a
  JSON file by hand: (1) the org it belongs to and the other members, (2) the
  agents it may dispatch work to, (3) the agent it reports to. Observable: run it
  for a newly registered agent and it returns those three answers, or names
  exactly which is undefined. Adding an agent to the org is one recorded act, and
  the org it joins is the same object `aim status --channel` reports participants
  for -- not a second roster that can drift.

The card names no command, and that is deliberate (`the best shape is probably
derived ... Deciding that is the work`). So this file discovers the surface
instead of guessing one: it reads the subcommand list out of `aim --help`, probes
each subcommand's own `--help` for the card's vocabulary, and probes a short list
of plausible names that are *not* subcommands (`org`, `team`, `roster`, ...) to
prove they are absent rather than merely unnamed. The discovery runs once and its
result is asserted before anything is run, so on a build with no org surface the
failure names the search rather than a missing flag.

Why the assertions have the shape they have:

  * `test_joining_the_org_is_one_recorded_act` is not decorated: `aim channel add`
    is the recorded join today, and the org the card wants must be the same
    object, so the test only asserts what exists -- the manifest, the ledger
    record, and the row `aim status --channel` prints. It is the baseline the two
    failing methods are compared against, not a claim that the acceptance passes.
  * The three answers are checked separately, because the card allows an answer
    to be "exactly ... undefined": a surface that says "you report to: (undefined)"
    satisfies (3) while a surface that says nothing does not.
  * The member set is checked against `aim status --channel`'s participants, which
    is the card's anti-drift clause. A second roster that disagreed would fail
    here even if the command answered all three questions.

Revision measured: `fac2a0ce9ead85da7533d378087a96f748d3080b` (HEAD) with
`bin/aim` **dirty** (585 insertions / 90 deletions vs HEAD) and `/api/revision`
`stale: true`. The absence is in **committed** lines: neither `git show
HEAD:bin/aim` nor the dirty working tree declares any org verb -- `aim --help`
lists `{init,card,register,new-channel,channel,say,seal,inbox,wait,advance,
request-advance,synthesis-input,task,reveal,push,pull,confirm,outbox,nudge,
tension,status,verify,friction,doctor}`, and no subcommand's help text contains
org/team/roster/dispatch/report vocabulary. The two failing methods are
`@unittest.expectedFailure`.

Context measured while writing this, and not asserted on: an uncommitted prototype
`reviews/org/aim-org.py` (a review artifact by another hand, not a `aim` verb and
not reachable from the CLI) already derives membership and leadership from
`registry.json` + `aim status --channel`, and reads the reporting line from a
declared `org.json`. That is the shape the card's comment argues for -- derived,
with the underivable answer named as underivable -- but it is not "one command" a
participant can run, so the card's acceptance is still open here.

Run: python3 tests/test_org_chart.py     (exit code = number of failures)
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
ORG_WORDS = re.compile(
    r"\b(org|organisation|organization|orgchart|team|roster|dispatch|reports?|reporting|"
    r"hierarchy|chain_of_command)\b", re.I)
# Names that are not subcommands today; probed so "absent" is measured, not assumed.
ABSENT_PROBES = ("org", "team", "roster", "orgchart", "org-chart", "structure",
                 "whois", "whoami", "reports", "dispatch")
MEMBERS = ("alpha", "beta", "gamma")


def aim(root, *argv):
    env = dict(os.environ, AIM_ROOT=str(root))
    return subprocess.run([sys.executable, str(AIM), *[str(a) for a in argv]],
                          capture_output=True, text=True, env=env, timeout=120)


def help_of(root, *argv):
    p = aim(root, *argv, "--help")
    return p.stdout + p.stderr


def subcommands(root):
    m = re.search(r"\{([a-z0-9,\-]+)\}", help_of(root))
    return m.group(1).split(",") if m else []


def org_surfaces(root):
    """Every surface that could be the org view, found, not named by this file.

    The probes run in parallel: a help page is one `python3 bin/aim` process, and
    thirty-six of them in series is most of a minute for a discovery that must be
    cheap enough to run on every suite.
    """
    subs = subcommands(root)
    names = list(subs) + [n for n in ABSENT_PROBES if n not in subs]
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=8) as pool:
        probes = dict(zip(names, pool.map(lambda n: help_of(root, n), names)))
    found = [n for n in subs if ORG_WORDS.search(probes[n])]
    found += [n for n in ABSENT_PROBES
              if n not in subs and "invalid choice" not in probes[n]]
    return subs, found


def measure(root, name):
    """Run the candidate surface tolerantly and return its output, if it answered."""
    for argv in ((name, "--as", "alpha"), (name, "--as", "alpha", "--channel", "team"),
                 (name, "alpha"), (name,)):
        p = aim(root, *argv)
        if p.returncode == 0 and (p.stdout + p.stderr).strip():
            return argv, p.stdout + p.stderr
    return None, ""


class OrgChartTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.root = Path(tempfile.mkdtemp(prefix="aim-t0231-", dir="/tmp"))
        for argv in (("init",),
                     ("register", "--as", "human", "--kind", "human"),
                     ("register", "--as", "alpha", "--kind", "codex"),
                     ("register", "--as", "beta", "--kind", "claude"),
                     ("register", "--as", "gamma", "--kind", "codex"),
                     ("new-channel", "--id", "team", "--topic", "the team",
                      "--participants", "alpha,beta", "--leader", "human")):
            p = aim(cls.root, *argv)
            assert p.returncode == 0, f"setup aim {' '.join(argv)} -> {p.returncode}: {p.stderr}"
        cls.subs, cls.surfaces = org_surfaces(cls.root)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.root, ignore_errors=True)

    def test_joining_the_org_is_one_recorded_act(self):
        p = aim(self.root, "channel", "add", "--as", "human", "--channel", "team",
                "--agent", "gamma", "--reason", "a new joiner for T-0231")
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        manifest = json.loads((self.root / "channels" / "team" / "manifest.json").read_text())
        self.assertIn("gamma", manifest["participants"], "the join is not in the manifest")
        ledger = (self.root / "channels" / "team" / "ledger.jsonl").read_text()
        self.assertIn("channel_member_added", ledger, "the join is not in the ledger")
        self.assertIn("gamma", ledger, "the join record does not name the joiner")
        status = aim(self.root, "status", "--channel", "team").stdout
        for who in MEMBERS:
            self.assertIn(who, status, f"aim status does not list {who} as a participant")

    @unittest.expectedFailure
    def test_a_command_answers_the_three_org_questions_for_a_named_agent(self):
        self.assertTrue(
            self.surfaces,
            "no `aim` surface answers the org chart. Probed subcommands "
            f"{self.subs} for help text matching {ORG_WORDS.pattern!r}, and probed the "
            f"absent names {list(ABSENT_PROBES)}; none matched and none exist.")
        missing = []
        for name in self.surfaces:
            argv, out = measure(self.root, name)
            self.assertTrue(out, f"`aim {name}` did not answer at all")
            if not all(who in out for who in MEMBERS):
                missing.append(f"{name}: the org it belongs to and its members (got {out!r})")
            if not re.search(r"(?i)dispatch|may push|peers", out):
                missing.append(f"{name}: the agents it may dispatch to (got {out!r})")
            if not re.search(r"(?i)report", out):
                missing.append(f"{name}: the agent it reports to (got {out!r})")
        self.assertEqual(missing, [], "the org surface does not answer: " + "; ".join(missing))

    @unittest.expectedFailure
    def test_the_org_view_lists_the_same_members_as_the_channel(self):
        self.assertTrue(
            self.surfaces,
            "no org view exists to compare against the channel's participants; probed "
            f"{self.subs} and the absent names {list(ABSENT_PROBES)}.")
        status = aim(self.root, "status", "--channel", "team").stdout
        for name in self.surfaces:
            argv, out = measure(self.root, name)
            self.assertTrue(out, f"`aim {name}` did not answer at all")
            for who in MEMBERS:
                self.assertIn(who, out, f"the org view omits {who}, a participant of team")
                self.assertIn(who, status, f"aim status omits {who}, a participant of team")
            # The card's anti-drift clause: the same members, not a second roster.
            named = {w for w in re.findall(r"\b[a-z][a-z0-9_-]{2,}\b", out) if w in
                     {"alpha", "beta", "gamma", "human"}}
            self.assertEqual(named, set(MEMBERS), f"the org view's members: {sorted(named)}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
