from dotenv import load_dotenv
load_dotenv()
import os
from openai import OpenAI

client = OpenAI(
    base_url="https://api.tokenfactory.nebius.com/v1/",
    api_key=os.environ["NEBIUS_API_KEY"],
)

tools = [{
    "type": "function",
    "function": {
        "name": "read_file",
        "description": "Read a file",
        "parameters": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
    },
}]

r = client.chat.completions.create(
    model="nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B",
    max_tokens=200,
    tools=tools,
    messages=[{"role": "user", "content": "Read the file notes.txt"}],
)

msg = r.choices[0].message
print("Tool call made:", bool(msg.tool_calls))
print("Details:", msg.tool_calls)
print("Tokens used:", r.usage.prompt_tokens, r.usage.completion_tokens)