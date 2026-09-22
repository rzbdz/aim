# 10 — MCP wrapper: one writer, one identity, tools derived from the CLI

The leader's final shape names MCP as one of five layers, and the rule from
`design/08` is narrower than “add an MCP server”: **the wrapper is not a second
writer.** This note is the interface for T-0120 and T-0121.

## 1. Survey

The standard and SDK are already measured in `design/09`:

| dependency | stars (2026-09-21) | decision |
|---|---:|---|
| `modelcontextprotocol/modelcontextprotocol` | 9,265 | the spec |
| `modelcontextprotocol/python-sdk` | 24,350 | **adopted** for the server and in-memory client |

The implementation uses the SDK's low-level `Server`, not a web framework and
not a second JSON-RPC dispatcher. It speaks stdio when run as a command and is
tested in memory through the SDK's own client, so conformance is not inferred
from a hand-written transport.

## 2. Contract

1. **No fabric write happens in the MCP module.** Every call runs
   `bin/aim` as a subprocess with an argv list, never a shell. The wrapper returns
   the subprocess's `stdout`, `stderr` and exit code unchanged. If `aim` refuses,
   the MCP result is an error result carrying the refusal text, and `aim` records
   the refusal exactly as it would for a terminal call.
2. **Identity is a server startup fact.** `--as <agent>` is required. For verbs
   that accept `--as`, the wrapper drops any caller-supplied `--as` and appends
   the server's identity. This is the same rule as the dashboard (`design/06`
   R1): a read may borrow a view; a write may not borrow a name.
3. **The served root is the subprocess root.** The wrapper exports `AIM_ROOT`
   to the root it was started with, so an MCP call cannot write into the default
   fabric while a different fabric is being served.
4. **One tool per top-level verb.** The tool list is parsed from `aim --help`.
   A new verb therefore appears in MCP automatically; if parsing misses it, the
   test comparing MCP tools with the CLI's own choices fails.
5. **Tool input is `argv`.** Each generated tool accepts an array of strings that
   follow the verb. The CLI remains the authority on options, required fields and
   validation; duplicating argparse in JSON schemas would be a second interface
   and would drift.
6. **Errors are results, not exceptions.** A non-zero `aim` exit is returned as
   an MCP tool error with the same text. Transport failure and wrapper misuse are
   also tool errors; they never mutate the fabric.

## 3. Boundaries

The wrapper does not expose resources, prompts, subscriptions or HTTP. Those are
new capabilities with their own security questions. It starts as a stdio server
for a local operator, exactly like an MCP client launching a command.

The falsifier for this design is a task that needs the MCP server to write the
store directly for performance or atomicity. Nothing in the current store
requires that: `bin/aim` already owns locking, id allocation, refusal recording
and hash chaining, and a second implementation would be a second set of bugs in
the one place this repository measures them.
