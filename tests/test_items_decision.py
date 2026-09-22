"""T-0176: an item that needs a decision offers the decision, and the control
carries the exact argv that resolves it -- or it does not render.

`design/11` §2: the surfaces that answer "what needs me" hold decisions and
approvals, and every row there has an action. `design/12` §1.3: every `Decision`
carries the exact argv that resolves it, "a control with no argv is a dead end
and must not render". The work-items table is where the leader met the defect:
T-0004 (`owner: human`, `ready`, "Leader: approve the plan; advance hello past
SEALED_DIVERGENT") and T-0035 (`review`, a plan seed) are both rows that need a
decision, and both drew a single button reading `inspect`. The row named the
bookkeeping, not the decision.

What this file pins, and why each check is the one that goes red on the old code:

  1. the action cell branches on a decision predicate, and the branch it draws
     for those rows contains no `inspect` button -- the pre-fix cell is one
     unconditional `inspect` and fails check 1 immediately;
  2. every control inside that branch carries a non-empty argv. This is the
     T-0211 shape asserted on the *rendered control* rather than on a payload
     that does not exist yet: `data-argv` is bound to the builder, so a button
     added without one fails here instead of shipping as a dead end;
  3. the three decisions `design/11` §2 names (approve / request changes /
     reject) are offered for a `review` row, and a plan promise -- which has no
     record for a move to act on -- is offered the one control the drawer draws
     for a seed, `Record this work item`, rather than an approval that would
     create work that does not exist;
  4. the status every decision records is legal in `bin/aim`'s own state
     machine, read from the tool by `ast` rather than restated here -- a
     `ready -> done` approval would pass a spelling test and be refused by the
     tool the moment the leader pressed it (measured: `REFUSED: illegal
     transition doing -> done`, the same class);
  5. a plan seed's decision is a *record*, never a move: a seed has no work item
     for `task move` to act on, so the seed branch must go through `task new`,
     carry the promise's own status, and address its follow-up to the id that
     command allocated.

  6. the claim control this pane draws for an unowned row is offered only to the
     seat the server writes as. The command it carries is `--as <writer>`, so a
     control drawn for any other viewer is a command that assigns the leader's
     name to the item -- and the predicate read backwards (`!== 'human'`) draws
     it for every agent and hides it from the leader. `web/tests/unassigned.spec.js`
     is the browser half of this check and needs a built bundle; this is the half
     that runs in CI.

Checks 4 and 5 are the ones a plausible wrong fix fails: moving a seed, or
recording `done` for a row the tool only lets reach `doing`.

Run: python3 tests/test_items_decision.py            (exit code = failures)
     AIM_ITEMS_PANE=/tmp/old-ItemsPane.vue python3 tests/test_items_decision.py
     runs the same assertions against a candidate file, which is how the
     pre-fix pane was measured red.
"""
import ast
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AIM = ROOT / "bin" / "aim"
PANE = Path(os.environ.get("AIM_ITEMS_PANE", ROOT / "web" / "src" / "panes" / "ItemsPane.vue"))

passed = failed = 0


def check(name, ok, detail=""):
    global passed, failed
    if ok:
        passed += 1
        print(f"  PASS  {name}")
    else:
        failed += 1
        print(f"  FAIL  {name}" + (f"\n          {detail}" if detail else ""))


def constants(path, *names):
    """Top-level assignments in `bin/aim`, as the tool defines them."""
    out = {}
    for node in ast.parse(path.read_text(encoding="utf-8")).body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
            if isinstance(target, ast.Name) and target.id in names:
                out[target.id] = ast.literal_eval(node.value)
    return out


def region(text, start, end):
    i = text.find(start)
    return "" if i < 0 else text[i:text.find(end, i) + len(end)]


src = PANE.read_text(encoding="utf-8")
script = region(src, "<script setup>", "</script>")
cell = region(src, '<el-table-column label="action"', "</el-table-column>")
# The branch the decision rows get, up to the `v-else` that is the old control:
# `v-else` is the boundary between "offers the decision" and "offers inspect".
_start = cell.find('v-if="needsDecision(row)"')
_end = cell.find("v-else", _start) if _start >= 0 else -1
decide = cell[_start:_end] if _start >= 0 and _end > _start else ""

print(f"== the action cell offers the decision (T-0176) -- {PANE} ==")
check("the action cell exists", cell != "")
check("it branches on needsDecision(row) rather than on provenance",
      'v-if="needsDecision(row)"' in cell,
      "the cell has no decision branch: " + " ".join(cell.split())[:160])
check("the branch a needs-decision row gets holds no inspect button",
      decide != "" and "inspect" not in decide,
      "the decision branch still offers the bookkeeping control")

print("== every control in that branch carries the exact argv (T-0211) ==")
buttons = re.findall(r"<el-button\b.*?(?:/>|</el-button>)", decide, re.S)
check("the branch draws at least one control", len(buttons) >= 1, f"{len(buttons)} found")
check("every control in it binds data-argv",
      buttons != [] and all(":data-argv=" in b for b in buttons),
      f"{[b[:40] for b in buttons if ':data-argv=' not in b]}")
check("and the argv is the builder, not a literal empty",
      ':data-argv="JSON.stringify(decisionArgv(' in decide,
      "the argv is not produced by decisionArgv()")
