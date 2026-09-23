"""The wire shape the front-end reads.

One payload, assembled once, with every access rule applied before anything is
serialised. The browser is not trusted to hide what it was sent - a client-side
filter is a suggestion, and this project has a word for suggestions that are
enforced somewhere else.
"""
import ast
import collections
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from .a2a import ERROR_CODES, NATIVE_ONLY, TASK_STATES, error_reason
from .const import DIVERGENCE, STATUSES, TERMINAL
from .revision import default_dist, describe as describe_revision
from .fold import drift, report_data, task_history, fold_tasks, merge_plan
from .gate import (conversation_view, gate_channel, may_see_peer_secrets,
                   stuck_tasks, visible_tasks)
from .primitives import read_seal_claims


# Every vocabulary a surface draws. Imported where the code already owns the
# list, spelled out only where it does not -- a second copy of the vocabulary is
# the defect T-0214 names, so the rule for adding a row here is "find the
# constant, do not retype the values".
#
# Three of the lists have no constant to import, and that is a finding, not a
# permission to invent:
#
#   * the phase list. `const.DIVERGENCE` is a *subset* (the three sealed
#     phases) and `a2a.DIVERGENCE_PHASES` is the same subset repeated, so the
#     registry would be describing three phases of six. `bin/aim`'s `PHASES` is
#     the whole lifecycle but it is a script, and importing a script to read a
#     constant is how the module graph acquires a dependency on the CLI. Named
#     in the round's report: `const.PHASES` is a two-line change in a file this
#     agent does not own.
#   * the provenance values. `fold.merge_plan` assigns them inline as
#     `"store + seed"`, `"seed only (not yet in the store)"` and `"store only"`,
#     next to the branch that chose them; extracting them is that file's call.
#   * the cross-examination move kinds. `bin/aim` holds `CROSS_EXAMINE_KINDS`
#     (the acceptance set) and the channel log records `kind`; the tool's own
#     `aim say` documents the moves. Same script problem as the phases.
#
# The label is the human half and the description says what the token *does to
# you* -- what it lets you do, or what it refuses. A token the map cannot
# explain is a token a surface has to guess at, which is the whole card.
CONCEPTS = (
    # (token, group, label, description). `group` is the surface family the
    # token belongs to, so a renderer can pull one vocabulary without the rest.
    ("SEALED_DIVERGENT", "phase", "Sealed",
     "Positions are being formed in private: you may not read a peer's reasoning, "
     "and a request to is refused out loud."),
    ("COMMIT", "phase", "Committed",
     "Every position is written down as a claim with a confidence and a falsifier, "
     "and the barriers are still up."),
    ("SYNTHESIS", "phase", "Synthesising",
     "A third party is mapping where the committed positions diverge; the seals are "
     "still closed."),
    ("CROSS_EXAMINE", "phase", "Cross-examining",
     "The seals are open and the positions answer each other, as labelled moves."),
    ("RESOLVE", "phase", "Resolving",
     "The disagreement is being decided; the channel accepts no new arguments."),
    ("CLOSED", "phase", "Closed",
     "The channel is finished. It is read for its record and takes no new moves."),
    ("draft", "visibility", "Draft",
     "Not published: it is withheld from the channel's participants while the seal "
     "is up, and a stranger may not read it at all."),
    ("published", "visibility", "Published",
     "Deliberately released, so the phase no longer gates it."),
    ("seed only (not yet in the store)", "provenance", "From the plan, not recorded",
     "The value comes from a plan file and no act in the record has confirmed it. "
     "It is a statement of intent, not a measurement."),
    ("store + seed", "provenance", "Recorded, from the plan",
     "The record has events for this item; the plan file filled the fields no "
     "event carried."),
    ("store only", "provenance", "Recorded",
     "Every value here came from an act in the record."),
    # Move kinds: what a message in the public channel is *doing*. The register
    # is the point -- a proposal invites a decision, a claim invites a falsifier,
    # and an unlabelled remark does neither.
    ("evidence", "move", "Evidence", "Something a reader can check."),
    ("objection", "move", "Objection",
     "Asserts the position is wrong, with a reason the author would have to answer."),
    ("rebuttal", "move", "Rebuttal", "Answers an objection to a position already made."),
    ("question", "move", "Question", "Asks for what is missing before deciding."),
    ("concession", "move", "Concession",
     "Gives ground explicitly, so the record shows the position moved and why."),
    ("proposal", "move", "Proposal", "Offers an action for the leader to accept or refuse."),
    ("note", "move", "Note",
     "Context with no claim attached: it commits nobody, so it decides nothing."),
    ("T-", "id", "Work item",
     "Minted by `aim task new`; every pointer at a work item -- comments, blockers, "
     "the plan -- names it by this id."),
    ("M", "id", "Milestone",
     "A dated group of work items in the plan file; the count on screen comes from "
     "the record, never from the label."),
    ("D", "id", "Decision",
     "A recorded decision, which is what a disagreement leaves behind when it is "
     "resolved."),
    ("R", "id", "Revision / return",
     "An item sent back with a reason, so the change of mind is a recorded move "
     "rather than a silent edit."),
    ("barrier", "refusal", "The barrier",
     "You asked for something the phase withholds. Recorded with the phase it "
     "happened in, because the temptation is the evidence."),
    # `form`'s text is a2a's own sentence: whether A2A can express this class is
    # the binding's claim to make, and a copy here would be a second place for it
    # to drift. See `a2a.NATIVE_ONLY`.
    ("form", "refusal", "Malformed request",
     NATIVE_ONLY["form"]),
    ("unrecorded", "refusal", "Class not recorded",
     "The refusing site did not say whether this was the barrier or a malformed "
     "request. A weaker claim than either, and printed as one."),
)


