"""Day 22 step 2: the GenAI bridge. OpenInference spans gain the gen_ai.* keys that GenAI-convention readers
(Agent Runtime's Session view; here, our SQL view) look for. OpenInference attributes stay intact.

  session.id                     -> gen_ai.conversation.id
  AGENT span (or root)           -> gen_ai.operation.name = invoke_agent
  LLM span                       -> generate_content, + gen_ai.usage.input_tokens / output_tokens
  TOOL span                      -> execute_tool, + gen_ai.tool.name
  status OK                      -> UNSET (the console counts any non-UNSET status as an error)

OTel's Python SDK hands on_end() a read-only span, so like the course's 15-liner this writes to the
span's internal attribute dict. It must run BEFORE the exporting processor, hence install_ prepends it.
"""
from opentelemetry.sdk.trace import SpanProcessor, TracerProvider
from opentelemetry.trace import Status, StatusCode

KIND = {"AGENT": "invoke_agent", "CHAIN": "invoke_agent", "LLM": "generate_content", "TOOL": "execute_tool"}


class GenAIBridgeSpanProcessor(SpanProcessor):
    def on_end(self, span) -> None:
        a = span._attributes  # noqa: SLF001 (see module docstring)
        if a is None:
            return
        kind = a.get("openinference.span.kind")
        if "session.id" in a:
            a["gen_ai.conversation.id"] = a["session.id"]
        op = KIND.get(kind) or ("invoke_agent" if span.parent is None else None)
        if op:
            a["gen_ai.operation.name"] = op
        if kind == "LLM":
            for src, dst in (("llm.token_count.prompt", "gen_ai.usage.input_tokens"),
                             ("llm.token_count.completion", "gen_ai.usage.output_tokens"),
                             ("llm.model_name", "gen_ai.request.model")):
                if src in a:
                    a[dst] = a[src]
        if kind == "TOOL" and "tool.name" in a:
            a["gen_ai.tool.name"] = a["tool.name"]
        if span.status.status_code == StatusCode.OK:
            span._status = Status(StatusCode.UNSET)  # noqa: SLF001


def install_genai_bridge(tp: TracerProvider) -> None:
    """Prepends the bridge so it runs before exporters."""
    multi = tp._active_span_processor  # noqa: SLF001
    multi._span_processors = (GenAIBridgeSpanProcessor(), *multi._span_processors)  # noqa: SLF001
