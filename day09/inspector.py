"""The storage inspector agent (the course's pab_storage_inspector), on Claude."""
import sys
from pathlib import Path

from google.adk.agents.llm_agent import Agent
from google.adk.models.lite_llm import LiteLlm

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "day05"))
import cloud  # noqa: E402
import iam_lib  # noqa: E402

MODEL = LiteLlm(model="anthropic/claude-opus-5-5")


def build() -> Agent:
    token = iam_lib.mint("storage_inspector")

    def list_objects(bucket: str) -> dict:
        """Lists the objects in a storage bucket, e.g. 'stamping-press-data'."""
        return cloud.list_objects(token, bucket.removeprefix("gs://"))

    return Agent(
        model=MODEL, name="storage_inspector",
        description="Inspects storage buckets and lists their objects.",
        instruction=("You inspect storage buckets with list_objects and summarize what you find. "
                     "If access fails, report the exact error message."),
        tools=[list_objects],
    )
