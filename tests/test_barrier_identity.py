#!/usr/bin/env python3
"""the barrier's exemption is a *kind*, not the leader -- so the same read is released
to anyone who registers as `human`, and the A2A surface releases it to everyone.

`bin/aim` exempts the leader from the barrier with one two-token comparison --
`kind != "human"` -- and in exactly one of its 26 sites, `require_leader`
(bin/aim:831 while this file was written; `bin/aim` is being edited by another
session as these lines land, so read the numbers here as "at this revision" and
the shapes as the claim), is that comparison joined by a second one against the
manifest:

    if kind != "human" or who != manifest["leader"]:

`kind` is a self-declaration. `aim register --as <anything> --kind human` writes
it, nothing approves it, and `resolve_actor` (bin/aim:806) hands the value to
every gate. So the read gates ask a question the caller answers for itself, and
the answer is a field the caller chose.

Measured on a scratch root built with the real CLI -- channel `c` in
SEALED_DIVERGENT, one draft owned by `codex`, `impostor` and `human` both
`kind: human` while only `human` is the manifest's leader, `stranger`
`kind: codex` and not a participant:

    reader                            aim task list        ledger      gate.visible_tasks  POST /rpc
    stranger (kind codex, not part)   rc 2, refused        1 refusal   hidden (1)          RETURNS it
    impostor (kind human, not part)   rc 0, TITLE ON STDOUT 0 rows     released            returns it
    human    (kind human, THE leader) rc 0, title printed  0 rows      released            returns it

The middle row is the defect: the reader the CLI refuses *and records* is refused
for one self-declared value of a field it set on itself, and released for another.
The row below it is the rule rather than the symptom -- the leader is the audience
and sees everything -- and a fix that closes the hole by walling the leader out is
a second defect wearing the first one's number.

    the read                          what it does today                                 verdict
    --------------------------------  -------------------------------------------------  -----------------
    `aim task list` as stranger       rc 2 + one `refusal` row naming `task list`        CORRECT, must stay
    `aim task list` as impostor       rc 0, the draft's title on stdout, no ledger file  DEFECT (W1)
    gate.visible_tasks(stranger)      ({}, 1) -- hidden                                  CORRECT, must stay
    gate.visible_tasks(impostor)      ({"T-0001": ...}, 0) -- released                    DEFECT (W1)
    a2a ListTasks as stranger         returns T-0001 -- the card, `accept` and       DEFECT (W2)
                                      `owner` in metadata, the title nowhere
    a2a ListTasks as leader           returns it                                         CORRECT, must stay
    `aim advance` as impostor         rc 2, refused, one row -- require_leader           CORRECT, must stay

Why `require_leader` is in this file at all: it is the one site that gets the
exemption right, and it is what proves the *shape* of the rule is available. The
hole is not that the rule is unimplementable; it is that the other 25 sites spell it
`kind != "human"` and this one spells it `kind != "human" or who != leader`, which
is `who in (leader, <anyone who said human>)`.

What this file does *not* assert, and the sentence it replaces:

  * it does not assert that the A2A payload carries the *title*. It does not, for
    any viewer including the leader: `a2a_task` (aimboard/a2a.py:836) builds
    `{id, contextId, status, metadata}`, the title is not among those keys, and
    `history` is read off `task["history"]` while neither fold writes that key --
    `bin/aim`'s fold initialises the card with `"history": []` and
    `aimboard/fold.py:76` builds `{"id", "events", "comments", "visibility"}`.
    Measured with `historyLength=10, includeArtifacts=True`: the field comes back
    `[]`. So the divergence that is real is the card's *existence* plus its
    `accept` and `owner`, and that is what is asserted -- a title-in-metadata
    check would have been a check that cannot fail.
  * it does not assert the fix, and it does not attempt one. What a candidate fix
    costs the six suites is measured in the report, not here.

Every check names the change that would turn it red. The `DEFECT` rows go red when
the hole is closed -- that is what they are for, and closing it must retire them,
the way `tests/test_audit_dependency_cycle.py` retired its own.

Run: python3 tests/test_barrier_identity.py     (exit code = number of failures)
"""
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AIM = ROOT / "bin" / "aim"
BOARD = ROOT / "bin" / "aimboard.py"
sys.path.insert(0, str(ROOT))

