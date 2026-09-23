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
import datetime
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

# T-0229: the top-level fields `lf.a2a.v1.AgentCard` actually has, read from
# a2a-sdk 1.1.5's descriptor (`AgentCard.DESCRIPTOR.fields`). `metadata` is
# deliberately absent: A2A carries `metadata` on Message/Part/Artifact/Task and
# never on the card, and the reference client's protobuf refuses a card that has
# one outright -- `ParseError: Message type "lf.a2a.v1.AgentCard" has no field
# named "metadata"`. A card whose top level is a subset of this set is a card
# the reference implementation can parse at all; that is the floor T-0229 sets.
AGENT_CARD_TOP_LEVEL_FIELDS = {
    "name", "description", "supportedInterfaces", "provider", "version",
    "documentationUrl", "capabilities", "securitySchemes", "securityRequirements",
    "defaultInputModes", "defaultOutputModes", "skills", "signatures", "iconUrl",
}

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

    # T-0229. The reference client's protobuf parses the card field by field and
    # rejects the first unknown top-level field by name, so an extra key here is
    # not a lint: it is the whole card being unreadable to a foreign client.
    # Asserted here, without importing the SDK, so this contract does not depend
    # on the throwaway venv; the run that carries the SDK is
    # tests/test_a2a_reference_client.py.
    unknown = sorted(set(card) - AGENT_CARD_TOP_LEVEL_FIELDS)
    check("the card has no top-level field outside the A2A AgentCard schema",
          not unknown,
          f"unknown top-level fields {unknown}; the reference client rejects the "
          f"first one by name ('Message type \"lf.a2a.v1.AgentCard\" has no field "
          f"named \"{unknown[0] if unknown else '?'}\"') and then no client can read us")

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

    print("== T-0104: the withheld count stays on the board (D17) ==")
    # The accept line is about a *difference*: the A2A caller gets
    # `TaskNotFoundError` with no count and no `withheld` field, and the leader's
    # board keeps the count it has today. So the fixture has to produce a real
    # fabric with a real peer draft and then ask both surfaces the same question.
    # A hand-built state dict would let the two halves agree because I wrote both,
    # which is the one thing this check must not be able to do.
    a2a_root, state, boards = build_a2a_state()
    try:
        channel = [c for c in state["channels"] if c["id"] == "t"][0]
        # `gamma` is the viewer with no claim on the draft: not its owner, not its
        # creator, and a participant. Both of those exemptions are real, so a
        # two-participant fixture cannot provoke the refusal at all — the rule is
        # a union and each of its arms needs a viewer who is not covered by the
        # other. [measured: with only alpha and beta in the channel, every GetTask
        # returned the task and the check would have passed for the wrong reason]
        draft_id = "T-0001"
        # `created_by` is asserted from the *event*, not from the folded dict,
        # and the reason is itself a measurement: `aimboard/fold.py` copies only
        # `PLAN_FIELDS` off the `created` record, and `created_by` is not among
        # them, so the renderer's task dict has no `created_by` key at all — the
        # union rule's second arm cannot fire on anything the board folds.
        # [measured: `'created_by' in state['tasks']['T-0001']` is False while
        # the event carries `actor: alpha`]. Asserting the event keeps the
        # fixture honest about what it built without pretending the board kept a
        # field it drops; the consequence is reported to codex with T-0104.
        created = [e for e in state["tasks"][draft_id].get("events", [])
                   if e.get("event") == "created"]
        check("the fixture has a draft that names a peer, and a viewer who is neither",
              draft_id in state["tasks"]
              and state["tasks"][draft_id].get("owner") == "beta"
              and len(created) == 1 and created[0].get("actor") == "alpha"
              and "gamma" in channel.get("participants", []),
              f"got {json.dumps(created)[:200]}")

        got = getattr(a2a, "get_task", lambda *a, **k: {})(draft_id, "req-1", tasks=state["tasks"],
                                                           viewer="gamma", channels=state["channels"],
                                                           registry=state["registry"])
        err = (got.get("error") or {})
        check("GetTask on a peer's draft answers TaskNotFoundError",
              err.get("code") == -32001 and got.get("result") is None,
              f"got {json.dumps(got)[:240]}")

        listed = getattr(a2a, "list_tasks", lambda *a, **k: {})( "req-2", tasks=state["tasks"],
                                                                viewer="gamma",
                                                                channels=state["channels"],
                                                                registry=state["registry"])
        result = listed.get("result") or {}
        # Both halves in one assertion: the draft is absent *and* the response says
        # nothing about anything being absent. An empty page and a withheld page
        # must be the same bytes, because a client that can tell them apart has
        # been told that a resource exists.
        blob = json.dumps(listed)
        check("ListTasks omits it, and the page says nothing about a count",
              all(t.get("id") != draft_id for t in result.get("tasks", []))
              and "withheld" not in blob and "hidden" not in blob
              and "context-hidden" not in blob,
              f"got {blob[:260]}")
        check("nextPageToken is present and empty, as §3.1.4 requires of a last page",
              "nextPageToken" in result and result["nextPageToken"] == "",
              f"got {json.dumps(result)[:200]}")

        # The other half of the accept line, and it is not "the board also hides
        # it": the leader's board keeps the count. `boards` is what
        # `aimboard.gate.visible_tasks` computes for the same fabric, so this
        # compares two implementations rather than one function against itself.
        check("the board keeps the count it has today",
              boards.get("gamma", (None, None))[1] == 1
              and boards.get("human", (None, None))[1] == 0,
              f"gate.visible_tasks says {boards}")

        # And the two answers are about the same task, not two fixtures that
        # happen to differ. The leader reads it on both surfaces.
        leaders = getattr(a2a, "get_task", lambda *a, **k: {})(draft_id, "req-3", tasks=state["tasks"],
                                                               viewer="human", channels=state["channels"],
                                                               registry=state["registry"])
        check("the leader reads the same draft through both surfaces",
              (leaders.get("result") or {}).get("id") == draft_id
              and boards.get("human", ([], None))[0]
              and draft_id in boards["human"][0],
              f"a2a={json.dumps(leaders)[:120]} gate={boards.get('human')}")

        # §3.1.4: the artifacts field MUST be omitted entirely when
        # includeArtifacts is false — not an empty array, not null. An empty array
        # is a claim ("this task has no artifacts") and an omitted field is not.
        rows = getattr(a2a, "list_tasks", lambda *a, **k: {})( "req-4", tasks=state["tasks"],
                                                              viewer="human",
                                                              channels=state["channels"],
                                                              registry=state["registry"],
                                                              include_artifacts=False)["result"]["tasks"]
        check("artifacts is omitted rather than emptied when it is not asked for",
              rows and all("artifacts" not in t for t in rows),
              f"got {[sorted(t) for t in rows][:2]}")

        # The access rule is written twice — once in `bin/aim`, which must not
        # import this package, and once in `aimboard/a2a.py`. A comment claiming
        # they agree is worth nothing; this reads both sources and checks that
        # each one's *claim* test mentions both arms of the union. That is crude,
        # and it is still the check that would have caught the disagreement this
        # whole block is about: `gate.visible_tasks`'s claim test names `owner`
        # and not `created_by`, and `bin/aim`'s names both.
        aim_src = (HERE / "bin" / "aim").read_text()
        body = aim_src.split("def _visible_to(")[1].split("\ndef ")[0]
        claim = [ln.strip() for ln in body.splitlines() if "return" in ln and "owner" in ln]
        rule = getattr(a2a, "TASK_VISIBILITY_RULE", {})
        check("both copies of the access rule claim on owner *and* creator",
              claim and all("created_by" in ln for ln in claim)
              and "owner" in rule.get("claim", "") and "created_by" in rule.get("claim", ""),
              f"bin/aim return line: {claim} ; a2a claim: {rule.get('claim')!r}")

        # And the phase tuple, which is the other half of the same duplication.
        # A `bin/aim` that gains a fourth divergence phase while this module keeps
        # three is a barrier that the A2A surface stops enforcing, silently.
        phases = aim_src.split("DIVERGENCE_PHASES = (")[1].split(")")[0]
        have = tuple(re.findall(r'"([A-Z_]+)"', phases))
        check("the divergence phases are the same on both sides",
              have and have == tuple(getattr(a2a, "DIVERGENCE_PHASES", ())),
              f"bin/aim={have} a2a={getattr(a2a, 'DIVERGENCE_PHASES', None)}")
    finally:
        shutil.rmtree(a2a_root, ignore_errors=True)

    print("== T-0106: the doorbell hook becomes a TaskPushNotificationConfig ==")
    bell_root, bell_state, _ = build_a2a_state()
    try:
        bell = str(HERE / "bin" / "aim")

        def run_bell(*argv, env_extra=None):
            env = os.environ | {"AIM_ROOT": bell_root} | (env_extra or {})
            return subprocess.run([bell, *argv], env=env, capture_output=True,
                                  text=True, timeout=30)

        # (1) The accept line's first half: url, token and authenticationInfo as
        # the spec defines. Built through the verb, then read back off disk, so a
        # config the CLI accepted but never wrote fails here rather than passing
        # on the CLI's own echo.
        created = run_bell("task", "doorbell", "create", "--as", "alpha",
                           "--channel", "t", "--id", "T-0001",
                           "--url", "https://hooks.example.invalid/a2a",
                           "--token", "s3cret-token")
        check("a push notification config is created against a task",
              created.returncode == 0, f"rc={created.returncode} {created.stderr[:200]}")
        stored = None
        push_path = Path(bell_root) / "channels" / "t" / "push.jsonl"
        for line in push_path.read_text().splitlines():
            rec = json.loads(line)
            if rec.get("event") == "doorbell_created":
                stored = rec
        check("what it wrote carries url, token and authenticationInfo",
              stored is not None
              and stored.get("url") == "https://hooks.example.invalid/a2a"
              and stored.get("token") == "s3cret-token"
              and (stored.get("authenticationInfo") or {}).get("scheme") == "Bearer"
              and (stored.get("authenticationInfo") or {}).get("credentials") == "s3cret-token",
              f"got {json.dumps(stored)[:260]}")
        # §4.3.3 presents the *credentials* as the header value, so a config whose
        # two secrets disagree has one it will never send. Refused rather than
        # stored, because a caller who checks the other one would see it as valid.
        check("a config whose token and credentials disagree is refused",
              run_bell("task", "doorbell", "create", "--as", "alpha", "--channel", "t",
                       "--id", "T-0001", "--url", "https://hooks.example.invalid/b",
                       "--token", "one", "--credentials", "two").returncode == 2,
              "the command accepted two different secrets for one header")

        # (2) The accept line's second half, and the measured fix behind it: the
        # token check must be the *tool's* refusal, not argparse's. With
        # `--token required=True` this exited 2 from argparse, printed a usage
        # block, never reached `note_context`, and left the ledger empty — a
        # refusal with no record, which is the one artifact that answers "did
        # anyone try this". [measured: that is what the first version did]
        no_token = run_bell("task", "doorbell", "create", "--as", "alpha",
                            "--channel", "t", "--id", "T-0001",
                            "--url", "https://hooks.example.invalid/c")
        refusals = []
        for line in (Path(bell_root) / "channels" / "t" / "ledger.jsonl").read_text().splitlines():
            rec = json.loads(line)
            if rec.get("event") == "refusal":
                refusals.append(rec)
        check("a config with no token is refused by the tool, and recorded",
              no_token.returncode == 2
              and "usage:" not in no_token.stderr
              and any(r.get("action") == "task doorbell create"
                      and "token" in r.get("reason", "") for r in refusals),
              f"rc={no_token.returncode} stderr={no_token.stderr[:200]} "
              f"refusals={[r.get('action') for r in refusals]}")

        # (3) "The config is additive" is a claim about the hook, and the only
        # way to test it is to run the hook. A config that changed the hook's
        # output would have made the local doorbell conditional on a webhook
        # somewhere else, which is the dependency the design rejected.
        run_bell("push", "--as", "alpha", "--to", "beta", "--body", "ring ring")
        hook_env = {"AIM_ROOT": bell_root, "AIM_BIN": bell, "AIM_AGENT": "beta"}

        def ring():
            return subprocess.run([str(HERE / "bin" / "aim-doorbell-hook"), "beta"],
                                  env=os.environ | hook_env, capture_output=True,
                                  text=True, timeout=30)

        before = ring()
        check("the local hook rings with no config anywhere",
              before.returncode == 0 and "unread message" in before.stdout,
              f"rc={before.returncode} out={before.stdout[:200]!r}")
        check("and creating a config does not change one byte of what it prints",
              ring().stdout == before.stdout,
              "the hook's output depends on whether a webhook is configured")

        # (4) `aim verify` covers the config chain. An unverified chain is a
        # decoration: the file carries `prev` and `hash` that nothing reads,
        # which looks like tamper-evidence and is not.
        check("the config file's chain is verified with the channel's other files",
              run_bell("verify", "--channel", "t").returncode == 0,
              "aim verify does not cover push.jsonl")
        # ...and the claim is that it *would* notice. A chain nobody can break in
        # a test is a chain nobody has shown is being read.
        push_path.write_text(push_path.read_text().replace("s3cret-token", "rotated!!!"))
        tampered = run_bell("verify", "--channel", "t")
        check("and an edited token is reported rather than rendered",
              tampered.returncode == 1 and "TAMPER" in tampered.stdout
              and "rotated!!!" not in tampered.stdout,
              f"rc={tampered.returncode} out={tampered.stdout[:200]}")
        # Restore, so the checks after this one judge the rest of the fabric and
        # not this deliberate edit. [measured: leaving it edited turned the next
        # check red for a reason that had nothing to do with it]
        push_path.write_text(push_path.read_text().replace("rotated!!!", "s3cret-token"))

        # (5) The rules are implemented once, in `aimboard/a2a.py`, and the verb
        # reads them. Two implementations of one rule is what this project keeps
        # finding, so the check is that the same input makes both refuse for the
        # same *field* — the CLI's sentence and the module's `fieldViolations`.
        cases = [
            ({"url": "file:///tmp/hook", "token": "x"}, "url",
             ["--url", "file:///tmp/hook", "--token", "x"]),
            ({"url": "https://ok.invalid/h", "token": ""}, "token",
             ["--url", "https://ok.invalid/h"]),
        ]
        for config, field, argv in cases:
            module = getattr(a2a, "validate_push_config", lambda c: [("", "missing")])(config)
            out = run_bell("task", "doorbell", "create", "--as", "alpha", "--channel", "t",
                           "--id", "T-0001", *argv)
            check(f"the verb and the module refuse {field!r} for the same reason",
                  module and module[0][0] == field and out.returncode == 2
                  and field in out.stderr,
                  f"module={module} cli_rc={out.returncode} err={out.stderr[:180]!r}")

        # (6) The four operations, module half: the gate runs before the config is
        # read, so a caller who may not see the task cannot learn that a webhook
        # is configured for it — §13.1's ordering rule applied to the write path.
        as_gamma = getattr(a2a, "create_push_config", lambda *a, **k: {})(
            "T-0001", "r1", config={"url": "https://x.invalid/h", "token": "t"},
            tasks=bell_state["tasks"], viewer="gamma",
            channels=bell_state["channels"], registry=bell_state["registry"])
        check("a caller who cannot read the task cannot configure a doorbell for it",
              (as_gamma.get("error") or {}).get("code") == -32001,
              f"got {json.dumps(as_gamma)[:200]}")
        # And for a caller who *can*, a refused config is §3.3.2's validation
        # category — `-32602` with `fieldViolations` — not one of the nine. None
        # of the nine means "your url is malformed", and dressing it in one would
        # be a semantic the request never had. The caller here is `beta`, who
        # *owns* T-0001 in the renderer's fold; see the divergence check below for
        # why the owner and not the creator is the one the module can answer.
        as_beta = getattr(a2a, "create_push_config", lambda *a, **k: {})(
            "T-0001", "r2", config={"url": "not-a-url", "token": "t"},
            tasks=bell_state["tasks"], viewer="beta",
            channels=bell_state["channels"], registry=bell_state["registry"])
        viol = (((as_beta.get("error") or {}).get("data") or [{}])[0]
                .get("fieldViolations") or [])
        check("a config for a task the caller can read fails as -32602 fieldViolations",
              (as_beta.get("error") or {}).get("code") == -32602
              and viol and viol[0].get("field") == "url",
              f"got {json.dumps(as_beta)[:220]}")

        # The CLI side of the same two answers, read out of the ledger: the
        # refusal a *participant who cannot see the task* gets must map onto
        # `TaskNotFoundError`, which is T-0104's rule reaching the push path. The
        # whole point of `class: barrier` being decided at the refusal site rather
        # than read off the message is that this mapping works for a verb nobody
        # had written when the table was made.
        as_gamma_cli = run_bell("task", "doorbell", "create", "--as", "gamma",
                                "--channel", "t", "--id", "T-0001",
                                "--url", "https://x.invalid/h", "--token", "t")
        mapped = None
        for line in (Path(bell_root) / "channels" / "t" / "ledger.jsonl").read_text().splitlines():
            rec = json.loads(line)
            if (rec.get("event") == "refusal"
                    and rec.get("action") == "task doorbell create"
                    and "draft owned by someone else" in rec.get("reason", "")):
                mapped = getattr(a2a, "mapped_error", lambda *a, **k: None)(
                    rec["reason"], action=rec["action"], refusal_class=rec["class"])
        check("a participant who cannot see the task is refused, and maps to TaskNotFoundError",
              as_gamma_cli.returncode == 2 and mapped == "TaskNotFoundError",
              f"rc={as_gamma_cli.returncode} mapped={mapped}")

        # This check was written *as a divergence* rather than as an expectation of
        # either answer, so that fixing `aimboard/fold.py` would turn it red and
        # someone would update it on purpose. That is what happened: T-0250 gave
        # the renderer's fold the `created_by` it was missing, and the divergence
        # is gone. The agreement is now the thing to freeze, so the check is
        # inverted rather than deleted -- a regression that drops `created_by`
        # again fails here, and it fails as a *disagreement* rather than as a
        # changed constant, which is what this whole block is about.
        #
        # T-0001 and not the published T-0002, which is the mistake the first
        # version made: a published task is visible to everyone under every rule,
        # so the two answers agreed and the check was green for a reason that had
        # nothing to do with the divergence. [measured: with T-0002 both returned a
        # config, and the check failed on its own fixture rather than on the bug]
        cli_wrote = run_bell("task", "doorbell", "create", "--as", "alpha",
                             "--channel", "t", "--id", "T-0001",
                             "--url", "https://x.invalid/gate", "--token", "t")
        mod_says = getattr(a2a, "create_push_config", lambda *a, **k: {})(
            "T-0001", "r5", config={"url": "https://x.invalid/gate", "token": "t"},
            tasks=bell_state["tasks"], viewer="alpha",
            channels=bell_state["channels"], registry=bell_state["registry"])
        check("the two folds agree for the creator of a handed-over task, and one rule "
              "answers on both surfaces",
              cli_wrote.returncode == 0
              and (mod_says.get("error") or {}).get("code") != -32001,
              f"cli_rc={cli_wrote.returncode} module={json.dumps(mod_says)[:160]}")

        # (7) The secret, on the read shapes. §13.2 calls the token something to
        # treat as a secret and rotate; a Get that returns it hands it to whoever
        # can call the operation. So a read masks and a create echoes, and the
        # mask is a comparison rather than a fixed `***` — a caller who cannot
        # tell a rotated token from an unchanged one will rotate blind.
        live = [{"taskId": "T-0001", "configId": "cfg-x", "url": "https://x.invalid/h",
                 "token": "topsecret", "authenticationInfo": {"scheme": "Bearer",
                                                              "credentials": "topsecret"}}]
        read = getattr(a2a, "get_push_config", lambda *a, **k: {})(
            "cfg-x", "r3", configs=[("T-0001", live[0])], task_id="T-0001")
        listed = getattr(a2a, "list_push_configs", lambda *a, **k: {})(
            "T-0001", "r4", configs=[("T-0001", live[0])])
        blob = json.dumps([read, listed])
        check("no read shape returns the token itself",
              "topsecret" not in blob and "masked" in blob,
              f"got {blob[:240]}")
        # Equal *lengths* on purpose: two secrets of different lengths would mask
        # differently for a reason that has nothing to do with the digest, and the
        # check would pass on a mask that is nothing but a length.
        check("and the mask distinguishes one token from another",
              getattr(a2a, "mask_secret", lambda s: "")("topsecret")
              != getattr(a2a, "mask_secret", lambda s: "")("topsecre2")
              and getattr(a2a, "mask_secret", lambda s: "")("topsecret")
              == getattr(a2a, "mask_secret", lambda s: "")("topsecret"),
              "the mask cannot tell two secrets apart, so a rotation is invisible")
    finally:
        shutil.rmtree(bell_root, ignore_errors=True)

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
            # The surface is honest, not merely present (T-0122). A method with
            # no backing verb answers `-32004 UnsupportedOperation`, which is
            # what a capability that does not exist must say (§3.4's argument
            # for pushNotifications applies to the whole surface: a route that
            # returns 200 with a fake result is the same lie one level down).
            unsupported = [("SendMessage", {"message": {}}),
                           ("CancelTask", {"id": "T-0001"}),
                           ("SubscribeToTask", {"id": "T-0001"})]
            for method, params in unsupported:
                resp = post_rpc(url, method, params)
                body = resp.get("body", "")
                # Streaming ops answer inside an SSE event: a `data: ...\n\n`
                # envelope whose JSON body is the JSON-RPC response. The content
                # type is honoured, not the wire shape, so a client gets the
                # same {jsonrpc, id, error} object either way.
                if resp.get("content_type", "").startswith("text/event-stream"):
                    body = body.split("data: ", 1)[-1].splitlines()[0]
                try:
                    doc = json.loads(body)
                except (ValueError, TypeError):
                    doc = {}
                check(f"{method} is an honest UnsupportedOperation, not a fake result",
                      doc.get("error", {}).get("code") == -32004,
                      f"expected -32004, got {body[:160]!r}")
            # And a task nobody can see is withheld through the wire, the same
            # way it is withheld through every other read: D17's no-count rule
            # is a property of the folded model, and a new surface that reuses
            # it must not be the one place a foreign caller learns a task
            # exists. GetExtendedAgentCard is the viewer's own identity, so it
            # is the positive control that the wire is actually talking.
            body = post_rpc(url, "GetTask", {"id": "T-0001", "historyLength": 10}).get("body", "")
            try:
                doc = json.loads(body)
            except (ValueError, TypeError):
                doc = {}
            check("a task the caller cannot see is withheld on /rpc, with no count",
                  doc.get("error", {}).get("code") == -32001,
                  f"expected -32001 TaskNotFound, got {body[:160]!r}")
            body = post_rpc(url, "GetExtendedAgentCard", {}).get("body", "")
            try:
                doc = json.loads(body)
            except (ValueError, TypeError):
                doc = {}
            check("GetExtendedAgentCard answers with the viewer's own card",
                  bool((doc.get("result") or {}).get("name")),
                  f"expected a card, got {body[:160]!r}")
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
    must("task", "new", "--as", "alpha", "--channel", "t", "--title", "alpha's own line of work",
         "--owner", "alpha")
    must("task", "new", "--as", "alpha", "--channel", "t", "--title", "the shared one")
    must("task", "publish", "--as", "alpha", "--channel", "t", "--id", "T-0002")

    # `t4` is carried to SYNTHESIS by the leader, which is the only way to reach
    # the phase where sealing is closed.
    must("say", "--as", "alpha", "--channel", "t4", "--private", "--body", "alpha's position, in alpha's own words, at some length")
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


