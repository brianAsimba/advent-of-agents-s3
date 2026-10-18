"""Day 13 tests (no real API calls)."""
import os
import subprocess
import sys
from datetime import datetime
from types import SimpleNamespace

import sandbox
from probe import PROBE


def test_probe_never_prints_secret_values():
    env = dict(os.environ, ANTHROPIC_API_KEY="sk-ant-SHOULD-NOT-APPEAR", MY_SECRET="hunter2-SHOULD-NOT-APPEAR")
    out = subprocess.run([sys.executable, "-c", PROBE], capture_output=True, text=True, env=env, timeout=30).stdout
    assert "SHOULD-NOT-APPEAR" not in out and "ANTHROPIC_API_KEY visible: YES" in out


class FakeClient:
    """Two responses: first pauses mid-turn, second finishes. Records the container passed in."""
    def __init__(self):
        self.messages, self.calls = self, []

    def create(self, **kw):
        self.calls.append(kw)
        tool = SimpleNamespace(type="server_tool_use", input={"code": "print(2+2)"},
                               model_dump=lambda **k: {"type": "server_tool_use"})
        result = SimpleNamespace(type="bash_code_execution_tool_result",
                                 content=SimpleNamespace(stdout="4\n", stderr="", error_code=None),
                                 model_dump=lambda **k: {"type": "bash_code_execution_tool_result"})
        text = SimpleNamespace(type="text", text="The answer is 4.", model_dump=lambda **k: {"type": "text"})
        cont = SimpleNamespace(id="container_abc", expires_at=datetime(2026, 10, 17, 18, 0))
        stop = "pause_turn" if len(self.calls) == 1 else "end_turn"
        return SimpleNamespace(content=[tool, result] if stop == "pause_turn" else [text], container=cont, stop_reason=stop)


def test_pause_turn_is_continued_and_container_is_reused():
    c, s = FakeClient(), sandbox.Session()
    answer, runs = sandbox.ask(s, "what is 2+2", client=c)
    assert answer == "The answer is 4." and runs[0]["stdout"] == "4\n"
    assert "container" not in c.calls[0] and c.calls[1]["container"] == "container_abc"


def test_next_turn_uses_same_container():
    c, s = FakeClient(), sandbox.Session()
    sandbox.ask(s, "first", client=c)
    c.calls.clear()
    sandbox.ask(s, "second", client=c)
    assert c.calls[0]["container"] == "container_abc"
