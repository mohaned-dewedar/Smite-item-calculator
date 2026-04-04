"""Apply god tables to the existing smite2.db (safe, non-destructive)."""
import os, sqlite3

DB_PATH     = os.path.join(os.path.dirname(__file__), "..", "db", "smite2.db")
SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "..", "db", "schema.sql")

conn = sqlite3.connect(DB_PATH)
with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
    conn.executescript(f.read())
conn.commit()
conn.close()
print("Migration complete.")
