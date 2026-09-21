#!/usr/bin/env python3
"""A2A conformance contract, written before the implementation.

This file deliberately does not import an SDK and does not start a server. It
asserts the shape of `aimboard/a2a.py` — the module the binding will live in —
so that the first implementation is written against a contract rather than
against a reading of the spec.

Run: python3 tests/test_a2a_conformance.py     (exit code = number of failures)
"""
import re
import shutil
import sys
import json
import os
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))

try:
    from aimboard import a2a
except ImportError:
    a2a = type("Missing", (), {})()

results = []


def check(name, ok, detail=""):
    results.append((name, bool(ok), detail))
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"\n          {detail}" if detail and not ok else ""))


EXPECTED_OPERATIONS = {
    "SendMessage",
    "SendStreamingMessage",
    "GetTask",
    "ListTasks",
    "CancelTask",
    "SubscribeToTask",
    "CreateTaskPushNotificationConfig",
    "GetTaskPushNotificationConfig",
    "ListTaskPushNotificationConfigs",
    "DeleteTaskPushNotificationConfig",
    "GetExtendedAgentCard",
}

EXPECTED_ERRORS = {
    "TaskNotFoundError": -32001,
    "TaskNotCancelableError": -32002,
    "PushNotificationNotSupportedError": -32003,
    "UnsupportedOperationError": -32004,
    "ContentTypeNotSupportedError": -32005,
    "InvalidAgentResponseError": -32006,
    "ExtendedAgentCardNotConfiguredError": -32007,
    "ExtensionSupportRequiredError": -32008,
    "VersionNotSupportedError": -32009,
}

EXPECTED_TASK_STATES = {
    "TASK_STATE_UNSPECIFIED",
    "TASK_STATE_SUBMITTED",
    "TASK_STATE_WORKING",
    "TASK_STATE_COMPLETED",
    "TASK_STATE_FAILED",
    "TASK_STATE_CANCELED",
    "TASK_STATE_INPUT_REQUIRED",
    "TASK_STATE_REJECTED",
    "TASK_STATE_AUTH_REQUIRED",
}

EXPECTED_ROLES = {"ROLE_UNSPECIFIED", "ROLE_USER", "ROLE_AGENT"}

ISO_8601_UTC = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$")


