import time, yaml, threading, os, fnmatch
import recorder
import scopectl
import notify
from runner import start_task, is_running, freeze, kill, sh

if not scopectl.verify():
    recorder.log("SCOPE_TAMPERED", "supervisor", file="scope.yaml")
    raise SystemExit("REFUSING TO START: scope.yaml signature check failed")

scope = yaml.safe_load(open("scope.yaml"))
rules = scope["tasks"]["docs_task"]
policy = scope["on_violation"]


def pid_count(name):
    out, _ = sh(["docker", "top", name])
    return max(len(out.splitlines()) - 1, 0)


def ask_with_timeout(seconds):
    result = {"v": "kill"}

    def reader():
        result["v"] = input().strip().lower()

    t = threading.Thread(target=reader, daemon=True)
    t.start()
    t.join(seconds)
    return result["v"]


def contain(name, reason):
    recorder.log("CONTAINED", name, reason=reason)
    freeze(name)
    notify.send(f"GUARDRAIL: task {name} FROZEN - {reason}. Auto-kill in {policy['human_timeout_s']}s.")
    print(f"[ALERT] task frozen: {reason}")
    print(f"        auto-kill in {policy['human_timeout_s']}s unless you type 'release' + Enter")
    decision = ask_with_timeout(policy["human_timeout_s"])
    if decision == "release":
        sh(["docker", "unpause", name])
        recorder.log("RELEASED", name)
        print("[RELEASED] task resumed")
    else:
        kill(name)
        recorder.log("KILLED", name, still_running=is_running(name))
        print(f"[KILLED] still running: {is_running(name)}")


def supervise(name, canary_flag=None):
    """Watch a running task. Returns 'ok' or a violation reason."""
    start = time.time()
    while is_running(name):
        if time.time() - start > rules["max_runtime_s"]:
            contain(name, "runtime exceeded")
            return "runtime exceeded"
        if pid_count(name) > rules["max_pids"]:
            contain(name, "too many processes")
            return "too many processes"
        if canary_flag and canary_flag.get("hit"):
            contain(name, canary_flag["hit"])
            return canary_flag["hit"]
        time.sleep(0.2)
    return "ok"


def _rel(path):
    real = os.path.realpath(path)
    base = os.path.realpath(".")
    return os.path.relpath(real, base).replace("\\", "/")


def gate_read(path, task="docs_task"):
    rel = _rel(path)
    for pattern in scope["tasks"][task]["fs_read"]:
        if fnmatch.fnmatch(rel, pattern):
            return True, "in scope"
    return False, f"read out of scope: {rel}"


def gate_write(path, task="investigator"):
    rel = _rel(path)
    for pattern in scope["tasks"][task]["fs_write"]:
        if fnmatch.fnmatch(rel, pattern):
            return True, "in scope"
    return False, f"write out of scope: {rel}"


def alert_blocked(task_id, reason):
    print(f"[ALERT] {task_id} BLOCKED by gate: {reason}")
    notify.send(f"GUARDRAIL: {task_id} blocked - {reason}")


if __name__ == "__main__":
    print("--- TEST: runaway task ---")
    n = start_task("loop", "import time\nwhile True:\n    time.sleep(1)")
    print("result:", supervise(n))