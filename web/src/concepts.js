/**
 * One dictionary for the words the product uses.
 *
 * The problem this solves is specific: `SEALED_DIVERGENT` was drawn as the
 * primary label in three places, and a reader had to infer the protocol from an
 * identifier. The fix is not "translate the enums somewhere", it is *one* place
 * that knows what a phase is called, what it means and what it lets you do, so
 * that adding a phase cannot produce a second, quietly different explanation.
 *
 * Two rules for anything added here:
 *
 *   1. The raw protocol value stays canonical and stays available. It is the
 *      thing the record holds, the thing `aim` takes as an argument and the
 *      thing you need when filing a bug, so it is never hidden -- it just stops
 *      being the *primary* label. Every concept carries its own `key`.
 *   2. A concept has to say what it *does to you*. "Positions are sealed" is a
 *      description; "you cannot read a peer's reasoning yet, and the tool will
 *      refuse you if you try" is the sentence that makes it usable.
 */

/** The lifecycle, in order. `key` is the value the record and `bin/aim` use. */
export const PHASES = [
  {
    key: 'SEALED_DIVERGENT',
    label: 'Sealed',
    summary: 'Positions are being formed in private',
    what: 'Each participant works out their own position and writes it down without seeing anyone else\'s. '
      + 'This is the only phase in which the disagreement is genuinely independent.',
    consequence: 'You cannot read a peer\'s reasoning, and they cannot read yours. If you ask anyway, the tool '
      + 'refuses — and the refusal is recorded as evidence that you were tempted.',
    next: 'COMMIT',
  },
  {
    key: 'COMMIT',
    label: 'Committed',
    summary: 'Every position is written down and frozen',
    what: 'The positions that were formed in private become formal claims, each with a confidence and a '
      + 'sentence saying what would change the author\'s mind.',
    consequence: 'A committed claim cannot be quietly revised. Changing your mind is allowed; it happens as a '
      + 'new, recorded move rather than an edit — so the record shows that you moved.',
    next: 'SYNTHESIS',
  },
  {
    key: 'SYNTHESIS',
    label: 'Synthesising',
    summary: 'A third party is mapping where the positions diverge',
    what: 'The leader or a synthesizer compares the committed positions and names the places they actually '
      + 'disagree, as opposed to the places they use different words for the same thing.',
    consequence: 'The map is drawn from the committed claims only. Positions are still sealed from each other, '
      + 'so nobody can soften their claim after seeing which way the synthesis leans.',
    next: 'CROSS_EXAMINE',
  },
  {
    key: 'CROSS_EXAMINE',
    label: 'Cross-examining',
    summary: 'The seals are open and the positions answer each other',
    what: 'This is the first phase in which participants can read each other. On the channel, moves are labelled: '
      + 'evidence, objection, rebuttal, question, concession or proposal.',
    consequence: 'Now you can read a peer\'s reasoning and reply to it directly. What you can no longer do is '
      + 'pretend you had not read it — every move is recorded with the kind you gave it.',
    next: 'RESOLVE',
  },
  {
    key: 'RESOLVE',
    label: 'Resolving',
    summary: 'The leader is deciding',
    what: 'The argument is closed to new messages. The leader weighs the positions as recorded and writes the '
      + 'decision the record will carry forward.',
    consequence: 'You can read everything and say nothing new on this channel. The next thing that happens to '
      + 'this channel is that it closes.',
    next: 'CLOSED',
  },
  {
    key: 'CLOSED',
    label: 'Closed',
    summary: 'The record is finished',
    what: 'The channel is done. Everything stays readable, hash-chained and auditable; nothing new is added.',
    consequence: 'Nothing further happens here. If the question reopens, that is a new channel — the closed one '
      + 'stays as the evidence that the decision was made this way.',
    next: null,
  },
]

/** What a phase with no entry is called. Never invent a description for one. */
const UNKNOWN_PHASE = {
  label: 'Unknown phase',
  summary: 'This channel names a phase this build does not describe',
  what: 'The channel manifest records a phase the dashboard has no description for. That is a fact about the '
    + 'build, not about the channel.',
  consequence: 'Treat the channel as unreadable until you know what its phase permits: the gate on the server '
    + 'is the authority, and this page cannot predict it.',
  next: null,
}

const phaseIndex = Object.fromEntries(PHASES.map((phase) => [phase.key, phase]))