def main():
    print("== the A2A contract, before the code ==")
    check("aimboard.a2a exists", not a2a.__class__.__name__ == "Missing",
          "the binding module does not exist yet; this is the definition of done for T-0103..T-0107")

    check("all eleven core operations are named exactly once",
          set(getattr(a2a, "OPERATIONS", [])) == EXPECTED_OPERATIONS,
          f"got {sorted(getattr(a2a, 'OPERATIONS', []))}")

    check("all nine A2A errors are mapped to their JSON-RPC codes",
          getattr(a2a, "ERROR_CODES", {}) == EXPECTED_ERRORS,
          f"got {getattr(a2a, 'ERROR_CODES', {})}")

    response = getattr(a2a, "error_response", lambda *_: None)("TaskNotFoundError", "req-1")
    # Shape per §9.5 and §3.3.2: the payload must convey an error *code*, a
    # human-readable *message*, and *details* as an array where each object carries
    # `@type`. The previous assertion required `data` to be a dict with
    # `{"type": <name>}`, which is a contract the spec does not define — §9.5's own
    # example has `data` as a list whose element is a `google.rpc.ErrorInfo`. The
    # machine-readable identifier of *which* A2A error this is, is the code; the
    # `reason` in `data` repeats it structurally. So the message is asserted to be
    # prose, not the enum name, because that is what the example shows
    # (`"code": -32001, "message": "Task not found"`).
    #
    # `reason` is `TASK_NOT_FOUND`, not `TaskNotFoundError`, and that changed after
    # the first version of this check passed at 21/32. §9.5's example, §10.6's
    # gRPC table and §11.6's HTTP/REST table say the same thing in the same words:
    # "The A2A error type in UPPER_SNAKE_CASE **without the 'Error' suffix**". The
    # assertion below was checking our own type name, so it passed against a wire
    # format the spec states differently — a green check that certified the bug.
    info = (response.get("error") or {}).get("data")
    has_errorinfo = (isinstance(info, list) and len(info) == 1
                     and isinstance(info[0], dict)
                     and info[0].get("@type") == "type.googleapis.com/google.rpc.ErrorInfo"
                     and info[0].get("reason") == "TASK_NOT_FOUND"
                     and info[0].get("domain") == "a2a-protocol.org")
    msg = (response.get("error") or {}).get("message")
    check("an error response is a JSON-RPC 2.0 error object (code + message + data[])",
          isinstance(response, dict)
          and response.get("jsonrpc") == "2.0"
          and response.get("id") == "req-1"
          and isinstance(response.get("error"), dict)
          and response["error"].get("code") == -32001
          and isinstance(msg, str) and msg and msg != "TaskNotFoundError"
          and has_errorinfo,
          f"got {response}")

    check("every error type spells its reason the way §9.5 does",
          getattr(a2a, "error_reason", lambda *_: None)("TaskNotFoundError") == "TASK_NOT_FOUND"
          and getattr(a2a, "error_reason", lambda *_: None)("PushNotificationNotSupportedError")
          == "PUSH_NOTIFICATION_NOT_SUPPORTED"
          and getattr(a2a, "error_reason", lambda *_: None)("VersionNotSupportedError")
          == "VERSION_NOT_SUPPORTED",
          "the rule is mechanical, so it is one function over ERROR_CODES rather "
          "than a second table that can drift from the first")

    check("field names normalize from snake_case to camelCase",
          getattr(a2a, "normalize_keys", lambda x: x)({
              "context_id": "c", "task_id": "t", "message_id": "m",
              "reference_task_ids": [], "push_notification_config": {},
          }) == {
              "contextId": "c", "taskId": "t", "messageId": "m",
              "referenceTaskIds": [], "pushNotificationConfig": {},
          })

    check("TaskState is exactly the nine SCREAMING_SNAKE values",
          set(getattr(a2a, "TASK_STATES", [])) == EXPECTED_TASK_STATES,
          f"got {sorted(getattr(a2a, 'TASK_STATES', []))}")

    check("Role is exactly the three SCREAMING_SNAKE values",
          set(getattr(a2a, "ROLES", [])) == EXPECTED_ROLES,
          f"got {sorted(getattr(a2a, 'ROLES', []))}")

    check("timestamps are ISO-8601 UTC with millisecond precision",
          getattr(a2a, "is_iso8601_utc", lambda *_: False)("2026-09-21T09:30:00.000Z") is True
          and getattr(a2a, "is_iso8601_utc", lambda *_: True)("2026-09-21T09:30:00+08:00") is False,
          "the spec's JSON form is YYYY-MM-DDTHH:mm:ss.sssZ")

    print("== the AgentCard (T-0102) ==")
    # The card is the one A2A object this fabric can emit today, because it is a
    # read of the registry and needs no endpoint. These checks are here rather
    # than in a new file because this file is the contract: a second suite for
    # the same protocol is how two readings of one spec start.
    card1, card2 = build_card(twice=True)
    card = card1
    check("`aim card` renders an AgentCard for a registered agent",
          isinstance(card, dict) and bool(card.get("name")),
          f"got {card if not isinstance(card, dict) else sorted(card)}")

    required = ["name", "description", "capabilities", "skills",
                "supportedInterfaces", "defaultInputModes", "defaultOutputModes", "version"]
    check("the card carries every field the spec marks REQUIRED, and an interface",
          all(f in card for f in required),
          f"missing {[f for f in required if f not in card]}")

    iface = (card.get("supportedInterfaces") or [{}])[0]
    check("the interface declares a version in Major.Minor form",
          re.fullmatch(r"\d+\.\d+", str(iface.get("protocolVersion", ""))) is not None,
          f"got {iface.get('protocolVersion')!r}; the spec's service parameter is "
          f"'the A2A protocol version that the client is using', e.g. '0.3'")
    check("the version this binding pins is the one the card declares",
          iface.get("protocolVersion") == getattr(a2a, "PROTOCOL_VERSION", None),
          f"card says {iface.get('protocolVersion')!r}, module pins "
          f"{getattr(a2a, 'PROTOCOL_VERSION', None)!r} — a card that drifts from the "
          f"constant the suite pins is a version claim nobody can falsify")
    check("a custom protocolBinding is identified by a URI",
          str(iface.get("protocolBinding", "")).startswith("https://"),
          f"got {iface.get('protocolBinding')!r}; section 5.8 says a custom binding "
          f"SHOULD be identified by a URI so implementations do not collide")

    caps = card.get("capabilities") or {}
    check("capabilities has the four boolean/array fields",
          set(caps) >= {"streaming", "pushNotifications", "extensions", "extendedAgentCard"},
          f"got {sorted(caps)}")
    check("streaming is declared false, not omitted",
          caps.get("streaming") is False,
          "an absent capability and a false one both make the operations fail, but "
          "only one of them tells a client why; we must state it (section 12.5)")
    check("no capability is declared true without the surface behind it",
          all(caps.get(k) is False for k in ("streaming", "extendedAgentCard")),
          f"streaming={caps.get('streaming')} extendedAgentCard={caps.get('extendedAgentCard')}")

    exts = caps.get("extensions") or []
    check("each extension is a URI in the D16 namespace with required:false",
          len(exts) >= 3
          and all(e.get("uri", "").startswith("https://") and e.get("required") is False
                  and e.get("description") for e in exts),
          f"got {exts}")

    skills = card.get("skills") or []
    check("every skill carries the spec's fields",
          bool(skills) and all({"id", "name", "description", "tags"} <= set(s) for s in skills),
          f"got {[sorted(s) for s in skills]}")

    check("name and description are strings, and description is not empty",
          isinstance(card.get("name"), str) and isinstance(card.get("description"), str)
          and bool(card["description"].strip()),
          "the canonicalization example (section 8.4) has description:'' for a "
          "REQUIRED field; we always have something to say")

    card1, card2 = build_card(twice=True)
    card = card1
    check("the card is deterministic: same registry, same bytes",
          card1 == card2,
          "a card that changes between two reads of an unchanged registry cannot be cached")

    print("== T-0103: the five mandated refusal classes (design/05 §5) ==")
    # The accept line has two halves and both are asserted here from one object:
    # the mapped A2A error type *and* the ledger record. The fixture drives the
    # real verb in a real fabric, because a mapping asserted against a refusal
    # sentence I typed into the test would pass even if `bin/aim` had never
    # emitted that sentence. [measured: the first version of this fixture reused
    # the selftest's channels with no tasks in them, so `task move` refused with
    # "no such task" — a form error — and the check certified an untested path]
    fabric_root, refusals = build_refusals()
    try:
        check("the five mandated refusals all reached the ledger",
              len(refusals) == 5, f"got {len(refusals)}: {[r['label'] for r in refusals]}")

        print("== T-0103: half one — the mapped A2A error type ==")
        for r in refusals:
            mapped = getattr(a2a, "mapped_error", lambda *a, **k: None)(
                r["reason"], r["action"], r["class"])
            check(f"the {r['label']} refusal maps onto {r['expect']}",
                  mapped == r["expect"],
                  f"got {mapped!r} for action={r['action']!r} class={r['class']!r} "
                  f"reason={r['reason'][:70]!r}")

        # A refusal that maps onto nothing is a *decision*, not an omission, and
        # the two are indistinguishable from a None return. So the unmapped
        # classes are named in the module (NATIVE_ONLY) and a refusal that maps
        # to nothing must be one of them — otherwise `None` is how a missing row
        # hides.
        unmapped = [r for r in refusals if r["expect"] is None]
        check("a refusal A2A has no word for is a named decision, not a missing row",
              all(r["class"] in getattr(a2a, "NATIVE_ONLY", {}) for r in unmapped)
              and bool(getattr(a2a, "NATIVE_ONLY", {})),
              f"unmapped classes {[r['class'] for r in unmapped]}, "
              f"NATIVE_ONLY covers {sorted(getattr(a2a, 'NATIVE_ONLY', {}))}")

        print("== T-0103: half two — the ledger still keeps our own shape ==")
        # Per channel, because the five refusals are not all in one: the phase
        # rules fire on `t4` and the board rules on `t`. The first version of this
        # check read only `t`, so a refusal recorded in `t4` would have been
        # reported as missing. [measured: it failed on the fifth row, which is
        # exactly that]
        def ledger_rows(ch):
            p = Path(fabric_root) / "channels" / ch / "ledger.jsonl"
            return [json.loads(l) for l in p.read_text().splitlines() if '"refusal"' in l]

        for r in refusals:
            rows = ledger_rows(r["channel"])
            check(f"the {r['label']} refusal is in the ledger with its class",
                  any(rec.get("reason", "").startswith(r["reason"][:60])
                      and rec.get("class") == r["class"]
                      and rec.get("phase") == r["phase"]
                      for rec in rows),
                  f"ledger in {r['channel']} holds "
                  f"{[(rec.get('class'), rec.get('reason', '')[:40]) for rec in rows][-3:]}")

        check("the ledger's class agrees with the mapping table's own key",
              all(getattr(a2a, "mapped_error", lambda *a, **k: None)(r["reason"], r["action"],
                                                                    r["class"]) == r["expect"]
                  for r in refusals),
              "a record whose class says `barrier` while the mapper treats it as "
              "`form` is the two halves disagreeing about one event")

        # One response, both halves — §5.4 requires a custom binding to say how
        # it represents A2A errors natively, and our native form is the ledger
        # record. So the refusal travels *with* the error a foreign client reads.
        sample = [r for r in refusals if r["expect"] == "TaskNotFoundError"][0]
        response = getattr(a2a, "error_response", lambda *a, **k: {})(sample["expect"], "req-2",
                                                                    sample["reason"],
                                                                    action=sample["action"],
                                                                    reason=sample["reason"],
                                                                    native=getattr(a2a, "native_error")(sample["reason"], cls=sample["class"], action=sample["action"]))
        data = (response.get("error") or {}).get("data") or []
        check("an A2A error carries our refusal record beside the ErrorInfo",
              len(data) == 2
              and data[0].get("@type") == "type.googleapis.com/google.rpc.ErrorInfo"
              and data[1].get("refusal") == sample["reason"]
              and data[1].get("class") == "barrier"
              and "ledger.jsonl" in str(data[1].get("recorded", "")),
              f"got {json.dumps(data)[:300]}")
    finally:
        shutil.rmtree(fabric_root, ignore_errors=True)

    print("== the JSON-RPC surface ==")
    root, proc, url = start_server()
    try:
        check("the board serves an A2A JSON-RPC endpoint", url is not None,
              "the server did not announce its address")
        if url:
            for method, params, stream in REQUESTS:
                response = post_rpc(url, method, params)
                check(f"{method} answers on /rpc",
                      response["status"] == 200
                      and (response["content_type"].startswith("text/event-stream") if stream
                           else response["content_type"].startswith("application/json")),
                      f"got HTTP {response['status']} {response['content_type']}")
    finally:
        if proc:
            proc.terminate()
            proc.wait(timeout=20)
        if root:
            root.cleanup()

    return finish()


