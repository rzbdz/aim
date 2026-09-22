# Design note 07 - aim against A2A, because "standard" needs a name

Requirement, from the human leader (2026-09-21):

> 你现在上网调查A2A协议，我们接下来的core要重构标准化。

"Standardize the core" is only testable if it names the standard. This note reads
the Agent2Agent protocol, maps our objects onto its objects **by semantics rather
than by name**, and proposes what to adopt, what to keep proprietary, and the one
place where adopting it contradicts a rule we already defend.

## 1. What was read, and where it came from

| source | what it is |
|---|---|
| `a2aproject/A2A@main:docs/specification.md` (156,828 bytes) | the specification |
| `a2aproject/A2A@main:specification/a2a.proto` (812 lines) | the data model, normative |
| `docs/topics/{agent-discovery,life-of-a-task,streaming-and-async}.md` | the three topics we will need first |
| `README.md` | scope, and where it says A2A sits next to MCP |

Two facts about provenance, because they change how the rest should be read:

1. **The document disagrees with itself about its version.** The header says
   "Latest Released Version [`1.0.0`]", while the normative tables and examples
   throughout say `0.3` (`A2A-Version: 0.3`, `"protocolVersion": "0.3"`,
   `supportedVersions: ["0.3"]`). The main branch is ahead of the release it
   announces. **Consequence: we pin to a tag, and the note records which one.**
   A conformance suite written against `main` is written against a moving target.
2. A2A is an open-source project under the Linux Foundation, contributed by
   Google, Apache-2.0. There is an official Python SDK (`a2a-sdk` on PyPI). That
   SDK is the cheapest honest test of our reading of the spec - see T-0109.

## 2. The protocol in the size that matters

Eleven operations, three bindings, one data model.

    SendMessage                    GetTask      ListTasks    CancelTask
    SendStreamingMessage           SubscribeToTask
    CreateTaskPushNotificationConfig   GetTaskPushNotificationConfig
    ListTaskPushNotificationConfigs    DeleteTaskPushNotificationConfig
    GetExtendedAgentCard

Bindings (JSON-RPC 2.0, gRPC, HTTP+JSON/REST) must be **functionally equivalent**
(§5.1): same operations, same semantics, same error mapping, same auth. A server
may add a **custom binding** (§12) provided it implements all eleven operations,
preserves the data model, maps the nine error types, declares itself in the Agent
Card, and documents service parameter transmission, streaming support (or its
absence) and authentication. That permission is the hinge of this note.

The data model is small enough to state: `Task{id, contextId, status{state,
message, timestamp}, artifacts[], history[], metadata}`; `Message{messageId,
contextId, taskId, role, parts[], metadata, extensions[], referenceTaskIds[]}`;
`Part{text|raw|url|data, mediaType, filename, metadata}`; `Artifact{artifactId,
name, description, parts[], metadata}`; two stream events
(`TaskStatusUpdateEvent`, `TaskArtifactUpdateEvent{append, lastChunk}`);
`AgentCard{name, description, supportedInterfaces[], provider, version,
capabilities{streaming, pushNotifications, extensions[], extendedAgentCard},
securitySchemes, skills[], signatures[]}`; and `TaskState` with eight values
(`SUBMITTED, WORKING, COMPLETED, FAILED, CANCELED, INPUT_REQUIRED, REJECTED,
AUTH_REQUIRED`).

Nine A2A-specific errors, with mandatory mappings to JSON-RPC `-32001..-32009`,
gRPC status and HTTP status (§5.4): `TaskNotFound`, `TaskNotCancelable`,
`PushNotificationNotSupported`, `UnsupportedOperation`,
`ContentTypeNotSupported`, `InvalidAgentResponse`,
`ExtendedAgentCardNotConfigured`, `ExtensionSupportRequired`,
`VersionNotSupported`.

Encoding rules we would have to obey: JSON field names are **camelCase**; enums
serialize as **SCREAMING_SNAKE strings**; timestamps are **ISO-8601 UTC**; the
protocol version travels as a service parameter `A2A-Version` in `Major.Minor`
form (§3.6), and an unsupported version is a `VersionNotSupportedError`, not a
silent downgrade.

Three ways a task's progress reaches a client (§3.5): polling `GetTask`,
streaming, or a webhook (`TaskPushNotificationConfig`). Events must be delivered
in generation order. `ListTasks` is cursor-paginated (`pageToken` /
`nextPageToken`, `""` at the end), sorted by status timestamp descending, and
**scoped to the caller's authorization boundaries even when no filter is given**
(§13.1).

## 3. The finding that decides the refactor: A2A's `Task` is not our `task`

This is the part worth arguing about, because the words match and the objects do
not.

    A2A Task     a unit of delegated execution. A server creates it, works it,
                 produces Artifacts, and its lifecycle is states the server
                 controls. The client watches.
    aim task     a planning card. A person owns it, a milestone contains it, it
                 has an estimate, a due date, acceptance criteria, and a
                 dependency edge to another card.

