# Design note 13 - the reference client, and the four gates it cannot pass

Card T-0207: *"Be tested by the reference implementation: a2a-sdk as the client.
The official Python SDK drives our endpoint and its errors are ours; before that
endpoint is reachable off localhost, authentication is either implemented or the
card says the binding is localhost-only and the suite asserts it is bound to
127.0.0.1."*

This note is the gap, written down. It is what `tests/test_a2a_reference_client.py`
asserts, and it is deliberately in the SDK's own words rather than ours.

SDK measured: `a2a-sdk==1.1.5`, installed into a throwaway venv under `/tmp`
(never the system interpreter, never a repo dependency). Method names, error
types and the `AgentCard` message come from that install, not from design/07.

## 1. What already holds, and is not a gap

- **The wire method names match.** The SDK's JSON-RPC transport sends
  `SendMessage`, `GetTask`, `ListTasks`, `CreateTaskPushNotificationConfig`,
  `GetTaskPushNotificationConfig`, `ListTaskPushNotificationConfigs`,
  `DeleteTaskPushNotificationConfig`, `CancelTask`, `SendStreamingMessage`,
  `SubscribeToTask`, `GetExtendedAgentCard` - the same names
  `aimboard/a2a.py::handle_rpc` dispatches on. (The spec's *operation* list and
  its JSON-RPC *method* strings are the same words; the `tasks/get`-style names
  belong to the HTTP+JSON binding, a different binding than ours.)
- **Its errors are ours.** Driven through `handle_rpc`, the SDK raises
  `a2a.utils.errors.TaskNotFoundError` and `UnsupportedOperationError`, with the
  `message` taken from our `MESSAGES` table (`"Task not found"`,
  `"Unsupported operation: no message send surface..."`). The nine A2A codes are
  the codes the reference client branches on.
- **`GetTask` and `ListTasks` return real work items**, and `nextPageToken` is
  present and empty at the end, as §3.1.4 requires.

So the binding's *inside* is reachable by the reference client. The gates are
all in front of it.

## 2. The four gates, and the exact message at each

| gate | what the SDK does | what happens | what would close it |
|---|---|---|---|
| discovery | `A2ACardResolver` GETs `<url>/.well-known/agent-card.json` | `aimboard serve` serves no such route, and `aim card` publishes no URL | serve the card at the well-known path, or say in the card that discovery is out of band |
| the card | `json_format.ParseDict(card, AgentCard())` | `ParseError: Message type "lf.a2a.v1.AgentCard" has no field named "metadata" at "AgentCard".` | move `metadata.aim` under a field the proto has (e.g. `capabilities.extensions[].params`) or drop it |
| binding | `ClientFactory.create(proto_card)` | `ValueError: no compatible transports found.` - the card names `.../aim-files/v1`; the SDK routes only `JSONRPC`, `HTTP+JSON`, `GRPC` | publish a standard `JSONRPC` interface (a custom binding is permitted by §12, and is undialable to an off-the-shelf client) |
| the dial | `httpx` POST to `supportedInterfaces[0].url` | `A2AClientError: Network communication error: Request URL is missing an 'http://' or 'https://' protocol.` - the URL is the fabric's file root | give the interface an `http(s)://` URL that a POST to `/rpc` answers |

The first is fatal: **a foreign A2A client cannot parse the AgentCard this
fabric publishes.** It is a top-level `metadata` field that the reference
implementation's normative message does not have. Everything else in the card
parses (removing only `metadata` parses cleanly), so this is a small edit with a
large consequence, and it is the single most valuable thing to fix.

## 3. The contradiction inside the card

The card's `metadata.aim.reachability` says *"localhost-only, no network endpoint
served yet"*. That was true when the card was written. It is no longer true:
`aimboard/cli.py` answers `POST /rpc` with `handle_rpc`. The card now understates
the surface - it tells a foreign client there is no endpoint while one exists -
and, because the field it says so in is the field the SDK refuses, the correction
is only visible to readers who already have a non-standard parser. Both halves
are asserted, so neither can age silently.

## 4. Authentication, which decides whether any of §2 may be closed

Design/07 §8: *"today this fabric has no authentication of any kind, and an A2A
binding without one is a localhost-only experiment, not an interoperable agent."*
That has not changed. `POST /rpc` takes no credential, and the suite drives it
with no `Authorization` header and gets a task back. Therefore:

- The endpoint is loopback-only by construction: `aimboard serve` still defaults
  to `--host 127.0.0.1` and `canonical_port()` is still `8777`. The suite asserts
  both from the source.
- Closing gates 1-4 **without** implementing authentication would be a
  regression, not a completion: it would make the endpoint reachable by an
  unauthenticated stranger. The two must move together, or the card says so.

## 5. What the suite does not exercise, and why

No server is started. The leader's rule for this card forbids a second listener,
and 8777 is held by the live board. The reference SDK still builds real httpx
requests and real JSON-RPC payloads; they are handed to the same `handle_rpc`
`aimboard/cli.py::_rpc_POST` calls, with the same arguments. The one thing not
exercised is the socket loop and `BaseHTTPRequestHandler` parsing -
`test_the_shim_tracks_the_server` pins the seam so this test cannot drift from
the server it stands in for. The endpoint port 8777 is asserted, never opened.
