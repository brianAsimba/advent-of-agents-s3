"""Grant, revoke and inspect agent permissions, and read the audit log.

Run from the repo root:
  uv run python day05/iam.py grant weather_agent      # both roles, like Step 11 of the course
  uv run python day05/iam.py revoke weather_agent     # containment: remove one agent's access
  uv run python day05/iam.py policy                   # show bindings
  uv run python day05/iam.py audit                    # who did what (Step 13)
"""
import json
import sys

import iam_lib


def main(argv: list[str]) -> None:
    cmd = argv[0] if argv else "policy"
    if cmd in ("grant", "revoke") and len(argv) == 2:
        principal = iam_lib.spiffe_id(argv[1])
        for role in iam_lib.REQUIRED_ROLES:
            (iam_lib.grant if cmd == "grant" else iam_lib.revoke)(principal, role)
        print(f"{cmd}: {', '.join(iam_lib.REQUIRED_ROLES)} → principal://{principal}")
    elif cmd == "policy":
        print(json.dumps(iam_lib.load_policy(), indent=2))
    elif cmd == "audit":
        if not iam_lib.AUDIT_FILE.exists():
            print("No audit entries yet.")
            return
        for line in iam_lib.AUDIT_FILE.read_text(encoding="utf-8").splitlines():
            e = json.loads(line)
            mark = "ALLOW" if e["allowed"] else "DENY "
            print(f"{e['ts']}  {mark}  {e['principalSubject']}  {e['detail']}")
    else:
        print(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
