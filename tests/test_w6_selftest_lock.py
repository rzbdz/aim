"""T-0144, as a test: `tests/selftest.sh` owns its run before it touches state.

The suite's verdict is the signal the project uses to decide whether the code is
right, so a run that can see another run is worse than a slow one. This checks
the three properties the fix claims, all against `AIM_SELFTEST_LOCK` pointed at
a private temp file so the test cannot itself block on a peer's suite:

  * the script holds the lock for as long as it is alive -- not just at startup;
  * a lock somebody else holds makes a second run fail loudly and quickly,
    rather than starting a suite it cannot safely run;
  * the lock is released when the run ends, so a killed or crashed run does not
    leave a lock nobody can clear.

Measured against the pre-fix script: the flock never appears (check W6-1 fails),
and the contended run ignores the lock entirely (W6-2 has to be killed).

Run: python3 tests/test_w6_selftest_lock.py
"""
import fcntl
import os
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SELFTEST = ROOT / "tests" / "selftest.sh"

passed = failed = 0


def check(name, cond, detail=""):
    global passed, failed
    if cond:
        passed += 1
        print(f"  ok    {name}")
    else:
        failed += 1
        print(f"  FAIL  {name}  {detail}")


def lock_free(path):
    """True if the file is currently unlocked (we can take LOCK_EX now)."""
    with open(path, "a+") as fh:
        try:
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
            return True
        except OSError:
            return False


def main():
    tmp = tempfile.mkdtemp(prefix="w6-lock-")
    lock = os.path.join(tmp, "selftest.lock")
    Path(lock).touch()
    env = dict(os.environ, AIM_SELFTEST_LOCK=lock, AIM_SELFTEST_LOCK_WAIT="3")

    # W6-1: the script itself takes the lock, and releases it on exit.
    proc = subprocess.Popen(["bash", str(SELFTEST)], env=env,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    held = False
    deadline = time.time() + 10
    while time.time() < deadline and proc.poll() is None:
        if not lock_free(lock):
            held = True
            break
        time.sleep(0.02)
    check("W6-1 the running script holds the lock", held,
          "no flock observed while selftest.sh was alive")
    if proc.poll() is None:
        proc.send_signal(signal.SIGTERM)
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()
    # A killed run must not leave a stale lock.
    released = False
    deadline = time.time() + 5
    while time.time() < deadline:
        if lock_free(lock):
            released = True
            break
        time.sleep(0.02)
    check("W6-3 the lock is released when the run ends", released,
          "lock still held after the process exited")
    # Remove the per-PID AIM_ROOT the killed run did not get to clean up.
    for leftover in ROOT.glob(f".selftest-{proc.pid}"):
        try:
            subprocess.run(["rm", "-rf", str(leftover)], check=False)
        except Exception:
            pass

    # W6-2: a lock held by somebody else fails a second run loudly, and fast.
    holder = open(lock, "a+")
    fcntl.flock(holder.fileno(), fcntl.LOCK_EX)
    t0 = time.time()
    try:
        r = subprocess.run(["bash", str(SELFTEST)], env=env,
                           capture_output=True, text=True, timeout=30)
        rc, output, elapsed = r.returncode, r.stdout + r.stderr, time.time() - t0
    except subprocess.TimeoutExpired as e:
        rc, output, elapsed = None, (e.stdout or b"").decode(errors="replace") \
            if isinstance(e.stdout, bytes) else (e.stdout or ""), time.time() - t0
    finally:
        fcntl.flock(holder.fileno(), fcntl.LOCK_UN)
        holder.close()
    check("W6-2 a held lock makes the second run fail, not race",
          rc == 3, f"rc={rc} after {elapsed:.1f}s; expected rc=3")
    check("W6-2b the refusal is loud and names the lock",
          "FATAL" in output and lock in output, repr(output[:200]))
    check("W6-2c it gave up in bounded time, not by hanging",
          elapsed < 25, f"{elapsed:.1f}s")

    subprocess.run(["rm", "-rf", tmp], check=False)
    print(f"\n{passed}/{passed + failed} checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