passed = failed = 0


def check(name, ok, detail=""):
    global passed, failed
    if ok:
        passed += 1
        print(f"  PASS  {name}")
    else:
        failed += 1
        print(f"  FAIL  {name}" + (f"\n        {detail}" if detail else ""))


def load_state(root):
    """The fold `aimboard/cli.py::_state` hands to `handle_rpc`, over a real root.

    Loaded rather than hand-built for the reason tests/test_a2a_conformance.py
    gives for the same choice: a fixture that builds both sides of a comparison
    proves only that its author was consistent, and this file's whole subject is
    two sides that disagree. Today's date, not a frozen one, because only the
    phase and the task set matter here and dormancy is a fact about `lifecycle`.
    """
    from aimboard import fabric
    return fabric.load_fabric(Path(root), ["plan/*.json"], datetime.now(timezone.utc).date())


def rpc(state, viewer, method, params=None, rid=1):
    """One call into the A2A surface, with the arguments the HTTP layer passes.

    The keyword set is copied from `cli.py::_rpc_POST` (aimboard/cli.py:640-648),
    including `tasks=state["tasks"]` -- the *raw* dict, which is the fact W2 is
    about: `handle_rpc` is handed what `gate` would have filtered and does its own
    filtering inside `a2a.task_visible`.
    """
    from aimboard import a2a
    resp, _ = a2a.handle_rpc(
        method, params or {}, request_id=rid, viewer=viewer,
        tasks=state["tasks"], channels=state["channels"],
        registry=state.get("registry") or {}, configs=[],
    )
    return resp


TITLE = "codex private work"
TOKEN = "SECRET-ACCEPT-TOKEN-9931"     # only on the withheld draft, and nowhere else

