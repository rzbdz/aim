"""The A2A boundary: an AgentCard for an agent in the fabric.

Why this lives in `aimboard/` rather than in `bin/aim`
-----------------------------------------------------
The card is a *read* of the registry rendered into another protocol's shape. It
writes nothing, holds no lock, and refuses nothing, so it belongs on the same
side of the line as the fold and the renderer: a pure function from fabric state
to an external document. `bin/aim` stays the single owner of the write
discipline (design/08 section 3); this module owns the *translation*, and there
is exactly one of those.

What is deliberately absent
---------------------------
No SDK import, no server, no network. The JSON-RPC surface is T-0103..T-0106 and
it will need a decision about authentication before it is reachable off
localhost (T-0109). A card that implied an endpoint we do not serve would be the
"well-formed file missing a fact" failure this repository has measured more than
once, so `supportedInterfaces[].url` names the file root this card was built
from and `metadata.aim.binding` says in one word that no network endpoint exists
yet.

Every field here is cited to the specification revision it was read from. Source:
`a2aproject/A2A@main:docs/specification.md`, 156,828 bytes, sha256
6a78d242fe0573d0b8713482947d1ca61e8833a9cdade5913366c0b742392e75 (the revision
design/07 section 1 cites), and the AgentCard example at line 1008.
"""
from __future__ import annotations

import hashlib
import json
import re

# The protocol version this binding implements. A2A service parameters are
# `Major.Minor` (§3.2.6: "The A2A protocol version that the client is using").
# The document's header says "Latest Released Version 1.0.0" while its examples
# say 0.3, because 0.3 is the compatibility floor for an empty `A2A-Version`
# header (line 712: "0.3 will be assumed for empty header"). We implement 1.0
# and the conformance suite pins this constant, so a spec bump is a failing test
# rather than a quiet drift.
PROTOCOL_VERSION = "1.0"

# §5.8, "Custom Binding Identification": a custom `protocolBinding` SHOULD be a
# URI, and a breaking change MUST take a new one. design/07 section 4 named the
# binding `AIM+FILES`; the URI form is the normative shape, so that is what the
# card carries and the short name is kept beside it for humans.
BINDING_URI = "https://github.com/rzbdz/aim/bindings/aim-files/v1"
BINDING_NAME = "AIM+FILES"

# D16: the extension namespace. Each URI is `<namespace>/<name>/v1`; the version
# is in the path so that a breaking change to an extension is a new URI rather
# than a silently different meaning for the old one.
_EXT_NS = "https://github.com/rzbdz/aim/extensions"

# The three capabilities this fabric has that A2A does not describe, each with
# the reason it is an extension rather than a mapping onto a core field. If a
# later A2A revision covers one of these, the extension is deleted rather than
# kept for compatibility — an extension that duplicates the core is how two
# implementations of one rule start (design/08 section 3).
EXTENSIONS = [
    {
        "uri": f"{_EXT_NS}/sealed-divergence/v1",
        "description": (
            "Positions are committed under a hash-chained seal before any "
            "participant may read another's reasoning, and a refusal is recorded "
            "in a ledger. A2A's core has no notion of a stage at which reading is "
            "forbidden, so this cannot be expressed as a core field."
        ),
        "required": False,
    },
    {
        "uri": f"{_EXT_NS}/planning/v1",
        "description": (
            "A task carries an estimate, a due date and a dependency edge, and "
            "its state is a fold over an append-only event log rather than a "
            "mutable status field."
        ),
        "required": False,
    },
    {
        "uri": f"{_EXT_NS}/receipts/v1",
        "description": (
            "A sent message records the sha256 and byte count of its body, and the "
            "recipient acknowledges the bytes it verified. Delivered-but-unread is "
            "a state A2A's Task states do not carry."
        ),
        "required": False,
    },
]

# Our skills, as the capabilities an A2A client can ask for. `id` is stable and
# machine-facing; `tags` are the discovery vocabulary.
def _skills():
    return [
        {
            "id": "sealed-divergence",
            "name": "Sealed independent divergence",
            "description": (
                "Collect independent positions on a question from several agents, "
                "each sealed before any of them can read another's reasoning, then "
                "open cross-examination. Every refusal to read early is recorded."
            ),
            "tags": ["adversarial-review", "independent-positions", "barrier"],
            "examples": [
                "get three independent readings of this failure mode, then cross-examine them",
            ],
            "inputModes": ["text/plain"],
            "outputModes": ["text/plain"],
        },
        {
            "id": "planning",
            "name": "Event-sourced task board",
            "description": (
                "Work items with estimates, due dates and dependency edges. State "
                "is derived from an append-only log, so who moved an item, when, "
                "and whether the move was legitimate are all answerable."
            ),
            "tags": ["planning", "dependencies", "audit"],
            "examples": ["what is blocked and who is holding it up?"],
            "inputModes": ["text/plain"],
            "outputModes": ["text/plain"],
        },
        {
            "id": "receipts",
            "name": "Verified delivery and receipt",
            "description": (
                "A message is a durable file with a content hash; the recipient "
                "confirms the bytes it read, so 'sent' and 'received' are "
                "distinguishable rather than assumed equal."
            ),
            "tags": ["delivery", "receipt", "accountability"],
            "examples": ["did the peer actually read the review I sent?"],
            "inputModes": ["text/plain"],
            "outputModes": ["text/plain"],
        },
    ]