def concept_group(group):
    """One group of the registry, generated where the code owns the list.

    The two generated groups are generated on purpose: the A2A task states, the
    nine error types and the statuses are already tables in `a2a` and `const`
    with the spec cited above them, and T-0214's rule is that the label source
    *is* the table the code reads. A hand-written label per error code would be a
    second copy of a list the binding's own test asserts against (`ERROR_CODES`).
    """
    if group == "status":
        return {token: {
            "label": token.title(),
            "description": ("Terminal: no further transition is expected from it."
                            if token in TERMINAL else
                            "Not terminal: the card is still expected to move."),
            "group": "status"} for token in STATUSES}
    if group == "a2a":
        out = {}
        for state in TASK_STATES:
            out[state] = {
                "label": state[len("TASK_STATE_"):].replace("_", " ").title(),
                "description": "An A2A task state. `STATUS_TO_STATE` in aimboard/a2a.py "
                               "says which of ours reaches it and why the rest cannot.",
                "group": "a2a"}
        for name, code in ERROR_CODES.items():
            out[name] = {
                "label": error_reason(name).replace("_", " ").title(),
                "description": f"A2A error type, JSON-RPC code {code}.",
                "group": "a2a"}
        return out
    return {token: {"label": label, "description": description, "group": group}
            for token, g, label, description in CONCEPTS if g == group}


# Where the CLI that owns these vocabularies lives, resolved against this
# package rather than the process's cwd: a board started from another directory
# would otherwise publish an empty state machine and look like a build that had
# lost it. Not `state["root"]` either -- `AIM_ROOT` names the *fabric* (the
# channels and the plan), and a fabric read from a temp directory is still read
# by the `aim` beside this file.
_CLI = Path(__file__).resolve().parent.parent / "bin" / "aim"


def _cli_constant(path, *names):
    """Read constants out of `bin/aim` without importing `bin/aim`.

    The Help pane had to write two vocabularies down because the payload
    carried neither: the statuses' legal moves and the refusal classes. Both
    live in the CLI -- `TASK_FLOW` beside the `advance` that enforces it, the
    `cls` default and its call sites in `die`/`_record_refusal` -- so dropping
    a second copy into the payload or into the page is the drift T-0214 names,
    and importing the script to reach them is the module-graph dependency this
    file already refused for `PHASES` (see the note above `CONCEPTS`).

    So the module is *parsed*, not run: `ast.literal_eval` on the assignment
    the CLI already made. The load-bearing assumption is that `bin/aim` has no
    top-level side effect -- measured, not assumed: every statement at its top
    level is an import, an assignment, a function or class definition, or the
    `__main__` guard, so no module is loaded and no CLI branch can run.

    A constant that is not there is not invented: the caller publishes the
    vocabulary empty rather than a guess, which is visible, where a guessed
    edge is a claim about what the tool will accept.
    """
    src = Path(path)
    if not src.exists():
        return {name: None for name in names}
    found = dict.fromkeys(names)
    for node in ast.parse(src.read_text(encoding="utf-8")).body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id in found:
                try:
                    found[target.id] = ast.literal_eval(node.value)
                except ValueError:
                    # A constant built by an expression is left unreported
                    # rather than half-read: an empty map here draws no moves,
                    # which a reader can see, and a partial one would draw a
                    # table that has silently lost the restriction.
                    found[target.id] = None
    return found


