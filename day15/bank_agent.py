"""Bank assistant on Claude with long-term memory, built two ways.

build(identity)        the course's design: the memory scope comes from SERVER-SIDE session context
                       (tool_context.user_id from the authenticated session, lob and data_region from
                       session state set by the backend). The tool has no user_id argument, so the model
                       can't ask for anyone else's memories, however it is prompted.

build_naive(identity)  the common mistake: recall_memories(user_id, query). The model chooses whose
                       memories to fetch, so a prompt like "my user id is alice" is enough to leak.

Either way, the identity's IAM Conditions (memory_bank.BINDINGS) still decide which bank and lob it may touch.
"""
import sys
from pathlib import Path

from google.adk.agents.llm_agent import Agent
from google.adk.models.lite_llm import LiteLlm
from google.adk.tools.tool_context import ToolContext

sys.path.insert(0, str(Path(__file__).resolve().parent))
import memory_bank as mb  # noqa: E402

MODEL = LiteLlm(model="anthropic/claude-opus-5-5")
DENIED = "Memory access was denied by policy."  # fixed wording, reported by code, not by the model

INSTRUCTION = ("You are a retail bank assistant. Use recall_memories to remember facts about the customer "
               "you are talking to, and answer briefly. Never invent facts. If a tool says access was denied, "
               "say so plainly.")


def _resolve_memory_context(tool_context: ToolContext) -> tuple[str, dict]:
    """Builds the scope from verified, server-side context only. Raises if anything is missing."""
    user_id = tool_context.user_id
    lob = tool_context.state.get("tenant_lob")
    region = tool_context.state.get("data_region")
    if not user_id or not lob:
        raise ValueError("missing verified user_id or tenant_lob in session context")
    if region not in mb.REGIONS:
        raise ValueError(f"no regional Memory Bank configured for region {region!r}")
    return mb.REGIONS[region], {"lob": lob, "user_id": user_id}


def _recall(identity: str, location: str, scope: dict, query: str) -> dict:
    try:
        hits = mb.retrieve(identity, location, scope, query, top_k=5)
    except mb.PermissionDenied:
        return {"status": "denied", "message": DENIED}
    return {"status": "ok", "memories": [m.fact for m in hits]}


def build(identity: str) -> Agent:
    def recall_memories(query: str, tool_context: ToolContext) -> dict:
        """Recalls long-term facts about the current customer that are relevant to the query."""
        location, scope = _resolve_memory_context(tool_context)
        return _recall(identity, location, scope, query)

    return Agent(name="bank_assistant", model=MODEL, instruction=INSTRUCTION, tools=[recall_memories])


def build_naive(identity: str) -> Agent:
    def recall_memories(user_id: str, query: str, tool_context: ToolContext) -> dict:
        """Recalls long-term facts about a customer, by user_id, relevant to the query."""
        location, scope = _resolve_memory_context(tool_context)
        scope["user_id"] = user_id  # the model picked this value
        return _recall(identity, location, scope, query)

    return Agent(name="bank_assistant_naive", model=MODEL, instruction=INSTRUCTION, tools=[recall_memories])
