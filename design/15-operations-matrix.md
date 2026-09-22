# 15 - The eleven A2A operations, one row each, read off the code

Card **T-0206**: *"Answer, on the board, which of the eleven operations this
fabric can actually do today."* The eleven are named in `design/07` §2 and their
statuses are argued in `design/14` §1; this note does the one thing those two do
not: it puts all eleven in one table, and for each one names either the verb or
the endpoint that implements it, or the anchor in the code where it stops.

`design/14` was written by another hand and is not edited here. Where its
`file:line` and the code disagree, the code wins and this note says so (§4).

**Everything below is a read, not a promise.** The one A2A endpoint is
`POST /rpc`, and the card's brief forbids POSTs, so the endpoint rows are read
from `aimboard/a2a.py` + `aimboard/cli.py` rather than probed live. The CLI rows
*are* probed, and the probes are in §3.

## 0. What was measured, and against which revision

    $ curl -s http://127.0.0.1:8777/api/revision
    {"fabric": "e9def54+dirty", "bundle": {... "revision": "e9def54+dirty", ...},
     "stale": true, "front_end_sha256": "6eb02ea3..."}

**Revision `e9def54+dirty`, `stale: true`.** The front-end bundle does not match
the source on disk, so the *page* is not the artifact these rows were read from;
the rows were read from `aimboard/a2a.py` and `bin/aim`. The revision was not
stable while this note was written: the first read returned `1edf47c+dirty` and
the second `e9def54+dirty` four minutes later. That is the environment, not a
defect in this note — but it is why §4 exists.

File shas at read time (`sha256sum`):

| file | sha256 (at read time) | `design/14` §0 pinned | moved? |
|---|---|---|---|
| `bin/aim` | `56aa15077218cbff97bd2cc0ffa7aa27f821edcca31b54dab6ed8ae6cff666f0` | `1326e1950fdc...` | yes |
| `aimboard/a2a.py` | `f57cc083fa9fea9f7dd2c264dbac7c3bb0411036e77d51d7ddd8862fa59c204c` | `2c4f82c01e9a...` | yes |
| `aimboard/cli.py` | `7191573c477e24c8586c44f7b280f80ab46bc2794b1b9ee921184811f9d263d0` | `756fb505e900...` | yes |

Because all three moved, **every row below names a search anchor, not a line
number** — the same convention `design/14` §0 adopted for `bin/aim` and
`cli.py`. `a2a.py` turns out to move too (it grew 23 lines between two reads
inside this session), so it gets the same treatment. The line numbers in
parentheses are the anchor's *current* answer at the sha above; re-run the
anchor and it may be a different number, which is the point.

## 1. The matrix

Verdict key:

- **implementable** — the JSON-RPC method returns a result (not an error), and
  there is a CLI verb over the same file store. A caller can do the thing.
- **partial** — the operation returns a result, but a property the spec requires
  of it is absent. Naming the property is the whole verdict.
- **absent** — the surface answers `UnsupportedOperationError` and there is no
  CLI verb that performs the operation.

| # | A2A operation | verdict | verb / endpoint that implements it | where it stops |
|---|---|---|---|---|
| 1 | `SendMessage` | **absent** | — (`aim push`/`aim say` write an outbox record, not a `Message`) | `aimboard/a2a.py` § `rg -nF '"SendMessage": "no message'` → `UNSUPPORTED` entry; dispatch at § `rg -n 'if method in UNSUPPORTED'` |
| 2 | `SendStreamingMessage` | **absent** | — | `aimboard/a2a.py` § `rg -n '^STREAMING = '`; card declares `"streaming": False` at § `rg -nF '"streaming": False'` |
| 3 | `GetTask` | **implementable** | `POST /rpc` `{"method":"GetTask"}`; CLI `aim task list --json` (no single-task verb) | implements at `aimboard/a2a.py` § `rg -nF 'def get_task'`; gate before lookup, same function |
| 4 | `ListTasks` | **implementable** | `POST /rpc` `{"method":"ListTasks"}`; CLI `aim task list --as … --channel …` (`cmd_task_list`) | implements at `aimboard/a2a.py` § `rg -nF 'def list_tasks'`; CLI at `bin/aim` § `rg -nF 'def cmd_task_list'` |
| 5 | `CancelTask` | **absent** | — (`aim task move --to dropped` is a *status move*, not a cancel a client invokes) | `aimboard/a2a.py` § `rg -nF '"CancelTask": "no task-cancel'`; the status move is `bin/aim` § `rg -nF 'def cmd_task_move'` |
| 6 | `SubscribeToTask` | **absent** | — | `aimboard/a2a.py` § `rg -n '^STREAMING = '` and the `UNSUPPORTED` entry below it |
| 7 | `CreateTaskPushNotificationConfig` | **implementable** | `POST /rpc` `{"method":"CreateTaskPushNotificationConfig"}`; CLI `aim task doorbell create` | implements at `aimboard/a2a.py` § `rg -nF 'def create_push_config'`; CLI at `bin/aim` § `rg -nF 'def cmd_task_doorbell'` |
| 8 | `GetTaskPushNotificationConfig` | **implementable** | `POST /rpc` `{"method":"GetTaskPushNotificationConfig"}`; CLI `aim task doorbell list --id …` | implements at `aimboard/a2a.py` § `rg -nF 'def get_push_config'` |
| 9 | `ListTaskPushNotificationConfigs` | **implementable** | `POST /rpc` `{"method":"ListTaskPushNotificationConfigs"}`; CLI `aim task doorbell list --id …` | implements at `aimboard/a2a.py` § `rg -nF 'def list_push_configs'` |
| 10 | `DeleteTaskPushNotificationConfig` | **implementable** | `POST /rpc` `{"method":"DeleteTaskPushNotificationConfig"}`; CLI `aim task doorbell delete` | implements at `aimboard/a2a.py` § `rg -nF 'def delete_push_config'` |
| 11 | `GetExtendedAgentCard` | **partial** | `POST /rpc` `{"method":"GetExtendedAgentCard"}` returns the *public* card; CLI `aim card --as …` | returns at `aimboard/a2a.py` § `rg -nF 'if method == "GetExtendedAgentCard"'`; the extended half is refused by `"extendedAgentCard": False` at § `rg -nF '"extendedAgentCard": False'` |