REQUESTS = [
    ("SendMessage", {"message": {"messageId": "m1", "role": "ROLE_USER", "parts": [{"text": "hello"}]}}, False),
    ("SendStreamingMessage", {"message": {"messageId": "m1", "role": "ROLE_USER", "parts": [{"text": "hello"}]}}, True),
    ("GetTask", {"id": "T-0001", "historyLength": 10}, False),
    ("ListTasks", {"contextId": "c", "pageSize": 50, "pageToken": ""}, False),
    ("CancelTask", {"id": "T-0001"}, False),
    ("SubscribeToTask", {"id": "T-0001"}, True),
    ("CreateTaskPushNotificationConfig", {"taskId": "T-0001", "url": "https://example.invalid/hook", "token": "t"}, False),
    ("GetTaskPushNotificationConfig", {"taskId": "T-0001", "configId": "cfg1"}, False),
    ("ListTaskPushNotificationConfigs", {"taskId": "T-0001"}, False),
    ("DeleteTaskPushNotificationConfig", {"taskId": "T-0001", "configId": "cfg1"}, False),
    ("GetExtendedAgentCard", {}, False),
]


REFUSALS = [
    # (label, argv, the A2A error type this refusal must map onto; None = the
    #  binding has no A2A word for it and says so in NATIVE_ONLY)
    #
    # Order matters: the board row comes after the two that create and publish a
    # task, so it has exactly one draft to be refused over, and the workflow row
    # moves T-0002 — the *published* one. Pointing it at T-0001 would refuse with
    # "a draft owned by someone else", a barrier refusal standing in for a
    # workflow one, which is precisely the substitution this fixture exists to
    # prevent. [measured: that is what the first run of this table did]
    ("publishing a work item in a divergence phase",
     ["task", "new", "--as", "beta", "--channel", "t", "--title", "leak",
      "--visibility", "published"],
     "UnsupportedOperationError"),
    ("moving a task to blocked without a reason",
     ["task", "move", "--as", "beta", "--channel", "t", "--id", "T-0002",
      "--to", "blocked"],
     None),
    ("assigning a task to an unregistered agent",
     ["task", "assign", "--as", "alpha", "--channel", "t", "--id", "T-0002",
      "--owner", "nobody"],
     None),
    ("reading a peer's draft on the board",
     ["task", "list", "--as", "beta", "--channel", "t", "--json"],
     "TaskNotFoundError"),
    ("sealing after the positions are committed",
     ["seal", "--as", "alpha", "--channel", "t4", "--summary", "a late position"],
     "UnsupportedOperationError"),
]


