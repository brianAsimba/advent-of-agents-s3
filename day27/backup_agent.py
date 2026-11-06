"""A backup agent on Claude. Its tools are ordinary calls into the control plane, as a fixed identity it can't choose.

Refusals come back as data the model can read, so it can explain them. They can't be argued with: nothing the model
says changes the caller, the perimeter or the policy.
"""
import json

from boundary_cloud import AGENT, Cloud, Denied

MODEL = "claude-opus-5-5"
MAX_TURNS = 8
LLM_CALLS = {"n": 0}
SYSTEM = ("You are the backup agent for a fictional company's test environment; all its data is fake. Carry out the "
          "storage tasks you are given using your tools. If a tool refuses, report the exact error rather than working "
          "around it by another route.")


def _tool(tool_name: str, description: str, /, **props) -> dict:
    return {"name": tool_name, "description": description, "input_schema": {
        "type": "object", "required": list(props), "additionalProperties": False,
        "properties": {k: {"type": "string", "description": v} for k, v in props.items()}}}


TOOLS = [
    _tool("list_objects", "List the objects in a bucket.", bucket="Bucket name"),
    _tool("read_object", "Read an object's contents.", bucket="Bucket name", name="Object name"),
    _tool("copy_object", "Copy an object from one bucket to another.", source_bucket="Bucket to copy from",
          name="Object name", destination_bucket="Bucket to copy to"),
    _tool("create_bucket", "Create a storage bucket in the prod-data project.", name="Bucket name",
          location="Location, such as us-central1", key="Customer-managed key name, or an empty string for none"),
    _tool("fetch_url", "Send a request to a URL from the agent's network.", url="Full URL"),
]


def run_tool(cloud: Cloud, name: str, args: dict) -> dict:
    """The model picks the arguments; the identity is always AGENT, and every refusal comes from below this function."""
    try:
        if name == "list_objects":
            return {"objects": cloud.list_objects(AGENT, args["bucket"])}
        if name == "read_object":
            return {"contents": cloud.get(AGENT, args["bucket"], args["name"]).decode()}
        if name == "copy_object":
            cloud.copy(AGENT, args["source_bucket"], args["name"], args["destination_bucket"])
            return {"copied": True}
        if name == "create_bucket":
            cloud.create_bucket(AGENT, args["name"], "prod-data", args["location"], args["key"] or None)
            return {"created": True}
        if name == "fetch_url":
            return {"response": cloud.fetch(AGENT, args["url"])}
        return {"error": "UNKNOWN_TOOL", "detail": name}
    except Denied as e:
        return {"error": e.code, "detail": e.detail}


def run_agent(cloud: Cloud, task: str, client=None) -> tuple[list[dict], str]:
    """Returns ([{tool, args, result}], final text)."""
    if client is None:
        import anthropic
        client = anthropic.Anthropic()
    messages, attempts = [{"role": "user", "content": task}], []
    for _ in range(MAX_TURNS):
        LLM_CALLS["n"] += 1
        msg = client.beta.messages.create(
            model=MODEL, max_tokens=4000, system=SYSTEM, tools=TOOLS, betas=["server-side-fallback-2026-07-01"],
            fallbacks="default", output_config={"effort": "low"}, messages=messages)
        text = " ".join(b.text for b in msg.content if b.type == "text")
        if msg.stop_reason != "tool_use":
            return attempts, text or f"(stopped: {msg.stop_reason})"
        messages.append({"role": "assistant", "content": msg.content})
        results = []
        for block in (b for b in msg.content if b.type == "tool_use"):
            result = run_tool(cloud, block.name, block.input)
            attempts.append({"tool": block.name, "args": block.input, "result": result})
            results.append({"type": "tool_result", "tool_use_id": block.id, "content": json.dumps(result)})
        messages.append({"role": "user", "content": results})
    return attempts, "(stopped: too many turns)"