def build_a2a_state():
    """A real fabric with a real peer draft, loaded by the renderer's own loader.

    Returns `(root, state, boards)`:
      * `state` is `aimboard.fabric.load_fabric`'s dict, which is what the A2A
        translation is written against;
      * `boards[viewer]` is `(visible ids, hidden count)` from
        `aimboard.gate.visible_tasks` — the board's answer to the same question.

    Loaded rather than hand-built, and the harness shells out to `aim` for the
    fabric itself, because a test that constructs both sides of a comparison
    proves only that its author was consistent. The one thing this fixture does
    *not* do is assert the two surfaces agree: they do not, for a task whose owner
    and creator differ (see the note in the T-0104 block), and that disagreement
    is reported to codex rather than papered over here.
    """
    root = tempfile.mkdtemp(prefix="a2a-state-")
    env = os.environ | {"AIM_ROOT": root}
    aim = str(HERE / "bin" / "aim")

    def run(*argv):
        return subprocess.run([aim, *argv], env=env, capture_output=True, text=True, timeout=30)

    def must(*argv):
        done = run(*argv)
        assert done.returncode == 0, f"{argv} failed: {done.stderr}"

    must("init")
    for who, kind in (("human", "human"), ("alpha", "claude"),
                      ("beta", "codex"), ("gamma", "codex")):
        must("register", "--as", who, "--kind", kind)
    must("new-channel", "--id", "t", "--topic", "the gate", "--participants",
         "alpha,beta,gamma", "--leader", "human")
    # T-0001 is alpha's draft, handed to beta: `owner` and `created_by` differ on
    # purpose, because that is the case the two gate implementations treat
    # differently and the case a union rule has to get right.
    must("task", "new", "--as", "alpha", "--channel", "t", "--title", "alpha's draft, handed to beta")
    must("task", "assign", "--as", "alpha", "--channel", "t", "--id", "T-0001", "--owner", "beta")
    must("task", "new", "--as", "human", "--channel", "t", "--title", "out in the open",
         "--visibility", "published")

    from aimboard import fabric, gate
    state = fabric.load_fabric(Path(root), [], datetime.date(2026, 9, 21))
    boards = {}
    for viewer in ("alpha", "beta", "gamma", "human"):
        visible, hidden = gate.visible_tasks(state, viewer, None)
        boards[viewer] = (sorted(visible), hidden)
    return root, state, boards


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
