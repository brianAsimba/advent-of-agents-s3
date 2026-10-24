"""A 'legacy' REST CRM (fake data) that nobody wants to rewrite: one endpoint, a huge response.

  GET /crm/v2/accounts/{id}  ->  ~30 KB of JSON: the 6 fields an agent needs, plus internal metadata,
                                  a 200-entry activity log and a raw XML blob.
Run: python day20/legacy_crm.py --port 8301
"""
import argparse
import random

import uvicorn
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route

CALLS = {"n": 0}  # how many requests reached the backend (the thing a spike arrest protects)


def account(customer_id: str) -> dict | None:
    if not customer_id.startswith("CUST-"):
        return None
    rnd = random.Random(customer_id)
    return {
        "customer_id": customer_id,
        "name": f"Customer {customer_id[-4:]}",
        "tier": rnd.choice(["gold", "silver", "bronze"]),
        "status": "active",
        "open_tickets": rnd.randint(0, 4),
        "balance_due_usd": round(rnd.uniform(0, 900), 2),
        "_internal": {"shard": rnd.randint(1, 64), "etl_batch": "2026-10-23T02:00:00Z", "schema": "crm_v2.17",
                      "legacy_ids": [f"L{rnd.randint(10**6, 10**7)}" for _ in range(12)]},
        "activity_log": [{"ts": f"2026-{1 + i % 9:02d}-{1 + i % 27:02d}T10:{i % 60:02d}:00Z",
                          "event": rnd.choice(["login", "statement_viewed", "address_checked", "email_opened"]),
                          "channel": rnd.choice(["web", "ivr", "branch"]), "session": f"s-{rnd.getrandbits(48):x}"}
                         for i in range(200)],
        "raw_xml": "<Account>" + "<Field k='x'>padding</Field>" * 120 + "</Account>",
    }


async def get_account(request):
    CALLS["n"] += 1
    a = account(request.path_params["customer_id"])
    return JSONResponse(a) if a else JSONResponse({"error": "not found"}, status_code=404)


async def stats(request):  # admin endpoint so the demo can count requests that reached the backend
    return JSONResponse(CALLS)


app = Starlette(routes=[Route("/crm/v2/accounts/{customer_id}", get_account), Route("/_stats", stats)])

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, required=True)
    uvicorn.run(app, host="127.0.0.1", port=ap.parse_args().port, log_level="warning")