## 2. The count

    implementable   6   GetTask, ListTasks, and the four push-notification config operations
    partial         1   GetExtendedAgentCard
    absent          4   SendMessage, SendStreamingMessage, CancelTask, SubscribeToTask

The split matches `a2a.py`'s own comment ("Seven operations have real backing.
Four do not") once the seventh — `GetExtendedAgentCard` — is downgraded from
backed to partial: it answers, but it answers with the anonymous card, so the
part of the operation that is *extended* does not exist.

Two caveats that belong next to the count rather than inside it:

- **The four push-config rows are implementable as objects, and not usable as a
  capability.** All four ops return results, but nothing opens an HTTP client to
  POST to the configured `url` — `design/14` row 10, re-checked with
  `rg -n 'urlopen|urllib.request|http.client|requests' aimboard bin`, which
  matches only `from urllib.parse import parse_qs`. A caller who creates a
  config gets a 200 and a doorbell that does not ring off-fabric.
- **`SendMessage`'s absence is a semantic choice, not a missing transport.**
  `design/07` §3: A2A's `Task` is a unit of delegated execution, ours is a
  planning card. `SendMessage` would have to create an A2A task, and the fabric
  has no such object to create.

## 3. Read-only verification

The brief allows `aim --help` and one `GET` of the board. What those actually
returned, because a matrix whose inputs are not shown is a claim:

    $ aim --help                    # the CLI verb list: task, card, say, push, … present
    $ aim task doorbell --help      # {create,list,rotate,delete}  -> ops 7..10 have verbs
    $ aim card --as codex           # a JSON AgentCard -> op 11's non-extended half
    $ aim task list --as codex --channel hello
    aim: REFUSED: 1 work item(s) in 'hello' are drafts owned by someone else, and the
    channel is in COMMIT ... --count-hidden ... or wait for CROSS_EXAMINE.

That refusal is the gate working (`design/14` row 34 / `bin/aim` `_visible_to`),
not a broken read; `--owner codex` reads as codex.

    $ curl -s http://127.0.0.1:8777/api/revision
    {"fabric": "e9def54+dirty", ..., "stale": true}
    $ curl -s 'http://127.0.0.1:8777/api/state?as=human' | head -c 200
    {"generated_at": "2026-09-22T08:26:27.300Z", "digest": "ea15eb98...", ...,
     "statuses": ["backlog", "ready", "doing", "review", "d...

`POST /rpc` was **not** called, per the brief's no-POST rule; the endpoint rows
come from the dispatch in `aimboard/cli.py` § `rg -nF 'def _rpc_POST'` and the
branch list in `aimboard/a2a.py` § `rg -n 'if method =='`.

## 4. Findings that belong on the record

1. **The card's acceptance names a file this card may not write.**
   T-0206's acceptance is *"the capability matrix from README section 9 gains an
   A2A section where every row is either a command that works or the word
   missing, and it is rendered rather than promised."* README §9 is the PM
   matrix; the A2A matrix is README §10. §10 still says every operation is
   **missing** (including `GetTask`, which `POST /rpc` implements), and README is
   outside this card's write set. This note is the checkable replacement; the
   README row is owed to whoever owns that file.
2. **`design/14`'s `file:line` rows are stale at the sha it recorded.** All three
   files moved past the shas in its §0 (table above), and `a2a.py` grew ~23 lines
   *within this session*. The anchors still resolve; the numbers do not.
3. **`GET /rpc` returns the SPA with HTTP 200, not 404/405.**
   `curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8777/rpc` → `200`,
   content-type `text/html`. `do_GET` (`aimboard/cli.py`) has no `/rpc` branch and
   the 404 guard is scoped to `path.startswith("/api/")`, so a monitoring client
   probing the A2A endpoint folds HTML as data — the exact failure AGENTS.md
   records for `/api/flow`, one path over. `GET /.well-known/agent-card.json`
   returns the same 200/HTML: there is no discovery endpoint.
4. **The four push-config operations are counted as implementable while the
   delivery transport they imply does not exist** (`design/14` row 10). The count
   in §2 is "the surface answers", not "the capability is real"; §2 says both.
