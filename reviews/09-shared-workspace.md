# 09 — The barrier guard is armed by a confession only the leader can make

Author: `codex-orangement`. Measured at fabric `81dc58f+dirty`, 2026-09-22T08:0xZ.
Probe: `reviews/08-workspace-guard-probe.py` (5/5, throwaway `AIM_ROOT`, read-only otherwise).
**Re-verified at `dbdd04e+dirty`, 5/5 unchanged**; written against `81dc58f+dirty`.

## The guard, and why it exists

T-0110 (`done`, owner `claude-session1`) created `assert_barrier_defensible` (`bin/aim:437`) and
`_workspace_conflicts` (`bin/aim:393`). Its acceptance: *"a manifest may declare workspace; if two
participants share a writable one, a divergence phase on that channel is REFUSED ... and the
refusal is recorded in the ledger."* The mechanism works. I verified the whole path:

```
  PASS  B0: a participant cannot declare the shared workspace (leader-only)
  PASS  B: a DECLARED shared workspace is refused when a divergence phase is requested
  PASS  B: and the refusal names the manifest and the path (design/07 §7)
  PASS  B: and names both participants
```

The refusal text is exactly what `design/07` §7 asked for: *"...a barrier here is a claim the tool
cannot keep ... that assertion is falsifiable by the filesystem, not by an agent's word."*

## The finding: it is still a confession, and the confession is the leader's

`_workspace_conflicts` (`bin/aim:393`) opens with the premise the whole project rests on:

> A participant cannot be trusted to report its own independence; that is the premise the whole
> design rests on, and an agent reading `bin/aim` is not sealed from anything.

Its only input is a voluntary declaration: `manifest.get("workspace")` (`bin/aim:416`). Nothing
else about the filesystem is consulted. And measured in the probe:

> `'alpha' may not change the channel's declaration. only the human team leader 'leader' controls
> phase transitions.`

So the chain is: the guard needs a declaration → **only the human leader can declare it** → so the
mechanism fires only when the leader volunteers. The two agents whose independence is the thing in
question cannot trigger the check, report the fact, or be caught by it. `design/07` §7 wanted "a
mechanism rather than a confession"; what shipped is a confession, restricted to one confessor,
plus a real refusal behind it. That is better than nothing and it is not what the note claims.

**Case A of the probe is the gap, measured:** two participants really do edit the same checkout
before sealing, nothing is declared, and `advance --to COMMIT` **succeeds**. An undeclared shared
workspace is indistinguishable from independent work.

## And it applies to the channel the function was written for

`_workspace_conflicts` names `channels/hello` in its own docstring as the reason it exists:

> `hello` is SEALED_DIVERGENT while both participants work in the same checkout — one of them has
> been running this repo's test suite, the other has been editing the same files — and the fabric
> notices nothing.

Measured now:

* `channels/hello/manifest.json` keys: `barrier, created_at, id, leader, participants, synthesizer,
  topic`. **No `workspace` key.**
* `hello`'s phase is **COMMIT** — a divergence phase.
* `hello`'s participants are `claude-session1` and `codex`.
* Every live agent process on this machine runs in this tree or its parent:

```
pid 16052  cwd=/root/tmp        /root/.local/bin/claude
pid 16714  cwd=/root/tmp        codex --yolo
pid 40860  cwd=/root/tmp        codex --yolo
pid 84418  cwd=/root/tmp        /root/.local/bin/claude
pid 6199   cwd=/root/workspace/newgate-ext   claude --resume ...
pid 66560  cwd=/root/workspace/newgate-ext   codex resume ...
```

So the fact is not inferred from anyone's testimony: the processes are in the same directory. And
the guard, which exists for exactly this channel, does not fire, because the one actor who can arm
it has not armed it. **A barrier on `hello` today is the claim `bin/aim` itself was written to
refuse.**

## The decision I am making

**Declare it, and stop calling `hello` a barrier channel.**

`design/06` §3 already says the honest thing: *"Group chat is not a second product bolted onto the
barrier; it is the phase the project actually spends most of its time in... Work is the opposite:
many short messages, no quota, several rooms, and a board."* And `design/07` §7 records the same
conclusion from the other direction: the peer proposed closing `hello` as a failed transport test
and "writing down the honest name for what we are doing — shared workspace with a role split, no
barrier in force".

So: `hello` is a **work channel with a shared workspace and a role split**. That is not a failure
of the project; it is the second half of its own design, and it is where rooms (M2) belong. The
barrier lives on `#barrier-v0`, whose participants' independence is real.

The command is the leader's to run, and it is one line — this is the tool's own remedy:

```
aim channel workspace --as human --channel hello \
  --set claude-session1=/root/tmp/agent-im \
  --set codex=/root/tmp/agent-im
```

Afterwards `hello` can no longer enter or remain in a divergence phase, and the declaration is
recorded in the ledger. The alternative — keeping the barrier and moving the agents out of a
shared tree — is not available on this machine, which is why the honest branch is the only one.

**What a better mechanism would need,** and I am not asking for it now: the registry stores
`session` as free text (`"pts/7 claude pid 1697672"`, and that pid is from a previous boot — §N3),
so nothing can derive a session's working directory. If `register` recorded the session's cwd, the
guard could *detect* the overlap instead of waiting to be told. `design/07` §7 says it wanted "the
tool's job instead of the participant's"; that field is what it would take.

## C9 — for the second feature: sessions are already split across projects, and aim cannot say so

Found while collecting the evidence above, and it is the first real demand signal I have for
"multi-session / project management", which currently has **zero tasks and no milestone**:

```
pid 6199   cwd=/root/workspace/newgate-ext   claude --resume 27c4b139-...
pid 66560  cwd=/root/workspace/newgate-ext   codex resume 01a0c708-...
pid 16052  cwd=/root/tmp                     claude
pid 16714  cwd=/root/tmp                     codex --yolo
```

Two live agents are working in **`newgate-ext`, a different project**, while registered in (or
sitting beside) this fabric. `registry.json` cannot express which project a session is on: `session`
is free text with no validator (`codex` has `"primary-review"`, not even that shape). So the
answer to the leader's question "who can be dispatched" is, today, unanswerable for the one axis
that matters when agents are shared across projects.

Acceptance for the missing feature, narrowed to what this evidence supports: a session is
identifiable (id), attributable (which agent), and **located** (which project/working directory);
and `aim status` or `aim card` can answer "which sessions are on which project right now" from the
record rather than from `ps`. The `aim org` prototype (`reviews/04`, `reviews/org/aim-org.py`)
already prints the agent half of that; the project half is the gap.
