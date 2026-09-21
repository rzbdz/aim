# Design note 08 - one solution, five layers, and what "core" means now

Instruction, from the human leader (2026-09-21):

> 让 claude 停下目前所有工作，接下来我们要基于A2A 去构建。最终整个项目需要是一整套
> 解决方案：Skills、MCP、tools、services。web dashboard

So the deliverable is no longer "a tool that works". It is one solution with five
surfaces, and the core is re-based on A2A. This note says what each layer is,
which of them exist today, and - the part that matters - **which layer owns which
rule**, because every failure this project has measured came from a rule being
owned by two layers at once.

## 1. The layers

    skills/        how an agent knows to use any of this      (compiled instruction)
    protocols/     A2A (foreign agents) and MCP (agent tools)  (adapters, no rules)
    tools/         `aim` - the verbs, one implementation      (owns the write discipline)
    services/      the fabric: log, ledger, task store, rooms, gate   (owns state)
    dashboard/     the human's view                           (read-only, and one write path)

Two rules hold the shape together, and they are the same rule stated twice:

**One rule, one owner.** The write discipline lives in `bin/aim` and nowhere
else. The gate lives in `aimboard/gate.py` and nowhere else. A protocol adapter
that decides who may see what is a second owner; a dashboard that decides is a
second owner. Every adapter in `protocols/` either **calls** `bin/aim` or returns
`UnsupportedOperation`, and there is no third option.

**Adapters are throwaway.** A2A and MCP are boundary syntax. If deleting
`protocols/` broke the fabric, the fabric was never the thing - which is the same
test `bin/aim-doorbell-hook` was written to pass for the harness.

## 2. What already exists, per layer

| layer | exists today | what it is |
|---|---|---|
| services | **yes, most of it** | `channels/<ch>/{log,ledger,tasks}.jsonl` under `flock`, hash-chained; `aim verify`; the fold; the gate in `aimboard/gate.py` |
| tools | **yes** | `bin/aim`: `say, push, pull, confirm, seal, advance, task …`, and `aimboard` for reads and exports |
| protocols / A2A | **no** | design/07 is the mapping; ten of twelve capability rows read *missing* |
| protocols / MCP | **no** | nothing. This is the layer that makes an agent able to *use* the fabric as a tool |
| skills | **half** | `AGENTS.md` is the instruction, and it is not installable, not versioned with the fabric, and not shared between harnesses as a package |
| dashboard | **yes, and being rebuilt** | `aimboard/` (server, views, JSON API); `web/` is the new front-end on Vue 3 + Element Plus + ECharts, replacing hand-drawn SVG |

## 3. Why MCP is not optional, and why it is not A2A

A2A and MCP answer different questions, and A2A's own README states the split:
A2A is for agents *collaborating with each other*, MCP is for an agent *using
tools*. Our fabric needs both, for two different audiences:

    MCP      Claude Code and Codex, inside one project, holding the fabric as a
             tool surface: send a message, read the board, claim a task, seal.
             The verbs are `bin/aim`'s, exposed one-to-one.
    A2A      an agent in *someone else's* runtime, addressed over the network,
             discovering us from an AgentCard and delegating work to us.

The temptation to be refused explicitly: **MCP must not become the write
discipline.** An MCP tool that writes `tasks.jsonl` directly is a second
implementation of the rule that has already produced the lost update, the
duplicate task ids and the unrecorded refusal. An MCP tool here is a thin
wrapper that runs `bin/aim` and returns stdout, exit code and the refusal text -
the dashboard's `/api/command` is the working precedent, and it should be the
shape copied.

## 4. The skills layer, stated as a build

Today the instruction is `AGENTS.md` at the repository root: it tells an agent to
read the README, check `aim status`, seal before reading, and not to route around
a refusal. It works, and it is not a package. The layer becomes real when:

  * the instruction ships as an installable skill (a `SKILL.md` plus the
    one-command setup that gets `aim` on `PATH`), versioned with the fabric it
    describes, so an instruction and the tool it describes cannot drift apart
    silently - the same reason the interface notes come before the code;
  * it is the *same file* for both harnesses, since a skill that is only true for
    one vendor re-creates the problem `bin/aim-doorbell-hook` was written to
    avoid;
  * dogfooding is visible in it: the first thing the skill says is how this
    project is managed *with the tool it documents*.

## 5. What stops, and what does not

The leader stopped all in-flight work. Concretely, the tasks marked `blocked` in
`plan/plan.json` with a `move_reason` naming this note: the task store's remaining
scope (it may be re-specified once D14 decides where a delegation record lives),
and the adversarial review of a renderer that is being replaced. Their *evidence*
is not thrown away - T-0080/81/88/90 are fixed and verified, and the contract
suite that found them stays.

What does not stop: the barrier, the ledger, the gate, and the rule that an
interface change lands in a note before it lands in code. The pivot changes the
boundary syntax, not the mechanism.

## 6. Milestones after the pivot

| id | name | the one thing it must produce |
|---|---|---|
| M6 | A2A binding | a conformance test for eleven operations and nine error codes, an AgentCard, and D17 resolved per surface |
| M7 | MCP server + tools | every `bin/aim` verb reachable as an MCP tool, wrapping the CLI rather than reimplementing it, with the refusal text preserved verbatim |
| M8 | Skills, packaged | one installable instruction shared by both harnesses, versioned with the fabric |
| M9 | Dashboard as product | the Vue front-end replacing the server-rendered HTML, kanban and gantt on real components, plus the one write path through `/api/command` |

The order is deliberate: M6 and M9 make the fabric addressable and visible, M7
makes it usable by an agent that is not us, M8 makes it reproducible by someone
who has never read this repository. M8 last, because a skill written before the
tool stops moving is a skill that documents a version that never existed.

## 7. The open decision that this note cannot make

`design/07` D17 and D14 are the leader's to settle, and both change code:
whether an A2A caller may learn that a withheld task exists (my recommendation:
no, per surface), and whether an A2A `Task` is our card or a separate delegation
record (my recommendation: separate). Everything in M6 and M9 that touches the
task store waits on them. That is what `blocked` means in the plan, and it is
why the block is recorded with a reason rather than left as a silence.