def task_flow(cli=None):
    """The task state machine and the statuses, read from the CLI that owns it.

    `const.STATUSES` is already published as `statuses` and is the vocabulary
    this board folds (a status the tool cannot reach is still worth knowing
    about); `TASK_STATUSES` is the list `aim task move` will *accept*, and the
    two were identical on 2026-09-22 (7 values each) -- which is not a
    guarantee either side is entitled to, so both keys are published rather
    than one derived from the other. The `next` list is what the refusal
    actually quotes back: `(allowed: review, blocked, dropped)`.
    """
    got = _cli_constant(cli or _CLI, "TASK_FLOW", "TASK_STATUSES")
    flow = got.get("TASK_FLOW")
    if not isinstance(flow, dict):
        flow = {}
    accepts = got.get("TASK_STATUSES")
    if not isinstance(accepts, list):
        accepts = []
    return {
        "flow": flow,
        "accepts": accepts,
        # A status with no entry in the table is not a status with no moves:
        # it is a status the tool would refuse as a target and drop the card
        # into by default. Saying which one it is beats a `v-for` over
        # `board.statuses` printing "nothing" for a row the CLI does not have.
        "unconstrained": [s for s in STATUSES if s not in flow],
    }


def refusal_classes(cli="bin/aim"):
    """Every class a ledger row can carry, with what the class means.

    Two of the three are a *default* rather than a list, so there is nothing in
    the CLI to import and this is where the vocabulary has to be declared: the
    set below is the same one `bin/aim` documents ("`class` is
    `barrier`|`form`|`unrecorded`", README §3) and files rows under, and the
    meaning of `form` is `a2a.NATIVE_ONLY`'s own sentence, because a class A2A
    cannot express is the binding's claim to make. Each row says where its
    class comes from, so a reader can tell a class a site stated from the
    default that means the site did not.
    """
    return [
        {"class": "barrier", "from": "stated at the site",
         "where": "enforced by the call that guards the barrier"},
        {"class": "form", "from": "stated at the site",
         "where": "a malformed request, rejected before the phase was consulted"},
        {"class": "unrecorded", "from": "the default in `_record_refusal`",
         "where": "the refusing site did not state a class"},
    ]


def concepts():
    """The registry: every token a surface renders, said once, by the server.

    `web/src/concepts.js` is being written against this right now. The payload is
    a plain token -> `{label, description, group}` map at a stable key, because
    the front-end is being written against it in parallel and two shapes for one
    contract is what T-0214 exists to stop; the richer per-token help (`what`,
    `consequence`, `next`) stays in the front-end, where the anchors
    `help#concept-<id>` already live.
    """
    out = {}
    for name in ("phase", "status", "visibility", "provenance", "move", "id",
                 "refusal", "a2a"):
        out.update(concept_group(name))
    return out


