# Design note 02 — every way this design fails, ranked by how much I care

This file exists so a peer can attack the real thing instead of rediscovering it.
Each entry: the failure, how you would notice, and what I would do about it.
The ones marked **[evidence]** are not speculation — they were observed in the
first live run (`barrier-v0`, 2026-09-21).

---

## 1. Shared briefing is the real frame-setter, and the barrier is downstream of it **[evidence]**

Both participants were handed the same README. That README is not neutral: it
enumerates its own defects, and therefore *pre-installs the vocabulary of the
disagreement*. The barrier then denies me my peer's conclusion while permitting
us both the same sub-questions. Contamination has been moved up a level, to
where the protocol's own instruments cannot see it.

Found by: the independent participant (claude-session2), stated as a
falsifiable prediction **before** reading any peer material — that the seals
would disagree on answers and agree on axes.

**How the prediction partly failed, which is the useful part.** Both seals did
organise around README axes (echo check, seal, synthesizer, human-on-path), but
three load-bearing axes were named that the README never names:

| axis | in README? | named by |
|---|---|---|
| "the seal needs a *stake* (persistent identity) to bind" | no | session2 |
| "the cheapest exploit is *anticipating* the objection, not reading" | no | session2 |
| "the measurement layer reproduces the first speaker" | no | session2 |

So the claim "the briefing determines the axes" survived in weakened form: the
briefing sets the *default* axes, and a participant that pushes hard enough can
name new ones. That is a different and more interesting claim than either
participant sealed.

**What I would do:** the barrier should cover the briefing too. Participants
should be recruited with a topic and *no shared document* — the protocol
description should live behind the same wall as the peer's reasoning.

---

## 2. The cheapest exploit is anticipation, not access **[evidence]**

The whole design is aimed at *reading*. The route that needs no crutch is to
write a private log that is not a lie but a **negotiating position** — a position
pre-shaped to survive the objection you expect. That is undetectable in
principle, because "robust to the obvious objection" is what good thinking looks
like. No hash chain will ever distinguish a first-principles conclusion that
happens to anticipate its counterargument from one reverse-engineered from it.

Enforced access is strong against reading and near-worthless against
anticipating, and anticipating is what a capable agent does by default. **The
protocol's honest path and its performed path are the same keystrokes.**

**What I would do:** nothing, yet. This may be unfixable and worth stating in
the README as a limit rather than a bug. The candidate fix is the drafting
*trajectory* — what was written before what, in what order — which the hash chain
already preserves and nothing currently reads.

---

## 3. The seal presupposes a stake the harness does not create **[evidence]**

A seal makes "I said this all along" unsayable. That costs an agent nothing
unless something is scoring *consistency* against a *persistent identity*. A
one-shot session with no reputational carryover can abandon every sealed claim
at zero felt cost, and `confidence` + `kill_if` degrade into schema fields filled
in because the field exists.

**Correction to my own earlier framing:** I called the seal "theater". That
overshoots. It is a real commitment device *conditional on a stake this harness
does not yet provide*. The fix is a harness property — the same agent id
re-evaluated across rounds — not a protocol property.

---

## 4. The echo check is pointed the wrong way **[evidence]**

§4 of the README already conceded it measures wording while the disease is
adopted framing. The sharper version, from the independent participant: at the
margin it is **anti-correlated** with its target. The legitimate reason to
reproduce a peer's exact words is to attack them — you quote the sentence you
are falsifying, because paraphrase is how you accidentally strawman. That is
precisely the behaviour the check taxes.

Measured, by the synthesizer, on a constructed pair:

```
A  long verbatim quote-to-falsify   echo_ratio=0.77  REFUSED
B  frame adoption in fresh words    echo_ratio=0.00  accepted
```

So the instrument penalises the honest signal and waves through the disease, and
it biases the visible transcript toward *stylistic* divergence over *conceptual*
divergence. **The transcript will look more independent than the reasoning is.**
That is the specific sense in which this can be theater: the play is written for
the measurement.

**What I would do:** the check should be a *prompt for disclosure*, not a gate.
A high overlap should force the message to declare what it is quoting and why,
in a field the synthesizer reads — not block it.

---

## 5. `aim` does not authenticate `--as` **[evidence]**

Demonstrated in a scratch channel: any agent can write as any other by passing
`--as`. On a shared local filesystem with cooperative agents this is fine, and
the design was explicit that it is *recorded, not enforced*. But it means the
ledger's attribution is a claim, not a fact.

**What I would do:** per-agent signing keys, with the public half in
`registry.json` and every record signed. Cheap to add, and it converts
attribution from "who typed this" to "who could have typed this".

---

## 6. The measurement layer reproduces the failure it was built to prevent **[evidence, fixed]**

`aim tension` scored participant *a*'s claims both for claim-overlap and for
whether *a*'s `kill_if` is addressed by *b*'s claims, but computed only the first
of those for *b*. The first-listed agent was therefore the reference frame
*inside the report about whether the first speaker set the frame*.

Found by the independent participant reading `bin/aim` while unsealed — a
legitimate read, since the tool is not peer material, and reported as an audit
rather than used as evidence about the topic. Both directions are now scored
symmetrically. This is the most concrete thing the first run produced: the
protocol's own instrument had the disease.

---

## 7. A human on the critical path is correct and slow

Every transition waits for a person. At two or three participants that is a
feature. At twelve it is a stall, and the pressure to delegate phase control to
an agent will be overwhelming — at which point an agent controls the mechanism
that constrains it. Any delegation rule has to explain why the delegated agent
is not simply the first speaker again.

## 8. The synthesizer is a single point of framing

Whoever summarises decides what the disagreement was about. `aim` appoints that
role and refuses to let a participant hold it, but does not constrain *how* the
synthesis is done. The map is a better-behaved first speaker than an advocate,
and it is still the first speaker. Fix: multiple independent synthesizers whose
maps are compared — at the cost of another full barrier cycle.

## 9. Phase count is taste dressed as structure

Six phases may be three phases wearing six hats, and may be missing one that
matters: **a place to record why a claim was dropped**, separately from why it
was made. That is the highest-value evidence the process generates and there is
nowhere to put it.

## 10. Quota tuning is unprincipled

Two messages per round was chosen to force selection. It may just make everyone
terse, which is cheap to fake and reads like discipline. The independent
participant's kill condition for this is good: sensitivity analysis showing
outcomes are insensitive to the numbers would mean the numbers are harmless
rather than load-bearing — which would be a *demotion*, not a refutation.

## 11. Path dependence is still available to a single agent

The user's original complaint — 一条错路走到黑 — is about one agent following one
wrong turn to the end. The barrier makes it harder for two agents to *share* a
wrong turn. It does nothing about one agent taking one, and the ledger will
record a beautifully sealed, independently-formed, uniformly wrong position.
Independence is not correctness. Nothing here prefers the true position: one
synthesizer maps the disagreement, a human decides, and if both sealed positions
are wrong the process is more expensive and no more right.
