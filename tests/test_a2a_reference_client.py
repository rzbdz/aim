#!/usr/bin/env python3
"""T-0207: the reference implementation has to be able to drive us.

`tests/test_a2a_conformance.py` asserts our reading of the A2A spec against
`aimboard/a2a.py`. That is a closed loop: the reader, the writer and the judge
are the same codebase. This file opens the loop with the one instrument that is
not ours -- the official `a2a-sdk` Python client -- and records, as assertions
with their exact messages, where it stops.

Four gates stood between a foreign A2A client and a task in this fabric. Gate 2
-- the card itself -- is closed by T-0229: the SDK's own protobuf now parses the
card `aim card` emits, because the aim facts moved into the `params` of a fourth
extension instead of a top-level `metadata` field `lf.a2a.v1.AgentCard` never
had. The reference client still fails the other three today:

  1. discovery  the SDK fetches `/.well-known/agent-card.json`; `aimboard serve`
                has no such route and `aim` publishes no URL.
  2. the card   closed. The card's top level is a subset of the SDK's AgentCard
                fields and `ParseDict` accepts it; the aim facts live under
                `capabilities.extensions[].params.aim`, the proto's own free-form
                field. `test_the_published_card_is_a_valid_agent_card` pins
                this, and every one of its assertions fails against the old
                shape -- a green run means the card is schema-valid, not that it
                still carries the field that broke it.
  3. binding    the card declares the custom binding URI `.../aim-files/v1`.
                The SDK routes only `JSONRPC`, `HTTP+JSON` and `GRPC`, so
                `ClientFactory.create` raises `ValueError: no compatible
                transports found.`
  4. the dial   with the binding forced to `JSONRPC`, the interface URL is still
                a filesystem path, so httpx refuses it: `Network communication
                error: Request URL is missing an 'http://' or 'https://'
                protocol.`

Only when the remaining three are bypassed by hand -- a hand-built JSONRPC card
and an in-process transport -- does the SDK reach `aimboard.a2a.handle_rpc`, and there
the news is good: `GetTask` and `ListTasks` return real tasks, and the SDK's
exception types carry *our* messages, so the nine A2A error codes this fabric
already emits are the ones the reference client raises.

No server is started: the leader's rule for this card is no second listener.
The SDK still builds real httpx requests and real JSON-RPC payloads; they are
handed to the exact function `aimboard/cli.py::_rpc_POST` calls, with the same
arguments, instead of to a bound port. `test_the_shim_tracks_the_server` pins
that seam so this file cannot silently drift from the server it stands in for.

Requires the reference SDK, which is deliberately not a repo dependency:

    python3 -m venv /tmp/a2a-ref-venv
    /tmp/a2a-ref-venv/bin/pip install a2a-sdk
    /tmp/a2a-ref-venv/bin/python tests/test_a2a_reference_client.py
"""
import asyncio
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
AIM = HERE / "bin" / "aim"

SDK = importlib.util.find_spec("a2a") is not None

# The standard bindings the reference client knows how to route. A card that
# names anything else is discoverable-but-undialable to an off-the-shelf SDK,
# which §12 permits and which is a fact a foreign client must be told.
SDK_STANDARD_BINDINGS = {"JSONRPC", "HTTP+JSON", "GRPC"}


def aim(root, *argv):
    """Run one `aim` verb against a throwaway root, and insist it worked."""
    done = subprocess.run(
        [sys.executable, str(AIM), *argv],
        env=dict(os.environ, AIM_ROOT=str(root)),
        capture_output=True,
        text=True,
        timeout=30,
    )
    if done.returncode != 0:
        raise AssertionError(f"aim {' '.join(argv)} failed ({done.returncode}): {done.stderr}")
    return done.stdout


