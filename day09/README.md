# Day 9 on Claude: Principal Access Boundaries (contain the blast radius)

In folder hierarchies, a grant on a folder is **inherited by every project under it**. An agent given read on the `manufacturing` folder for convenience can also read a sibling team's project. A prompt injection or a wrong tool call then becomes cross-project data exfiltration.

A **Principal Access Boundary (PAB)** is a fence around the *identity*, not the resource: "this agent may only ever reach these projects". A request succeeds only if **both** the IAM allow policy **and** the boundary allow it.

| Course (Google Cloud) | Here (`cloud.py`) |
|---|---|
| Folder → project hierarchy with inherited IAM | `PARENT`, `grant()`, `iam_allows()` walks up the chain |
| `gcloud iam principal-access-boundary-policies create` | `create_pab()` |
| `gcloud iam policy-bindings create --target-principal-set=…/projects/N` | `bind_pab()` to agents whose home is a project |
| `403 Forbidden: Principal Access Boundary violation` | Same message |
| Cloud Storage MCP `list_objects` | `list_objects` tool on fake buckets |

## Run
```bash
uv run pytest day09 -q
```
```bash
uv run python day09/demo.py
```
1. **Folder grant, no boundary:** the agent is asked to inspect its own bucket and, "for the quarterly audit", HR's payroll bucket. Both succeed (IAM inherited from the folder).
2. **Boundary bound to the stamping project's agents:** the same request. Stamping data still works; HR payroll gets `403 … Principal Access Boundary violation`.
3. **Someone mistakenly grants the agent read directly on HR:** still blocked. The boundary outlives future grant mistakes.

The audit lines show both checks side by side: `IAM=ALLOW (granted on folders/manufacturing)` and `PAB=…`.
