"""Day 23 local App Topology: one graph of the agent estate, queried with small JSON patterns.

What Google Cloud does                                   Here
-------------------------------------------------------  -------------------------------------------------------
Discovered resources = nodes (Cloud Run, GKE, Reasoning   Node(type, name, owner): Agent, MCPServer, Binding
  Engines, Agent Registry agents, MCP servers, bindings)
DEPENDS_ON edges from the registry                        from estate.json: Agent -> Binding -> MCPServer
Observability/SENDS_TRAFFIC edges from Cloud Trace        from OpenTelemetry tool-call spans (traffic.jsonl):
  with error rate and p95 latency                           calls, error rate, p95 per (agent, server)
`gcloud app-topology resources-graph generate` + pattern  query(pattern): start node, then hops (label, direction,
                                                            node types); FROM = "who points at me?"
"""
import json
import random
from dataclasses import dataclass, field
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEPENDS_ON, SENDS_TRAFFIC = "DEPENDS_ON", "Observability/SENDS_TRAFFIC"


@dataclass(frozen=True)
class Node:
    type: str   # Agent | MCPServer | Binding
    name: str
    owner: str = ""


@dataclass
class Edge:
    src: Node
    dst: Node
    label: str
    props: dict = field(default_factory=dict)


@dataclass
class Graph:
    nodes: dict[tuple[str, str], Node] = field(default_factory=dict)
    edges: list[Edge] = field(default_factory=list)

    def node(self, type_: str, name: str) -> Node | None:
        return self.nodes.get((type_, name))

    def add(self, n: Node) -> Node:
        return self.nodes.setdefault((n.type, n.name), n)


def _p95(values: list[float]) -> float:
    v = sorted(values)
    return v[min(len(v) - 1, int(round(0.95 * (len(v) - 1))))]


def build(estate: dict, spans: list[dict]) -> Graph:
    g = Graph()
    for s in estate["mcp_servers"]:
        g.add(Node("MCPServer", s["name"], s["owner"]))
    for a in estate["agents"]:
        g.add(Node("Agent", a["name"], a["owner"]))
    for b in estate["bindings"]:
        agent, server = g.node("Agent", b["agent"]), g.node("MCPServer", b["server"])
        binding = g.add(Node("Binding", f"{b['agent']}->{b['server']}", agent.owner))
        g.edges += [Edge(agent, binding, DEPENDS_ON), Edge(binding, server, DEPENDS_ON)]
    calls: dict[tuple[str, str], list[dict]] = {}
    for sp in spans:
        a = sp["attributes"]
        if a.get("gen_ai.operation.name") == "execute_tool" and a.get("mcp.server.name"):
            calls.setdefault((a["gen_ai.agent.name"], a["mcp.server.name"]), []).append(sp)
    for (agent_name, server_name), ss in calls.items():
        agent = g.node("Agent", agent_name) or g.add(Node("Agent", agent_name, "unknown"))  # discovered from traces
        server = g.node("MCPServer", server_name) or g.add(Node("MCPServer", server_name, "unknown"))
        errors = sum(s["status"] == "ERROR" for s in ss)
        g.edges.append(Edge(agent, server, SENDS_TRAFFIC, {
            "calls": len(ss), "error_rate": round(errors / len(ss), 3),
            "p95_ms": round(_p95([(s["end_ns"] - s["start_ns"]) / 1e6 for s in ss]), 1)}))
    return g


def query(g: Graph, pattern: dict) -> list[list]:
    """pattern = {"start": {"type", "name"}, "hops": [{"label", "direction": "FROM"|"TO", "types": [...]}, ...]}
    Returns every path as [node, (edge, node), (edge, node), ...]."""
    start = g.node(pattern["start"]["type"], pattern["start"]["name"])
    if start is None:
        raise LookupError(f"{pattern['start']['type']} '{pattern['start']['name']}' not found in the topology")
    paths = [[start]]
    for hop in pattern["hops"]:
        nxt = []
        for p in paths:
            here = p[-1] if isinstance(p[-1], Node) else p[-1][1]
            for e in g.edges:
                if e.label != hop["label"]:
                    continue
                other = e.src if hop["direction"] == "FROM" and e.dst == here else \
                    e.dst if hop["direction"] == "TO" and e.src == here else None
                if other is not None and other.type in hop["types"]:
                    nxt.append(p + [(e, other)])
        paths = nxt
    return paths


def load_estate() -> dict:
    return json.loads((HERE / "estate.json").read_text(encoding="utf-8"))


def sample_traffic(seed: int = 23) -> list[dict]:
    """24 h of tool-call spans, in the Day 22 shape. Includes a shadow consumer (nightly-report-job calls
    legacy-search-mcp with no binding) and a stale binding (revenue-insights-agent never calls it)."""
    rnd = random.Random(seed)
    mix = [("revenue-insights-agent", "customer-analytics-mcp", 140, 0.01, 180),
           ("governed-release-auditor", "release-notes-mcp", 30, 0.0, 90),
           ("billing-agent", "crm-accounts-mcp", 410, 0.02, 220),
           ("support-concierge", "crm-accounts-mcp", 95, 0.0, 240),
           ("support-concierge", "legacy-search-mcp", 60, 0.05, 900),
           ("nightly-report-job", "legacy-search-mcp", 12, 0.25, 2600)]
    spans, t = [], 0
    for agent, server, n, err, ms in mix:
        for _ in range(n):
            dur = rnd.lognormvariate(0, 0.35) * ms
            t += rnd.randint(1, 200) * 1_000_000
            spans.append({"name": f"execute_tool {server}", "start_ns": t, "end_ns": t + int(dur * 1e6),
                          "status": "ERROR" if rnd.random() < err else "UNSET",
                          "attributes": {"gen_ai.operation.name": "execute_tool", "gen_ai.agent.name": agent,
                                         "mcp.server.name": server}})
    return spans