def _canon(value):
    """One spelling for one value, so two runs of the same bytes hash the same."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                      default=str)


def scoped_digests(payload, conversation, drift_rows, blocked_rows, stuck_rows):
    """One digest per view, so a pane can invalidate on what it actually reads.

    The global `digest` is a fingerprint of the *files* (`fabric.fabric_digest`),
    so it moves for any write anywhere -- an outbox note, another room's
    message, a registry edit from an unrelated seat -- and the items list
    refreshes over all of them. A scroll position lost to a write the reader
    never asked about is the cost.

    So each scope is hashed over the slice of the payload that view renders, from
    a stable canonicalisation (a payload is a dict; dict order is insertion order
    and therefore not a property of the data). A pane that sees its own digest
    unchanged can skip the refetch.

    A scope can *over*-invalidate and that is deliberate: `plan` covers the
    milestones and the drift rows a plan page draws, `tasks` the task map and the
    one number that is about the whole set, `reports` the fold, `conversation`
    the gated conversation view plus the mail and the room log's own counts, and
    `barrier` the seals, refusals and phase the audit page exists for. The
    failure to avoid is a pane that does not move when its own data changed; a
    pane that moves for a neighbour's write is only the cost we already had.
    """
    tasks = payload.get("tasks") or {}
    # The `mail` folded into `conversation` is the outbox *counts*:
    # `fabric.load_mail` (`aimboard/fabric.py:171`) walks `root / "outbox"` and
    # only outbox -- it never opens `rooms/`, which `fabric.load_rooms` reads into
    # its own key. This comment used to say the opposite ("derives them from
    # `rooms/*.json`") and to name an `A2A_SCOPES` that is not in this repo; both
    # were wrong while the paragraph's conclusion was right, which is the worst
    # shape a wrong comment takes, because the reader cannot tell which half to
    # trust. The conclusion stands: taking the whole key costs an outbox write
    # re-hashing the conversation scope, which is cheap and errs toward a stale
    # pane never being possible.
    barrier = [{"id": c.get("id"), "phase": c.get("phase"), "sealed": c.get("sealed"),
                "refusals": c.get("refusals"), "concessions": c.get("concessions")}
               for c in payload.get("channels") or []]
    return {
        "tasks": hashlib.sha256(_canon([
            tasks, payload.get("withheld_tasks"), payload.get("unplaced_events"),
            {"phase": payload.get("phase")},
            # T-0252: the phase's *provenance* is hashed with the phase, because a
            # reader who switched seats and got the same phase from a different
            # channel has been shown a different statement, and a scope that did
            # not move would let a pane keep the old one on screen.
            {"phase_channel": payload.get("phase_channel")},
            sorted(payload.get("statuses") or []), sorted(payload.get("terminal") or []),
        ]).encode()).hexdigest(),
        "conversation": hashlib.sha256(_canon([
            conversation, payload.get("mail"), payload.get("unacked"),
        ]).encode()).hexdigest(),
        "reports": hashlib.sha256(_canon([
            payload.get("reports"), payload.get("reports_scope"),
        ]).encode()).hexdigest(),
        "plan": hashlib.sha256(_canon([
            payload.get("milestones"), payload.get("as_of"), drift_rows,
            # The tree itself, not one card's row in it, because the risk half of
            # a plan page is what a milestone's *set* of items adds up to.
            [(tid, t.get("milestone"), t.get("due"), t.get("start"),
              t.get("estimate_hours"), t.get("status"))
             for tid, t in sorted(tasks.items())],
        ]).encode()).hexdigest(),
        "barrier": hashlib.sha256(_canon([
            barrier, payload.get("root"),
        ]).encode()).hexdigest(),
        "stuck": hashlib.sha256(_canon(
            [stuck_rows, blocked_rows, payload.get("reports_scope")]).encode()).hexdigest(),
    }


def channel_payload(state, ch, viewer):
    secrets = may_see_peer_secrets(state, ch, viewer)
    sealed = []
    for who in ch.get("participants", []):
        seal = ch["seals"].get(who)
        if not seal:
            sealed.append({"agent": who, "sealed": False})
            continue
        claims = read_seal_claims(seal)
        entry = {"agent": who, "sealed": True,
                 "digest": (seal.get("digest") or seal.get("private_log_sha256") or ""),
                 # Counted from the same list that is published below, not from
                 # `seal["claims"]` directly. T-0247 measured the two disagreeing:
                 # a seal whose `claims` is the bare string `"not-a-list"` counted
                 # as `(10 claims)` -- the length of the string -- and then raised
                 # `'str' object has no attribute 'get'` on the way to publishing
                 # them, so `/api/state` was a 500 for the leader and for every
                 # viewer who may see the seal, while the CLI printed a claim
                 # count it had composed rather than measured.
                 "claims_count": len(claims),
                 "ts": seal.get("ts", "")}
        # your own seal is yours; a peer's is withheld while the channel is sealed
        if secrets or who == viewer:
            entry["claims"] = [{"id": c.get("id", ""), "claim": c.get("claim", ""),
                                "confidence": c.get("confidence", ""),
                                "kill_if": c.get("kill_if", "")}
                               for c in claims]
        else:
            entry["withheld"] = True
        sealed.append(entry)
    return {
        "id": ch["id"], "topic": ch["manifest"].get("topic", ""), "phase": ch["phase"],
        "round": ch["round"], "leader": ch["leader"], "synthesizer": ch["manifest"].get("synthesizer", ""),
        "participants": ch["participants"], "history": ch["history"],
        "sealed": sealed, "chain": ch["chain"], "tasks_recorded": len(ch["tasks_recorded"]),
        "tasks_store_exists": ch["tasks_exists"],
        # The fold counts events it could not place (a `moved` for a task whose
        # `created` never appeared, say) and nobody was reading the number, which
        # is the "well-formed and missing a fact" failure this project keeps
        # finding: a log that silently drops events still draws a clean board.
        "tasks_unknown_events": ch.get("tasks_unknown_events", 0),
        "refusals": [{"ts": r.get("ts", ""), "agent": r.get("agent", ""),
                      "action": r.get("action", ""), "class": r.get("class", ""),
                      "phase": r.get("phase", ""), "reason": r.get("reason", "")}
                     for r in ch["refusals"]],
        "concessions": len(ch["concessions"]),
        "friction": ch.get("friction", []),
    }


def phase_channel_provenance(state, viewer, channel):
    """Where the payload's top-level `phase` was read from, and what chose it.

    T-0252. `phase` is the phase of `gate_channel`'s default channel, and that
    function answers a question about *tasks* ("which channel's phase governs a
    task that does not name one", `gate.py:37`), so on a root with several
    channels the reader is shown one channel's phase with nothing naming it. The
    channel is the provenance and it is a fact the payload already holds; the arm
    is the other half, and it is derived here rather than asserted, because
    "the viewer participates in it" and "no channel has them, so the store arm
    picked the first channel with a store" are different statements about the
    same number and the difference is the whole finding.

    Measured on the live root 2026-09-23: three of the four seats resolve through
    participation and land on three different channels; the fourth, the leader,
    participates in none and resolves through `tasks_exists`.

    `id` is `""` when the root holds no channel at all -- the same null the header
    prints as `-`, so the provenance and the value it explains cannot disagree.
    """
    if not state.get("channels"):
        return {"id": "", "arm": "no channel"}
    if viewer in channel.get("participants", []):
        return {"id": channel.get("id", ""), "arm": "participation"}
    for ch in state["channels"]:
        if ch.get("tasks_exists"):
            return {"id": channel.get("id", ""), "arm": "tasks_exists"}
    return {"id": channel.get("id", ""), "arm": "first channel"}


def payload(state, viewer, register, generated_at=None, as_of=None, digest=None, write=None, read=None):
    generated_at = generated_at or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
    channel = gate_channel(state, viewer, {})
    tasks, hidden = visible_tasks(state, viewer, channel)
    as_of_date = as_of or state["as_of"]
    # `visible_tasks` is the one implementation of "may this viewer see this id",
    # so every other key that names ids is filtered through *its* answer rather
    # than re-deriving the rule -- two implementations of an access rule is the
    # bug class `gate.conversation_view` was written to end. `hidden` is the
    # published count; this is the set behind it.
    withheld_ids = set(state["tasks"]) - set(tasks)
    # Every channel keeps its own `tasks_recorded`, and reading `channels[0]`
    # compared the plan against whichever channel happened to sort first --
    # `barrier-v0`, which holds 2 of the 71 -- so the drift list was computed
    # against almost no store at all. `fabric.load` unions the channels for the
    # board; drift is a statement about the same store, so it unions them here.
    recorded = {}
    for ch in state["channels"]:
        recorded.update(ch["tasks_recorded"])
    drift_rows, drift_withheld = [], 0
    for row in drift(state["seed_tasks"], recorded):
        if row["id"] in withheld_ids:
            # A drift row names a task id. Emitting one the viewer may not see
            # would be this payload serving what `visible_tasks` withheld, which
            # is the route around a refusal this file exists to not be.
            drift_withheld += 1
            continue
        drift_rows.append(row)
    # The report is a statement about the fabric, so it is folded over the whole
    # task set: a total that changes with the seat you read it from is not a
    # total, it is one seat's view (`reviews/05`, S2). Only counts may be
    # published to everyone, though -- the per-item `blocked` rows carry titles,
    # so they are filtered through the same rule as everything else below.
    reports = report_data(state["tasks"], state["milestones"],
                          datetime.fromisoformat(as_of_date).date())
    blocked_rows = [row for row in reports["blocked"] if row["id"] not in withheld_ids]
    reports["blocked_withheld"] = len(reports["blocked"]) - len(blocked_rows)
    reports["blocked"] = blocked_rows
    # T-0239. Two facts, two fields, because one field carrying both is how a
    # reader stops being able to tell which one they are looking at. `blocked`
    # above says "the status is blocked", and a *dependency* can close it -- which
    # is why T-0041 left the list the moment T-0040 finished, though nobody had
    # touched the card. `stuck` says "a human said this is stuck": still blocked,
    # with no open blocker to wait on. Only a person reopens that one, so the
    # attention surface is the only place it can clear.
    stuck_all = stuck_tasks(state, state["tasks"])
    stuck_rows = [row for row in stuck_all if row["id"] not in withheld_ids]
    reports["stuck"] = stuck_rows
    reports["stuck_withheld"] = len(stuck_all) - len(stuck_rows)
    # The done/undone accumulation, and the one count on this payload that had
    # no fabric-wide form. `tasks` is viewer-scoped and is the right thing for a
    # pane to *draw* -- a card the viewer may not open must not be listed -- but
    # the figure the leader reads off the report page is "how much of the work
    # is finished", and a seat that can see 131 of 139 done cards read a
    # smaller board than the one that exists. Both are true at once, so both
    # are published, each labelled with the scope it was folded over rather
    # than left for a consumer to guess: an unlabelled total that changes with
    # who reads it is precisely the failure `reports_scope` was added for.
    # Statuses only, never ids -- the same shape as `withheld_tasks`, and for
    # the same reason.
    visible_statuses = collections.Counter(t.get("status") for t in tasks.values())
    fabric_statuses = collections.Counter(t.get("status") for t in state["tasks"].values())
    # The two universal sets are spelled out rather than read from `const`, for
    # the reason `concepts` above states: a status the fabric adds later is
    # then *visible* as a new key in `by_status` instead of being absorbed into
    # a bucket nobody declared. The consequence is that they are the one thing
    # here a reader must not extend by guesswork, so they are named in the doc.
    # `TERMINAL` is every status no longer outstanding, and it holds `dropped`
    # as well as `done` -- right for "does this card still need attention",
    # wrong for "is this card finished". Subtracting the one member rather than
    # retyping `{"done"}` keeps the authority with the constant while saying
    # which of its members this figure means.
    done_ids = TERMINAL - {"dropped"}
    out_scope = {}
    for label, counts in (("visible", visible_statuses), ("fabric", fabric_statuses)):
        done = sum(counts.get(s, 0) for s in done_ids)
        total = sum(counts.values())
        # `dropped` is dismissed rather than unfinished, so it belongs in
        # neither figure -- counting it done flatters the board, counting it
        # undone keeps a card that was deliberately closed open forever.
        scored = total - counts.get("dropped", 0)
        out_scope[label] = {
            "by_status": {s: counts.get(s, 0) for s in sorted(counts)},
            "total": total,
            "done": done,
            "dropped": counts.get("dropped", 0),
            "undone": scored - done,
            "scored": scored,
            "finished_pct": round(100.0 * done / scored, 1) if scored else 0.0,
        }
    reports["board_scope"] = out_scope
    # Built once: the payload serves it and the `conversation` digest below hashes
    # the same object, and two calls to a gate is two chances for them to differ.
    conversation = conversation_view(state, viewer)
    out = {
        "generated_at": generated_at,
        # the fingerprint the front-end polls, so the page can say "the record
        # moved" without reloading itself under the reader's hands
        "digest": digest or "",
        "as_of": as_of_date,
        # the state machine is the server's, not the browser's: a front-end that
        # hard-codes the status list is a second copy of the contract, and this
        # project has measured what a second copy costs (design/05, T-0086)
        "statuses": STATUSES,
        "terminal": sorted(TERMINAL),
        # The two vocabularies the Help pane had to write down because this
        # payload carried no key for them: the moves between the statuses
        # above, and the classes a refusal can carry.
        "task_flow": task_flow(),
        "refusal_classes": refusal_classes(),
        "root": state["root"],
        "viewer": viewer,
        "viewer_kind": (state["registry"].get(viewer) or {}).get("kind", ""),
        # design/06 R2: the write posture is the server's to declare, so the
        # composer can name the identity it will write as and disappear when
        # there is none, instead of offering a control that will be refused.
        "write": write or {"enabled": False, "as": ""},
        # design/06 R2 declares the write posture for the same reason on the read
        # side: a consumer that forgot `?as=` used to read the leader's seat and
        # had no way to tell, and one really did -- it reported that seat's
        # numbers as the project's for an hour. The seat is reported here, and
        # `borrowed` says whether this server chose it or the caller did.
        "read": read or {"as": viewer, "borrowed": False},
        # T-0252. `phase` above the channel list is the *default* channel's phase,
        # and the default is chosen by `gate_channel`, whose three arms are about a
        # different question ("which channel's phase governs a task that does not
        # name one"). On a root with several channels that means the bare `phase`
        # is a different channel's phase for almost every reader: measured on
        # 2026-09-23, `claude-session1` and `human` read `SYNTHESIS` from
        # `barrier-v0` (6 raw rows), `codex` read `SEALED_DIVERGENT` from `dev` (no
        # store at all) and `codex-orangement` read `COMMIT` from `hello` (501
        # rows). An unlabelled value that changes with who reads it is exactly the
        # failure `reports_scope` was added for, one key away, so the channel is
        # published beside the phase. `id` is the channel the phase was read from,
        # `""` when the root holds no channel at all; `arm` names which arm of
        # `gate_channel` chose it, so a reader can tell "you participate in this
        # channel" from "nobody's choice put you here" without re-deriving the
        # rule. This does not change which channel is picked -- that is a design
        # decision for the leader, not a rendering one.
        "phase": channel.get("phase", "-"),
        "phase_channel": phase_channel_provenance(state, viewer, channel),
        "withheld_tasks": hidden,
        "unplaced_events": state.get("unplaced_events", 0),
        "channels": [channel_payload(state, ch, viewer) for ch in state["channels"]],
        "tasks": tasks,
        "milestones": state["milestones"],
        "reports": reports,
        # The report is fabric-wide while `tasks` is viewer-scoped, and a
        # consumer that cannot tell the two apart is how a seat's slice gets
        # quoted as the project's numbers. Naming the scope is the cheap half of
        # that fix; folding the report over the full set is the other half.
        "reports_scope": "fabric",
        "reports_viewer": viewer,
        "conversation": conversation,
        # T-0214: one dictionary for the words the product uses, so no surface
        # invents a label. The Help pane is written against this key; the shape is
        # token -> {label, description, group} and it is not a second vocabulary,
        # it is the one the server reads out of its own constants.
        "concepts": concepts(),
        "mail": state["mail"],
        "unacked": state["unacked"],
        "drift": drift_rows,
        # Same spirit as `withheld_tasks`: the fact that rows were withheld is
        # published, the rows are not. A reader who is shown 72 of 87 rows and
        # no count cannot tell a complete drift list from a gated one.
        "drift_withheld": drift_withheld,
        # Which program answered: the tree the server runs from, and the
        # revision the served bundle recorded about itself at build time. They
        # can differ, and `stale` is that difference -- `design/12` §1.6.
        "revision": describe_revision(state["root"], default_dist()),
        "register": register or {},
        "agents": {k: {"kind": v.get("kind", ""), "model": v.get("model", "")}
                   for k, v in state["registry"].items()},
    }
    # T-0215: the global `digest` above stays where it was -- it is the
    # fingerprint of the *tree*, and `/api/digest` polls it cheaply. What is added
    # is a digest per view, so a pane compares the scope it draws instead of
    # invalidating on every write anywhere. Assigned after the literal because a
    # scope's digest is taken over the payload it names, and a dict cannot hash
    # itself while it is still being built.
    out["view_digests"] = scoped_digests(out, conversation, drift_rows, blocked_rows, stuck_rows)
    return out
