"""T-0224: a `--body` holding a file path is refused, not delivered as text.

The defect, as measured: `aim push --body /tmp/x.md` sent the literal string
`/tmp/x.md`. The message was well-formed, signed, delivered, and said nothing --
and nothing in the output of the send said a word was missing. The artifact was
24 bytes and had a valid `body_sha256`, so every downstream check passed. A
refusal is a fact; a 24-byte message that looks fine is a lie.

This file pins the accept line:

  * every verb that takes free text (`say`, `push`, `reveal`, `task comment`, and
    `seal --summary`, which is the same defect under a different flag name)
    refuses a `--body`/`--summary` naming an existing readable file, with a
    message naming `--body-file`, and writes nothing;
  * the refusal is about the command line, not about the channel: it fires even
    when the verb is otherwise closed in the current phase (that is why `say`,
    `reveal` and `seal` are exercised in SEALED_DIVERGENT, and `task comment`
    against a task that exists and is commentable);
  * a bare token that is *not* a file is untouched, because a guard that eats
    legal messages is a worse bug than the silent path it was added to stop;
  * the literal text is still sendable -- `--body-literal <path>` puts the path
    on the wire on purpose, and `--body-file` still sends a file whose content
    is that path.

Run: python3 tests/test_body_path_guard.py
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AIM = ROOT / "bin" / "aim"

passed = failed = 0


def check(name, ok, detail=""):
    global passed, failed
    if ok:
        passed += 1
        print(f"  PASS  {name}")
    else:
        failed += 1
        print(f"  FAIL  {name}" + (f"\n        {detail}" if detail else ""))


def run(root, args):
    env = dict(os.environ, AIM_ROOT=str(root))
    p = subprocess.run([str(AIM)] + args, capture_output=True, text=True, env=env)
    return p.returncode, p.stdout, p.stderr


def fingerprint(paths):
    """What is in these stores right now, as a dict a comparison can see.

    A refused message must leave the store byte-identical. The channel's
    `ledger.jsonl` is deliberately *not* in `paths`: the refusal itself is
    recorded there, and a test that called the recording of the refusal a
    delivery would have to be thrown away.
    """
    import hashlib
    out = {}
    for p in paths:
        if p.is_dir():
            for f in sorted(p.rglob("*")):
                if f.is_file():
                    out[str(f.relative_to(p))] = hashlib.sha256(f.read_bytes()).hexdigest()
        elif p.is_file():
            out[p.name] = hashlib.sha256(p.read_bytes()).hexdigest()
        else:
            out[p.name] = None
    return out


def newest_bodies(outbox):
    return [json.loads(f.read_text())["body"] for f in sorted(outbox.glob("*.json"))]


def main():
    root = Path(tempfile.mkdtemp(prefix="aim-t0224-"))
    bodydir = Path(tempfile.mkdtemp(prefix="aim-t0224-body-"))
    try:
        body = bodydir / "x.md"
        body.write_text("the real message body\n")
        literal_file = bodydir / "literal.md"
        literal_file.write_text(str(body) + "\n")

        for args in (
            ["init"],
            ["register", "--as", "alpha", "--kind", "codex"],
            ["register", "--as", "beta", "--kind", "claude"],
            ["register", "--as", "human", "--kind", "human"],
            ["new-channel", "--id", "ch", "--topic", "fixture", "--participants", "alpha,beta"],
        ):
            rc, _, err = run(root, args)
            if rc != 0:
                print(f"setup failed: aim {' '.join(args)}\n{err}")
                return 1
        rc, out, err = run(root, ["task", "new", "--as", "alpha", "--channel", "ch",
                                  "--title", "a card that exists and can take a comment"])
        if rc != 0:
            print(f"setup failed: task new\n{err}")
            return 1
        task_id = re.match(r"(T-\d+)", out).group(1)

        ch = root / "channels" / "ch"
        cases = [
            ("say", ["say", "--as", "alpha", "--channel", "ch", "--body", str(body)],
             [ch / "private" / "alpha.jsonl"]),
            ("push", ["push", "--as", "alpha", "--to", "beta", "--channel", "ch",
                      "--subject", "s", "--body", str(body)],
             [root / "outbox" / "beta"]),
            ("reveal", ["reveal", "--as", "alpha", "--channel", "ch",
                        "--claim-id", "claim-1", "--body", str(body)],
             [ch / "log.jsonl"]),
            ("seal", ["seal", "--as", "alpha", "--channel", "ch", "--summary", str(body)],
             [ch / "seals" / "alpha.json"]),
            ("task comment", ["task", "comment", "--as", "alpha", "--channel", "ch",
                              "--id", task_id, "--body", str(body)],
             [ch / "tasks.jsonl"]),
        ]
        for name, argv, store in cases:
            before = fingerprint(store)
            rc, out, err = run(root, argv)
            after = fingerprint(store)
            check(f"{name}: --body <file> is refused (rc={rc})", rc != 0, out + err)
            check(f"{name}: the refusal names --body-file", "--body-file" in err, err.strip())
            check(f"{name}: nothing was delivered", before == after,
                  f"before={before} after={after}")

        # The escapes. A guard that makes the literal text unsendable has moved
        # the bug rather than fixed it.
        outbox = root / "outbox" / "beta"
        rc, out, err = run(root, ["push", "--as", "alpha", "--to", "beta", "--channel", "ch",
                                  "--subject", "from a file", "--body-file", str(body)])
        check("--body-file still sends the file's bytes",
              rc == 0 and "the real message body\n" in newest_bodies(outbox), out + err)

        rc, out, err = run(root, ["push", "--as", "alpha", "--to", "beta", "--channel", "ch",
                                  "--subject", "the literal path", "--body-literal", str(body)])
        check("--body-literal still sends the path as text",
              rc == 0 and str(body) in newest_bodies(outbox), out + err)

        rc, out, err = run(root, ["push", "--as", "alpha", "--to", "beta", "--channel", "ch",
                                  "--subject", "a file whose content is the path",
                                  "--body-file", str(literal_file)])
        check("--body-file sends a file whose content is the path",
              rc == 0 and str(body) + "\n" in newest_bodies(outbox), out + err)

        rc, out, err = run(root, ["say", "--as", "alpha", "--channel", "ch", "--private", "--body", "yes"])
        check("a bare token that is not a file is untouched", rc == 0, out + err)

        print(f"\n{passed} passed, {failed} failed")
        return 1 if failed else 0
    finally:
        shutil.rmtree(root, ignore_errors=True)
        shutil.rmtree(bodydir, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