with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    env = dict(os.environ, AIM_ROOT=str(root))

    def run(*argv):
        return subprocess.run([sys.executable, str(AIM), *[str(a) for a in argv]],
                              capture_output=True, text=True, env=env, timeout=60)

    def task_list(who):
        """The one command shape every W1 row is measured with.

        Same argv list, same substitution point, so a difference between two rows
        cannot come from the commands having been written differently -- which is
        the failure a characterization test of a *permission* difference is most
        likely to have.
        """
        return run("task", "list", "--as", who, "--channel", "c")

    def ledger_rows():
        path = root / "channels" / "c" / "ledger.jsonl"
        if not path.exists():
            return None                       # None: the file is absent, which is not []
        return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]

    def refusals():
        return [r for r in (ledger_rows() or []) if r.get("event") == "refusal"]

    # ----------------------------------------------------------------- fixture
    run("init")
    for who, kind in (("human", "human"), ("codex", "codex"),
                      ("impostor", "human"), ("stranger", "codex")):
        got = run("register", "--as", who, "--kind", kind)
        check(f"fixture: '{who}' registered as {kind}", got.returncode == 0,
              got.stdout + got.stderr)
    opened = run("new-channel", "--id", "c", "--topic", "barrier identity",
                 "--participants", "codex", "--leader", "human")
    check("fixture: the channel is in a divergence phase, or none of this is about the barrier",
          "SEALED_DIVERGENT" in opened.stdout, opened.stdout + opened.stderr)
    made = run("task", "new", "--as", "codex", "--channel", "c",
               "--title", TITLE, "--owner", "codex", "--accept", TOKEN)
    check("fixture: codex's draft exists, with a token on it that appears nowhere else",
          made.returncode == 0 and made.stdout.strip().endswith(TITLE),
          made.stdout + made.stderr)
    check("fixture: writing the fixture left no ledger file, so the first refusal below "
          "owns the file and its line count is readable",
          ledger_rows() is None,
          f"ledger.jsonl already exists with {len(ledger_rows() or [])} row(s)")

    # --------------------------------------------- 1. W1, the ledger half
    print("\n== 1. the same read, two self-declared kinds ==")

    # Reader one: a registered non-participant who declared `kind: human` and is
    # not the manifest's leader. Nothing approves that declaration.
    impostor = task_list("impostor")
    check("W1: the reader who declared `kind: human` is released -- rc 0 and the "
          "draft's title on stdout",
          impostor.returncode == 0 and TITLE in impostor.stdout,
          f"rc={impostor.returncode} out={impostor.stdout!r} err={impostor.stderr!r}")
    check("DEFECT W1: and the release is UNRECORDED -- no ledger file at all, so the "
          "audit that exists to show an agent tried shows nothing",
          ledger_rows() is None,
          f"ledger.jsonl exists: {json.dumps(ledger_rows(), ensure_ascii=False)[:300]}")

    # Reader two: a registered non-participant who declared `kind: codex`. Same
    # command, same argv, one substituted word.
    stranger = task_list("stranger")
    check("W1 control: the reader who declared `kind: codex` is refused -- rc non-zero "
          "and no title on stdout",
          stranger.returncode != 0 and TITLE not in stranger.stdout,
          f"rc={stranger.returncode} out={stranger.stdout!r} err={stranger.stderr!r}")
    # The count, asserted per reader rather than over the whole file. The whole
    # file's count is not this row's subject: a fixed build records the impostor's
    # read *too*, so a global `len(refusals()) == 1` would go red for the fix
    # landing instead of for the audit failing, and a check that fires on the
    # change it is asking for is a check that cannot be retired. Selected by
    # `agent`, which is the field the ledger is read for.
    wrote = [r for r in refusals() if r.get("agent") == "stranger"]
    check("W1 control: and the refusal IS on the record -- exactly one row for this "
          "reader, and the count is asserted because one row is the whole audit",
          len(wrote) == 1, json.dumps(ledger_rows(), ensure_ascii=False)[:400])
    check("W1 control: that one row names the action, the agent, the phase and the class, "
          "so the ledger alone answers 'who tried what, where'",
          bool(wrote) and wrote[0].get("action") == "task list"
          and wrote[0].get("agent") == "stranger"
          and wrote[0].get("phase") == "SEALED_DIVERGENT"
          and wrote[0].get("class") == "barrier",
          json.dumps(wrote, ensure_ascii=False)[:400])
    check("and the two readers differ in nothing but the kind each declared on itself "
          "-- if this row goes red the W1 rows above are measuring a different variable",
          [r.get("kind") for r in (
              json.loads((root / "registry.json").read_text())["agents"][n]
              for n in ("impostor", "stranger"))] == ["human", "codex"],
          json.dumps(json.loads((root / "registry.json").read_text())["agents"], ensure_ascii=False)[:300])

    # ------------------------------------------- 2. W1, the library half
    print("\n== 2. the same question, asked of the gate directly ==")
    from aimboard import gate
    state = load_state(root)
    channel = [c for c in state["channels"] if c["id"] == "c"][0]
    check("fixture: the loaded channel agrees about who the leader is and what phase it is in",
          channel.get("leader") == "human" and channel.get("phase") == "SEALED_DIVERGENT"
          and "impostor" not in channel.get("participants", [])
          and "stranger" not in channel.get("participants", []),
          json.dumps({k: channel.get(k) for k in ("leader", "phase", "participants")}))

    seen_s, hidden_s = gate.visible_tasks(state, "stranger", None)
    check("gate control: a registered non-participant with kind codex gets ({}, 1) -- "
          "hidden, and the count is public while the contents are not",
          seen_s == {} and hidden_s == 1,
          f"visible={sorted(seen_s)} hidden={hidden_s}")

    seen_i, hidden_i = gate.visible_tasks(state, "impostor", None)
    check("DEFECT W1: the same call for the reader who declared kind human releases the "
          "draft -- title and all -- with a hidden count of zero",
          hidden_i == 0 and TITLE in json.dumps(seen_i),
          f"visible={sorted(seen_i)} hidden={hidden_i} "
          f"task={json.dumps(seen_i.get('T-0001'), ensure_ascii=False)[:240]}")

    # The participant who owns the card is the third arm of the same rule and is
    # NOT the exemption: it is the owner clause. Asserted so a fix cannot "close
    # the hole" by deleting the owner exemption, which would break codex's own read.
    seen_o, hidden_o = gate.visible_tasks(state, "codex", None)
    check("gate control: the draft's owner is not walled off either, and that is the "
          "owner clause rather than the kind exemption -- a fix must not take this row "
          "with it",
          hidden_o == 0 and "T-0001" in seen_o,
          f"visible={sorted(seen_o)} hidden={hidden_o}")

    # ------------------------------------------------------- 3. W2, /rpc
    print("\n== 3. the A2A surface, for the viewer the gate hides it from ==")
    listed = rpc(state, "stranger", "ListTasks", {}, rid=41)
    ids = [t.get("id") for t in (listed.get("result") or {}).get("tasks", [])]
    check("DEFECT W2: `handle_rpc('ListTasks')` returns the card the gate just refused "
          "-- asserted as the DIVERGENCE between two answers to one question, not as "
          "the RPC answering",
          ids == ["T-0001"] and seen_s == {},
          f"rpc ids={ids} gate visible={sorted(seen_s)} hidden={hidden_s}")

    got = rpc(state, "stranger", "GetTask",
              {"id": "T-0001", "historyLength": 10, "includeArtifacts": True}, rid=42)
    result = got.get("result") or {}
    meta = (result.get("metadata") or {}).get("aim") or {}
    check("DEFECT W2: `GetTask` hands the same viewer the card's own `accept` field, "
          "both as metadata and as the artifact §3.1.4 says to build from it, on a card "
          "the CLI refuses to show",
          result.get("id") == "T-0001" and meta.get("accept") == TOKEN
          and any(TOKEN in json.dumps(a) for a in (result.get("artifacts") or [])),
          json.dumps(got, ensure_ascii=False)[:400])
    check("W2 context: the payload says `visibility: draft` and names the owner, so the "
          "caller is told this is a sealed card while being handed it",
          meta.get("visibility") == "draft" and meta.get("owner") == "codex",
          json.dumps(meta, ensure_ascii=False)[:240])

    # The CLI agrees with the gate and not with /rpc, measured here so the file
    # carries all three answers rather than the two it can call directly.
    found = run("search", "--as", "stranger", "--channel", "c", "--tasks", "work")
    check("and `aim search` refuses the same viewer the same title -- no match, and the "
          "withheld count named rather than silent",
          TITLE not in found.stdout and "not searched" in (found.stdout + found.stderr),
          f"rc={found.returncode} out={found.stdout!r} err={found.stderr!r}")

    # The board's own routes, in the server process that serves /rpc. Included
    # because it localises the defect: three of the four surfaces agree and one
    # does not, and the one that does not is reachable at the same address.
    proc = subprocess.Popen([sys.executable, "-u", str(BOARD), "serve", "--root", str(root),
                             "--port", "0", "--as-of", datetime.now(timezone.utc).date().isoformat()],
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    url, said, deadline = None, [], time.time() + 30
    while time.time() < deadline:
        said.append(proc.stdout.readline())
        m = re.search(r"http://[\d.]+:(\d+)/", "".join(said))
        if m:
            url = f"http://127.0.0.1:{m.group(1)}"
            break
    check("the board serves, so the /rpc row below is a live route and not a dead one",
          url is not None, "".join(said)[-300:])
    try:
        if url:
            def fetch(path):
                with urllib.request.urlopen(url + path, timeout=20) as fh:
                    return fh.read().decode()

            as_stranger = fetch("/api/state?as=stranger")
            check("the SAME process's /api/state for the same viewer withholds the draft, "
                  "so the hole is one route in one process and not the whole server",
                  TOKEN not in as_stranger and "T-0001" not in as_stranger,
                  as_stranger[:300])
            req = urllib.request.Request(
                url + "/rpc", data=json.dumps({"jsonrpc": "2.0", "id": 43,
                                               "method": "ListTasks", "params": {}}).encode(),
                headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=20) as fh:
                live = fh.read().decode()
            check("DEFECT W2: and POST /rpc in that same process returns it anyway -- "
                  "the divergence survives the HTTP layer, so it is not an artifact of "
                  "calling `handle_rpc` by hand",
                  "T-0001" in live, live[:300])
        else:
            check("DEFECT W2: POST /rpc to a live server returns the draft (skipped: no server)",
                  False, "the server did not start, so this row could not be measured")
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()

    # --------------------------------- 4. the leader, whom no fix may wall out
    print("\n== 4. the rule the defect must not be fixed by breaking ==")
    leader_list = task_list("human")
    check("the leader reads the draft through the CLI -- rc 0, title printed",
          leader_list.returncode == 0 and TITLE in leader_list.stdout,
          f"rc={leader_list.returncode} out={leader_list.stdout!r} err={leader_list.stderr!r}")
    seen_l, hidden_l = gate.visible_tasks(state, "human", None)
    check("the leader reads it through the gate too, with a hidden count of zero -- the "
          "leader is the audience, not a participant, and is exempt from the barrier "
          "and from the participant rule alike",
          hidden_l == 0 and "T-0001" in seen_l,
          f"visible={sorted(seen_l)} hidden={hidden_l}")
    leader_rpc = rpc(state, "human", "ListTasks", {}, rid=44)
    check("and through the A2A surface, because the leader's read must be unchanged by "
          "whatever fix lands on the rows above",
          [t.get("id") for t in (leader_rpc.get("result") or {}).get("tasks", [])] == ["T-0001"],
          json.dumps(leader_rpc, ensure_ascii=False)[:300])

    # The exemption that IS correct, and the reason it is correct: it compares the
    # *identity* to the manifest's `leader` instead of the caller's own `kind`.
    # `impostor` declared the same kind as the leader and is still refused, which is
    # the whole difference and the shape a fix has to copy.
    advanced = run("advance", "--as", "impostor", "--channel", "c")
    check("the reader who declared `kind: human` may NOT advance the barrier -- "
          "`require_leader` is the one site that compares `who` to manifest['leader'], "
          "and this row is the proof that the correct shape is already written down",
          advanced.returncode != 0 and "human" in (advanced.stdout + advanced.stderr),
          f"rc={advanced.returncode} out={advanced.stdout!r} err={advanced.stderr!r}")
    # Selected by agent *and* action, for the reason the stranger row above gives:
    # a fixed build records the impostor's read in step 1 as well, and a row that
    # counted every refusal this agent leaves would go red for the fix landing.
    leader_rows = [r for r in refusals()
                   if r.get("agent") == "impostor" and r.get("action") in ("advance", "phase advance")]
    check("and its refusal is recorded too, with the action named -- the same audit the "
          "released read above does not leave",
          len(leader_rows) == 1, json.dumps(ledger_rows(), ensure_ascii=False)[:400])
    # Not asserted: that the impostor cannot *read* via `_visible_to`'s owner clause
    # in some other verb. That would be a second measurement of W1 with a different
    # command, and the two rows above already carry it.

print(f"\n{passed}/{passed + failed} checks passed")
print("Three DEFECT rows pin W1 (a self-declared `kind: human` releases what the CLI")
print("refuses and records) and three pin W2 (the A2A surface releases it to a viewer the")
print("gate, the CLI and the same server's /api/state all hide it from). They are red the")
print("day the hole is closed, and retiring them is the fix's last step. The five")
print("`control` rows and the leader block are the other half: they are the rows a fix")
print("that closes the hole by over-refusing would take with it.")
sys.exit(1 if failed else 0)