def build_refusals():
    """Drive the five design/05 §5 refusals through `bin/aim` and read the ledger.

    What comes back is what the *tool* wrote — class and sentence included — not
    what the test expected. The expectation (`expect`) is compared against it in
    `main`, so a fixture that fails to provoke a refusal cannot silently certify
    the previous row's record: each row asserts its own command failed *and* that
    the ledger grew by exactly one refusal. That failure mode is not hypothetical
    here; the first version of this fixture reused channels with no tasks in them
    and `task move` refused with "no such task", a form error, so the class check
    was reading a refusal the row never provoked.
    """
    root = tempfile.mkdtemp(prefix="a2a-refusals-")
    env = os.environ | {"AIM_ROOT": root}
    aim = str(HERE / "bin" / "aim")

    def run(*argv):
        return subprocess.run([aim, *argv], env=env, capture_output=True, text=True, timeout=30)

    def must(*argv):
        done = run(*argv)
        assert done.returncode == 0, f"{argv} failed: {done.stderr}"

    must("init")
    for who, kind in (("human", "human"), ("alpha", "claude"), ("beta", "codex")):
        must("register", "--as", who, "--kind", kind)
    for ch in ("t", "t4"):
        must("new-channel", "--id", ch, "--topic", "refusals",
             "--participants", "alpha,beta", "--leader", "human")

    # `t` holds one draft owned by alpha (so the board refusal has something to
    # withhold) and one published task (so the workflow refusals have a task both
    # participants may act on, and are not answering "no such task").
    must("task", "new", "--as", "alpha", "--channel", "t", "--title", "alpha's own line of work")
    must("task", "new", "--as", "alpha", "--channel", "t", "--title", "the shared one")
    must("task", "publish", "--as", "alpha", "--channel", "t", "--id", "T-0002")

    # `t4` is carried to SYNTHESIS by the leader, which is the only way to reach
    # the phase where sealing is closed.
    must("say", "--as", "alpha", "--channel", "t4", "--body", "alpha's position, in alpha's own words, at some length")
    must("seal", "--as", "alpha", "--channel", "t4", "--summary", "alpha; confidence 0.7")
    must("seal", "--as", "beta", "--channel", "t4", "--summary", "beta; confidence 0.4")
    must("advance", "--as", "human", "--channel", "t4", "--to", "COMMIT")
    must("advance", "--as", "human", "--channel", "t4", "--to", "SYNTHESIS", "--synthesizer", "human")

    def ledger(ch):
        p = Path(root) / "channels" / ch / "ledger.jsonl"
        return [json.loads(l) for l in p.read_text().splitlines() if '"refusal"' in l]

    out = []
    for label, argv, expect in REFUSALS:
        ch = argv[argv.index("--channel") + 1]
        before = len(ledger(ch))
        done = run(*argv)
        fresh = ledger(ch)[before:]
        assert done.returncode != 0, f"expected a refusal from {argv}, got rc=0"
        assert len(fresh) == 1, (
            f"{argv} wrote {len(fresh)} refusal record(s), expected 1 — the row below "
            f"would then be reading another row's record")
        rec = fresh[0]
        out.append({"label": label, "argv": " ".join(argv), "class": rec.get("class"),
                    "reason": rec.get("reason", ""), "action": rec.get("action", ""),
                    "phase": rec.get("phase", ""), "channel": ch, "expect": expect})
    return root, out


