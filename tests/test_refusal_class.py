"""The refusal ledger's `class` field: at the refusal site, and inherited by nobody.

T-0222. Every refusal record carries a `class`, and the barrier page offers
exactly two of them to filter by -- `barrier` and `form` (BarrierPane.vue:151-152)
-- so a class is a claim a reader audits with, not a label. `die()` used to
default to `cls="form"` (`bin/aim:201` before this change) and **no call site
chose it**: `rg 'cls="form"' bin/aim` found only the two default parameters, at
`:171` and `:201`. The default was the answer for everything that did not claim
otherwise, and for identity refusals it was false. Measured on a throwaway root
with the pre-fix file; all four probes exit 2 and write one row each:

    aim say --as outsider --channel c --body ...   -> class=form
    aim seal --as outsider --channel c --summary .. -> class=form
    aim task new --as outsider --channel c ...     -> class=form
    aim friction --as outsider --channel c --add .. -> class=form
    aim advance --as alpha --channel c --to COMMIT -> class=barrier

`require_leader` (`:567` at the time) passed `cls="barrier"` for the identical
shape of check, in a comment that says why: "the request is well-formed and is
refused for who sent it". `gate.py:11` names the same second way of being shut
out as the barrier ("being a **stranger**: you are a registered agent and not a
participant"). So the project had already decided this in prose and in one gate,
and the membership gates wrote the opposite into the record. On the live
`channels/hello/ledger.jsonl` the same defect is visible in the artifact: 6 rows
`'stranger' is not a participant` and 1 `unknown agent` under `class=form`.

This file pins three properties, and the third is the one a fix can get wrong:

  1. a well-formed request refused for identity records `barrier` -- asserted on
     the *membership* gates, because those are the sites that were wrong. A test
     that asserted on `require_leader` would have been green before the fix and
     would certify nothing (require_leader already passed `cls="barrier"`);
  2. a genuinely malformed request still records `form` -- an unknown phase name,
     an unknown status, an unregistered owner, which is the row
     `tests/selftest.sh:190-197` already pins;
  3. ledger rows that already exist are not rewritten. Two measurements: the
     prefix of the file is byte-identical across a later refusal, and a
     reconstructed pre-fix row (a correctly chained `class=form` identity
     refusal, which is what the old writer produced) still says `form` after the
     tool has written a `barrier` row beside it. The reconstruction is chained
     with the file's own `prev`/`hash` rule and `aim verify` is asserted green
     over it, so the row is a real chain link rather than a corrupt line that
     would have failed for an unrelated reason.

The four `barrier` rows above are the defect; row 2 of the list is the guard
against flipping everything to one class, because a fix that made every refusal
`barrier` would satisfy property 1 and fail property 2.

Run: python3 tests/test_refusal_class.py
"""
import ast
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AIM = ROOT / "bin" / "aim"
BARRIER_PANE = ROOT / "web" / "src" / "panes" / "BarrierPane.vue"

passed = failed = 0


def check(name, ok, detail=""):
    global passed, failed
    if ok:
        passed += 1
        print(f"  PASS  {name}")
    else:
        failed += 1
        print(f"  FAIL  {name}" + (f"\n        {detail}" if detail else ""))


