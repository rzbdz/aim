# 04 — Proposal: `aim org`, and a working prototype

**Author:** `codex-orangement`, the orchestrator seat (T-0218).
**Measured at:** fabric `5b78a89+dirty`, `stale: false`, 2026-09-22T07:52Z.
**Prototype:** `reviews/org/aim-org.py` — runnable, read-only, ~150 lines, no dependencies.

## The question this answers

The leader, twice, in his own words:

> "I just don't get how these channels organized. that's a big problem right now."

> "我感觉我们 aim 还缺少一个团队管理的功能，比如让agent加入组织，能否最快获取到组织架构，
> 清楚谁可以调度，向谁汇报"

Today the answer exists only as prose that one agent typed into a message to another.
I know who I report to because `codex` told me in a doorbell message, and he would have
to retype it for everyone who joins. That is the fabric outsourcing a fact it should own.

## Run it

    $ python3 reviews/org/aim-org.py

    == agents (derived from registry.json) ==
      claude-session1    claude  Opus 5       registered 2026-09-21T07:33  #barrier-v0, #dev, #hello, #s2-scratch2
      claude-session2    claude  Opus 5       registered 2026-09-21T07:38  #barrier-v0, #s2-scratch, #s2-scratch2
      codex              codex   gpt-5        registered 2026-09-21T08:03  #dev, #hello
      codex-orangement   codex   gpt-5-codex  registered 2026-09-22T07:25  — in no channel —
      human              human                registered 2026-09-21T07:33  — in no channel —   [leads #barrier-v0, #dev, #hello, #s2-scratch, #s2-scratch2]
      synthesizer-v0     claude  Opus 5       registered 2026-09-21T07:44  — in no channel —   [synthesises #barrier-v0]

    == channels (derived from `aim status`) ==
      #barrier-v0     SYNTHESIS         leader=human  synthesizer=synthesizer-v0   log=2 public messages
          participants: claude-session1(sealed), claude-session2(sealed)
      #dev            SEALED_DIVERGENT  leader=human  synthesizer=(unset)          log=0 public messages
          participants: claude-session1(unsealed), codex(unsealed)
      #hello          COMMIT            leader=human  synthesizer=(unset)          log=1 public messages
          participants: claude-session1(sealed), codex(sealed)
      #s2-scratch     SEALED_DIVERGENT  leader=human  synthesizer=(unset)          log=0 public messages
          participants: claude-session2(sealed)
      #s2-scratch2    SEALED_DIVERGENT  leader=human  synthesizer=(unset)          log=0 public messages
          participants: claude-session1(unsealed), claude-session2(unsealed)

    == dispatch surface (derived: who is reachable at all) ==
      in at least one channel : 5 of 6
      leads at least one      : 1 of 6
      synthesises at least one: 1 of 6
      in no channel           : ['codex-orangement']

    == reporting lines (DECLARED, not derivable) ==
      no org.json at /root/tmp/agent-im. Nothing in the record states who reports to
      whom, and this tool will not infer it.

**Read the last line of the dispatch block again.** Five of six agents are placed. The
one that is not is the newest member — this session. A tool that answers "how is this
organised" should make the unplaced agent obvious, and this one does, which is the whole
argument for having it.

## The rule it keeps: derive what is recorded, declare what is not

Two sections, never merged, never labelled with the same word:

| relation | status | source |
|---|---|---|
| who exists, their kind, model, session | **derived** | `registry.json` |
| who is a participant of what, and sealed | **derived** | `aim status --channel <id>` |
| who leads a channel | **derived** | `manifest.leader` |
| who synthesises a channel | **derived** | `manifest.synthesizer` |
| **who reports to whom** | **DECLARED** | an `org.json` that does not exist yet |

The last row is the entire point. It is *not* in the record, and it cannot be inferred
without guessing — "codex authored most task events, therefore codex is in charge" is an
inference, and this project refuses exactly that move everywhere else. So the tool refuses
it here too, prints the shape of the file that would declare it, and says so plainly.

## It reads nothing that is gated

`registry.json` is root-level and outside every channel. `aim status` is a verb a
registered non-member may already run, and it is refused by the barrier when it should be.
The tool reads **no** private log, **no** seal file, **no** task store and **no** ledger —
not because it would be caught, but because an org chart built from gated bytes is a route
around a refusal, and an org chart that is itself a leak is worse than no org chart. It
shells out to `aim` rather than parsing files, so it inherits whatever the barrier decides
rather than reimplementing it.

## Two errors I made building it, recorded because they are the failure class

**First: `\s+` let an optional group cross a newline.** The parser matched each participant
line as `^  (\S+)\s+private=…\s+public=…\s+(\w+)(?:\s+(\w+))?`, and on a line ending
`unsealed` — with no seal digest — the optional group consumed the *next* line's agent
name. `#dev` has two participants and the tool reported one, confidently, in a clean two-row
list. That is the project's own named failure: *"a renderer that silently reads zero events
draws a clean empty board and calls it 'no work items yet'."* Fixed by using `[ \t]+`.

**Second, and worse: it modelled one relation and called the other two absent.**
It counted `participants` only, so it printed the leader of all five channels as *"in no
channel"* and `synthesizer-v0` — the synthesizer of the one channel in `SYNTHESIS` — as
*"in no channel"*. Two of six agents were reported unplaced while occupying the two most
specified roles in the system. An org chart that knows one relation is not approximately
right; it is wrong in the direction that matters, because it hides the people who own
things.

Both errors share a shape worth naming, because it is the same shape as `reviews/02` §1
and `reviews/03` §F3: **a confident answer produced by reading less of the record than the
question requires.** That is the failure this fabric was built to make visible, and building
a small tool inside it reproduced it twice in twenty minutes.

## What I am not proposing

Not a new store. Not a second source of truth. `aim org` is a *fold of what is already
written* plus one declared file for the single edge that is genuinely not derivable.
Everything in the "derived" column is already in the record today; the command is the only
thing missing.

## Adoption

If the team wants it, the prototype is at `reviews/org/aim-org.py`, it has no dependencies,
and it passes `python3 -m py_compile`. Two additions would make it real work rather than a
proposal: a `--json` output (already implemented) and a test that asserts the *unplaced*
list, since that is the field a reader will act on and the one my own bugs corrupted.
