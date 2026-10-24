"""billing_agent on Claude, plus the egress side: the platform only builds toolsets for allowlisted MCP endpoints.

Two gateways, two questions:
  egress  (Agent Gateway, Days 8/18/19): may THIS agent reach THIS endpoint?  -> egress_toolset()
  ingress (Apigee, Day 20):              how may agents consume THIS backend? -> ingress_gateway.py
"""
from google.adk.agents.llm_agent import Agent
from google.adk.models.lite_llm import LiteLlm
from google.adk.tools.mcp_tool import McpToolset, StreamableHTTPConnectionParams

MODEL = LiteLlm(model="anthropic/claude-opus-5-5")
EGRESS_ALLOW = {"127.0.0.1:8300", "127.0.0.1:8302", "127.0.0.1:8303"}  # governed MCP endpoints only, deny the rest


class EgressDenied(Exception):
    pass


def egress_toolset(url: str, client_id: str) -> McpToolset:
    host = url.split("//", 1)[-1].split("/", 1)[0]
    if host not in EGRESS_ALLOW:
        raise EgressDenied(f"403: egress to {host} is not allowlisted for this agent")
    return McpToolset(connection_params=StreamableHTTPConnectionParams(
        url=url, timeout=15, headers={"x-client-id": client_id}))


def build(url: str, client_id: str = "billing-agent") -> Agent:
    return Agent(name="billing_agent", model=MODEL,
                 instruction=("You answer billing questions about customer accounts using lookup_customer_account. "
                              "Be brief. If a tool call fails or is rate limited, say so and stop."),
                 tools=[egress_toolset(url, client_id)])
