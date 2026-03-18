# Building a Coding Agent with Python + Docker

**What's a Coding Agent?**
A program that uses an LLM to write and execute code autonomously.

**What's Docker?**
A tool to run applications in isolated containers.

**What model are we using?**
Qwen 2.5 Coder 14B, running locally via LM Studio.

---

## About me

**Juan Olvera**, Software Engineer

I run a small Dev Shop focused on building SaaS applications.

Previously:

| Company                | Role              |
|------------------------|-------------------|
| Capital One            | DevOps Engineer   |
| Archipelago Analytics  | Backend Engineer  |
| HostGator              | Frontend Engineer |
| adWhite                | Web Developer     |

---

## What is a Coding Agent?

A program that can write, run, and fix code on its own.

**What does it do?**
You describe a task in plain English. The agent figures out
what commands to run, executes them, reads the results, and
keeps going until the task is done.

**How does it work?**
It uses a Large Language Model (LLM) to decide what to do next.
After each step, it looks at the output and decides whether to
continue or finish.

---

## The Agent Loop

The core of the agent is a loop. We send the user's task to the LLM,
parse a bash command from its response, run it, and feed the output
back as context. The LLM iterates until the task is done.

```
User Task
   |
   v
+----------+     +-------+     +---------+
|   LLM    | --> | Parse | --> | Execute |
+----------+     +-------+     +---------+
   ^                               |
   |         feedback              |
   +-------------------------------+
```

---

## The Prompt

```python
SYSTEM_PROMPT = """You solve tasks using bash commands.
Your response must contain exactly ONE bash code block.

Rules:
- ONE command per response
- Do exactly what was asked. Nothing more.
- When done: echo TASK_COMPLETE
"""
```

---

## Calling the LLM

```python
import httpx

client = httpx.Client(base_url=BASE_URL, timeout=300)

def query(messages):
    """Send messages to the LLM and return its text response."""

    payload = {"model": MODEL, "messages": messages}
    headers = {"Authorization": f"Bearer {API_KEY}"}

    response = client.post("/chat/completions", json=payload, headers=headers)
    response.raise_for_status()

    data = response.json()
    return data["choices"][0]["message"]["content"]
```

---

## Parse + Execute

```python
import re, subprocess

cmd_re = re.compile(r"```bash\s*\n(.*?)\n```", re.DOTALL)

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
    return result.stdout + result.stderr, result.returncode
```

---

## The Loop

```python
def run(task):
    """Orchestrate the agent loop: send the task to the LLM, parse a bash
    command from its response, execute it, and feed the output back. Repeat
    until the LLM signals completion or the step limit is reached."""

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": task},
    ]

    for step in range(MAX_STEPS):
        response = query(messages)
        cmd, ok = parse(response)
        output, code = execute(cmd)

        if "echo TASK_COMPLETE" in cmd:
            return

        messages.append({"role": "user",
            "content": f"<output>\n{output}\n</output>"})
```

---

## The Loop - Step by Step

```
  +----------------------------+
  |   1. query(messages)       |   Send task to LLM
  +-------------+--------------+
                |
                v
  +----------------------------+
  |   2. parse(response)       |   Extract bash command
  +-------------+--------------+
                |
                v
  +----------------------------+
  |   3. execute(cmd)          |   Run the command
  +-------------+--------------+
                |
                v
  +----------------------------+
  |   4. TASK_COMPLETE?        |
  +-------------+--------------+
          /           \
        Yes            No
         |              |
         v              v
  +-----------+   +----------------------------+
  |   Done    |   |   5. Append output         |
  +-----------+   |      to messages            |
                  +-------------+--------------+
                                |
                                +---> Go to step 1
```

---

## Why Docker?

Docker packages applications into containers: lightweight, isolated
environments that include everything needed to run. Each container
has its own filesystem, network, and processes, separate from the host.

```
+---------------------------------------------------------------+
|                        Host Machine                           |
|                                                               |
|   +-------------------------+   +-------------------------+   |
|   |      Container A        |   |      Container B        |   |
|   |                         |   |                         |   |
|   |   Python, bash          |   |   Go, curl              |   |
|   |   own filesystem        |   |   own filesystem        |   |
|   +-------------------------+   +-------------------------+   |
|                                                               |
|                       Docker Engine                           |
+---------------------------------------------------------------+
```

The agent runs **arbitrary bash commands**. Without containment:
- `rm -rf /`
- Access to your files, keys, network
- No isolation

Docker gives us a **sandbox**.

The agent can do whatever it wants inside the container
without affecting our machine.

---

## Our Dockerfile

```docker
# Start from a minimal Linux image
FROM alpine:3.21

# Install tools the agent might need when executing commands
RUN apk add --no-cache bash python3 go jq curl git

# Install uv (fast Python package manager)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Set up working directory
WORKDIR /app

# Install Python dependencies first (cached layer)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# Copy the agent source code
COPY . .

# Run the agent as the default command
ENTRYPOINT ["uv", "run", "agent.py"]
```

---

## Docker Compose

Docker Compose lets us define how to build and run our container
in a single file. Instead of passing flags every time, we declare
the configuration once and run it with a simple command.

```yaml
services:
  agent:
    build: .
    network_mode: host
    environment:
      - BASE_URL
      - MODEL
      - API_KEY
```

Run with:

```bash
docker compose run --build agent "your task here"
```

---

## Demo

### System

| Parameter       | Value                              |
|-----------------|------------------------------------|
| Model           | Qwen 2.5 Coder 14B Instruct       |
| Running on      | LM Studio (local)                  |
| GPU             | AMD Radeon RX 6700 (12GB VRAM)     |
| Context window  | 128K tokens                        |
| Quantization    | Q4_K_M                             |

### Network

```
+-------------+                +------------------+
|             |   Tailscale    |                  |
|   MacBook   | =============> |   PC at home     |
|   (here)    |   encrypted    |   LM Studio      |
|             |   tunnel       |   RX 6700 GPU    |
|             |                |                  |
+-------------+                +------------------+
```

### Prompts to try

    docker compose run agent "List all files from this directory"

    docker compose run agent "Make a Go script that calls the Pokemon API
    (https://pokeapi.co/api/v2/pokemon/pikachu), parses the response,
    and print its weight. Then run the script."

    docker compose run agent "Make a Python script that calls the ISS
    location API (http://api.open-notify.org/iss-now.json) and prints
    the current latitude and longitude. Then run the script."

---

# Thanks!

- Bluesky: https://bsky.app/profile/juan.bz
- Website: https://juan.bz
- GitHub: https://github.com/juanbzz
