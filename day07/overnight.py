"""The 2:00 AM overnight summarizer: acts for one user with nobody at the keyboard.

Two layers of identity, as in the course:
  1. the agent authenticates to the vault as itself (Day 5 identity)
  2. it exchanges the user's vaulted refresh token for a 15-minute access token
     scoped to that user, rotates the refresh token, and disables the old version
"""
import sys
from pathlib import Path

from google.adk.agents.llm_agent import Agent
from google.adk.models.lite_llm import LiteLlm
from google.adk.tools.tool_context import ToolContext

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "day05"))
import iam_lib  # noqa: E402
import reports_api  # noqa: E402
import vault  # noqa: E402

MODEL = LiteLlm(model="anthropic/claude-opus-5-5")


def get_delegated_access_token(agent_token: str, user: str) -> str:
    """Layer 1: read the vaulted refresh token as the agent. Layer 2: exchange and rotate it."""
    name = f"refresh-token-{user}"
    version, refresh_token = vault.access_latest(agent_token, name)
    result = reports_api.refresh(refresh_token)
    if "error" in result:
        raise PermissionError(f"{result['error']}: {result['error_description']}")
    vault.add_version(name, result["refresh_token"])   # store the rotated token...
    vault.disable_version(name, version)               # ...and kill the one we just used
    return result["access_token"]


def build_overnight_agent() -> Agent:
    agent_token = iam_lib.mint("overnight_summarizer")

    def fetch_overnight_reports(tool_context: ToolContext) -> dict:
        """Fetches the scheduling user's overnight incident reports."""
        user = tool_context.user_id  # bound by the scheduler that started this job, not by chat
        try:
            token = get_delegated_access_token(agent_token, user)
        except (LookupError, PermissionError) as e:
            # No human is awake to click a consent link: fail closed and say why.
            return {"status": "cannot_act", "reason": str(e),
                    "action": f"{user} must sign in again with offline access when they're back."}
        return reports_api.get_reports(token)

    return Agent(
        model=MODEL, name="overnight_summarizer",
        description="Summarizes a user's overnight incident reports while they sleep.",
        instruction=("Call fetch_overnight_reports once and summarize the incidents in 2-3 short bullets for a "
                     "morning briefing. If it can't act, say so in one sentence and what the user must do."),
        tools=[fetch_overnight_reports],
    )