def build_card(twice=False):
    """Run `aim card` against a real fabric and return the parsed card.

    Deliberately end-to-end rather than a call into `aimboard.a2a.agent_card`:
    the accept line for T-0102 is "aim card --as <agent> prints a card", so the
    thing under test is the verb. The module-level checks above can pass while
    the verb is not wired up at all, which is a green suite for an absent
    feature — the failure mode this project keeps finding.

    `twice=True` runs the verb twice against the *same* root and returns both
    cards, which is the only way to ask whether the output is deterministic. Two
    separate fabrics cannot answer it: `supportedInterfaces[].url` is the root,
    so their cards differ for a reason that has nothing to do with stability.
    [measured: the first version of this check built a fresh fabric each time and
    failed on its own fixture, not on the card]
    """
    root = tempfile.TemporaryDirectory(prefix="a2a-card-")
    env = os.environ | {"AIM_ROOT": root.name}
    for argv in (["init"],
                 ["register", "--as", "human", "--kind", "human"],
                 ["register", "--as", "carder", "--kind", "claude", "--model", "Opus 5"]):
        subprocess.run([str(HERE / "bin" / "aim"), *argv], env=env,
                       capture_output=True, text=True, timeout=20)

    def once():
        done = subprocess.run([str(HERE / "bin" / "aim"), "card", "--as", "carder"],
                              env=env, capture_output=True, text=True, timeout=20)
        try:
            return json.loads(done.stdout)
        except (json.JSONDecodeError, ValueError):
            return {"_unparsable": done.stdout[:200], "_stderr": done.stderr[:200],
                    "_rc": done.returncode}

    first = once()
    second = once() if twice else None
    root.cleanup()
    return (first, second) if twice else first


