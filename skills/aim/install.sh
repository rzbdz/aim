#!/usr/bin/env sh
# aim skill installer: one file, both harnesses, versioned with the fabric.
#
# What this is for
# ----------------
# The instruction layer of this project was `AGENTS.md` at the checkout root: it
# works, and it is not a package. It is not installable, so a session in another
# directory has to be told about it by hand; it is not versioned *with* the tool,
# so an instruction and the tool it describes can drift apart with nobody
# noticing; and it is written for a reader who is already inside the repo.
#
# `SKILL.md` beside this script is the instruction as a package, and this script
# is the whole install:
#
#   * it puts `aim` and `aimboard` on PATH. On this checkout those are symlinks
#     from /usr/local/bin into `bin/` -- that symlink *is* the install, which is
#     what AGENTS.md says and what a fresh checkout does not have.
#   * it installs the skill into both harnesses from the one file. Claude Code
#     reads `~/.claude/skills/<name>/SKILL.md`; Codex reads
#     `$CODEX_HOME/skills/<name>/SKILL.md` (this box has skills there already:
#     `/root/.codex/skills/.system/*/SKILL.md`). Two copies written by one script
#     from one source is the difference between "the same file for both
#     harnesses" and "two files that started equal".
#
# Why `--print-version` exists
# ---------------------------
# `aim` has no `--version`, and the absence is deliberate -- a version string is
# a claim that can drift from the tool. What identifies this tool is its bytes.
# So the installer prints the two facts the rest of the project already uses for
# exactly this problem (`aimboard/revision.py`: the tree revision, and a content
# hash of the program), and it prints them *at install time* so a skill on disk
# can always be checked against the checkout it came from:
#
#     tree_revision  -- `git rev-parse --short HEAD` plus `+dirty` when the
#                       program paths have uncommitted changes, which is the
#                       same figure `/api/revision` publishes as `fabric`
#     aim_sha256     -- sha256 of bin/aim, the file the skill instructs you to
#                       run. A revision string alone is not enough and the tree
#                       proved it: `73e43a2+dirty` measured equal while bin/aim
#                       had already changed underneath it.
#
# It writes no revision *file*. A stamp written at install time and never
# compared is decoration; the two facts are printed so the reader (or a test) can
# compare them against the checkout, and nothing here claims to have checked
# anything on its own.
#
# Idempotent, and it says what it wrote. `--uninstall` removes exactly the two
# skill directories this installed and nothing else.
#
# Wire it in, in one line:
#
#     skills/aim/install.sh
#
# Exit code is the number of failures, the convention the rest of this repo's
# suites already use.
set -u

HERE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)   # <root>/skills/aim
ROOT=$(CDPATH= cd -- "$HERE/../.." && pwd)          # <root>
SKILL="$HERE/SKILL.md"
NAME=aim

CLAUDE_HOME="${CLAUDE_HOME:-$HOME/.claude}"
CODEX_HOME_DIR="${CODEX_HOME:-$HOME/.codex}"
BIN_DIR="${AIM_BIN_DIR:-/usr/local/bin}"

FAILURES=0
fail() { echo "FAIL: $*" >&2; FAILURES=$((FAILURES + 1)); }
ok()   { echo "  ok    $*"; }

usage() {
    cat <<EOF
usage: install.sh [--print-version] [--uninstall] [--dry-run]

Installs the aim skill for both harnesses and puts aim on PATH.

  --print-version   print the tree revision and bin/aim's sha256 and exit
  --uninstall       remove the two installed skill directories
  --dry-run         print every action and change nothing
EOF
}

DRY=0
MODE=install
while [ $# -gt 0 ]; do
    case "$1" in
        --print-version) MODE=version ;;
        --uninstall)     MODE=uninstall ;;
        --dry-run)       DRY=1 ;;
        -h|--help)       usage; exit 0 ;;
        *) usage >&2; exit 2 ;;
    esac
    shift
done

# ---------------------------------------------------------------- version facts
# Both reads, no lock, no ledger, no write: a version probe that mutates the tree
# is not a version probe.
tree_revision() {
    sha=$(git -C "$ROOT" rev-parse --short HEAD 2>/dev/null) || return 0
    [ -n "$sha" ] || return 0
    if [ -n "$(git -C "$ROOT" status --porcelain -- bin aimboard web 2>/dev/null)" ]; then
        printf '%s+dirty\n' "$sha"
    else
        printf '%s\n' "$sha"
    fi
}

