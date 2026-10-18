"""Run model-written code in Anthropic's code execution sandbox, reusing one container across turns.

Course (Google Cloud)                                  Here (Claude)
-----------------------------------------------------  ------------------------------------------------
Agent Platform Code Execution sandbox, air-gapped        Anthropic code execution tool (code_execution_20260521),
                                                         runs in an isolated container on Anthropic's servers
Sandbox name kept in tool_context.state, reused          container id from the first response, passed back
  so variables and files persist across turns              on later requests. FILES persist; Claude usually runs
                                                           `python3` via bash (a new process each time), so
                                                           working variables are saved to a file and reloaded
TTL (30 min here, up to 14 days)                         container.expires_at from the API
reset_or_cleanup_sandbox                                 start a new conversation without the container id
"""
from dataclasses import dataclass, field

MODEL = "claude-opus-5-5"
TOOLS = [{"type": "code_execution_20260521", "name": "code_execution"}]


@dataclass
class Session:
    """One user conversation with its own sandbox container."""
    messages: list = field(default_factory=list)
    container_id: str | None = None
    container_expires: str | None = None


def _outputs(content) -> list[dict]:
    """Pulls the code Claude ran and what the sandbox printed out of the response blocks."""
    runs, code = [], None
    for b in content:
        if b.type == "server_tool_use":
            inp = b.input or {}
            code = inp.get("code") or inp.get("command") or str(inp)
        elif b.type.endswith("code_execution_tool_result"):
            c = b.content
            runs.append({"code": code, "stdout": getattr(c, "stdout", "") or "",
                         "stderr": getattr(c, "stderr", "") or "",
                         "error": getattr(c, "error_code", None)})
    return runs


def ask(session: Session, text: str, client=None) -> tuple[str, list[dict]]:
    """Sends one user turn; returns (Claude's final text, code runs in the sandbox)."""
    if client is None:
        import anthropic
        client = anthropic.Anthropic()
    session.messages.append({"role": "user", "content": text})
    runs = []
    while True:
        kw = dict(model=MODEL, max_tokens=16000, tools=TOOLS, messages=session.messages,
                  output_config={"effort": "low"})
        if session.container_id:
            kw["container"] = session.container_id  # same sandbox → variables survive
        r = client.messages.create(**kw)
        session.messages.append({"role": "assistant",
                                 "content": [b.model_dump(exclude_none=True) for b in r.content]})
        if r.container:
            session.container_id = r.container.id
            session.container_expires = str(r.container.expires_at)
        runs += _outputs(r.content)
        if r.stop_reason == "refusal":
            return "[MODEL DECLINED: safety refusal]", runs
        if r.stop_reason != "pause_turn":  # pause_turn = long server-side work; continue the turn
            text_out = " ".join(b.text for b in r.content if b.type == "text")
            return text_out, runs
