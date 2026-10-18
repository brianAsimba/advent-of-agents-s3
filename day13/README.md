# Day 13 on Claude: run model-written code in a sandbox

Agents often need to write and run their own code (a mortgage schedule, a CSV analysis, a simulation). Running that code **on your machine** exposes your credentials (environment variables), your files, your network, and your CPU (infinite loops). The course runs it in Google's air-gapped **Code Execution sandbox**. Claude has its own equivalent: Anthropic's **code execution tool**, which runs code in an isolated container on Anthropic's servers.

| Course (Google Cloud) | Here (Claude) |
|---|---|
| `execute_sandbox_code` tool → Agent Platform sandbox | `code_execution_20260521` server tool, called via the Anthropic SDK |
| Sandbox name in `tool_context.state`, reused across turns | The response's `container.id`, passed back on the next request |
| Variables + up to 100 MB of files persist until TTL | **Files persist.** Claude usually runs `python3` through bash (a new process each time), so state is saved to a file and reloaded |
| TTL / `reset_or_cleanup_sandbox` | `container.expires_at`; start a new session to get a fresh container |

## Run
```bash
uv run pytest day13 -q
```
```bash
uv run python day13/demo.py
```
1. A harmless probe ("can I see API keys? reach the internet? read the home folder?") **run on your PC**, the unsafe way. It prints only YES/NO answers and counts, never secret values.
2. **The same probe run in Anthropic's sandbox.** Compare line by line.
3. **A stateful sandbox session:** the course's mortgage questions over three turns in one container (expected payment **$2,807.41**, total interest **≈ $560,669**).
