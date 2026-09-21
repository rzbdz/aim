#!/usr/bin/env python3
"""A2A conformance contract, written before the implementation.

This file deliberately does not import an SDK and does not start a server. It
asserts the shape of `aimboard/a2a.py` — the module the binding will live in —
so that the first implementation is written against a contract rather than
against a reading of the spec.

Run: python3 tests/test_a2a_conformance.py     (exit code = number of failures)
"""
import re
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
    check("an error response is a JSON-RPC 2.0 error object",
          isinstance(response, dict)
          and response.get("jsonrpc") == "2.0"
          and response.get("id") == "req-1"
          and isinstance(response.get("error"), dict)
          and response["error"].get("code") == -32001
          and response["error"].get("message") == "TaskNotFoundError"
          and response["error"].get("data", {}).get("type") == "TaskNotFoundError",
          f"got {response}")

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
