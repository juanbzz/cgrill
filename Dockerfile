# Start from a minimal Linux image
FROM alpine:3.21

# Install tools the agent might need when executing commands
RUN apk add --no-cache bash python3 py3-pip go jq curl git

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
