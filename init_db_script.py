import os
import sys

# Load env vars
from dotenv import load_dotenv
load_dotenv()

try:
    from db import init_db, get_connection_url
    import psycopg2
    import psycopg2.extras

    print("Initializing database...")
    init_db()

    # Safe migration: add department_id to units if missing
    conn = psycopg2.connect(
        get_connection_url(),
        cursor_factory=psycopg2.extras.RealDictCursor
    )
    cur = conn.cursor()
    cur.execute("""
        ALTER TABLE units ADD COLUMN IF NOT EXISTS
        department_id INT REFERENCES departments(id) ON DELETE SET NULL
    """)
    conn.commit()
    cur.close()
    conn.close()
    print("Database ready.")

except Exception as e:
    print(f"DB init warning (non-fatal): {e}", file=sys.stderr)
    # Don't exit with error — let gunicorn start anyway
    sys.exit(0)
