"""HR analytics agent on Claude, with PII redaction two ways.

mode="callbacks" (the course's design):
    before_agent_callback  -> ends the turn if the prompt is an injection
    before_model_callback  -> swaps every user message in the request for its redacted text
    Result: the MODEL never sees raw PII, but ADK still STORES the raw message in the session.

mode="ingress" (adds an ADK plugin):
    on_user_message_callback redacts the message before the runner stores it,
    so the session history (and anything that logs it) holds placeholders too.
"""
import sqlite3
import sys
from pathlib import Path
from typing import Optional

from google.adk.agents.callback_context import CallbackContext
from google.adk.agents.llm_agent import Agent
from google.adk.models import LlmRequest, LlmResponse
from google.adk.models.lite_llm import LiteLlm
from google.adk.plugins.base_plugin import BasePlugin
from google.genai import types

sys.path.insert(0, str(Path(__file__).resolve().parent))
import deid  # noqa: E402

MODEL = LiteLlm(model="anthropic/claude-opus-5-5")
MODEL_SAW: list[str] = []  # every user text actually sent to the model (for the demo)

_DB = sqlite3.connect(":memory:", check_same_thread=False)
_DB.execute("CREATE TABLE employees (employee_id INT, department TEXT, job_title TEXT, hire_date TEXT, salary INT)")
_DB.executemany("INSERT INTO employees VALUES (?,?,?,?,?)", [
    (1, "Engineering", "Software Engineer", "2021-03-15", 165000),
    (2, "Engineering", "Staff Engineer", "2018-07-01", 210000),
    (3, "Engineering", "Engineering Manager", "2019-05-20", 230000),
    (4, "Sales", "Account Executive", "2022-01-10", 120000),
    (5, "HR", "HR Business Partner", "2020-11-02", 115000),
])


def run_sql(query: str) -> dict:
    """Runs a read-only SQL SELECT on table employees(employee_id, department, job_title, hire_date, salary)."""
    if not query.strip().lower().startswith("select"):
        return {"status": "error", "error": "read-only: SELECT statements only"}
    cur = _DB.execute(query)
    return {"status": "ok", "columns": [c[0] for c in cur.description], "rows": cur.fetchall()}


def block_injection(callback_context: CallbackContext) -> Optional[types.Content]:
    """Once per turn. Returning Content ends the turn before the model is called."""
    uc = callback_context.user_content
    for part in (uc.parts or []) if uc else []:
        if part.text and deid.is_injection(part.text):
            return types.Content(role="model", parts=[types.Part(
                text="🛡️ Blocked: this looks like a prompt injection or jailbreak attempt.")])
    return None


def redact_for_model(callback_context: CallbackContext, llm_request: LlmRequest) -> Optional[LlmResponse]:
    """Before every model call: replace each user message (this turn and history) with its redacted text."""
    for content in llm_request.contents:
        if content.role != "user":
            continue
        for part in content.parts or []:
            if part.text:
                part.text = deid.deidentify(part.text)[0]
                MODEL_SAW.append(part.text)
    return None


class RedactAtIngress(BasePlugin):
    """Redacts the user's message when it arrives, before ADK stores it in the session."""

    def __init__(self):
        super().__init__(name="redact_at_ingress")

    async def on_user_message_callback(self, *, invocation_context, user_message: types.Content) -> Optional[types.Content]:
        parts = [types.Part(text=deid.deidentify(p.text)[0]) if p.text else p for p in (user_message.parts or [])]
        return types.Content(role=user_message.role, parts=parts)


def build() -> Agent:
    return Agent(
        model=MODEL, name="hr_analytics",
        description="HR analytics assistant over a read-only employees table.",
        instruction=("You answer HR analytics questions with run_sql on the employees table. Prompts are sanitized: "
                     "values like [EMAIL_ADDRESS] or [US_SOCIAL_SECURITY_NUMBER] are masked. Never try to unmask or "
                     "guess them. Report aggregates, not individual salaries."),
        tools=[run_sql],
        before_agent_callback=block_injection,
        before_model_callback=redact_for_model,
    )
