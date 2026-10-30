"""Day 23 step 2: blast radius of retiring (or breaking) one MCP server. Run from the repo root:

  uv run python day23/blast_radius.py legacy-search-mcp
  uv run python day23/blast_radius.py --list
Exit code 0 = SAFE, 1 = STOP (so a pipeline such as Day 17's can refuse the change).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import topology as t  # noqa: E402


def dependents_pattern(server: str) -> dict:
    """Static (declared contract): MCPServer <- Binding <- Agent."""
    return {"start": {"type": "MCPServer", "name": server},
            "hops": [{"label": t.DEPENDS_ON, "direction": "FROM", "types": ["Binding"]},
                     {"label": t.DEPENDS_ON, "direction": "FROM", "types": ["Agent"]}]}


def callers_pattern(server: str) -> dict:
    """Live (actual traffic): MCPServer <- SENDS_TRAFFIC <- Agent."""
    return {"start": {"type": "MCPServer", "name": server},
            "hops": [{"label": t.SENDS_TRAFFIC, "direction": "FROM", "types": ["Agent"]}]}


def blast_radius(g: t.Graph, server: str) -> dict:
    deps = {p[-1][1].name: p[-1][1].owner for p in t.query(g, dependents_pattern(server))}
    live = {p[1][1].name: {"owner": p[1][1].owner, **p[1][0].props} for p in t.query(g, callers_pattern(server))}
    rows = []
    for name in sorted(set(deps) | set(live)):
        kind = ("registered + live" if name in deps and name in live else
                "SHADOW (live, no binding)" if name in live else "stale binding (no traffic)")
        rows.append({"agent": name, "owner": deps.get(name) or live[name]["owner"], "kind": kind,
                     **({k: live[name][k] for k in ("calls", "error_rate", "p95_ms")} if name in live else {})})
    verdict = "SAFE" if not rows else "STOP"
    return {"server": server, "verdict": verdict, "rows": rows,
            "contact": sorted({r["owner"] for r in rows})}


def report(r: dict) -> str:
    lines = [f"Blast radius of {r['server']}:"]
    for row in r["rows"]:
        live = (f"{row['calls']:>4} calls/24h, errors {row['error_rate']:.0%}, p95 {row['p95_ms']:.0f} ms"
                if "calls" in row else "no traffic in 24h")
        lines.append(f"  {row['agent']:<26} {row['owner']:<18} {row['kind']:<28} {live}")
    lines.append(f"  VERDICT: {r['verdict']}" + (f"; contact first: {', '.join(r['contact'])}" if r["contact"] else
                                                   "; no registered dependents, no live callers"))
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    g = t.build(t.load_estate(), t.sample_traffic())
    if not argv or argv[0] == "--list":
        for n in sorted(n.name for n in g.nodes.values() if n.type == "MCPServer"):
            print(f"  MCPServer  {n}")
        return 0
    try:
        r = blast_radius(g, argv[0])
    except LookupError as e:
        print(f"ERROR: {e}")
        return 2
    print(report(r))
    return 0 if r["verdict"] == "SAFE" else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