@unittest.skipUnless(SDK, "the official a2a-sdk reference client is not installed")
class ReferenceA2AClientTest(unittest.TestCase):
    """Drive this fabric with a2a-sdk, and assert the failures by their message."""

    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="aim-a2a-ref-"))
        # The whole point of the card: this test never touches the live fabric.
        self.assertNotEqual(self.root.resolve(), HERE.resolve())
        aim(self.root, "init")
        aim(self.root, "register", "--as", "human", "--kind", "human")
        aim(self.root, "register", "--as", "alice", "--kind", "codex")
        aim(self.root, "new-channel", "--id", "hello", "--topic", "T-0207",
            "--participants", "alice,human", "--leader", "human")
        aim(self.root, "task", "new", "--as", "alice", "--channel", "hello",
            "--title", "a card the reference client can fetch", "--owner", "alice",
            "--accept", "the official client gets this task or the exact error")
        self.card = json.loads(aim(self.root, "card", "--as", "alice"))

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    # -- our own state, loaded the way the server loads it -------------------
    def _state(self):
        """The same fold `aimboard/cli.py::_state` hands to `handle_rpc`."""
        from datetime import datetime, timezone
        from aimboard.fabric import load_fabric
        return load_fabric(self.root, ["plan/*.json"], datetime.now(timezone.utc).date())

    def _card_facts(self):
        """The `aim` block, read from where A2A lets it live.

        T-0229 relocated it from the card's top level into the `params` of the
        card-facts extension, the proto's free-form field, because
        `lf.a2a.v1.AgentCard` has no top-level `metadata`. Reading it from
        anywhere else is reading the old shape.
        """
        from aimboard.a2a import CARD_FACTS_URI

        extensions = self.card["capabilities"]["extensions"]
        carriers = [ext for ext in extensions if ext.get("uri") == CARD_FACTS_URI]
        self.assertEqual(len(carriers), 1,
                         f"expected exactly one {CARD_FACTS_URI} extension, got {len(carriers)}")
        return carriers[0]["params"]["aim"]

    # -- gate 2, now closed: the card the reference client can parse ---------
    def test_the_published_card_is_a_valid_agent_card(self):
        """The inverse of the T-0229 failure, asserted with the SDK's own parser.

        The first version of this test asserted the card *had* a top-level
        `metadata` and that `ParseDict` refused it, so a green run meant the card
        was still unreadable. A green run now means the opposite: the card's top
        level is a subset of the AgentCard message's fields, `ParseDict` accepts
        it, and the aim facts survive the parse under `params.aim`.
        """
        from google.protobuf.json_format import ParseDict
        from a2a.types.a2a_pb2 import AgentCard

        from aimboard.a2a import BINDING_URI, CARD_FACTS_URI

        # `fields_by_name` is snake_case (`default_input_modes`); the JSON the
        # card emits is camelCase, so compare against the proto's `json_name`.
        schema = {field.json_name for field in AgentCard.DESCRIPTOR.fields}
        unknown = sorted(set(self.card) - schema)
        self.assertEqual(
            unknown, [],
            f"top-level fields outside lf.a2a.v1.AgentCard: {unknown}; the reference "
            f"client refuses the first by name, which makes the whole card unreadable")
        # `metadata` is still not a field of the card message. That is *why* the
        # facts moved, and the absence is asserted so a later A2A revision that
        # adds the field is a visible change rather than a silent re-use of the
        # shape that broke the client.
        self.assertNotIn("metadata", schema)

        proto_card = ParseDict(self.card, AgentCard())
        self.assertEqual(proto_card.name, "alice")
        self.assertEqual([interface.protocol_binding
                          for interface in proto_card.supported_interfaces],
                         [BINDING_URI])

        # The facts must survive the parse, not merely exist in the JSON: `params`
        # is a google.protobuf.Struct, so the SDK's own protobuf carries them and
        # a client does not need a second, non-standard parser to read them.
        carried = [extension for extension in proto_card.capabilities.extensions
                   if extension.uri == CARD_FACTS_URI]
        self.assertEqual(len(carried), 1)
        facts = carried[0].params["aim"]
        self.assertEqual(facts["agentId"], "alice")
        self.assertEqual(facts["bindingUri"], BINDING_URI)
        self.assertEqual(facts["authentication"], "none")

    # -- gate 3: the card parses, and the SDK still cannot route it ----------
    def test_the_sdk_cannot_route_the_custom_binding(self):
        from google.protobuf.json_format import ParseDict
        from a2a.client.client_factory import ClientFactory
        from a2a.client.client import ClientConfig
        from a2a.types.a2a_pb2 import AgentCard

        from aimboard.a2a import BINDING_URI

        # The card the fabric actually publishes, parsed by the SDK's parser:
        # gate 2 is closed, so gate 3 is shown on the real card rather than on a
        # copy that had the offending field stripped out by hand.
        proto_card = ParseDict(self.card, AgentCard())

        bindings = [interface.protocol_binding for interface in proto_card.supported_interfaces]
        self.assertEqual(bindings, [BINDING_URI])
        self.assertNotIn(BINDING_URI, SDK_STANDARD_BINDINGS,
                         "the reference SDK routes standard bindings only; a custom URI is a documented gap")

        with self.assertRaises(ValueError) as caught:
            ClientFactory(ClientConfig()).create(proto_card)
        self.assertEqual(str(caught.exception), "no compatible transports found.")

    # -- gate 4: the URL is the file root, not something httpx can dial ------
    def test_the_sdk_cannot_dial_the_filesystem_url(self):
        from a2a.client import create_client
        from a2a.client.errors import A2AClientError
        from a2a.types.a2a_pb2 import GetTaskRequest

        async def scenario():
            card = self._sdk_shaped_card(self.card["supportedInterfaces"][0]["url"])
            client = await create_client(card)  # a real httpx client, no shim
            with self.assertRaises(A2AClientError) as caught:
                await client.get_task(GetTaskRequest(id="T-0001"))
            return caught

        caught = asyncio.run(scenario())
        self.assertEqual(
            str(caught.exception),
            "Network communication error: Request URL is missing an 'http://' or 'https://' protocol.",
        )
        self.assertFalse(self.card["supportedInterfaces"][0]["url"].startswith(("http://", "https://")),
                         "the only interface this fabric publishes is a filesystem path")

    # -- the half that works: same SDK, hand-built card, in-process transport -
    def test_the_sdk_drives_the_jsonrpc_surface_and_the_errors_are_ours(self):
        asyncio.run(self._scenario_the_sdk_drives_handle_rpc())

    async def _scenario_the_sdk_drives_handle_rpc(self):
        import httpx
        from a2a.client import create_client
        from a2a.client.client import ClientConfig
        from a2a.types.a2a_pb2 import (
            GetTaskRequest, ListTasksRequest, Role, SendMessageRequest, TaskState,
        )
        from a2a.utils.errors import TaskNotFoundError, UnsupportedOperationError

        from aimboard.a2a import MESSAGES, STATUS_TO_STATE

        transport = _HandleRpcTransport(self._state(), viewer="alice")
        http = httpx.AsyncClient(transport=transport)
        try:
            # The URL is a lie the transport never dials; the binding is the
            # point. Everything else here is the reference client's real code:
            # its payloads, its JSON-RPC framing, its response parsing.
            card = self._sdk_shaped_card("http://127.0.0.1:8777/rpc")
            client = await create_client(card, ClientConfig(httpx_client=http))

            task = await client.get_task(GetTaskRequest(id="T-0001"))
            self.assertEqual(task.id, "T-0001")
            self.assertEqual(TaskState.Name(task.status.state), STATUS_TO_STATE["backlog"])

            listed = await client.list_tasks(ListTasksRequest())
            self.assertEqual([row.id for row in listed.tasks], ["T-0001"])
            self.assertEqual(listed.next_page_token, "", "§3.1.4: nextPageToken is present and empty at the end")

            with self.assertRaises(TaskNotFoundError) as caught:
                await client.get_task(GetTaskRequest(id="T-9999"))
            # The message is this fabric's own table, so the reference client is
            # raising *our* error, not a generic JSON-RPC failure.
            self.assertEqual(str(caught.exception), MESSAGES["TaskNotFoundError"])

            request = SendMessageRequest()
            request.message.message_id = "m-1"
            request.message.role = Role.ROLE_USER
            request.message.parts.add().text = "hello"
            with self.assertRaises(UnsupportedOperationError) as caught:
                async for _ in client.send_message(request):
                    self.fail("an operation with no backing must raise, not yield")
            self.assertTrue(str(caught.exception).startswith(MESSAGES["UnsupportedOperationError"]))
            self.assertIn("no message send surface", str(caught.exception))

            # No credentials were presented anywhere above, and that is exactly
            # why the endpoint may exist at all: it is loopback and unauthenticated.
            self.assertNotIn("authorization", transport.last_headers)
        finally:
            await http.aclose()

    # -- the acceptance line: no auth, so localhost-only, and the suite says so
    def test_the_binding_is_localhost_only_because_there_is_no_auth(self):
        # Asserted from the source rather than by importing `cli`: another agent
        # edits this file while the suite runs, and a half-written module must
        # not be what decides whether this card passed.
        source = (HERE / "aimboard" / "cli.py").read_text()
        host_default = re.search(r'add_argument\("--host", default="([^"]+)"\)', source)
        self.assertIsNotNone(host_default, "the serve parser no longer declares a host")
        self.assertEqual(host_default.group(1), "127.0.0.1",
                         "with no authentication, a bind address other than loopback is a leak")
        self.assertRegex(source, r'def canonical_port\(\):[\s\S]{0,2000}?return 8777',
                         "the canonical port must stay 8777 even when the board is not running")

        facts = self._card_facts()
        self.assertEqual(facts["authentication"], "none")
        self.assertIn("localhost-only", facts["reachability"])

    # -- the seam between this test's shim and the real server ---------------
    def test_the_shim_tracks_the_server(self):
        """The in-process transport must not drift from `cli.py`.

        The shim calls `handle_rpc` with the arguments the server passes. If the
        server's call site changes, this test has to be updated with it rather
        than quietly testing a shape the server no longer has.
        """
        source = (HERE / "aimboard" / "cli.py").read_text()
        self.assertIn("handle_rpc(", source, "the HTTP layer no longer calls the binding")
        for kwarg in ('request_id=req.get("id", 1)', 'viewer=self._viewer()',
                      'tasks=state.get("tasks", {})', 'channels=state.get("channels", [])',
                      'registry=state.get("registry", {})', 'configs=self._public_configs(),'):
            self.assertIn(kwarg, source, f"cli.py no longer passes {kwarg} to handle_rpc")
        self.assertIn('if path == "/rpc":', source)
        # The server serves /rpc while the card says the opposite; that
        # contradiction is asserted so it stays visible rather than ageing into
        # a lie nobody reads. The sentence lives in `card_facts` in
        # `aimboard/a2a.py`, which is outside this lane's write scope: the fix is
        # reported, not made here. design/16 section 3 already records it as
        # false -- the contradiction is real and this assertion is the alarm.
        self.assertIn("no network endpoint served yet",
                      json.dumps(self._card_facts()))

    # -- fixtures ------------------------------------------------------------
    def _sdk_shaped_card(self, url, binding="JSONRPC"):
        """A card the reference SDK accepts, so the transport can be exercised.

        This is the hand-built bypass of gates 1-3. It is not a proposal for what
        `aim card` should emit; it is the minimum a foreign client needs before
        `handle_rpc` can be reached at all.
        """
        from a2a.types.a2a_pb2 import AgentCard
        card = AgentCard(name="alice", description="an aim agent, JSON-RPC binding", version="1")
        interface = card.supported_interfaces.add()
        interface.url = url
        interface.protocol_binding = binding
        interface.protocol_version = "1.0"
        # §12.5: the card must say when streaming is absent, and this fabric has
        # no stream, so the client takes the non-streaming path honestly.
        card.capabilities.streaming = False
        return card


