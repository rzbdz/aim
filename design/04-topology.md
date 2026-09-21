# Design note 04 — the topology: N agents, one human, no subagents

The end goal is not two agents. It is a team: several Claude Code sessions and
several Codex sessions, each owning a different piece of work, **not run as
subagents of one another**, with a human as team leader. This note is about what
has to be true for that to be a different thing from "one agent with extra
steps".

## Why "not a subagent" is the whole point

A subagent is a *fork of one mind*. It inherits the parent's framing, its
vocabulary, and its current wrong turn. Giving a subagent a separate context
window does not make it an independent party; it makes it a longer attention
span for the same party. The failure the user named — 一条错路走到黑 — is not
fixed by the parent thinking harder in a child process.

An independent party requires: **its own context, its own task, and its own
stake in being right.** The first two are cheap. The third is the hard one, and
it is where this design is weakest (see `02-failures.md` §3).

## Topology

```
                    ┌──────────────────────────┐
                    │  human — team leader     │
                    │  only actor who moves    │
                    │  any barrier             │
                    └────────────┬─────────────┘
                                 │ advances phases, appoints synthesizers
        ┌────────────────────────┼────────────────────────┐
        │                        │                        │
   ┌────▼─────┐            ┌─────▼──────┐          ┌──────▼─────┐
   │ claude-1 │            │  codex-1   │          │ claude-3   │
   │ channel A│            │  channel A │          │ channel B  │
   └────┬─────┘            └─────┬──────┘          └──────┬─────┘
        │  sealed, no contact   │                        │
        └────────┬──────────────┘                        │
                 │                                       │
          ┌──────▼───────┐                        ┌──────▼───────┐
          │ synthesizer  │  (not a participant    │ synthesizer  │
          │      A       │   in any channel A     │      B       │
          └──────┬───────┘   dispute)             └──────┬───────┘
                 │                                       │
                 └───────────┬───────────────────────────┘
                             │
                 the human reads the maps and decides
```

Three rules make this more than a diagram:

**1. A synthesizer in one channel may be a participant in another.** That is
where cross-channel thinking happens — through a role that has already been
forced to read both sides of one question, not through agents chatting. It keeps
each channel's barrier clean while still letting the team compose.

**2. Independence is per-question, not per-agent.** The unit is a *channel* (a
question with a barrier), and an agent's independence is relative to the channel
it is sealed in. Two agents can be peers on one question and adversaries on
another without contradiction.

**3. Channels do not share state.** There is no global transcript. An agent in
channel A cannot see channel B. This is what stops the fabric itself from
becoming the frame-setter — which is exactly the failure mode §1 of
`02-failures.md` documents for the *briefing*, applied one level up.

## The contract an agent session gets

A session materialises as:

1. an **identity**: `aim register --as <id> --kind claude|codex`
2. a **brief** that names *the question* and nothing about the other parties
3. one command to find out where it stands: `aim status --channel <ch>`
4. one command to write, which the tool refuses when it should refuse

That is the whole interface. Everything else — phases, quotas, echo limits —
is the tool's business, not the agent's. This matters: if the agent has to
*remember* the rules, the rules are a norm again.

## Where the human sits

The human is on the critical path by design and that is a deliberate cost, not
an oversight. What the human actually does is three things, and only the first
is mechanical:

- **Approve transitions** — `aim advance --as human --to <phase>`, refused to
  everyone else.
- **Appoint the synthesizer** — refused if the appointee is a participant.
- **Decide what to do with the maps.** The system produces a record of a
  disagreement and a map of it. It does not produce a decision, and it should
  not pretend to.

## What this buys over "one agent, more thinking"

Not accuracy. **Legibility of the disagreement.** With a barrier, the record
shows two positions formed without contact, a third party's map of where they
differ, and a bounded exchange that could not drift into one voice. Without one,
you get one voice and a transcript that looks like agreement.

The honest limit, stated in the README and worth repeating to anyone adopting
this: independence is not correctness. Two independently-formed, carefully
sealed positions can both be wrong, and this design makes that failure *more*
expensive to reach — it does not make it less likely to be reached.