aim_sha256() {
    if [ -f "$ROOT/bin/aim" ]; then
        python3 -c 'import hashlib,sys;print(hashlib.sha256(open(sys.argv[1],"rb").read()).hexdigest())' \
            "$ROOT/bin/aim"
    fi
}

print_version() {
    printf 'skill      %s\n' "$NAME"
    printf 'source     %s\n' "$SKILL"
    printf 'checkout   %s\n' "$ROOT"
    printf 'tree_revision  %s\n' "$(tree_revision)"
    printf 'aim_sha256     %s\n' "$(aim_sha256)"
    # The one claim this script makes about the pair, stated where a reader can
    # check it: the hash above is of the file the skill tells you to run.
    printf 'skill_sha256   %s\n' "$(python3 -c 'import hashlib,sys;print(hashlib.sha256(open(sys.argv[1],"rb").read()).hexdigest())' "$SKILL")"
}

if [ "$MODE" = version ]; then
    print_version
    exit 0
fi

# --------------------------------------------------------------------- install
install_skill() {   # $1 = harness home
    dest="$1/skills/$NAME"
    if [ -e "$dest" ] && [ ! -f "$dest/SKILL.md" ]; then
        fail "$dest exists and is not a skill this installer wrote; leaving it"
        return
    fi
    if [ "$DRY" -eq 1 ]; then
        echo "  would  install $dest/SKILL.md"
        return
    fi
    mkdir -p "$dest" || { fail "cannot create $dest"; return; }
    cp "$SKILL" "$dest/SKILL.md" || { fail "cannot copy into $dest"; return; }
    ok "installed $dest/SKILL.md"
}

uninstall_skill() { # $1 = harness home
    dest="$1/skills/$NAME"
    if [ ! -e "$dest" ]; then
        ok "nothing at $dest"
        return
    fi
    # Only a directory this installer could have written: the name it installs
    # under, holding the file it installs. `rm -rf` on a path built from `$HOME`
    # is the one line here that could do real damage, so it checks what it is
    # about to delete rather than trusting the variable.
    if [ ! -f "$dest/SKILL.md" ]; then
        fail "$dest holds no SKILL.md; refusing to remove it"
        return
    fi
    if [ "$DRY" -eq 1 ]; then
        echo "  would  remove $dest"
        return
    fi
    rm -rf "$dest" || { fail "cannot remove $dest"; return; }
    ok "removed $dest"
}

link_bin() {        # $1 = source, $2 = link path
    src="$1"; link="$2"
    if [ -e "$link" ] || [ -L "$link" ]; then
        # An existing symlink into *this* checkout is already the install; one
        # into another checkout is someone else's install, and replacing it
        # silently is how a measurement gets filed against the wrong build.
        current=$(readlink "$link" 2>/dev/null)
        if [ "$current" = "$src" ]; then
            ok "$link already points at $src"
            return
        fi
        if [ -n "$current" ]; then
            fail "$link points at $current, not $src; refusing to replace it"
            return
        fi
        fail "$link exists and is not a symlink; refusing to replace it"
        return
    fi
    if [ "$DRY" -eq 1 ]; then
        echo "  would  link $link -> $src"
        return
    fi
    if ln -s "$src" "$link" 2>/dev/null; then
        ok "linked $link -> $src"
    else
        fail "cannot create $link (is $BIN_DIR writable? set AIM_BIN_DIR)"
    fi
}

echo "== aim skill: $ROOT =="
if [ "$MODE" = uninstall ]; then
    uninstall_skill "$CLAUDE_HOME"
    uninstall_skill "$CODEX_HOME_DIR"
else
    [ -f "$SKILL" ] || { fail "no SKILL.md at $SKILL"; exit "$FAILURES"; }
    install_skill "$CLAUDE_HOME"
    install_skill "$CODEX_HOME_DIR"
    link_bin "$ROOT/bin/aim" "$BIN_DIR/aim"
    link_bin "$ROOT/bin/aimboard" "$BIN_DIR/aimboard"
    echo
    print_version
fi

echo
echo "$FAILURES failure(s)"
exit "$FAILURES"