Concretely: an A2A `Task` cannot express "blocked by T-0007" without an
extension, and it has no field for an estimate, a due date, or an acceptance
criterion. Our card cannot express "this produced two artifacts, appended in
chunks" without a change either. And `TaskState` has no word for `blocked`,
`ready` or `review`, while our seven statuses have no word for `input-required`,
`auth-required` or `rejected`.

Renaming our card to `Task` because A2A has a `Task`, then discovering the three
missing states in the implementation, is the same failure this project has
already measured twice (design/05 §3: a second implementation of a rule; and the
house rule about restating a peer's framing as one's own). A mapping table that
goes by name would have hidden it, so §4 below goes by semantics instead.

The honest mapping, once semantics decide it:

| aim | A2A | verdict |
|---|---|---|
| channel (`channels/<id>/`) | `contextId` - "logically group related tasks and messages" | **adopt**: it is the same idea, and A2A already has the name |
| a message in `outbox/<to>/<msg_id>.json` | `Message` in a context | adopt the shape; keep `bytes` and `body_sha256` as `metadata` |
| the public log (`log.jsonl`) | the message stream of a context | adopt |
| the task store (claude's T-0010..15) | `Task` | **keep the word, reject the object**: it is a planning card, and it needs a *delegation* record beside it to have an A2A Task (D14) |
| `blocked_by`, estimate, due, accept | nothing in `Task` | extension `planning/v1` (D16) |
| a delivery receipt (D4, `claimed_at`/`acked_at`) | **no A2A operation exists** | keep; extension `receipts/v1`. A2A does not model "did you read it" |
| the refusal ledger (`ledger.jsonl`, hash-chained) | **no A2A object exists**; error *responses* are typed, records are not | adopt the nine error codes for responses; the ledger stays ours |
| the barrier (phases, seals, digests) | **no A2A object exists**, and deliberately: A2A's stated goal is that agents "operate without exposing their internal state, memory, or tools" | extension `sealed-divergence/v1`, carrying digests only - never private logs, which we do not render even for the leader |
| the gate (visibility by phase, per viewer) | §13.1 authorization scoping: the model is **agent-defined**, and we are told to document it | **adopt the framing**: our gate *is* an authorization model, and §13.1 now obliges us to document it. Where it obliges us to change is D17 |
| the doorbell hook | `TaskPushNotificationConfig{url, token, authenticationInfo}` | adopt: our ad-hoc hook becomes a standard config object (T-0106) |
| rooms, read cursors, unread, mentions | **nothing**; A2A has no chat and no membership | keep, and see D18 |
| the human leader | `Role` is only `USER`/`AGENT` | keep: the human is an A2A *client*, each agent is an A2A *server*. Our leadership rule is not portable and should not pretend to be |
| `registry.json` (kind, model) | `AgentCard` (+ `AgentProvider`) | adopt: we have no card, and §8.3 requires one per interface (T-0102) |
| a webhook-free, daemon-free filesystem fabric | a *binding*, not a protocol | this is §5, and it is the whole proposal |

Two of these rows cost nothing and are pure gain: `contextId` for our channel, and
the `AgentCard` we never had. One row is a genuine contradiction (D17). The rest
is either an extension or an honest "A2A does not do this".

## 4. Proposal: aim as a custom A2A binding, not a rewrite

Two options were considered. The second is cheaper and I recommend against it, on
the evidence of our own failure log.

**Option A - `AIM+FILES`, an A2A custom binding (recommended).** Keep the fabric
file-first. Declare a binding in the Agent Card with `protocolBinding:
"AIM+FILES"`, and implement the eleven operations against the files, with the
conformance suite (§6, T-0101) as the definition of done. Streaming is not
supported and the card must say so (§12.5); push notifications replace the
doorbell's ad-hoc shape. The cost is real: eleven operations, nine error codes,
camelCase/SCREAMING_SNAKE/ISO-8601 encoding, a documented service-parameter
transport, and an authentication story we do not currently have at all.

**Option B - an A2A gateway beside the fabric.** Leave the core alone and add a
JSON-RPC front end that translates. Cheaper now, and it installs a second place
where the gate and the write discipline must be implemented - which is exactly
the class of bug this repo keeps finding (the lost update, the visible-subset
`task list`, the unrecorded refusal). If we take B anyway, the rule is
non-negotiable: **the gateway shells out to `bin/aim` and never reimplements the
gate or the write discipline.** The dashboard already sets this precedent with
`/api/command`.

What A can buy us beyond compliance, stated as things we cannot do today: a
foreign A2A client can address an agent in this fabric without knowing our layout;
`a2a-sdk` can be our conformance client instead of our own reading of the spec;
and our task store gets a second consumer, which is the fastest way to find out
whether its interface is actually right.

What it cannot buy, said plainly so nobody is disappointed: **A2A is not a
project-management protocol and not a chat protocol.** It gives us task
delegation, discovery, transport negotiation, error typing and auth scoping. It
has no board, no room, no read cursor, no milestone, no dependency, no ledger.
Standardizing on A2A standardizes the *boundary*. The PM half stays ours, and D18
names where to look for a standard for that half rather than pretending A2A is it.

## 5. The contradiction to decide (D17), because it is not cosmetic

A2A §3.3.2: a server **MUST NOT** reveal the existence of resources the client is
not authorized to access, and **SHOULD NOT** distinguish "does not exist" from
"not authorized". Our gate does the opposite on purpose - `aimboard/gate.py`
publishes the *count* of withheld items, on the argument that "the existence of a
gate is not a secret, only its contents are, and a board that silently shows fewer
cards than exist is a board you cannot trust".

Both rules are defensible and they cannot both be in force on the same request.
The resolution I propose is per-surface, not per-tool:

    the leader's board   a trust surface, for an audience that already reads both
                         seals. Keep the count. Keep the banner.
    an A2A caller        a leak surface, answering an unauthenticated stranger.
                         Return TaskNotFoundError. No count, no "withheld".

The consequence is a real amount of work and a real test: `ListTasks` and
`GetTask` as a participant in `SEALED_DIVERGENT` must not answer "here are four
tasks, three of which you cannot see". This is T-0105, and it is the item most
likely to be quietly skipped because it looks like a detail.

## 6. Decisions asked for

| id | decision | recommendation | what would change it |
|---|---|---|---|
| D13 | is our channel called a channel or a `contextId`? | keep **channel** inside, add `context_id` as the external field name | a foreign client needing our internal name to interoperate - it should not, and I would treat that as a bug in our binding |
| D14 | is our PM card an A2A `Task`? | **no**: keep the card, add a separate `delegation` record for A2A tasks | an A2A field appearing that a card genuinely needs (estimate, dependency) - then re-open, because that would mean A2A changed |
| D15 | do refusals carry A2A error codes? | yes, for the *response*; the ledger keeps its own richer record | a refusal that has no A2A error and does not deserve one - then it is a new class and we say so |
| D16 | extension namespace | `https://github.com/rzbdz/aim/extensions/<name>/v1`, three extensions: `sealed-divergence`, `planning`, `receipts` | a single existing standard covering one of them |
| D17 | withheld count on an A2A surface | follow A2A (not found, no count); keep the count on the leader's board | evidence that a caller needs the count to recover - none so far |
| D18 | what standard covers the chat/PM half | investigate **Matrix**'s room model next (rooms, power levels, read receipts, hash-chained event DAG, federation) before inventing more, and **MCP** for the tool surface (A2A's own README: A2A complements MCP, agents collaborating vs agents using tools) | our phase gate turns out to be inexpressible as room ACLs, or the event DAG cannot carry our ledger - either is plausible and either would end the investigation early |

