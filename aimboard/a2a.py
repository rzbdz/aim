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


# The protocol version this binding implements. A2A service parameters are