def agent_card(agent, root, *, description=None) -> dict:
    """Build an A2A AgentCard for `agent` (a registry record).

    `agent` is the registry entry, verbatim: the card must be derivable from what
    the fabric already records, or it is a second source of truth about identity.
    Nothing here is invented that the registry does not hold, and the two fields
    the registry does not hold (the endpoint and the version) say so.
    """
    agent_id = agent["id"]
    kind = agent.get("kind") or "other"
    model = (agent.get("model") or "").strip()

    # The card's own `version` is the *agent's* version, not the protocol's: the
    # spec's example carries "version": "1.2.0" beside "protocolVersion": "1.0"
    # (lines 2152 and 2143). We derive ours from the identity so it is stable and
    # cannot drift from the record it describes.
    identity = hashlib.sha256(
        json.dumps({"id": agent_id, "kind": kind, "model": model},
                   sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()[:12]

    desc = description or (
        f"An agent in an aim fabric, registered as '{agent_id}' ({kind}"
        + (f", {model}" if model else "") + "). "
        "This card describes a file-first binding: the fabric's transport is the "
        "filesystem and its protocol is the `aim` CLI. No network endpoint is "
        "served today, so the card is discoverable but the interface is not yet "
        "reachable off localhost."
    )

    return {
        "name": agent_id,
        "description": desc,
        # §5.8: a URI, so two implementations of this binding do not collide.
        "supportedInterfaces": [
            {
                "url": str(root),
                "protocolBinding": BINDING_URI,
                "protocolVersion": PROTOCOL_VERSION,
            }
        ],
        "version": identity,
        "capabilities": {
            # Honest, and stated rather than faked: we have no streaming surface
            # (§12.5 requires the card to say when streaming is absent, and the
            # binding must answer SendStreamingMessage with UnsupportedOperation
            # rather than pretend). Turning this true without a stream is the
            # single most damaging lie this card could tell.
            "streaming": False,
            # True because the object now exists rather than because the idea
            # does. Until T-0106 this claim rested on `bin/aim-doorbell-hook` —
            # harness glue that rings on a session's next turn and knows nothing
            # about A2A — which made the card claim a capability the tool could
            # not honour. `aim task doorbell create|list|rotate|delete` is the
            # object the four operations address, and §3.4 is explicit about the
            # cost of the opposite: with this false, all four MUST answer
            # `PushNotificationNotSupportedError`, and a card that said false
            # while the verb worked would be the same lie facing the other way.
            "pushNotifications": True,
            # No extended card: there is nothing we would say to an authenticated
            # caller that we do not say to an anonymous one, and a capability
            # declared without a reason is how a surface starts lying.
            "extendedAgentCard": False,
            "extensions": EXTENSIONS,
        },
        "defaultInputModes": ["text/plain"],
        "defaultOutputModes": ["text/plain"],
        "skills": _skills(),
        # Not a spec field, and named so that it cannot be mistaken for one: what
        # this card knows that A2A has no field for, including the part that is a
        # limitation.
        "metadata": {
            "aim": {
                "binding": BINDING_NAME,
                "bindingUri": BINDING_URI,
                "protocolVersionImplemented": PROTOCOL_VERSION,
                "agentId": agent_id,
                "agentKind": kind,
                "agentModel": model,
                "registeredAt": agent.get("registered_at", ""),
                "authentication": "none",
                "reachability": "localhost-only, no network endpoint served yet",
                "specRevision": {
                    "source": "a2aproject/A2A@main:docs/specification.md",
                    "bytes": 156828,
                    "sha256": "6a78d242fe0573d0b8713482947d1ca61e8833a9cdade5913366c0b742392e75",
                },
            }
        },
    }


# --------------------------------------------------------------------------
# Vocabulary: the enums and the error mapping (T-0103)
# --------------------------------------------------------------------------
# Everything below is a translation table and nothing below it writes. It is here
# rather than in `bin/aim` for the reason the card is: `bin/aim` owns the write
# discipline and the *refusal*; this module owns how a refusal is spelled to a
# foreign client. One owner each.

# The nine A2A error types and their JSON-RPC codes, verbatim from §5.4's
# "Error Code Mappings" table (lines 1182-1190 of the revision cited above). The
# codes are the spec's, not ours; a hard-coded table with a citation is the point,
# because a code that drifts is a code a client cannot branch on.
ERROR_CODES = {
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

# The eleven core operations, in the spec's own order (§3.1 and the gRPC table at
# §11.3). Named exactly, because these strings are the `method` a client sends.
OPERATIONS = [
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
]

# §4.5.3 / §4.4: the TaskState enum. The nine values the A2A 1.0 protobuf carries,
# in declaration order. `TASK_STATE_UNSPECIFIED` is the zero value and is present
# on purpose: a suite that omits it cannot tell a card that speaks 1.0 from one
# that speaks the 0.3 shape the spec's own error example quotes (line 1614 lists
# eight, without UNSPECIFIED).
TASK_STATES = [
    "TASK_STATE_UNSPECIFIED",
    "TASK_STATE_SUBMITTED",
    "TASK_STATE_WORKING",
    "TASK_STATE_COMPLETED",
    "TASK_STATE_FAILED",
    "TASK_STATE_CANCELED",
    "TASK_STATE_INPUT_REQUIRED",
    "TASK_STATE_REJECTED",
    "TASK_STATE_AUTH_REQUIRED",
]

# §4.4 Message roles. Three values including the zero one, same reasoning.
ROLES = ["ROLE_UNSPECIFIED", "ROLE_USER", "ROLE_AGENT"]

# `class: barrier` in our ledger means "a refusal whose reason is the barrier" —
# that is what the field is documented as in design/05 §1 ("whether it was a
# phase refusal or a malformed request") and what README §3 tells the leader it
# can ask. `bin/aim` sets it at the sites that enforce the barrier and defaults
# to `form` everywhere else; this module never infers it.
#
# The mapping table below is keyed on `(ledger class, action, substring)`: the
# class because A2A has no word for a malformed request and dressing one in an
# A2A code would be a claim we did not make, the action because two verbs can
# refuse for different reasons with the same words, and a substring last because
# a table of full sentences is a table that breaks on every rewording.
#
# Read the *spec's own* error lists, not our reading of them — each row cites
# the operation whose list decides it, and that is what makes the table
# checkable rather than plausible:
#
#   * §3.1.3 / §3.1.4 list exactly one error for a task that exists but is not
#     readable by the caller: `TaskNotFoundError`, described as "The task ID does
#     not exist **or is not accessible**". §3.3.2's Resource Errors class then
#     settles the direction: "MUST return a not found error when a requested
#     resource does not exist **or is not accessible**", and "SHOULD NOT
#     distinguish between 'does not exist' and 'not authorized' to prevent
#     information leakage". So the refusal to read a peer's draft is not merely
#     *allowed* to be a 404 — it is required to be one.
#   * §3.1.1 lists what `SendMessage` may refuse with, and a message the server
#     will not accept is `UnsupportedOperationError`; a refusal to publish a
#     work item is the same shape (a well-formed request the server declines).
#   * §3.1.5 lists `TaskNotCancelableError` — "The task is not in a cancelable
#     state (e.g., it has already reached a terminal state)" — for `CancelTask`.
#     A task whose blockers are unresolved cannot be moved to a terminal state,
#     so that is the row we can answer with a code the spec defines.
#
# `VersionNotSupportedError` is absent because there is no `A2A-Version` surface
# here to reject (T-0108 records that as a missing row, not a mapping). And
# `TaskNotFoundError` is deliberately absent from any *rights* direction: our
# barrier refusals are answered by "not accessible", which is the same code, so
# distinguishing them would be a distinction only a caller who already lost the
# information could make. D17 is where the per-surface scoping is decided
# (T-0104); until then this returns the spec's answer, not a friendlier one.
_BARRIER_ERRORS = [
    # (ledger class, action, substring of the refusal, A2A error type)
    ("barrier", "say", "only the appointed synthesizer", "UnsupportedOperationError"),
    ("barrier", "say", "synthesis may only be published", "UnsupportedOperationError"),
    ("barrier", "advance", "may not advance the barrier", "UnsupportedOperationError"),
    ("barrier", "advance", "cannot enter SYNTHESIS before every", "UnsupportedOperationError"),
    ("barrier", "advance", "SYNTHESIS needs a synthesizer", "UnsupportedOperationError"),
    ("barrier", "advance", "is a participant in this channel", "UnsupportedOperationError"),
    ("barrier", "seal", "sealing is closed", "UnsupportedOperationError"),
    ("barrier", "reveal", "reveal is only open", "UnsupportedOperationError"),
    ("barrier", "synthesis-input", "may read mixed inputs", "UnsupportedOperationError"),
    ("barrier", "synthesis-input", "synthesis input is only available", "UnsupportedOperationError"),
    ("barrier", "tension", "tension report is visible", "UnsupportedOperationError"),
    ("barrier", "tension", "has not sealed. There is nothing", "UnsupportedOperationError"),
    ("barrier", "inbox", "cross-reading is closed", "TaskNotFoundError"),
    ("barrier", "task list", "drafts owned by someone else", "TaskNotFoundError"),
    ("barrier", "*", "draft owned by someone else", "TaskNotFoundError"),
    ("barrier", "task new", "cannot publish a work item", "UnsupportedOperationError"),
    ("barrier", "*", "are not done", "TaskNotCancelableError"),
]

# A2A's JSON-RPC binding puts `error.data` as an array of objects each carrying a
# `@type` (§9.5). The `ErrorInfo` shape is the spec's own example, so a client
# written against their sample can read ours.
_ERROR_INFO_TYPE = "type.googleapis.com/google.rpc.ErrorInfo"
_ERROR_DOMAIN = "a2a-protocol.org"


# §5.4's "Custom Binding Requirements": "Custom protocol bindings MUST define
# equivalent error code mappings that preserve the semantic meaning of each A2A
# error type. The binding specification SHOULD provide a similar mapping table
# showing how each A2A error type is represented in the custom binding's native
# error format." `_BARRIER_ERRORS` above *is* that table for us, and this is the
# column that makes it a table: our native error format is a `REFUSED:` line in
# a ledger record, and that is what a caller of this binding sees.
NATIVE_ERROR_FORM = "REFUSED: <sentence> in a ledger refusal record"

# The other half of a mapping table is the entries that say "none", and they have
# to be *stated*, not inferred from an absence. A refusal class left out of the
# table and a class deliberately declared unmapped look identical to
# `mapped_error()` — both return None — and those are not the same claim. So the
# classes this binding answers only in its native shape are listed here by name,
# with the reason, and T-0103's test asserts a refusal that maps to nothing is
# listed rather than merely missing.
#
# `form` is the whole list, and the reason is the spec's, not ours: §3.3.2's
# Resource/Authorization/Validation classes are the *categories* a binding maps
# onto its own codes, and JSON-RPC's word for a malformed request is `-32602
# InvalidParamsError` — which is not an A2A error type and is not in the
# -32001..-32009 range. Dressing "moving to 'blocked' requires --reason" in one
# of the nine would be claiming an A2A semantics the request never had. §5.4 also
# says the mapping MUST *preserve the semantic meaning* of each type; inventing
# meaning is how a binding stops preserving anything.
NATIVE_ONLY = {
    "form": "A2A defines no error type for a malformed request; the JSON-RPC "
            "binding's own -32602 InvalidParamsError is the transport's word, "
            "not one of the nine, so this binding answers in its native shape.",
}


# §11.6 (and §9.5's example, and §10.6's) all state that the `reason` of a
# `google.rpc.ErrorInfo` for an A2A-specific error is "The A2A error type in
# UPPER_SNAKE_CASE **without the 'Error' suffix**". The unqualified sentence in
# §3.3.2's list is the same rule. So `TaskNotFoundError` is `TASK_NOT_FOUND` on
# the wire, not `TaskNotFoundError` — and a client that reads `reason` as the
# proto enum name is reading a field the spec says is spelled differently. Both
# spellings are recoverable from each other, which is why this is a function
# rather than a second table that can drift from `ERROR_CODES`.
def error_reason(error_type):
    """`TaskNotFoundError` -> `TASK_NOT_FOUND`, per §11.6 / §9.5 / §10.6."""
    stem = error_type[:-len("Error")] if error_type.endswith("Error") else error_type
    out, prev_lower = [], False
    for ch in stem:
        if ch.isupper() and prev_lower:
            out.append("_")
        out.append(ch.upper())
        prev_lower = ch.islower() or ch.isdigit()
    return "".join(out)


# §3.3.2 requires an error payload to convey "a human-readable description of the
# error", and §9.5's own example pairs `"code": -32001` with `"message": "Task not
# found"` — not with the type name. So the machine-readable identifier is the code
# and the `reason` in `data`; `message` is prose. A client that matches on
# `message` is matching on text the spec does not freeze, which is why the reason
# is in the structured half as well.
MESSAGES = {
    "TaskNotFoundError": "Task not found",
    "TaskNotCancelableError": "Task not cancelable",
    "PushNotificationNotSupportedError": "Push notifications not supported",
    "UnsupportedOperationError": "Unsupported operation",
    "ContentTypeNotSupportedError": "Content type not supported",
    "InvalidAgentResponseError": "Invalid agent response",
    "ExtendedAgentCardNotConfiguredError": "Extended agent card not configured",
    "ExtensionSupportRequiredError": "Extension support required",
    "VersionNotSupportedError": "Protocol version not supported",
}


def mapped_error(refusal_text, action="", refusal_class=""):
    """Which A2A error a refusal maps onto, or None if A2A has no word for it.

    Three inputs because one is not enough, and each is a different kind of
    fact: `refusal_class` is the ledger's own marker and decides whether a
    refusal is even a statement about the barrier; `action` is the verb, because
    two verbs can refuse with the same words for different reasons; the text is
    consulted last.

    A refusal outside `barrier` returns None *before* any text is consulted. That
    is the point rather than a shortcut: A2A models nine errors and a malformed
    request is not among them (-32001..-32009 are protocol errors, and -32602 is
    the *transport's* word, not A2A's). Mapping a workflow rule onto an A2A code
    would put a claim in our mouths that neither the ledger nor the spec makes.
    """
    for need_class, need_action, needle, name in _BARRIER_ERRORS:
        if refusal_class != need_class:
            continue
        if need_action != "*" and need_action != action:
            continue
        if needle in refusal_text:
            return name
    return None


def native_error(refusal_text, *, cls="form", action="", metadata=None):
    """Our own error shape, for a client that speaks this binding rather than A2A.

    §5.4 requires a custom binding to *preserve the semantic meaning* of each A2A
    error type and to say how it represents them natively. Our native error is
    not a code — it is a `REFUSED:` sentence in a hash-chained ledger record, and
    that record is the thing T-0103 says must survive whatever we say on an A2A
    surface. Emitting it as the first element of `data` is what makes the
    conformance test able to assert *both halves* from one response instead of
    one half from the response and the other from a file the response never
    mentions.
    """
    body = {
        "@type": f"{_EXT_NS}/refusal/v1",
        "refusal": refusal_text,
        "class": cls,
        "action": action or None,
        "recorded": "channels/<channel>/ledger.jsonl, event=refusal",
    }
    if metadata:
        body["metadata"] = normalize_keys(metadata)
    return normalize_keys(body)


def error_response(error_type, request_id, detail=None, *, action="",
                   reason="", metadata=None, native=None):
    """A JSON-RPC 2.0 error object for an A2A error type.

    `data` is a list because §9.5 says it is ("array of objects, each containing
    a `@type` key"), and §9.5 adds that "additional error context MAY be included
    as further objects in the `data` array" — which is the door our own refusal
    record walks through, in second position so the spec's `ErrorInfo` stays
    first and a client that reads `data[0]` gets the thing the spec promises.

    `detail` is appended to `message` rather than replacing it: §3.3.2 requires a
    human-readable description, and our refusal sentences *are* the human-readable
    description — the standard message alone would tell a caller "Task not found"
    for a task that plainly exists and that we refused to hand over.
    """
    code = ERROR_CODES.get(error_type)
    if code is None:
        raise ValueError(f"{error_type!r} is not one of the nine A2A error types")
    data = [{
        "@type": _ERROR_INFO_TYPE,
        "reason": error_reason(error_type),
        "domain": _ERROR_DOMAIN,
    }]
    info_metadata = dict(metadata or {})
    if reason:
        info_metadata.setdefault("aimReason", reason)
    if info_metadata:
        data[0]["metadata"] = normalize_keys(info_metadata)
    if native:
        data.append(native)
    body = {"jsonrpc": "2.0", "id": request_id,
            "error": {"code": code, "message": MESSAGES[error_type], "data": data}}
    if detail:
        body["error"]["message"] = f"{MESSAGES[error_type]}: {detail}"
    return body


def normalize_keys(obj):
    """snake_case -> camelCase for every key, recursively.

    §5.2 and line 1208: the JSON form is camelCase where the protobuf field is
    snake_case (`protocol_version` -> `protocolVersion`). `bin/aim` writes
    snake_case throughout, so this is the one place the two spellings meet — a
    function rather than a habit, so a field added later cannot be forgotten at
    one call site and remembered at another.
    """
    if isinstance(obj, dict):
        out = {}
        for key, value in obj.items():
            parts = str(key).split("_")
            camel = parts[0] + "".join(p[:1].upper() + p[1:] for p in parts[1:])
            out[camel] = normalize_keys(value)
        return out
    if isinstance(obj, list):
        return [normalize_keys(x) for x in obj]
    return obj


_ISO_UTC = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$")


def is_iso8601_utc(value):
    """The spec's timestamp form, exactly: `YYYY-MM-DDTHH:mm:ss.sssZ`.

    Millisecond precision and a literal `Z`. A `+08:00` offset is a valid
    ISO-8601 instant and a *different* wire format, so this returns False for it
    rather than accepting both: a client that parses one may not parse the other.
    """
    return isinstance(value, str) and _ISO_UTC.match(value) is not None



# --------------------------------------------------------------------------
# Tasks: the read surface, and the authorization model behind it (T-0104)
# --------------------------------------------------------------------------
# GetTask and ListTasks are the two A2A operations this fabric can answer today,
# because both are reads of state the fabric already holds and neither needs a
# socket: a `Task` is the fold, and the gate is an access rule. What follows is
# therefore a *translation*, and its caller today is the conformance suite.
#
# The gap it closes is D17, and the access rule it has to satisfy now exists in
# three places — this module, `bin/aim`, and `aimboard/gate.py`. That is one more
# than the project's own rule allows, so the measurements below are written down
# rather than summarised: the disagreement is real, it is confined to one shape of
# record, and it is reported rather than patched from here.
#
#   [measured on one fabric: alpha creates a draft, `task assign` hands it to
#    beta, alpha then runs `aim advance --as alpha`]
#     bin/aim `task list`,  phase=SEALED_DIVERGENT   alpha sees it, beta does NOT
#     bin/aim `task list`,  phase=OPEN    (unsealed) both see it
#     gate.visible_tasks,   phase=SEALED_DIVERGENT   alpha hidden,  beta sees it
#
# The two rules are *inverses* of each other, not one buggy copy of the other:
#
#   bin/aim `_visible_to`      owner == who  or  created_by == who
#   gate.visible_tasks         owner == viewer (and hides a draft from anyone
#                              else who is walled off)
#
# So exactly one record in the fabric can make them disagree — a draft whose
# `owner` and `created_by` differ — and for that record `bin/aim` serves it to
# whoever wrote it while the board serves it to whoever holds it. Both are
# defensible readings of "their own work", and the fabric's own vocabulary is the
# union: `task assign` exists to hand work to a peer, so the creator has not given
# up the record, and the owner may be a different agent entirely from the one who
# will do it.
#
# Two consequences follow, and both are reported rather than fixed from this side:
#
#   * `gate.visible_tasks` should be the union too, so one question has one
#     answer. `gate.py` is codex's file (design/05 §8).
#   * `aimboard/fold.py` copies only `PLAN_FIELDS` off the `created` event, and
#     `created_by` is not among them, so **the renderer's task dict has no
#     `created_by` key at all**. [measured: `'created_by' in state['tasks']['T-0001']`
#     is False, while the same task's `created` event carries `actor: alpha`].
#     Today nothing is broken by that — `gate.visible_tasks` compares `owner` and
#     never asks for the key, and no view renders a task's author (`grep` over
#     `aimboard/views/` finds no reader). It becomes load-bearing the moment the
#     board's gate is united with `bin/aim`'s, because the union's second arm has
#     nothing to fire on: `alpha`'s own draft, handed to `beta`, is served by
#     `aim task list` and would stay hidden on the board whatever `gate.py` says.
#
# `bin/aim` keeps its own copy of the rule because it must not import this
# package, and a test asserts the two agree — see TASK_VISIBILITY_RULE below.
#
# The unified rule is the union: `task_visible`, which is where the decision now
# lives and the only place either surface should ask. T-0104's accept line only
# requires the *withheld* half to be exercised, and that half holds under either
# rule, so nothing here depends on either correction landing first.

# §4.4's TaskState, mapped from this fabric's status vocabulary by *semantics*,
# not by name — the failure design/07 §3 was written to prevent. Every entry
# carries the reason it is the right state, because a mapping table that cannot be
# argued with is a mapping table nobody can check.
#
# The four that are not obvious:
#
#   backlog -> SUBMITTED   created, accepted, not started. A2A's zero value is
#                          deliberately not used: a state a client cannot
#                          distinguish from "we forgot to set it" is not an answer.
#   review  -> INPUT_REQUIRED  a reviewer's decision is the input being waited on.
#   blocked -> INPUT_REQUIRED  what is waited on is a peer's work. A2A has no word
#                          for a dependency and inventing one is what the
#                          planning/v1 extension is for.
#   dropped -> CANCELED    withdrawn, not failed. FAILED is for a task that ran
#                          and did not succeed, which is a different fact about it.
STATUS_TO_STATE = {
    "backlog": "TASK_STATE_SUBMITTED",
    "ready": "TASK_STATE_SUBMITTED",
    "doing": "TASK_STATE_WORKING",
    "review": "TASK_STATE_INPUT_REQUIRED",
    "blocked": "TASK_STATE_INPUT_REQUIRED",
    "done": "TASK_STATE_COMPLETED",
    "dropped": "TASK_STATE_CANCELED",
}

# The other direction exists so that the *absence* of a mapping is a decision
# rather than an oversight. A2A has no word for this fabric's `blocked` or
# `review`; it has `AUTH_REQUIRED`, `REJECTED` and `FAILED`, which this fabric has
# never had a reason to express. T-0107 is codex's table; this is the constant it
# can read rather than re-deriving.
STATES_WE_CANNOT_EXPRESS = ["TASK_STATE_UNSPECIFIED", "TASK_STATE_FAILED",
                            "TASK_STATE_REJECTED", "TASK_STATE_AUTH_REQUIRED"]

# §3.3.2's "Message": "At least one part is required" (§9.5's own BadRequest
# example names `message.parts`). A task's title is its human-readable content and
# therefore its first part; `accept` is the falsification condition, which is the
# only thing in a work item that behaves like an artifact — the work product you
# can check the task against.
def _task_messages(task, history_length: int) -> list:
    """`history[]`, most recent last, truncated to the last `history_length`.

    §3.2.4: 0 means the field is omitted entirely; > 0 means at most that many
    recent messages. So the caller filters, and this returns the *content* — a
    client that asks for zero history must not receive an empty array, which is a
    different statement from "there is no history".
    """
    events = list(task.get("history") or [])
    if history_length:
        events = events[-history_length:]
    out = []
    for event in events:
        text = _event_text(event)
        if not text:
            continue
        out.append({
            "messageId": f"{task['id']}:{event.get('event', '?')}:{event.get('ts', '')}",
            "contextId": task.get("context_id") or None,
            "taskId": task["id"],
            # §4.4: the agent's utterances are ROLE_AGENT. Every event in this
            # store is written by an agent acting on the task, never by a user
            # handing work in.
            "role": "ROLE_AGENT",
            "parts": [{"text": text, "mediaType": "text/plain"}],
            "metadata": {"aim": {"event": event.get("event", ""), "actor": event.get("actor", "")}},
        })
    return [m for m in out if m.get("parts")]


def _event_text(event) -> str:
    """One sentence for one task event, or "" for an event with nothing to say.

    Returns "" rather than a placeholder: a client that receives a Message with
    an empty part has been told something false, and §3.3.2 says at least one part
    is required. An event we cannot describe is better omitted than faked.
    """
    kind, actor = event.get("event", ""), event.get("actor", "")
    if kind == "created":
        return f"created by {actor}: {event.get('title', '')}".strip()
    if kind == "moved":
        reason = f" — {event['reason']}" if event.get("reason") else ""
        return f"{actor} moved it {event.get('from', '?')} -> {event.get('to', '?')}{reason}"
    if kind == "assigned":
        return f"{actor} assigned it to {event.get('owner', '?')}"
    if kind == "published":
        return f"{actor} published it to the channel"
    if kind == "linked":
        return f"{actor} made it blocked by {event.get('blocked_by', '?')}"
    if kind == "dropped":
        return f"{actor} dropped it — {event.get('reason', '')}".strip()
    if kind == "commented":
        return f"{actor} commented: {event.get('body', '')}".strip()
    return ""


# The phases in which a participant may only see their own drafts. The same tuple
# `bin/aim` keeps, and it is duplicated here because this module must not import
# the CLI: `bin/aim` is not importable as a module by design (design/08 §3 gives
# it the write discipline, and a second importer is a second entry point into it).
# A test asserts the two agree, which is the only form of duplication that can be
# caught when one side moves.
DIVERGENCE_PHASES = ("SEALED_DIVERGENT", "COMMIT", "SYNTHESIS")


def task_visible(task, viewer, channel, registry) -> bool:
    """May `viewer` read this task? The unified rule, decided once.

    Three things make a task readable, and they are the same three `bin/aim`
    applies — the difference is that until now only `bin/aim` applied the third:

      * it is published, not a draft;
      * the channel's phase is past the barrier, or the viewer is not walled off;
      * the viewer **owns** it or **created** it.

    The leader bypasses the gate entirely, which is the fabric's oldest rule: the
    leader is the audience, not a participant, and the whole point of sealing is
    that the leader can read both sides.

    The two middle tests are the ones `bin/aim` gets from *its own* wall: `aim
    task list` refuses outright for a registered non-participant (the refusal
    `gate.py`'s docstring calls T-0041), and it never reaches the third test with
    a phase that is open, because the fold it reads is the channel it was asked
    about. Both are spelled out here because this function is also asked about
    tasks from *other* channels than the viewer's, via `hidden_count`, and a rule
    that is only correct for the caller's own channel is a rule that leaks.

    `channel` is the manifest as `fabric.load_fabric` builds it: `{"phase": ...,
    "participants": [...], "leader": ...}`. Passing state rather than a root is
    deliberate — this module must not open files, or the two surfaces stop
    agreeing about *when* the state was read.
    """
    if (registry.get(viewer) or {}).get("kind") == "human":
        return True
    if (task.get("visibility") or "draft") == "published":
        return True
    if channel.get("phase") not in DIVERGENCE_PHASES:
        return True                # the barrier is open; drafts are readable
    if viewer not in channel.get("participants", []):
        return True                # a stranger is not a participant; T-0041's case
    return viewer in (task.get("owner"), task.get("created_by"))


def hidden_count(tasks, viewer, channels, registry) -> int:
    """How many work items the viewer cannot see. A count, never a title.

    This is the number T-0104 is about: the board publishes it and the A2A surface
    must not. Returning it as a value rather than as a phrase is what lets the
    conformance suite assert the two halves against each other instead of against
    a sentence one of them happens to print.

    This module defines it and does not call it, which is the point rather than an
    oversight: the A2A surface must never be able to reach a number that describes
    what it is withholding. A caller that wants the count is the board, and the
    board asks `gate.visible_tasks`. It is here, exported and tested, so the two
    halves of D17 can be asserted against the *same* rule instead of against two
    rules that happen to agree today.
    """
    by_id = {c["id"]: c for c in channels}
    return sum(1 for t in tasks.values()
               if not task_visible(t, viewer, by_id.get(t.get("context_id")
                                                        or t.get("channel") or "", {}),
                                   registry))


# The rule above, written a second time in Python source so a test can read it
# without importing the package — see the note on `bin/aim`'s copy below. tests/
# `test_access_rule_agreement` parses both this table and `bin/aim`'s function,
# which is a crude check that would nonetheless have caught the disagreement this
# block is about, because that disagreement was two different *expressions*, not
# two different intentions.
TASK_VISIBILITY_RULE = {
    "leader_bypass": "registry[viewer].kind == 'human'",
    "published": "task.visibility == 'published'",
    "barrier_open": "channel.phase not in DIVERGENCE_PHASES",
    "stranger": "viewer not in channel.participants",
    "claim": "viewer in (task.owner, task.created_by)",
}


def a2a_task(task, *, history_length: int = 0, include_artifacts: bool = False) -> dict:
    """One work item as an A2A `Task` (§4.1.1).

    Fields A2A requires are all present: `id`, `contextId`, `status{state}`. The
    four A2A *does not* model — estimate, due date, dependency edge, acceptance
    condition — go in `metadata.aim.planning`, which is exactly what D16 registers
    an extension for. A reader who does not know the extension sees a Task that is
    correct as far as it goes; a reader who does sees the planning card.

    Enum-valued fields are already SCREAMING_SNAKE, and `normalize_keys` must not
    touch *values* — it does not, because it only rewrites keys, and §5.2's
    camelCase rule is a rule about field names.
    """
    out = {
        "id": task["id"],
        "contextId": task.get("context_id") or None,
        "status": {
            "state": STATUS_TO_STATE.get(task.get("status") or "backlog",
                                         "TASK_STATE_UNSPECIFIED"),
            "timestamp": task.get("updated_at") or task.get("created_at") or "",
        },
    }
    if include_artifacts:
        # §3.1.4: when `includeArtifacts` is false the field MUST be omitted
        # entirely — not an empty array, not null. When it is true, the
        # acceptance condition is the artifact, because it is the one field in a
        # work item that says what would make the work *finished* rather than
        # merely claimed.
        out["artifacts"] = ([{
            "artifactId": f"{task['id']}-accept",
            "name": "acceptance condition",
            "description": task.get("accept", ""),
            "parts": [{"text": task.get("accept", ""), "mediaType": "text/plain"}],
        }] if task.get("accept") else [])
    if history_length:
        out["history"] = _task_messages(task, history_length)
    out["metadata"] = {"aim": {
        "kind": "planning", "extension": f"{_EXT_NS}/planning/v1",
        "priority": task.get("priority", "normal"),
        "milestone": task.get("milestone", ""),
        "blocked_by": list(task.get("blocked_by") or []),
        "estimate": task.get("estimate_pts", 0),
        "start": task.get("start", ""),
        "due": task.get("due", ""),
        "accept": task.get("accept", ""),
        "tags": list(task.get("tags") or []),
        "visibility": task.get("visibility", "draft"),
        "owner": task.get("owner", ""),
    }}
    return out


def get_task(task_id, request_id, *, tasks, viewer, channels, registry,
             history_length: int = 0, include_artifacts: bool = False):
    """§3.1.3. `TaskNotFoundError` for a task that does not exist **or is not
    accessible to the caller** — one answer for both, because the two must be
    indistinguishable to the caller.

    This is D17 and it is why the refusal is not merely allowed to be a 404 but
    required to be one. §3.3.2's Resource Errors: "Servers **MUST** return a not
    found error when a requested resource does not exist **or is not
    accessible**", and "**SHOULD NOT** distinguish between 'does not exist' and
    'not authorized' to prevent information leakage". §3.1.3's error list has one
    entry, `TaskNotFoundError`.

    §13.1 adds the staging rule, and it is the one that is easy to get wrong:
    "Authorization checks **MUST** occur before any database queries or operations
    that could leak information about the existence of resources outside the
    caller's authorization scope". So the gate is applied *before* the id is
    looked up, and the two paths below are ordered that way on purpose. Reversing
    them is a change to what this function answers, not an optimisation.

    The response contains no count, no "withheld" field and no hint that anything
    else exists. What the board does with the same verdict is T-0104's other half
    and is deliberately *not* this function's business: a count is a fact about
    the channel, and a channel is something a participant is entitled to know
    about. A foreign A2A caller is not, and §13.1 says so in its own words.
    """
    by_id = {c["id"]: c for c in channels}
    channel = by_id.get(task_channel(task_id, tasks, by_id) or "", {})
    visible = [t for t in tasks.values()
               if task_visible(t, viewer, channel, registry)]
    found = next((t for t in visible if t["id"] == task_id), None)
    if found is None:
        return error_response("TaskNotFoundError", request_id,
                              action="GetTask", reason="not found or not accessible")
    return {"jsonrpc": "2.0", "id": request_id,
            "result": a2a_task(found, history_length=history_length,
                               include_artifacts=include_artifacts)}


def task_channel(task_id, tasks, by_id) -> str:
    """Which channel a task id belongs to, or "" if the caller may not know.

    Only ever used to pick the channel whose phase governs the verdict, so a task
    the caller cannot see still gets judged by the phase of the channel it is in —
    otherwise a draft in a divergence phase would be answered by the fallback
    channel's phase, and a draft would become visible by asking from the wrong
    side of the board.
    """
    task = tasks.get(task_id) or {}
    return task.get("context_id") or task.get("channel") or ""


def list_tasks(request_id, *, tasks, viewer, channels, registry,
               context_id: str = "", page_size: int = 50, page_token: str = "",
               history_length: int = 0, include_artifacts: bool = False):
    """§3.1.4. Only visible tasks; sorted by last update, descending; cursor
    pagination; `nextPageToken` always present and "" on the last page.

    Every one of those is a MUST or a MUST-NOT in the spec, and three of them are
    the kind a translation quietly skips:

      * "MUST use cursor-based pagination" and "`nextPageToken` MUST always be
        present ... MUST be set to an empty string" — so a single-page result
        still carries the field, and "" is a statement rather than an omission.
      * "Tasks MUST be sorted by their status timestamp time in descending
        order". A stable sort over a stable key: two tasks updated in the same
        millisecond must not swap between two pages, or a client paginating
        repeats one and misses the other.
      * "MUST return only tasks visible to the authenticated client" — the same
        gate, applied per task, and the count of what was withheld is *not* in
        the response.
    """
    by_id = {c["id"]: c for c in channels}
    rows = []
    for task in tasks.values():
        channel = by_id.get(task.get("context_id") or task.get("channel") or "", {})
        if context_id and (task.get("context_id") or task.get("channel")) != context_id:
            continue
        if not task_visible(task, viewer, channel, registry):
            continue
        rows.append(task)

    def sort_key(task):
        return (task.get("updated_at") or task.get("created_at") or "", task["id"])

    rows.sort(key=sort_key, reverse=True)
    start = 0
    if page_token:
        ids = [t["id"] for t in rows]
        start = ids.index(page_token) if page_token in ids else len(rows)
    size = max(0, int(page_size or 0))
    page = rows[start:start + size] if size else []
    next_token = page[-1]["id"] if page and start + size < len(rows) else ""
    return {"jsonrpc": "2.0", "id": request_id, "result": {
        "tasks": [a2a_task(t, history_length=history_length,
                           include_artifacts=include_artifacts) for t in page],
        "nextPageToken": next_token,
    }}


# --------------------------------------------------------------------------
# Push notification configs: the doorbell, as an object (T-0106)
# --------------------------------------------------------------------------
# `bin/aim-doorbell-hook` is the doorbell and is not this. The hook is *harness
# glue* — it prints your unread outbox on your next turn — and its own header
# says the thing that makes it correct: "`aim` must not know how any harness
# wakes a session". Moving it into `aim` would be the queue-based doorbell the
# design already rejected, and deleting it would cost nothing. So the hook stays
# the default and stays where it is; what follows is the *object* beside it.
#
# So this is not a rewrite and it is not the delivery mechanism. It is the
# standard shape `bin/aim-doorbell-hook`'s ad-hoc configuration was missing, and
# the shape is worth having on its own merits, because it is the only place in
# this fabric where a *secret* is written down (§13.2: "Authentication tokens in
# TaskPushNotificationConfig SHOULD be treated as secrets and rotated
# periodically"). That single fact decides most of the design below.
#
# §3.1.7's own state freeze. Read off the spec's text, not assumed, because
# `pushNotifications` is the schema:
PUSH_FIELDS = ["taskId", "url", "token", "authenticationInfo", "configId", "id"]

# What we do with a field the spec defines and we do not. Refused rather than
# ignored, and the reason is the serialization the spec mandates rather than
# caution: §5.5 adopts ProtoJSON, and ProtoJSON's default decision on an unknown
# field is to **reject** it — a client sending `{"url_": ...}` has made a typing
# mistake, and a server that ignores it has accepted a webhook config with no
# URL in it and reported success.
UNSUPPORTED_FIELDS = {
    "id": ("the field is sparsely documented in the revision this binding was "
           "built against (§4.3.1 and §10.5.1 both state the object as a "
           "generated table) and we will not guess which id it means: `configId` "
           "is the one the four operations address a config by, and accepting a "
           "second spelling of identity is how two ids for one thing start"),
}

# The credential half of `AuthenticationInfo`. §4.3.2's shape is stated as a
# generated table too; §6.6's example is the only place the field names appear in
# the clear (`{"scheme": "Bearer", "credentials": "…"}`, and the payload example
# builds its header as `Authorization: Bearer <credentials>`). That is the source
# cited here rather than a name we chose.
AUTH_INFO_FIELDS = ["scheme", "credentials"]

# A URL we will accept a doorbell at. `file:` and bare paths are deliberately
# excluded and that is not a policy — §4.3.3 says the notification is "an HTTP
# POST request to the configured webhook URL", so a scheme that cannot receive
# one is a config that can never fire. §13.2 adds "Webhook URLs SHOULD use HTTPS
# to protect payload confidentiality in transit": SHOULD, not MUST, so plain
# `http://localhost` is accepted and a *remote* `http://` is refused, because the
# only thing travelling in it is a token AND task content.
_LOCAL_HOSTS = ("localhost", "127.0.0.1", "::1", "[::1]")


def push_config_id(task_id, config) -> str:
    """A stable, server-assigned id for one config (§3.1.7's "assigned ID").

    Derived from the task and the URL rather than from a counter or a clock, so
    that re-creating the identical configuration against a task returns the id
    the caller already has instead of accumulating a second copy of one webhook
    — an idempotent create, which is what a retrying client needs and what a
    counter cannot give. `token` and `credentials` are deliberately **not** in
    the digest: rotating a secret should not orphan the config that carries it.
    """
    material = json.dumps({"task": task_id, "url": config.get("url", "")},
                          sort_keys=True, ensure_ascii=False)
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]
    return f"cfg-{digest}"


def normalise_auth(auth) -> dict:
    """§4.3.2, camelCase already at the wire so `normalize_keys` has nothing to do."""
    if auth in (None, ""):
        return {}
    if not isinstance(auth, dict):
        return {"_malformed": auth}
    return {str(k): v for k, v in auth.items()}


def validate_push_config(config):
    """Every rule a config must satisfy, as `(field, why)` pairs.

    Returned rather than raised because the caller decides which surface it is
    answering on: a problem here becomes `fieldViolations` in a `-32602` when the
    caller is a JSON-RPC client, and a one-line sentence when the caller is
    `aim`'s own CLI. A validator that exited or raised would make that choice for
    its caller, in the wrong place, and would make the CLI's answer a traceback.

    The field list is checked *first* and the whole check is skipped if it
    matched, which is load-bearing rather than tidy: a caller who sent
    `{"url": …, "toke": "x"}` must be told about the typo, not about the missing
    token the typo caused.
    """
    problems = []
    for field in sorted(config):
        if field in UNSUPPORTED_FIELDS:
            problems.append((field, UNSUPPORTED_FIELDS[field]))
        elif field not in PUSH_FIELDS:
            problems.append((field, f"not a field of TaskPushNotificationConfig; "
                                    f"the object is {', '.join(PUSH_FIELDS)}"))
    if problems:
        return problems

    auth = config.get("authenticationInfo")
    if auth not in (None, "") and not isinstance(auth, dict):
        return [("authenticationInfo",
                 f"must be an object with {' and '.join(AUTH_INFO_FIELDS)}, got "
                 f"{type(auth).__name__}")]

    url = config.get("url") or ""
    token = config.get("token") or ""
    info = normalise_auth(auth)
    credentials = info.get("credentials") or ""
    if not url:
        problems.append(("url", "a push notification config needs a URL: a doorbell "
                                "with nowhere to ring is a config that can never fire"))
    elif not (url.startswith("https://") or url.startswith("http://")):
        problems.append(("url", f"'{url[:60]}' is not an http(s) URL; §4.3.3 delivers "
                                f"a notification as an HTTP POST, so no other scheme "
                                f"can receive one"))
    elif url.startswith("http://") and len(url.split("/")) > 2 and not any(
            host in url.split("/")[2] for host in _LOCAL_HOSTS):
        problems.append(("url", f"'{url[:60]}' is http:// and not local; §13.2 says "
                                f"webhook URLs SHOULD use HTTPS, and what travels in "
                                f"one is a token *and* the task content. Use https://, "
                                f"or localhost."))
    if not token:
        # The accept line's own rule: "a config with no token is refused". §4.3.3
        # is the reason and it is a reason about identity rather than hygiene —
        # the agent presents the credentials on every notification, so a config
        # without any is a webhook any process on the host can ring, and the
        # receiving end has nothing to tell our agent from that process.
        problems.append(("token", "a push notification config needs a token: §4.3.3 "
                                  "has the agent present it as `Authorization: "
                                  "<scheme> <credentials>`, so without one the "
                                  "config names a webhook that will accept a ring "
                                  "from anything"))
    elif credentials and credentials != token:
        problems.append(("authenticationInfo.credentials",
                         "disagrees with `token`; §4.3.3 sends the *credentials* as "
                         "the header value, so a config carrying two different "
                         "secrets has one it will never present and a reader who "
                         "checked the other would see it as valid"))
    return problems


def push_config(task_id, config, *, config_id="", reveal_token=False) -> dict:
    """One config as the wire object, on a read or on a create.

    `reveal_token=False` is the default and is the whole point. §13.2 calls the
    token a secret to be rotated; a `GetTaskPushNotificationConfig` that returns
    it hands the secret to whoever can call the operation, and §3.1.8's own text
    is why that is not a theoretical worry — "The operation MUST fail if the
    configuration does not exist **or the client lacks access**", which is a
    sentence about a config being some client's and not another's. So the read
    shape masks by default, a create echoes back what the caller just sent (they
    already have it, and a response that hid it would be lying about what was
    stored), and the full value is reachable only through one verb that says so
    in its name.

    The mask is not `"***"`: it keeps the length and four characters of the
    digest, so `--rotate` has something to compare against and a caller can tell
    "the same token as last time" from "a different one" without being handed
    either.
    """
    auth = normalise_auth(config.get("authenticationInfo"))
    token = config.get("token") or ""
    out = {
        "taskId": task_id,
        "configId": config_id or push_config_id(task_id, config),
        "url": config.get("url", ""),
    }
    shown = token if reveal_token else mask_secret(token)
    if shown:
        out["token"] = shown
    if auth or token:
        out["authenticationInfo"] = {
            "scheme": auth.get("scheme") or "Bearer",
            "credentials": (auth.get("credentials") or token) if reveal_token
            else mask_secret(auth.get("credentials") or token),
        }
    if config.get("_created_at"):
        # Not a spec field, and it is in `metadata` rather than beside `url` for
        # that reason: §3.1.7 says the configuration "MUST persist until task
        # completion or explicit deletion", and a reader asking why a config
        # survived needs to know when it was made. A non-spec field at the top
        # level is the wire shape a strict ProtoJSON client rejects.
        out["metadata"] = {"aim": {"createdAt": config["_created_at"],
                                   "rotation": "the token is masked on every read; "
                                               "`aim task doorbell --rotate` is the "
                                               "only verb that returns it in the clear"}}
    return out


def mask_secret(secret) -> str:
    """The shape a masked secret keeps: length, and something to compare against.

    Not a fixed `"***"`. §13.2 asks for rotation, and rotation is a comparison —
    a caller who cannot tell a rotated token from an unchanged one will rotate
    on a schedule instead of on evidence. Printing a digest prefix and the length
    leaks nothing a holder of the token does not already have and makes the
    comparison possible.
    """
    if not secret:
        return ""
    digest = hashlib.sha256(str(secret).encode("utf-8")).hexdigest()[:12]
    return f"<masked:{len(str(secret))}b:sha256:{digest}>"


def push_not_supported(request_id, detail, action="CreateTaskPushNotificationConfig"):
    """`PushNotificationNotSupportedError`, with the one-line way back.

    §3.4's capability rule, applied to us: the operation is answered with this
    when `AgentCard.capabilities.pushNotifications` is false — and our card says
    `true`. So this refusal is only ever emitted on a path where that claim does
    not hold, and the message says which capability would have to be true. A
    capability the card claims and the tool cannot honour is the card lying, and
    T-0102's own note is that the claim carries the obligation to test it.
    """
    return error_response("PushNotificationNotSupportedError", request_id, detail,
                          action=action)


def create_push_config(task_id, request_id, *, config, tasks, viewer, channels,
                       registry, created_at=""):
    """§3.1.7. Gate first, then validate, then persist — in that order.

    The order is the same argument T-0104's `get_task` makes and §13.1 states:
    "Authorization checks MUST occur before any database queries or operations
    that could leak information about the existence of resources outside the
    caller's authorization scope." A config is *about* a task, so answering
    "bad url" for a task the caller cannot see has told them the task is there —
    which is the same leak, moved from the read path to the write one.

    §3.1.7 lists two errors for this operation, `PushNotificationNotSupported`
    and `TaskNotFoundError`, and neither is "the url is malformed". A malformed
    config is §3.3.2's *validation* category, whose JSON-RPC word the spec gives
    in its own table as `-32602 Invalid params`, and §3.3.2 requires the details
    to carry `fieldViolations` — so a caller is told which field, not just that
    something was wrong.
    """
    got = get_task(task_id, request_id, tasks=tasks, viewer=viewer,
                   channels=channels, registry=registry)
    if got.get("error"):
        return got
    problems = validate_push_config(dict(config))
    if problems:
        return {
            "jsonrpc": "2.0", "id": request_id,
            "error": {
                "code": -32602, "message": "Invalid params",
                "data": [{
                    "@type": "type.googleapis.com/google.rpc.BadRequest",
                    "fieldViolations": [{"field": field, "description": why}
                                        for field, why in problems],
                }],
            },
        }
    stored = dict(config)
    stored["_created_at"] = created_at
    cid = push_config_id(task_id, stored)
    return {"jsonrpc": "2.0", "id": request_id,
            "result": push_config(task_id, stored, config_id=cid, reveal_token=True)}


def config_id_of(task_id, config) -> str:
    """The id a stored config is addressed by, whichever generation wrote it.

    One function so the four operations agree by construction rather than by four
    call sites remembering the same fallback. A stored config carries `configId`
    because `bin/aim` wrote it; a config the suite hands in from the wire may not,
    and the id is then derived the same way a create would have derived it.
    """
    return config.get("configId") or push_config_id(task_id, config)


def get_push_config(config_id, request_id, *, configs, task_id="", reveal_token=False):
    """§3.1.8. `TaskNotFoundError` when the config does not exist or is not theirs.

    §3.1.8 states the error as `TaskNotFoundError` for a missing *config*, which
    reads oddly and is the spec's own choice: the four push operations are
    addressed by task, so the thing that was not found is named in the task's
    error type. We follow it rather than inventing a config-shaped error, because
    a client branching on `-32001` is the client the spec is written for.
    """
    for task, config in configs:
        if task == task_id and config_id_of(task, config) == config_id:
            return {"jsonrpc": "2.0", "id": request_id,
                    "result": push_config(task, config, config_id=config_id,
                                          reveal_token=reveal_token)}
    return error_response("TaskNotFoundError", request_id,
                          action="GetTaskPushNotificationConfig",
                          reason="no such push notification configuration")


def list_push_configs(task_id, request_id, *, configs, reveal_token=False):
    """§3.1.9. Every active config for a task, and this is where the mask matters most.

    Listing is the operation that would otherwise hand over every secret a task
    holds in one response, to a caller who may only be asking what is configured —
    which is a different question and does not need the answer to this one.
    """
    rows = [push_config(task, config, config_id=config_id_of(task, config),
                        reveal_token=reveal_token)
            for task, config in configs if task == task_id]
    return {"jsonrpc": "2.0", "id": request_id, "result": {"configs": rows}}


def delete_push_config(config_id, request_id, *, configs, task_id=""):
    """§3.1.10. The "explicit deletion" half of §3.1.7's persistence rule."""
    for task, config in configs:
        if task == task_id and config_id_of(task, config) == config_id:
            return {"jsonrpc": "2.0", "id": request_id,
                    "result": {"deleted": True, "configId": config_id, "taskId": task}}
    return error_response("TaskNotFoundError", request_id,
                          action="DeleteTaskPushNotificationConfig",
                          reason="no such push notification configuration")


# ---------------------------------------------------------------------------
# the JSON-RPC surface (T-0122)
# ---------------------------------------------------------------------------
# This is the one place that turns a wire method into an aim operation. The HTTP
# handler in `aimboard/cli.py` stays a thin translation (parse the request, load
# the fabric, call here, serialise the response) for the same reason every other
# rule in this module is one-owned: a second implementation of "what GetTask
# does" is the second-answer-to-one-question failure this project keeps finding.
#
# Seven operations have real backing. Four do not -- and the honest first
# surface answers those four with UnsupportedOperationError rather than faking
# a result or returning 200 for nothing. A surface that claims the operations it
# cannot perform is the same lie as §3.4's pushNotifications flag on a fabric
# with no doorbell: it reads as a capability and is not one. `-32004` is the
# JSON-RPC code for UnsupportedOperation (design/07), so a client that branches
# on the code stays correct.
#
# The two streaming operations that have no backing are answered with the same
# error but over `text/event-stream`, because that is the content-type honouring
# the operation's own contract: a streaming method that answers `application/json`
# is a method that lied about being streamable, and a client that opened an SSE
# reader would hang forever on a JSON body it never asked for. One event, one
# error, and the stream is closed.
STREAMING = {"SendStreamingMessage", "SubscribeToTask"}
UNSUPPORTED = {
    "SendMessage": "no message send surface without a room binding",
    "SendStreamingMessage": "no streaming transport is bound on this server",
    "CancelTask": "no task-cancel operation is defined for a planning plate",
    "SubscribeToTask": "no task subscription without a streaming transport",
}


def handle_rpc(method, params, *, request_id=1, viewer="",
               tasks=None, channels=None, registry=None, configs=None):
    """Dispatch one JSON-RPC method to the aim operation it names.

    Returns `(response, mime)` so the HTTP layer can pick the content-type:
    `application/json` for the nine, `text/event-stream` for the two streaming
    operations. Everything a caller must not see is decided upstream — the
    viewer is the server's own identity, and the fabric state was already gated
    by the server before it reached here. This function never hands a caller
    something the caller's viewer could not have seen through any other read.
    """
    tasks = tasks or {}
    channels = channels or []
    registry = registry or {}
    configs = configs or []
    CCTV_INVALID = -32602
    rid = params.get("id") or request_id if isinstance(params, dict) else request_id

    def mime():
        return "text/event-stream" if method in STREAMING else "application/json"

    if method == "GetTask":
        return (get_task(params.get("id", ""), rid, tasks=tasks, viewer=viewer,
                         channels=channels, registry=registry,
                         history_length=int(params.get("historyLength") or 0),
                         include_artifacts=bool(params.get("includeArtifacts"))),
                mime())
    if method == "ListTasks":
        return (list_tasks(rid, tasks=tasks, viewer=viewer, channels=channels,
                           registry=registry,
                           context_id=str(params.get("contextId") or ""),
                           page_size=int(params.get("pageSize") or 50),
                           page_token=str(params.get("pageToken") or ""),
                           history_length=int(params.get("historyLength") or 0),
                           include_artifacts=bool(params.get("includeArtifacts"))),
                mime())
    if method == "GetExtendedAgentCard":
        agent = registry.get(viewer) or {}
        if not agent:
            return (error_response("TaskNotFoundError", rid, action="GetExtendedAgentCard",
                                   reason="the caller is not a registered agent"),
                    mime())
        return ({"jsonrpc": "2.0", "id": rid,
                 "result": agent_card(agent, "", description=agent.get("description"))},
                mime())
    if method == "CreateTaskPushNotificationConfig":
        config = dict(params or {})
        for key in ("taskId", "url", "token"):
            if key not in config:
                return ({"jsonrpc": "2.0", "id": rid,
                         "error": {"code": CCTV_INVALID, "message": "Invalid params",
                                   "data": [{"@type": "type.googleapis.com/google.rpc.BadRequest",
                                             "fieldViolations": [{"field": key, "description": "missing"}]}]}},
                        mime())
        return (create_push_config(config["taskId"], rid, config=config,
                                   tasks=tasks, viewer=viewer, channels=channels,
                                   registry=registry),
                mime())
    if method == "GetTaskPushNotificationConfig":
        return (get_push_config(str(params.get("configId") or ""), rid,
                                configs=configs,
                                task_id=str(params.get("taskId") or "")),
                mime())
    if method == "ListTaskPushNotificationConfigs":
        return (list_push_configs(str(params.get("taskId") or ""), rid, configs=configs),
                mime())
    if method == "DeleteTaskPushNotificationConfig":
        return (delete_push_config(str(params.get("configId") or ""), rid,
                                   configs=configs,
                                   task_id=str(params.get("taskId") or "")),
                mime())
    if method in UNSUPPORTED:
        return (error_response("UnsupportedOperationError", rid,
                               action=method, detail=UNSUPPORTED[method]), mime())
    # Anything else is not an A2A operation at all, so it is the JSON-RPC
    # standard's own word (Method not found), not one of the nine A2A types.
    return ({"jsonrpc": "2.0", "id": rid, "error": {"code": -32601,
            "message": "Method not found", "data": [method]}}, mime())
