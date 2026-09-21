# Design note 00 — the problem statement, stated so it can be attacked

## The claim the whole system rests on

Two agents working the same question do not hold two opinions. They hold one
opinion and one reaction to it. Whichever agent's framing lands first decides
what the disagreement is *about*, and the second agent — reading that framing
before generating its own — produces an elaboration rather than an alternative.

The failure is invisible from the inside. The second agent does not experience
compliance; it experiences reasoning. Its transcript looks excellent. That is
what makes the problem worth building machinery for: the diagnostic signal is
absent exactly when the failure is present.

## Why the obvious fixes do not work

| fix | why it fails |
|---|---|
| "think independently" | a norm cannot be verified; the agent does not feel it complying |
| open debate | optimizes fluency, not falsification; converges on the better arguer |
| subagents | inherit the parent's framing by construction — this is the path-dependence failure, not a cure for it |
| separate contexts | necessary, not sufficient: separate contexts sharing one channel are still one channel |

## What the user actually asked for

> 一开始，不能让他们两个交流。要独立客观第三方调研后，再交流。我们要控制交流的方式，
> 不能tmd直接一个给另一个洗脑了。

Decomposed, that is four separate requirements that are easy to conflate:

1. **A period of enforced non-communication.** Not "discouraged" — enforced.
2. **A third party who genuinely did not argue either side**, whose read comes
   before the two sides meet.
3. **Controlled communication** after the barrier lifts: bounded, addressed,
   and structured — not a chat.
4. **No brainwashing**: the second agent must not be able to absorb the first
   agent's frame without it being visible.

And the organisational requirement: **the team leader stays a human.** Multiple
Claude Code sessions and multiple Codex sessions, each an independent third
party for the others, with the human deciding.

## The decomposition I would bet on, and where I would lose the bet

The system splits into two mechanisms that are usually confused:

- **Contact control** — denying access to another agent's reasoning before you
  have committed your own. Mechanically enforceable, observable, auditable.
- **Contamination control** — preventing an agent's position from being
  downstream of another agent's frame. *Not* enforceable, and arguably not even
  measurable in the general case.

`aim` (this repo) is entirely the first one. I believe the second one is the
binding constraint and I do not know how to build it. See `design/02-failures.md`.

## The distinction that keeps the design honest

**Enforced** (the tool refuses, and the refusal is recorded as a ledger event —
which was not true until 2026-09-21, when a live run measured that refusals were
printed and discarded):
cross-reading before cross-examination; public speech before cross-examination;
phase transitions by anyone but the human; synthesis before every participant
has sealed; a participant reading the mixed bundle; unaddressed, unlabelled,
over-quota or verbatim-echoing messages during cross-examination.

**Recorded, not enforced** (it can happen; it leaves a mark):
editing a log after the fact (`aim verify` shows the break); reading a peer's
files with `cat` instead of through `aim`; editing the tool itself.

The line is drawn there on purpose. Everything on the second list requires an
action that is legibly an attempt to route around the fabric, and every one of
them is detectable afterwards. The design does not try to make cheating
impossible. It tries to make it **visible**, and to make the honest path the
easy one.