export function phaseConcept(key) {
  const known = phaseIndex[key]
  // `known` is what a caller needs to decide whether there is anything to link
  // to. An unrecognised phase still has to be *drawn* -- hiding it would be worse
  // than naming it plainly -- but it has no anchored section on the help page.
  return known ? { ...known, known: true } : { ...UNKNOWN_PHASE, key: key || '-', known: false }
}

/**
 * The human label for a phase. This is what a chip shows; the raw value goes in
 * the tooltip beside it, where it is available and not in the way.
 */
export function phaseLabel(key) {
  return phaseConcept(key).label
}

/** Anchor on the Help page for a phase, so a chip can link to its explanation. */
export const phaseAnchor = (key) => `phase-${String(key || '').toLowerCase()}`

/**
 * The vocabulary the product uses in its own copy. Ordered by how early a
 * reader meets the word, not alphabetically: an alphabetised glossary is a
 * dictionary, and the point of this one is to be read.
 */
export const GLOSSARY = [
  {
    term: 'record',
    anchor: 'concept-record',
    plain: 'The fabric\'s memory: an append-only set of files, each hash-chained to the one before it.',
    why: 'Nothing is overwritten. A correction is a new entry that says what it corrects, which is why every '
      + 'tool here can show you not just the current state but how it was reached.',
  },
  {
    term: 'channel',
    anchor: 'concept-channel',
    plain: 'A conversation with a phase, a leader and a set of participants.',
    why: 'The phase is not decoration: it decides who may read whom, and the server enforces it.',
  },
  {
    term: 'room',
    anchor: 'concept-room',
    plain: 'A side conversation inside a channel, for part of its participants.',
    why: 'A room inherits the parent channel\'s gate. It is draft until someone publishes it deliberately.',
  },
  {
    term: 'direct message',
    anchor: 'concept-direct',
    plain: 'A one-to-one message that is recorded and demands a receipt.',
    why: 'It is a durable handover, not a chat window: the sender can see whether it was read.',
  },
  {
    term: 'barrier',
    anchor: 'concept-barrier',
    plain: 'The rule that keeps positions independent until the leader opens cross-examination.',
    why: 'It is enforced by the tool, not by etiquette. Trying to read a peer too early is refused and the '
      + 'refusal is written to the ledger — the temptation is itself data.',
  },
  {
    term: 'phase',
    anchor: 'concept-phase',
    plain: 'Where a channel is in its lifecycle, from sealed positions to a closed record.',
    why: 'Access rules follow the phase, so the phase tells you what you may do next. See the table below.',
  },
  {
    term: 'seal',
    anchor: 'concept-seal',
    plain: 'A digest a participant commits to before they are allowed to read anyone else\'s position.',
    why: 'It is what makes "we disagreed independently" checkable instead of merely asserted.',
  },
  {
    term: 'work item',
    anchor: 'concept-work-item',
    plain: 'A unit of planned work with an owner, a status and an acceptance condition.',
    why: 'The acceptance condition is the part that matters: without one, "done" is an opinion.',
  },
  {
    term: 'plan seed',
    anchor: 'concept-plan-seed',
    plain: 'A work item that exists in the leader\'s plan file but has no record in the store yet.',
    why: 'A plan is a promise. A seed card shows what was intended; only a recorded item is evidence that '
      + 'anything happened.',
  },
  {
    term: 'drift',
    anchor: 'concept-drift',
    plain: 'A place where the plan and the store disagree.',
    why: 'The store wins, for the same reason a recorded event beats a plan: one of them is what happened.',
  },
  {
    term: 'refusal',
    anchor: 'concept-refusal',
    plain: 'A recorded decision by the tool to not do what was asked.',
    why: 'Refusals are the evidence the barrier is real. A system that never refuses has a barrier that is '
      + 'only a convention.',
  },
  {
    term: 'receipt',
    anchor: 'concept-receipt',
    plain: 'Acknowledgment that a message arrived and was read.',
    why: 'An unacknowledged message is a visible fact, which is what stops a handover being assumed.',
  },
  {
    term: 'viewer',
    anchor: 'concept-viewer',
    plain: 'Whose view the dashboard is drawing.',
    why: 'The gate is applied on the server for this viewer. Switching viewer changes what exists on the page, '
      + 'not merely what is hidden.',
  },
  {
    term: 'writer',
    anchor: 'concept-writer',
    plain: 'The identity a write from this dashboard will be recorded as.',
    why: 'The server decides it. A dashboard that could name its own writer could speak as the leader.',
  },
  {
    term: 'milestone',
    anchor: 'concept-milestone',
    plain: 'A dated group of work items, with an acceptance condition of its own.',
    why: 'Progress is counted from the store, so a milestone that is 80% done means 80% of its items are done.',
  },
  {
    term: 'dependency',
    anchor: 'concept-dependency',
    plain: 'A work item that must finish before another can.',
    why: 'It is an edge in a graph, not a label: it stops being a blocker the moment the item it names is done.',
  },
]

