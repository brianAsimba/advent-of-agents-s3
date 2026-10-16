"""Two versions of the same help-desk agent.

shared_agent     holds ONE service token that sees every ticket, and is told in its prompt
                 to show only the current user's tickets. Day 6: "that is a suggestion, not
                 access control."
delegated_agent  calls the ticket system AS the user who asked, with that user's token from
                 the auth manager. The ticket system enforces what that user may see.
"""
import sys
from pathlib import Path

from google.adk.agents.llm_agent import Agent
from google.adk.agents.readonly_context import ReadonlyContext
from google.adk.models.lite_llm import LiteLlm
from google.adk.tools.tool_context import ToolContext

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "day05"))
import auth_manager  # noqa: E402
import iam_lib  # noqa: E402
import tickets_api  # noqa: E402

MODEL = LiteLlm(model="anthropic/claude-opus-5-5")


# ---------- anti-pattern: one shared token + "please filter" in the prompt ----------

def shared_list_tickets(status: str = "") -> dict:
    """Lists help-desk tickets. Optional status filter: 'open' or 'closed'."""
    return tickets_api.list_tickets(tickets_api.SERVICE_TOKEN, status or None)


def _shared_instruction(ctx: ReadonlyContext) -> str:
    return (f"You are a help-desk assistant. The signed-in user is '{ctx.user_id}'. "
            f"Only show tickets whose owner is '{ctx.user_id}'.")


def build_shared_agent() -> Agent:
    return Agent(model=MODEL, name="helpdesk_shared",
                 description="Help-desk assistant using one shared service token.",
                 instruction=_shared_instruction, tools=[shared_list_tickets])


# ---------- right way: delegated, on behalf of the user ----------

def build_delegated_agent() -> Agent:
    agent_token = iam_lib.mint("helpdesk_delegated")  # Day 5 identity, never shown to the model

    def list_my_tickets(tool_context: ToolContext, status: str = "") -> dict:
        """Lists the signed-in user's help-desk tickets. Optional status filter: 'open' or 'closed'."""
        user = tool_context.user_id  # set by the app after login, not by anything typed in chat
        try:
            token = auth_manager.retrieve_credentials(agent_token, user)
        except auth_manager.ConsentRequired as e:
            return {"status": "consent_required",
                    "message": f"{user} must sign in to the ticket system first.", "auth_uri": e.auth_uri}
        return tickets_api.list_tickets(token, status or None)

    return Agent(
        model=MODEL, name="helpdesk_delegated",
        description="Help-desk assistant that acts on behalf of the signed-in user.",
        instruction=("You are a help-desk assistant. Use list_my_tickets; it runs with the signed-in user's own "
                     "permissions. If it says consent is required, tell the user to sign in at the auth_uri."),
        tools=[list_my_tickets],
    )
