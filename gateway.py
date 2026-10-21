from dotenv import load_dotenv
load_dotenv()
import os, sys, json
from http.server import BaseHTTPRequestHandler, HTTPServer
from openai import OpenAI
from tavily import TavilyClient
import recorder
import notify
import supervisor
from runner import sh

client = OpenAI(base_url="https://api.tokenfactory.nebius.com/v1/",
                api_key=os.environ["NEBIUS_API_KEY"])
tavily = TavilyClient(api_key=os.environ["TAVILY_API_KEY"])
MODEL = "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B"
TASK = "investigator"
BRAIN = "agent-brain"
PORT = 8787
MAX_SEARCHES = 6
MAX_TOKENS_RUN = 200000
RECOVER = "--recover" in sys.argv
SENSITIVE = ("canary", "secrets", "scope.yaml", "scope.sig", ".env")

state = {"searches": 0, "strikes": 0, "terminated": False,
         "report": False, "tokens": 0, "killed": False}


def terminate(reason):
    state["terminated"] = True
    recorder.log("TASK_TERMINATED", "gateway", reason=reason)
    notify.send(f"GUARDRAIL: agent TERMINATED - {reason}")
    print(f"[TERMINATED] {reason}")


def violation(step, reason, tool):
    state["strikes"] += 1
    recorder.log("BLOCKED", f"s{step}", reason=reason, tool=tool)
    supervisor.alert_blocked(f"s{step}", reason)
    if not RECOVER and any(w in reason for w in SENSITIVE):
        terminate("scope violation: " + reason)
    return {"status": "terminated", "reason": reason,
            "note": "Out of scope. Do not retry. Continue without it."}


def tool_read(step, path):
    ok, reason = supervisor.gate_read(path, TASK)
    if not ok:
        return violation(step, reason, "read_file")
    recorder.log("READ_OK", f"s{step}", path=path)
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()[:4000]
    return {"status": "ok", "output": "<untrusted>\n" + text + "\n</untrusted>"}


def tool_search(step, query):
    if state["searches"] >= MAX_SEARCHES:
        return {"status": "terminated", "reason": "search budget used up"}
    state["searches"] += 1
    recorder.log("SEARCH", f"s{step}", query=query[:200])
    r = tavily.search(query, max_results=3)
    items = [f'{x["title"]} | {x["url"]} | {x["content"][:200]}' for x in r["results"]]
    return {"status": "ok", "output": "<untrusted>\n" + "\n".join(items) + "\n</untrusted>"}


def tool_write(step, path, text):
    ok, reason = supervisor.gate_write(path, TASK)
    if not ok:
        return violation(step, reason, "write_file")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    recorder.log("WRITE_OK", f"s{step}", path=path)
    state["report"] = True
    return {"status": "ok",
            "output": "written. The task is complete; reply with a one-line summary."}


def handle_tool(body):
    name, args, step = body["name"], body.get("args", {}), body.get("step", 0)
    recorder.log("TOOL_CALL", f"s{step}", tool=name, args=str(args)[:300])
    print(f"[step {step}] {name}: {str(args)[:120]}")
    try:
        if name == "read_file":
            res = tool_read(step, args["path"])
        elif name == "tavily_search":
            res = tool_search(step, args["query"])
        elif name == "write_file":
            res = tool_write(step, args["path"], args["text"])
        else:
            res = {"status": "error", "reason": "unknown tool"}
    except KeyError:
        res = {"status": "error", "reason": "missing argument"}
    return {"result": res, "terminated": state["terminated"]}


def handle_llm(body):
    if state["tokens"] >= MAX_TOKENS_RUN:
        terminate("token budget exceeded")
        return {"terminated": True}
    r = client.chat.completions.create(
        model=MODEL, max_tokens=min(body.get("max_tokens", 1500), 1500),
        tools=body["tools"], messages=body["messages"])
    state["tokens"] += r.usage.prompt_tokens + r.usage.completion_tokens
    return json.loads(r.model_dump_json())


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        if state["terminated"]:
            out = {"terminated": True}
        elif self.path == "/llm":
            out = handle_llm(body)
        elif self.path == "/tool":
            out = handle_tool(body)
        else:
            out = {"error": "not found"}
        data = json.dumps(out).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)
        if state["terminated"] and not state["killed"]:
            state["killed"] = True
            sh(["docker", "kill", BRAIN])
            recorder.log("BRAIN_KILLED", BRAIN)
            print(f"[KILLED] container {BRAIN} killed. tokens={state['tokens']} "
                  f"strikes={state['strikes']} report={state['report']}")


if __name__ == "__main__":
    print(f"gateway on :{PORT} | mode: {'recover' if RECOVER else 'terminate-on-sensitive'}")
    HTTPServer(("0.0.0.0", PORT), H).serve_forever()