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
            # The doorbell is a webhook in everything but name: a config carries
            # the URL to call and the token to present (T-0106).
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

