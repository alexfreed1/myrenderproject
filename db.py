import os
import psycopg2
import psycopg2.extras
from flask import g
from dotenv import load_dotenv

load_dotenv()

def get_connection_url():
    url = os.environ.get('DATABASE_URL', '')
    # Render uses postgres:// but psycopg2 needs postgresql://
    if url.startswith('postgres://'):
        url = url.replace('postgres://', 'postgresql://', 1)
    return url


def get_db():
    if 'db' not in g:
        conn = psycopg2.connect(
            get_connection_url(),
            cursor_factory=psycopg2.extras.RealDictCursor,
            sslmode='require'
        )
        conn.autocommit = False
        g.db = conn
    else:
        try:
            g.db.cursor().execute("SELECT 1")
        except Exception:
            conn = psycopg2.connect(
                get_connection_url(),
                cursor_factory=psycopg2.extras.RealDictCursor,
                sslmode='require'
            )
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
    conn = psycopg2.connect(
        get_connection_url(),
        cursor_factory=psycopg2.extras.RealDictCursor,
        sslmode='require'
    )
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
        name VARCHAR(200) NOT NULL
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
        UNIQUE(class_id, unit_id, trainer_id)
    )""")

    cur.execute("""CREATE TABLE IF NOT EXISTS attendance (
        id SERIAL PRIMARY KEY,
        student_id INT NOT NULL REFERENCES students(id) ON DELETE CASCADE,
        unit_id INT NOT NULL REFERENCES units(id) ON DELETE CASCADE,
        unit_code VARCHAR(50),
        trainer_id INT NOT NULL REFERENCES trainers(id) ON DELETE CASCADE,
        lesson VARCHAR(10) NOT NULL,
        week INT NOT NULL,
        status VARCHAR(10) NOT NULL,
        attendance_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")

    cur.execute("""CREATE TABLE IF NOT EXISTS admins (
        id SERIAL PRIMARY KEY,
        username VARCHAR(100) NOT NULL UNIQUE,
        password VARCHAR(255) NOT NULL
    )""")

    cur.execute("SELECT id FROM admins WHERE username='admin'")
    if not cur.fetchone():
        cur.execute("INSERT INTO admins (username, password) VALUES ('admin', 'admin123')")

    conn.commit()
    cur.close()
    conn.close()
