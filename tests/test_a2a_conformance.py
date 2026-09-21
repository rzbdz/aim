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