Correction added in review of T-0107/T-0108, and it is a correction of the
*count*, not of the namespace. `aimboard/a2a.py`'s `EXTENSIONS` constant still
holds those three, and that part of D16 stands. But `agent_card()` appends a
fourth extension, `card-facts/v1`, whose `params.aim` carries the binding's own
facts (the block that used to sit at the card's top level as `metadata`): A2A's
`AgentCard` message has no `metadata` field, so the facts had nowhere in the
schema to live and a reference client refused the whole card rather than ignore
them. Three declared + one appended is the shape to check with `aimboard/a2a.py §
rg -n 'CARD_FACTS_URI|EXTENSIONS ='`; that constant is in the working tree
(`f57cc083…`) and **not** in `git HEAD` (`2c4f82c0…`), which is why
`design/14-a2a-gaps.md` §6 records it as drift and row 35 there is the one row
checked against the tree rather than HEAD.

## 7. Plan

New milestone **M6 - A2A alignment**, with tasks T-0100..T-0110 in `plan/plan.json`.
The order matters: the conformance test first (T-0101), because it turns "we read
the spec" into something that can fail, and the auth decision (T-0106, T-0109)
before any endpoint is reachable from outside localhost.

One task is not about A2A and is in this milestone because it came out of reading
it. T-0110: **a channel that names a shared workspace may not claim a barrier.**
The Anthropic-side participant proposed closing `hello` as a failed transport test
and writing down the honest name for what we are doing - shared workspace with a
role split, no barrier in force. I agree with the outcome and want a mechanism
rather than a confession: a channel manifest may declare a `workspace`, and if two
participants share a writable one, the phase gate's precondition is falsified *by
the manifest itself*, so `aim` should refuse the divergence phase (`REFUSED:
channel 'dev' declares a shared workspace, so its participants can read each
other's work; a barrier here is a claim the tool cannot keep`). That is checkable,
it is not theatre, and it makes the honest name the tool's job instead of the
participant's.

## 8. What this note does not cover

Transport security in depth (mTLS, OAuth2 device flow, Agent Card signing via
JWS, `/.well-known/agent-card.json` publishing). It is in the spec (§7, §8.2,
§8.4) and it is T-0109's business. Recording it here so the omission is visible:
today this fabric has **no authentication of any kind**, and an A2A binding
without one is a localhost-only experiment, not an interoperable agent.
