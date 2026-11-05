"""Child process: loads the PR's app, seeds fake data, sends HTTP inputs through Flask's in-process test client.

Nothing listens on a port. shell() only records what it was given and never runs anything.
Reads {"app_dir", "canaries", "probes"} on stdin; writes one JSON result list on stdout.
"""
import importlib.util
import json
import sqlite3
import sys
from pathlib import Path

BODY_LIMIT = 20000


def seed(canaries: dict) -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.executescript("""
        CREATE TABLE products (id INTEGER PRIMARY KEY, name TEXT);
        CREATE TABLE users (name TEXT, api_token TEXT);
        CREATE TABLE invoices (id INTEGER PRIMARY KEY, owner TEXT, memo TEXT);
        INSERT INTO products VALUES (1, 'Widget'), (2, 'Gadget');
    """)
    conn.execute("INSERT INTO users VALUES ('alice', 'alice-token'), ('bob', ?)", (canaries["bob_token"],))
    conn.execute("INSERT INTO invoices VALUES (1, 'alice', 'alice-march-invoice'), (2, 'bob', ?)",
                 (canaries["bob_memo"],))
    return conn


def main() -> None:
    req = json.loads(sys.stdin.read())
    out, sys.stdout = sys.stdout, sys.stderr  # prints from the PR's code must not land in the result
    calls: list = []

    def shell(command):
        calls.append(command)
        return "pong"

    spec = importlib.util.spec_from_file_location("pr_app_under_test", Path(req["app_dir"]) / "app.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    client = module.create_app(seed(req["canaries"]), shell).test_client()

    results = []
    for p in req["probes"]:
        calls.clear()
        params = {x["name"]: x["value"] for x in p.get("params", [])}
        post = p.get("method") == "POST"
        r = client.open(p["path"], method=p.get("method", "GET"), headers={"X-User": "alice"},
                        query_string=None if post else params, data=params if post else None)
        results.append({"status": r.status_code, "content_type": r.content_type or "",
                        "body": r.get_data(as_text=True)[:BODY_LIMIT], "shell_calls": list(calls)})
    out.write(json.dumps(results))


if __name__ == "__main__":
    main()
