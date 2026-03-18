import os
import re
import subprocess
import sys

import httpx

BASE_URL = os.environ["BASE_URL"]
MODEL = os.environ["MODEL"]
API_KEY = os.environ["API_KEY"]

COMPLETION_TOKEN = "TASK_COMPLETE"
MAX_STEPS = 25

SYSTEM_PROMPT = """You solve tasks using bash commands.
Your response must contain exactly ONE bash code block with ONE command.
Include a THOUGHT section before your command.

<format>
THOUGHT: your reasoning here.

```bash
your_command_here
```
</format>

Rules:
- ONE command per response. Never chain commands with ; or newlines.
- Commands connected with && or || count as one command and are allowed.
- Do exactly what was asked. Nothing more.
- When the task is fully complete, your final command MUST be: echo TASK_COMPLETE
  Do not combine it with any other command."""

client = httpx.Client(base_url=BASE_URL, timeout=300)
cmd_re = re.compile(r"```bash\s*\n(.*?)\n```", re.DOTALL)


def query(messages):
    """Send messages to the LLM and return its text response."""

    payload = {"model": MODEL, "messages": messages}
    headers = {"Authorization": f"Bearer {API_KEY}"}

    response = client.post("/chat/completions", json=payload, headers=headers)
    response.raise_for_status()

    data = response.json()
    return data["choices"][0]["message"]["content"]


def parse(response):
    """Extract a bash command from the LLM response."""

    match = cmd_re.search(response)
    if not match:
        return "", False
    return match.group(1).strip(), True


def execute(command):
    """Run a bash command and return its output and exit code."""

    result = subprocess.run(
        ["bash", "-c", command],
        capture_output=True, text=True, timeout=30,
    )
    output = result.stdout + result.stderr
    return output, result.returncode


def run(task):
    """Orchestrate the agent loop: send the task to the LLM, parse a bash
    command from its response, execute it, and feed the output back. Repeat
    until the LLM signals completion or the step limit is reached."""

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": task},
    ]

    for step in range(MAX_STEPS):
        print(f"\nThinking... (step {step + 1})", flush=True)
        response = query(messages)
        messages.append({"role": "assistant", "content": response})

        cmd, ok = parse(response)
        if not ok:
            messages.append({"role": "user", "content": "Respond with a ```bash``` block."})
            continue

        thought = response.split("```")[0].strip()
        print(f"\n{thought}\n")
        print(f"$ {cmd}\n")

        output, code = execute(cmd)
        print(output)

        if f"echo {COMPLETION_TOKEN}" in cmd:
            return

        feedback = output
        if code != 0:
            feedback = f"[exit {code}]\n{output}"
        messages.append({"role": "user", "content": f"<output>\n{feedback}\n</output>"})

    raise RuntimeError("step limit reached")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"usage: {sys.argv[0]} <task>", file=sys.stderr)
        sys.exit(1)
    try:
        run(" ".join(sys.argv[1:]))
    except Exception as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(1)