if SDK:
    import httpx as _httpx

    _TransportBase = _httpx.AsyncBaseTransport
else:
    _TransportBase = object


class _HandleRpcTransport(_TransportBase):
    """The HTTP framing of `cli.py::_rpc_POST`, without a socket.

    A real `httpx.AsyncBaseTransport`: the reference SDK builds the request, the
    JSON-RPC body and the SSE/JSON expectations; this only replaces the bound
    listener with a direct call to the same `handle_rpc` the server calls, using
    the same `viewer`/`tasks`/`channels`/`registry`/`configs` arguments. The
    leader's rule for T-0207 is no second server, so the port is the one thing
    this test does not exercise.
    """

    def __init__(self, state, viewer):
        self._state = state
        self._viewer = viewer
        self.last_headers = {}

    async def handle_async_request(self, request):
        import httpx
        from aimboard.a2a import handle_rpc

        self.last_headers = {key.lower(): value for key, value in request.headers.items()}
        body = json.loads(request.content.decode("utf-8") or "{}")
        response, mime = handle_rpc(
            body.get("method") or "",
            body.get("params") or {},
            request_id=body.get("id"),
            viewer=self._viewer,
            tasks=self._state.get("tasks", {}),
            channels=self._state.get("channels", []),
            registry=self._state.get("registry", {}),
            configs=[],  # this fabric has no push.jsonl, so [] is _public_configs()' result
        )
        if mime == "text/event-stream":
            return httpx.Response(200, headers={"content-type": "text/event-stream; charset=utf-8"},
                                  content=f"data: {json.dumps(response)}\n\n".encode())
        return httpx.Response(200, headers={"content-type": "application/json; charset=utf-8"},
                              content=json.dumps(response).encode())


if __name__ == "__main__":
    if not SDK:
        print("the reference client `a2a-sdk` is not importable, so nothing was verified.",
              file=sys.stderr)
        print("  python3 -m venv /tmp/a2a-ref-venv", file=sys.stderr)
        print("  /tmp/a2a-ref-venv/bin/pip install a2a-sdk", file=sys.stderr)
        print("  /tmp/a2a-ref-venv/bin/python tests/test_a2a_reference_client.py", file=sys.stderr)
        sys.exit(2)
    unittest.main(verbosity=2)