export const CONCEPTS = [
  {
    id: 'independent-positions',
    title: 'Why positions are formed before anyone reads anyone else',
    body: [
      'When a group is asked a question together, the first answer usually anchors the rest. Not because '
      + 'anyone is weak, but because disagreeing with a confident person is expensive and agreeing is cheap. '
      + 'The result is a decision that looks like consensus and is actually the first speaker\'s opinion with '
      + 'extra steps.',
      'This fabric removes the anchoring instead of asking people to resist it. Every participant forms and '
      + 'commits a position while the barrier is up. Only then does the leader open cross-examination, and only '
      + 'then can anyone read anyone else. The order is enforced by the tool, and trying to skip it is refused '
      + 'and recorded.',
    ],
    links: [
      { to: '/barrier', label: 'Audit & barrier — see the seals and the refusals' },
      { to: '/items', label: 'Work items — what the plan says will happen' },
    ],
  },
  {
    id: 'human-in-the-loop',
    title: 'A human stays in the loop, at the points that matter',
    body: [
      'Agents do the work; a person holds the decisions that cannot be delegated. Three of them, in this '
      + 'product: opening cross-examination (which ends the independence of the positions), resolving a '
      + 'disagreement into a decision, and accepting or returning a work item that claims to be finished.',
      'Everything else is a proposal an agent can make. That split is why the dashboard has an Attention page '
      + 'rather than a task list: it is a queue of things that are waiting on a person, not a wall of work in '
      + 'progress.',
    ],
    links: [
      { to: '/attention', label: 'Attention — what is waiting on you' },
      { to: '/plan', label: 'Plan & risks — the decisions already recorded' },
    ],
  },
  {
    id: 'acting-on-an-item',
    title: 'How a person acts on a work item',
    body: [
      'Click any work item anywhere — a card, a row, a blocker id, a milestone\'s list — and the same drawer '
      + 'opens: what it is, its acceptance condition, what it is waiting on, what has been recorded about it, '
      + 'and the actions available to you right now. A seed card offers to record it; a review offers accept, '
      + 'request changes, or reject.',
      'The drawer does not write anything itself. It runs the same aim command you would run in a terminal, '
      + 'as the identity the server declares, so a refusal here is the same refusal, with the same text, and it '
      + 'lands in the same ledger.',
    ],
    links: [
      { to: '/kanban', label: 'Board — work by status' },
      { to: '/reports', label: 'Reports — what is waiting on what' },
    ],
  },
]

/**
 * The single letters, and where they come from.
 *
 * `M3`, `D7` and `R4` are drawn all over the plan and dependency screens as if
 * they were words. They are not the tool's vocabulary: `bin/aim` mints work-item
 * ids and takes whatever the plan files call everything else, so this table
 * states the convention the plan follows and says which file is the authority.
 * The counts are read from the live record, never written here -- a page that
 * lists a prefix the board does not hold is the same defect as an enum in a
 * label.
 */
export const ID_PREFIXES = [
  {
    prefix: 'T-',
    kind: 'a work item',
    where: 'minted by aim task new; the store is the authority',
    detail: 'The handle you quote to talk about work: comments, blockers and everything that points at an '
      + 'item name it by this id, and clicking one opens the same drawer from any page.',
  },
  {
    prefix: 'M',
    kind: 'a milestone',
    where: 'written by hand in plan/plan.json',
    detail: 'A milestone groups work items and carries an acceptance condition of its own. Clicking one '
      + 'filters the work list to exactly the items that belong to it, so a milestone is a way in rather '
      + 'than a heading.',
  },
  {
    prefix: 'D',
    kind: 'a decision',
    where: 'written by hand in plan/risks.json',
    detail: 'What was settled, and the reason it was settled that way. This is what you cite when someone '
      + 'proposes re-opening a question that already has an answer.',
  },
  {
    prefix: 'R',
    kind: 'a risk',
    where: 'written by hand in plan/risks.json',
    detail: 'An open risk with an owner and a kill_if — the observation that would retire it. A risk '
      + 'without one is a worry, not a tracked thing.',
  },
]
