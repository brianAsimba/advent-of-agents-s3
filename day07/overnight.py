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

# Fixed wording for failures. Code sends these to the user directly; the model never rewords them.
NOTICES = {
    "not_set_up": "Overnight summaries aren't set up yet. Sign in once and allow offline access to turn them on.",
    "access_revoked": "Your offline access was revoked or has expired. Sign in again to resume overnight summaries.",
    "possible_token_theft": ("SECURITY ALERT: an old copy of your sign-in token was used by someone other than "
                             "this agent. All of the agent's access to your account was revoked to protect you. "
                             "Review your account activity, then sign in again."),
}
OUTBOX: list[dict] = []        # messages delivered to users by code, outside the model
SECURITY_LOG: list[dict] = []  # security events for the owner/admin to review


def notify(user: str, code: str) -> None:
    OUTBOX.append({"user": user, "code": code, "message": NOTICES[code]})
    if code == "possible_token_theft":
        SECURITY_LOG.append({"user": user, "event": "refresh_token_reuse", "action": "token family revoked"})


class TokenError(Exception):
    """The OAuth provider refused the refresh token."""


def get_delegated_access_token(agent_token: str, user: str) -> str:
    """Layer 1: read the vaulted refresh token as the agent. Layer 2: exchange and rotate it."""
    name = f"refresh-token-{user}"
    version, refresh_token = vault.access_latest(agent_token, name)
    result = reports_api.refresh(refresh_token)
    if "error" in result:
        raise TokenError(result["error_description"])
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
        except LookupError:
            code = "not_set_up"                      # no refresh token was ever vaulted
        except TokenError as e:
            code = "possible_token_theft" if "reuse detected" in str(e) else "access_revoked"
        else:
            return reports_api.get_reports(token)
        # No human is awake to click a consent link: fail closed, and tell the user in fixed words.
        notify(user, code)
        return {"status": "cannot_act", "code": code, "user_message": NOTICES[code],
                "note": "This notice was already delivered to the user word for word. Do not reword or soften it."}

    return Agent(
        model=MODEL, name="overnight_summarizer",
        description="Summarizes a user's overnight incident reports while they sleep.",
        instruction=("Call fetch_overnight_reports once and summarize the incidents in 2-3 short bullets for a "
                     "morning briefing. If it returns a user_message, repeat it exactly, with no other words."),
        tools=[fetch_overnight_reports],
    )
