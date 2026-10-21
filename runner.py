import subprocess, time, uuid

def sh(args):
    r = subprocess.run(args, capture_output=True, text=True)
    return r.stdout.strip(), r.returncode

def start_task(task_id, code):
    name = f"task-{task_id}-{uuid.uuid4().hex[:6]}"
    sh(["docker", "run", "-d", "--name", name,
        "--network", "none", "--memory", "256m", "--pids-limit", "20",
        "--read-only", "agent-sandbox", "python", "-c", code])
    return name

def is_running(name):
    out, _ = sh(["docker", "ps", "-q", "--filter", f"name={name}"])
    return bool(out)

def freeze(name):
    sh(["docker", "pause", name])

def kill(name):
    sh(["docker", "kill", name])
    sh(["docker", "rm", "-f", name])

if __name__ == "__main__":
    # dummy task: sleeps forever
    code = "import time\nwhile True:\n    time.sleep(1)"
    name = start_task("t1", code)
    time.sleep(2)
    print("running after start:", is_running(name))

    freeze(name)
    out, _ = sh(["docker", "inspect", "-f", "{{.State.Status}}", name])
    print("state after freeze:", out)

    kill(name)
    time.sleep(1)
    print("running after kill:", is_running(name))