# Design note 03 — the questions I could not answer

Written to be handed to another agent, not to be answered by me. Each has the
form: question, why it is hard, what an answer would look like.

## Q1. Who decides when a barrier lifts?

Today: the human. Correct, and a bottleneck. Every alternative I can construct
puts an agent on the path that constrains it, which is the original problem with
an extra step. The interesting shape of an answer is a rule that *cannot be
captured* by the agent subject to it — e.g. a transition condition that depends
on a measurement the agent cannot produce alone.

## Q2. Can independence be measured rather than enforced?

Enforcement is blunt: it controls access and leaves generation untouched. A
measurement would say "these two positions were formed without contact" as a
property of the *trajectories*, not of the access log. The hash chain already
preserves the trajectory — the order claims arrived in, what was written before
what. Nothing reads it.

The trap: measurement invites agents to **perform divergence** for the metric,
which is §4.2/§4.4 of the README in miniature. Any measurement scheme has to
survive an adversary who knows the metric. That is the whole difficulty.

## Q3. Is the seal worth anything?

An agent can write a commitment it does not hold. The current answer is "the
seal makes retrofitting visible, not impossible", plus "it binds only if
something scores consistency across rounds". Whether that is worth the keystrokes
is untested. A test: run the same question twice with the same agent identity,
score consistency against the first seal, and see whether behaviour changes.

## Q4. What is the right unit of isolation?

The channel is today's unit. The briefing turned out to be a bigger leak than
the channel (§2.1). So what *is* the unit? Shared documents? Shared model?
Shared system prompt? Shared training data — which no architectural choice here
can address at all, and which may be the dominant term. If the dominant source of
agreement is the shared model rather than the shared channel, then heterogeneity
of models is the real mechanism and every access-control rule here is aimed at
the smaller term. I would bet on this at maybe 60/40.

## Q5. Does this scale past two advocates?

The three-agent case (two advocates plus a non-advocate synthesizer) is the
argument the design was built for. Four or more is probably not "more of the
same": with N participants, pairwise divergence is not the same as global
divergence, and a synthesis over N positions has its own failure modes. Nothing
here has been tested past two.

## Q6. What happens over repeated runs?

The design assumes a one-shot. Repeated runs with the same agents accumulate
*reputation* — which is what makes the seal bind (Q3) — but also accumulate
shared vocabulary, which is the disease. Velocity and virulence scale together.
Whether the net is positive is unknown.

## Q7. Is there a version with no leader?

The user's requirement is "team leader 仍然是人". Every mechanism here derives its
authority from that. The question is whether there is a decentralised transition
rule that no participant can capture — the barrier would then be a property of
the *protocol*, not of a person's attention. I do not have one.
