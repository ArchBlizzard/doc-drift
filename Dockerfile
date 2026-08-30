# DocDrift web UI for Render (or any Docker host).
# Needs both Python (the pipeline) and Node (the Claude Code CLI that
# claude-agent-sdk talks to).
FROM python:3.12-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates \
    && curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && npm install -g @anthropic-ai/claude-code \
    && apt-get purge -y curl && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir -e .

COPY run_web.py lessons.md ./

# Render sets PORT itself. HOST must be 0.0.0.0 so the outside world reaches it.
ENV HOST=0.0.0.0
CMD ["python", "run_web.py"]
