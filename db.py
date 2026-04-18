import os
import psycopg2
import psycopg2.extras
from flask import g
from dotenv import load_dotenv

load_dotenv()

def get_connection_url():
    url = os.environ.get('DATABASE_URL', '')
    if url.startswith('postgres://'):
        url = url.replace('postgres://', 'postgresql://', 1)
    return url

def _connect():
    url = get_connection_url()
    if 'render.com' not in url:
        conn = psycopg2.connect(url, cursor_factory=psycopg2.extras.RealDictCursor)
    else:
        conn = psycopg2.connect(url, cursor_factory=psycopg2.extras.RealDictCursor, sslmode='require')
    with conn.cursor() as cur:
        cur.execute("SET TIME ZONE 'Africa/Nairobi'")
    conn.commit()
    return conn


def get_db():
    if 'db' not in g:
        conn = _connect()
        conn.autocommit = False
        g.db = conn
    else:
        try:
            g.db.cursor().execute("SELECT 1")
        except Exception:
            conn = _connect()
            conn.autocommit = False
            g.db = conn
    return g.db


def close_db(e=None):
    db = g.pop('db', None)
    if db is not None:
        try:
            db.close()
        except Exception:
            pass


def init_db():
    conn = _connect()
    cur = conn.cursor()

    cur.execute("""CREATE TABLE IF NOT EXISTS departments (
        id SERIAL PRIMARY KEY,
        name VARCHAR(100) NOT NULL UNIQUE
    )""")

    cur.execute("""CREATE TABLE IF NOT EXISTS classes (
        id SERIAL PRIMARY KEY,
        name VARCHAR(100) NOT NULL,
        department_id INT NOT NULL REFERENCES departments(id) ON DELETE CASCADE
    )""")

    cur.execute("""CREATE TABLE IF NOT EXISTS students (
        id SERIAL PRIMARY KEY,
        admission_number VARCHAR(50) UNIQUE,
        full_name VARCHAR(200),
        email VARCHAR(100),
        password VARCHAR(255),
        class_id INT REFERENCES classes(id) ON DELETE CASCADE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")

    cur.execute("""CREATE TABLE IF NOT EXISTS units (
        id SERIAL PRIMARY KEY,
        code VARCHAR(50) NOT NULL UNIQUE,
        name VARCHAR(200) NOT NULL,
        department_id INT REFERENCES departments(id) ON DELETE SET NULL
    )""")

    cur.execute("""CREATE TABLE IF NOT EXISTS trainers (
        id SERIAL PRIMARY KEY,
        name VARCHAR(200) NOT NULL,
        username VARCHAR(100) NOT NULL UNIQUE,
        password VARCHAR(255) NOT NULL,
        department_id INT REFERENCES departments(id) ON DELETE SET NULL
    )""")

    cur.execute("""CREATE TABLE IF NOT EXISTS class_units (
        id SERIAL PRIMARY KEY,
        class_id INT NOT NULL REFERENCES classes(id) ON DELETE CASCADE,
        unit_id INT NOT NULL REFERENCES units(id) ON DELETE CASCADE,
        trainer_id INT NOT NULL REFERENCES trainers(id) ON DELETE CASCADE,
        year INT NOT NULL DEFAULT 2026,
        term INT NOT NULL DEFAULT 1,
        UNIQUE(class_id, unit_id, trainer_id, year, term)
    )""")

    # Migrate class_units: drop old narrow constraint, add year/term columns if missing
    cur.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'class_units_class_id_unit_id_trainer_id_key'
            ) THEN
                ALTER TABLE class_units DROP CONSTRAINT class_units_class_id_unit_id_trainer_id_key;
            END IF;
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name='class_units' AND column_name='year'
            ) THEN
                ALTER TABLE class_units ADD COLUMN year INT NOT NULL DEFAULT 2026;
            END IF;
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name='class_units' AND column_name='term'
            ) THEN
                ALTER TABLE class_units ADD COLUMN term INT NOT NULL DEFAULT 1;
            END IF;
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'class_units_class_id_unit_id_trainer_id_year_term_key'
            ) THEN
                ALTER TABLE class_units
                    ADD CONSTRAINT class_units_class_id_unit_id_trainer_id_year_term_key
                    UNIQUE(class_id, unit_id, trainer_id, year, term);
            END IF;
        END$$;
    """)

    cur.execute("""CREATE TABLE IF NOT EXISTS attendance (
        id SERIAL PRIMARY KEY,
        student_id INT NOT NULL REFERENCES students(id) ON DELETE CASCADE,
        unit_id INT NOT NULL REFERENCES units(id) ON DELETE CASCADE,
        unit_code VARCHAR(50),
        trainer_id INT NOT NULL REFERENCES trainers(id) ON DELETE CASCADE,
        lesson VARCHAR(10) NOT NULL,
        week INT NOT NULL,
        year INT NOT NULL DEFAULT 2026,
        term INT NOT NULL DEFAULT 1,
        status VARCHAR(10) NOT NULL,
        attendance_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")

    cur.execute("""CREATE TABLE IF NOT EXISTS admins (
        id SERIAL PRIMARY KEY,
        username VARCHAR(100) NOT NULL UNIQUE,
        password VARCHAR(255) NOT NULL
    )""")

    # class_events: holiday / academic trip markers per session
    # unit_id uses 0 as sentinel (not NULL) so UNIQUE constraint works reliably
    cur.execute("""CREATE TABLE IF NOT EXISTS class_events (
        id SERIAL PRIMARY KEY,
        class_id INT NOT NULL REFERENCES classes(id) ON DELETE CASCADE,
        unit_id INT NOT NULL DEFAULT 0,
        trainer_id INT NOT NULL REFERENCES trainers(id) ON DELETE CASCADE,
        event_type VARCHAR(30) NOT NULL,
        week INT NOT NULL,
        lesson VARCHAR(10) NOT NULL,
        year INT NOT NULL DEFAULT 2026,
        term INT NOT NULL DEFAULT 1,
        note TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(class_id, unit_id, trainer_id, week, lesson, year, term)
    )""")

    # Migrate class_events if it exists with nullable unit_id
    cur.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name='class_events' AND column_name='unit_id'
                  AND is_nullable='YES'
            ) THEN
                UPDATE class_events SET unit_id=0 WHERE unit_id IS NULL;
                ALTER TABLE class_events ALTER COLUMN unit_id SET NOT NULL;
                ALTER TABLE class_events ALTER COLUMN unit_id SET DEFAULT 0;
            END IF;
        END$$;
    """)

    cur.execute("SELECT id FROM admins WHERE username='admin'")
    if not cur.fetchone():
        cur.execute("INSERT INTO admins (username, password) VALUES ('admin', 'admin123')")

    conn.commit()
    cur.close()
    conn.close()
