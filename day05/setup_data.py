"""Creates the sample warehouse (the course's `bq mk` + CREATE TABLE steps) and resets IAM.

Run from the repo root:  uv run python day05/setup_data.py
"""
import json
import sqlite3

from iam_lib import AUDIT_FILE, DB_FILE, IAM_FILE

DB_FILE.unlink(missing_ok=True)
con = sqlite3.connect(DB_FILE)
con.execute("CREATE TABLE cities_weather (city TEXT, state TEXT, temp_f INTEGER, condition TEXT)")
con.executemany("INSERT INTO cities_weather VALUES (?, ?, ?, ?)", [
    ("San Francisco", "CA", 60, "Foggy"),
    ("New York", "NY", 75, "Sunny"),
    ("Seattle", "WA", 58, "Rainy"),
])
con.commit()
con.close()

IAM_FILE.write_text(json.dumps({"bindings": []}, indent=2))  # every new identity starts with nothing
AUDIT_FILE.unlink(missing_ok=True)
print(f"Created {DB_FILE.name} (3 rows), empty {IAM_FILE.name}, cleared {AUDIT_FILE.name}.")
