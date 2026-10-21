import json, hashlib, time, os

LOG = "flight_log.jsonl"

def _last_hash():
    if not os.path.exists(LOG):
        return "GENESIS"
    last = None
    with open(LOG, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                last = line
    return json.loads(last)["hash"] if last else "GENESIS"

def log(event, task_id, **details):
    entry = {
        "ts": time.time(),
        "event": event,
        "task_id": task_id,
        "details": details,
        "prev": _last_hash(),
    }
    body = json.dumps(entry, sort_keys=True)
    entry["hash"] = hashlib.sha256(body.encode()).hexdigest()
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")
    return entry["hash"]

def verify_chain():
    prev = "GENESIS"
    with open(LOG, "r", encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            if not line.strip():
                continue
            e = json.loads(line)
            stored = e.pop("hash")
            if e["prev"] != prev:
                return False, f"chain broken at entry {i}"
            body = json.dumps(e, sort_keys=True)
            if hashlib.sha256(body.encode()).hexdigest() != stored:
                return False, f"entry {i} was modified"
            prev = stored
    return True, "chain intact"

if __name__ == "__main__":
    print(verify_chain())