"""The loop lab: a report job that never finishes, polled by an agent told not to give up."""
from token_meter import Budget, Limits, Meter, Result, run_bounded

AGENT = "report_poller"
SYSTEM = [{"type": "text", "text": ("You are a reporting agent. Request status with check_report_status and keep checking "
                                    "until the report is READY, then say it is ready. Do not stop while it is PENDING.")}]
CHECK = {"name": "check_report_status", "description": "Check a report job's status. Returns PENDING or READY.",
         "input_schema": {"type": "object", "additionalProperties": False, "required": ["report_id"],
                          "properties": {"report_id": {"type": "string"}}}}


def check_report_status(_name: str, _args: dict) -> dict:
    return {"status": "PENDING"}  # stuck forever, with no error, which is what makes this expensive


def run_stuck(client, session: str, variant: str, meter: Meter, budget: Budget, limits: Limits) -> Result:
    return run_bounded(client, agent=AGENT, session=session, variant=variant, system=SYSTEM, tools=[CHECK],
                       handler=check_report_status, task="Get me report R-42.", effort="low", meter=meter, budget=budget,
                       limits=limits, max_tokens=500)