def canonical(obj):
    """The same serialisation `append_chained` hashes with (bin/aim:118)."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def chained(recs, rec):
    """Append `rec` to `recs` the way `append_chained` would, and return it.

    Needed to reconstruct one historical row: a pre-fix `class="form"` identity
    refusal that is a *valid* link in the chain. A row appended with a wrong
    `prev` would make `aim verify` red for a reason that has nothing to do with
    the property under test, and this file would then be measuring its own
    fixture -- the failure mode test_a2a_conformance.py:778 records from a
    earlier version of its own refusal table.
    """
    body = dict(rec)
    body["prev"] = recs[-1]["hash"] if recs else "genesis"
    body["hash"] = hashlib.sha256(canonical({k: v for k, v in body.items()
                                             if k != "hash"}).encode("utf-8")).hexdigest()
    return body


with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    env = dict(os.environ, AIM_ROOT=str(root))

    def run(*argv):
        return subprocess.run([sys.executable, str(AIM), *argv], capture_output=True,
                              text=True, env=env, timeout=60)

    ledger = root / "channels" / "c" / "ledger.jsonl"

    def rows():
        if not ledger.exists():
            return []
        return [json.loads(l) for l in ledger.read_text(encoding="utf-8").splitlines()
                if l.strip()]

    def refusals():
        return [r for r in rows() if r.get("event") == "refusal"]

    def fresh_refusal(*argv):
        """Run one refused verb and return the single row it wrote.

        A row that cannot be tied to this command proves nothing about it, so the
        ledger is required to grow by exactly one refusal. Two of the assertions
        below are *about* the third row of a probe list, and reading `refusals()[-1]`
        would silently attribute one probe's row to another if any probe wrote
        two or none.
        """
        before = len(refusals())
        done = run(*argv)
        new = refusals()[before:]
        return done, new

    # ------------------------------------------------------------------ fixture
    run("init")
    for who, kind in (("alpha", "claude"), ("beta", "codex"),
                      ("human", "human"), ("outsider", "claude")):
        run("register", "--as", who, "--kind", kind, "--session", "refusal class")
    opened = run("new-channel", "--id", "c", "--topic", "refusal class",
                 "--participants", "alpha,beta", "--leader", "human")
    check("the fixture channel is in a divergence phase (or these refusals prove nothing)",
          "SEALED_DIVERGENT" in opened.stdout, opened.stdout + opened.stderr)

    # ------------------------------------------------------------------ 1. identity
    print("== a stranger is refused for identity, and that is what the ledger says ==")
    # `outsider` is registered and not a participant: the case gate.py:11 calls
    # the barrier's second way of being shut out. Every probe here names the
    # channel, so `note_context(channel=...)` has run by the time `die()` writes.
    IDENTITY = [
        ("say", ["say", "--as", "outsider", "--channel", "c",
                 "--body", "let me in"]),
        ("seal", ["seal", "--as", "outsider", "--channel", "c", "--summary", "in"]),
        ("task new", ["task", "new", "--as", "outsider", "--channel", "c",
                      "--title", "not mine to write"]),
        ("friction", ["friction", "--as", "outsider", "--channel", "c", "--add",
                      "--command", "aim say", "--cost", "5m"]),
        ("inbox (unregistered)", ["inbox", "--as", "ghost", "--channel", "c"]),
    ]
    for label, argv in IDENTITY:
        done, new = fresh_refusal(*argv)
        check(f"{label}: a registered non-participant is refused",
              done.returncode == 2, (done.stdout + done.stderr).strip()[:110])
        check(f"{label}: and the refusal reached the ledger",
              len(new) == 1, f"{len(new)} record(s) written by {argv}")
        if new:
            rec = new[0]
            # The class the tool *means* here is `barrier` (gate.py:11's second
            # closed door). `form` is a claim about the request and the request
            # was well-formed; a reader filtering by class is asking "did anyone
            # lean on the barrier", and the answer is yes.
            check(f"{label}: recorded as a barrier refusal, not a malformed request",
                  rec.get("class") == "barrier",
                  f"class={rec.get('class')!r} reason={rec.get('reason', '')[:70]!r}")
            check(f"{label}: the row still names the action and the phase",
                  rec.get("action") == label.split(" (")[0]
                  and rec.get("phase") == "SEALED_DIVERGENT",
                  json.dumps({k: rec.get(k) for k in ("action", "phase")}))

    print("== a caller the fabric does not know is the same kind of refusal ==")
    # `resolve_actor` is the first gate, taken before any phase rule: an id
    # nobody registered is "we do not know who is asking". The row carries an
    # empty `agent` field, and that is the record being honest rather than a
    # fault: `note_context(actor=...)` runs *after* the id is known, so the one
    # fact this refusal exists to report is the one fact the tool does not have.
    done, new = fresh_refusal("inbox", "--as", "ghost", "--channel", "c")
    check("an unregistered agent is refused", done.returncode == 2,
          (done.stdout + done.stderr).strip()[:110])
    check("and it is recorded as a barrier refusal, with the empty actor that is the finding",
          len(new) == 1 and new[0].get("class") == "barrier" and new[0].get("agent") == "",
          json.dumps([(r.get("class"), r.get("agent")) for r in new]))
    # A *missing* `--as` is deliberately not asserted here: argparse refuses it
    # before any command runs, so it never reaches `die()` and writes no row at
    # all (`aim task list --channel c` -> rc=2, usage line, 0 refusal records;
    # measured). `resolve_actor`'s `if not who` branch is therefore unreachable
    # from the CLI -- it is kept for the MCP wrapper, which calls the same code
    # path with a dict. This is the "missing argument" case T-0222 lists as
    # `form`, and it is handled by the parser rather than by the ledger; the
    # branch's class matters to the wrapper, not to this file.

    # ------------------------------------------------------------------ 2. form
    print("== a malformed request is still a malformed request ==")
    # These three are the guard against "flip everything to barrier": each is a
    # bad *value* in a correct argv, and none of them is a rule about the
    # barrier. `selftest.sh` already pins the owner row (`:171-183`); it is
    # repeated here so this file stands alone against the whole class of
    # over-correction, not just against the two rows it adds.
    MALFORMED = [
        ("unknown phase", ["advance", "--as", "human", "--channel", "c", "--to", "NOPE"]),
        ("unknown status", ["task", "new", "--as", "alpha", "--channel", "c",
                            "--title", "x", "--status", "todo"]),
        ("unregistered owner", ["task", "new", "--as", "alpha", "--channel", "c",
                                "--title", "x", "--owner", "nobody"]),
    ]
    # `--channel no-such-channel` is the other malformed case and it is
    # deliberately not in this list: `_record_refusal` returns early when the
    # channel's manifest cannot be read (`bin/aim:216-223`), so a refusal about
    # a channel that does not exist writes nothing at all. That is a real limit
    # of the ledger (the file it would have to append to is the missing thing),
    # and asserting `form` here would fail for a reason that has nothing to do
    # with the class. [measured: `aim say --as alpha --channel no-such-channel
    # --body x` -> rc=2, "aim: no such channel", 0 refusal records]
    for label, argv in MALFORMED:
        done, new = fresh_refusal(*argv)
        check(f"{label}: refused", done.returncode == 2,
              (done.stdout + done.stderr).strip()[:110])
        check(f"{label}: recorded as a form refusal",
              len(new) == 1 and new[0].get("class") == "form",
              json.dumps([r.get("class") for r in new]))

    print("== the barrier's own rules were already right, and stayed right ==")
    # The one row that is green before the fix. It is here as the control: if
    # this row moves, the change moved something it was not asked to move.
    done, new = fresh_refusal("advance", "--as", "alpha", "--channel", "c", "--to", "COMMIT")
    check("a non-leader cannot advance the barrier", done.returncode == 2,
          (done.stdout + done.stderr).strip()[:110])
    check("and it is still classed barrier (require_leader was already correct)",
          len(new) == 1 and new[0].get("class") == "barrier",
          json.dumps([r.get("class") for r in new]))

    classes = {r.get("class") for r in refusals()}
    check("both classes are in use, so neither direction was collapsed",
          classes == {"barrier", "form"}, f"classes seen: {sorted(classes)}")
    identity_rows = [r for r in refusals() if "is not a participant" in r.get("reason", "")
                     or "unknown agent" in r.get("reason", "")]
    check("every identity refusal in this ledger reads as barrier",
          identity_rows and all(r.get("class") == "barrier" for r in identity_rows),
          json.dumps([(r.get("class"), r.get("reason", "")[:40]) for r in identity_rows]))

    # ------------------------------------------------------------------ 3. forward only
    print("== what is already written is not rewritten ==")
    prefix_before = ledger.read_bytes()
    n_before = len(refusals())
    # A row the *pre-fix* writer would have produced: a membership refusal with
    # class="form". Reconstructed rather than edited into an existing row,
    # because the claim under test is about rows that already exist, and the
    # chain has to stay valid for `aim verify` to say anything.
    historical = chained(rows(), {
        "ts": "2026-09-22T00:00:00.000Z", "event": "refusal", "agent": "outsider",
        "action": "say", "phase": "SEALED_DIVERGENT", "class": "form",
        "reason": "'outsider' is not a participant in c, as recorded before T-0222",
    })
    with open(ledger, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(historical) + "\n")
    verified = run("verify", "--channel", "c")
    check("the reconstructed pre-fix row is a valid chain link, so what follows measures the property",
          verified.returncode == 0 and "chain OK" in verified.stdout,
          (verified.stdout + verified.stderr).strip()[:160])

    done, new = fresh_refusal("say", "--as", "outsider", "--channel", "c", "--body", "again")
    check("a new identity refusal is written beside the old one", len(new) == 1,
          f"{len(new)} row(s)")
    check("the new row is classed barrier",
          len(new) == 1 and new[0].get("class") == "barrier",
          json.dumps([r.get("class") for r in new]))
    after = refusals()
    kept = [r for r in after if r.get("reason") == historical["reason"]]
    check("the pre-fix row still says form -- the fix is forward only",
          len(kept) == 1 and kept[0].get("class") == "form"
          and kept[0].get("hash") == historical["hash"],
          json.dumps(kept[:1]))
    check("the whole earlier prefix is byte-identical",
          ledger.read_bytes().startswith(prefix_before),
          "the bytes before this command's row changed, which means a row was "
          "rewritten rather than appended")
    check("and the ledger only grew",
          len(after) == n_before + 2,
          f"{n_before} -> {len(after)} record(s); expected one historical row plus one new refusal")
    verified = run("verify", "--channel", "c")
    check("the chain over all of it is still intact", verified.returncode == 0
          and "chain OK" in verified.stdout, (verified.stdout + verified.stderr)[:200])

    # ------------------------------------------------------------------ 4. the default
    print("== the default is not a claim about the request ==")
    src = AIM.read_text(encoding="utf-8")
    tree = ast.parse(src)
    defaults = {}
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name in ("die", "_record_refusal"):
            args = node.args
            for name, default in zip(args.args[-len(args.defaults):], args.defaults):
                if name.arg == "cls":
                    defaults[node.name] = ast.literal_eval(default)
    check("both writers of a refusal class default to the same value",
          defaults.get("die") == defaults.get("_record_refusal") != None,
          json.dumps(defaults))
    # The honest shape, stated as a property rather than a spelling: whatever
    # the default is, it must not be one of the two classes the barrier page
    # offers as filters. A default that is a *claim* is indistinguishable from a
    # decision at every call site that forgets, which is what made `form` wrong;
    # a default outside the filter vocabulary shows up as a row that no filter
    # returns, i.e. as a visible omission instead of a false statement.
    options = re.findall(r'<el-option value="([^"]+)"', BARRIER_PANE.read_text(encoding="utf-8"))
    check("the barrier page still offers exactly the two classes this test asserts on",
          options == ["barrier", "form"], f"options: {options}")
    check("the default is not one of the classes a reader filters by",
          defaults.get("die") not in options,
          f"die() defaults to {defaults.get('die')!r}, which is a filter option "
          f"({options}) -- a forgotten class would then be a claim rather than an omission")

    unclassed = []
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id == "die"
                and not any(k.arg == "cls" for k in node.keywords)):
            unclassed.append(node.lineno)
    # The mechanism, not the intent: the default is only unreachable if every
    # site states a class. This is the assertion that goes red when someone adds
    # a refusal and forgets, which is the failure T-0222 was.
    check("no call site in bin/aim inherits the default",
          not unclassed,
          f"die() sites with no cls at lines {unclassed}")
    # `k.value` is the `ast.Constant` *node*, not its payload: comparing nodes died
    # with `'<' not supported between instances of 'Constant'` the first time this
    # ran, which is a test failing for a reason that says nothing about `bin/aim`.
    used = {k.value.value for n in ast.walk(tree) if isinstance(n, ast.Call)
            and isinstance(n.func, ast.Name) and n.func.id == "die"
            for k in n.keywords if k.arg == "cls" and isinstance(k.value, ast.Constant)}
    check("and both classes are chosen by real call sites",
          used == {"barrier", "form"}, f"classes chosen: {sorted(used)}")

print(f"\n{passed}/{passed + failed} checks passed")
print("The four identity rows in the first block are the defect T-0222 filed: they")
print("recorded `form` before the fix, from an argv that was well-formed. The three")
print("malformed rows beside them are the reason a blanket change to `barrier` is not")
print("the fix -- a class a reader filters by cannot be the answer for everything.")
sys.exit(1 if failed else 0)
