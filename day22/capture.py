"""Day 22 step 1: run one agent on one question and save its OpenTelemetry spans as JSON (in-memory exporter;
nothing leaves the machine except the model calls).

  uv run python day22/capture.py adk          ADK on Claude, native OTel (GenAI conventions: gen_ai.*)
  uv run python day22/capture.py anthropic    a plain Anthropic SDK tool loop + Arize OpenInference instrumentor
  options: --question default|serial   --no-bridge (anthropic only: skip the GenAI bridge)

Content capture follows the course: ADK's copy of prompts/responses is kept OFF spans
(ADK_CAPTURE_MESSAGE_CONTENT_IN_SPANS=false). OpenInference puts words on spans by design.
"""
import argparse
import asyncio
import json
import os
import sys
import warnings
from pathlib import Path

os.environ.setdefault("ADK_CAPTURE_MESSAGE_CONTENT_IN_SPANS", "false")
os.environ.setdefault("OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT", "EVENT_ONLY")
warnings.filterwarnings("ignore", message=r"\[EXPERIMENTAL\]", category=UserWarning)

from dotenv import load_dotenv  # noqa: E402
from opentelemetry import trace  # noqa: E402
from opentelemetry.sdk.trace import TracerProvider  # noqa: E402
from opentelemetry.sdk.trace.export import SimpleSpanProcessor  # noqa: E402
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter  # noqa: E402

HERE = Path(__file__).resolve().parent
TRACES = HERE / "traces"
load_dotenv(HERE / ".env")
sys.path.insert(0, str(HERE))
import genai_bridge  # noqa: E402

MODEL = "claude-opus-5-5"
QUESTIONS = {
    "default": "Hi, I'm jane.doe@example.com. Where is my order A-17?",
    "serial": "Check orders A-17 and B-42 one after the other, then tell me which one ships first.",
}
ORDERS = {"A-17": {"status": "shipped", "eta": "2026-10-27"}, "B-42": {"status": "packing", "eta": "2026-10-30"}}
INSTRUCTION = "You are a support agent. Use order_status for every order you mention. Be brief."


def order_status(order_id: str) -> dict:
    """Shipping status and ETA of an order, e.g. 'A-17'."""
    return {"order_id": order_id, **ORDERS.get(order_id, {"status": "unknown"})}


def _span_json(sp) -> dict:
    return {"name": sp.name, "trace_id": f"{sp.context.trace_id:032x}", "span_id": f"{sp.context.span_id:016x}",
            "parent_id": f"{sp.parent.span_id:016x}" if sp.parent else None,
            "start_ns": sp.start_time, "end_ns": sp.end_time, "status": sp.status.status_code.name,
            "attributes": {k: (list(v) if isinstance(v, tuple) else v) for k, v in sp.attributes.items()}}


async def run_adk(question: str, tp: TracerProvider) -> None:
    trace.set_tracer_provider(tp)
    from google.adk.agents.llm_agent import Agent
    from google.adk.models.lite_llm import LiteLlm
    from google.adk.runners import InMemoryRunner
    from google.genai import types
    agent = Agent(name="support_adk", model=LiteLlm(model=f"anthropic/{MODEL}"), instruction=INSTRUCTION,
                  tools=[order_status])
    runner = InMemoryRunner(agent=agent, app_name="day22")
    s = await runner.session_service.create_session(app_name="day22", user_id="customer")
    async for _ in runner.run_async(user_id="customer", session_id=s.id,
                                    new_message=types.Content(role="user", parts=[types.Part(text=question)])):
        pass


def run_anthropic(question: str, tp: TracerProvider, bridge: bool) -> None:
    """A minimal 'framework': a tool loop on the Anthropic SDK, instrumented the OpenInference way."""
    import anthropic
    from openinference.instrumentation import using_session
    from openinference.instrumentation.anthropic import AnthropicInstrumentor
    if bridge:
        genai_bridge.install_genai_bridge(tp)
    AnthropicInstrumentor().instrument(tracer_provider=tp)
    tracer = tp.get_tracer("support_anthropic")
    client = anthropic.Anthropic()
    tools = [{"name": "order_status", "description": order_status.__doc__,
              "input_schema": {"type": "object", "properties": {"order_id": {"type": "string"}},
                               "required": ["order_id"]}}]
    messages = [{"role": "user", "content": question}]
    try:
        with using_session(f"oi-{os.urandom(4).hex()}"), tracer.start_as_current_span(
                "support_anthropic", attributes={"openinference.span.kind": "AGENT", "input.value": question}) as root:
            for _ in range(6):
                r = client.messages.create(model=MODEL, max_tokens=400, system=INSTRUCTION, tools=tools,
                                           messages=messages)
                messages.append({"role": "assistant", "content": r.content})
                calls = [b for b in r.content if b.type == "tool_use"]
                if not calls:
                    root.set_attribute("output.value", " ".join(b.text for b in r.content if b.type == "text"))
                    break
                results = []
                for c in calls:
                    with tracer.start_as_current_span(c.name, attributes={
                            "openinference.span.kind": "TOOL", "tool.name": c.name,
                            "tool.parameters": json.dumps(c.input)}) as ts:
                        out = order_status(**c.input)
                        ts.set_attribute("output.value", json.dumps(out))
                    results.append({"type": "tool_result", "tool_use_id": c.id, "content": json.dumps(out)})
                messages.append({"role": "user", "content": results})
    finally:
        AnthropicInstrumentor().uninstrument()


def capture(agent: str, question: str = "default", bridge: bool = True) -> Path:
    exporter = InMemorySpanExporter()
    tp = TracerProvider()
    tp.add_span_processor(SimpleSpanProcessor(exporter))
    q = QUESTIONS[question]
    if agent == "adk":
        asyncio.run(run_adk(q, tp))
    else:
        run_anthropic(q, tp, bridge)
    TRACES.mkdir(exist_ok=True)
    out = TRACES / f"{agent}__{question}.json"
    out.write_text(json.dumps({"agent": agent, "framework": "adk" if agent == "adk" else "openinference",
                               "question": q, "spans": [_span_json(s) for s in exporter.get_finished_spans()]},
                              indent=2), encoding="utf-8")
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("agent", choices=["adk", "anthropic"])
    ap.add_argument("--question", default="default", choices=list(QUESTIONS))
    ap.add_argument("--no-bridge", action="store_true")
    a = ap.parse_args()
    p = capture(a.agent, a.question, not a.no_bridge)
    print(f"{len(json.loads(p.read_text())['spans'])} spans -> {p.relative_to(HERE.parent)}")