def start_server():
    root = tempfile.TemporaryDirectory(prefix="a2a-conformance-")
    env = os.environ | {"AIM_ROOT": root.name}
    subprocess.run([str(HERE / "bin" / "aim"), "init"], env=env, capture_output=True, text=True, timeout=20)
    for who, kind in (("human", "human"), ("codex", "codex")):
        subprocess.run([str(HERE / "bin" / "aim"), "register", "--as", who, "--kind", kind],
                       env=env, capture_output=True, text=True, timeout=20)
    subprocess.run([str(HERE / "bin" / "aim"), "new-channel", "--id", "c", "--topic", "a2a",
                    "--participants", "codex", "--leader", "human"],
                   env=env, capture_output=True, text=True, timeout=20)
    proc = subprocess.Popen([sys.executable, "-u", str(HERE / "bin" / "aimboard.py"), "serve",
                             "--root", root.name, "--port", "0", "--as", "human"],
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    said, url, deadline = [], None, time.time() + 20
    while time.time() < deadline:
        said.append(proc.stdout.readline())
        if proc.poll() is not None:
            break
        match = re.search(r"http://[\d.]+:(\d+)/", "".join(said))
        if match:
            url = f"http://127.0.0.1:{match.group(1)}"
            break
    return root, proc, url


def post_rpc(url, method, params):
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
    request = urllib.request.Request(f"{url}/rpc", data=body, method="POST",
                                     headers={"Content-Type": "application/json", "A2A-Version": "0.3"})
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return {"status": response.status, "content_type": response.headers.get("Content-Type", ""),
                    "body": response.read().decode()}
    except urllib.error.HTTPError as error:
        return {"status": error.code, "content_type": error.headers.get("Content-Type", ""),
                "body": error.read().decode()}


def finish():
    failed = [n for n, ok, _ in results if not ok]
    print(f"\n{len(results) - len(failed)}/{len(results)} checks passed")
    if failed:
        print("failed:")
        for name in failed:
            print(f"  - {name}")
    return len(failed)


if __name__ == "__main__":
    sys.exit(main())