check("the command is readable before it is pressed",
      ":title=" in decide and "argvText(" in script,
      "no tooltip: the reader cannot read the command without running it")

print("== the decision vocabulary ==")
table = region(script, "const DECISIONS = {", "\n}")
rows = dict(re.findall(r"(\w+):\s*\[(.*?)\n  \]", table, re.S))
keys = {k: re.findall(r"key: '([^']+)'", v) for k, v in rows.items()}
check("review rows offer approve, request changes and reject",
      keys.get("review") == ["approve", "return", "reject"], f"{keys.get('review')}")
check("a leader-owned promise in ready is recorded, not approved in place",
      keys.get("ready") == ["record"], f"{keys.get('ready')}")
check("and the record control carries the drawer's own word for it",
      "label: 'Record this work item'" in rows.get("ready", ""),
      f"{rows.get('ready')}")

print("== the decisions are legal in the tool's own state machine ==")
const = constants(AIM, "TASK_STATUSES", "TASK_FLOW")
flow, statuses = const.get("TASK_FLOW", {}), const.get("TASK_STATUSES", [])
check("bin/aim still defines the two tables this reads", flow and statuses,
      "TASK_FLOW/TASK_STATUSES not found -- this test cannot make its claim")
offered = {}
for status, body in rows.items():
    offered[status] = [s for _, s in re.findall(r"label: '([^']+)', type: '\w+', status: '([^']+)'", body)]
for status, targets in sorted(offered.items()):
    if status == "ready":
        # A record names no target status: the item it creates carries the
        # promise's own status, so there is no transition to be illegal.
        check("a 'record' decision names no status to move to", targets == [], f"{targets}")
        continue
    check(f"every status a '{status}' decision records is one the tool holds",
          targets != [] and all(t in statuses for t in targets), f"{targets} vs {statuses}")
    check(f"and every one of them is reachable from '{status}'",
          all(t in flow.get(status, []) for t in targets),
          f"{targets} vs TASK_FLOW['{status}']={flow.get(status)}")

print("== a plan seed is recorded, never moved ==")
builder = region(script, "function decisionArgv(", "\n}\n")
check("the builder writes the tool's verbs",
      "'task', 'comment'" in builder and "'task', 'move'" in builder and "'task', 'new'" in builder)
move_at, new_at = builder.find("'task', 'move'"), builder.find("'task', 'new'")
check("the move is the recorded branch", 0 < move_at < new_at,
      f"move at {move_at}, new at {new_at}")
check("the move branch is guarded by isPromise",
      re.search(r"if \(!isPromise\(task\)\)", builder) is not None,
      "a seed would be moved, and `task move` has no item to act on")
check("the record branch carries the status the promise itself holds",
      re.search(r"'--status', task\.status \|\| 'backlog'", builder) is not None,
      "a promise recorded with a status it does not hold is the seed moved by other means")
check("the follow-up is addressed to the id the record allocated",
      "const NEW_ID = '{new id}'" in script
      and "part === NEW_ID ? created[1] : part" in script
      and re.search(r"\^\(\\S\+\)\\s\+created", script) is not None,
      "the seed's words are addressed to a guessed id")

print("== the claim control answers to the gate of the write it names ==")
claim = region(script, "const claimable =", "\n\n")
# This pair was written against the pane as it shipped with T-0176, where the
# predicate was the literal `write.as === 'human'` and the argv builder was a
# function called `claimCommand`. Both moved under T-0227, and the checks are
# re-pointed at what the pane now does rather than at the spellings it used:
#
#   * the literal form asserts a fact about the payload (that the writer happens
#     to be the leader) where the clause asks about the *action* -- a write may
#     not assume a seat other than the writer's. The pane compares writer-kind
#     to viewer-kind instead (`sameSeat`), which is the same gate stated over the
#     thing it is a gate on.
#   * the argv builder is `rowCommand`, because it is the row's *one* command:
#     the control and the text a reader copies come from the same function, so a
#     reader whose seat cannot run it is still owed the string.
#
# Measured before this edit: the checks were reading `claim` for `=== 'human'`
# and an empty string for `function claimCommand(`, so both failed on a pane that
# is correct, and the failure read as a pane defect rather than a drift.
check("a claim is offered only to the seat the server writes as",
      "sameSeat()" in claim and "=== 'human'" not in claim,
      "the predicate does not compare the writer's seat with the viewer's: "
      + " ".join(claim.split())[:160])
check("and only when the board can write at all",
      "board.canWrite" in claim and "board.writer" in claim, claim)
claim_cmd = region(script, "function rowCommand(", "\n}\n")
check("the claim names the writer, the item's own channel and its id",
      "board.writer" in claim_cmd and "task.channel || task.context_id" in claim_cmd
      and "${task.id}" in claim_cmd, " ".join(claim_cmd.split())[:160])

print()
print(f"{passed}/{passed + failed} checks passed")
print("Checks 4 and 5 are the guard against the two ways this fix can be wrong:")
print("a decision whose status the tool refuses, and a move aimed at a promise that")
print("has no item behind it. The pre-fix file fails the first check in the first")
print("block -- measured with AIM_ITEMS_PANE pointed at `git show HEAD:...`.")
sys.exit(failed)
