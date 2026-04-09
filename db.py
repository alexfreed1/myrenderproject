import os
import psycopg
from psycopg.rows import dict_row
from flask import g
from dotenv import load_dotenv

load_dotenv()

def get_db():
    if 'db' not in g:
        g.db = psycopg.connect(
            os.environ['DATABASE_URL'],
            row_factory=dict_row
        )
        g.db.autocommit = False
    return g.db

def close_db(e=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()

def init_db():
    db = psycopg.connect(
        os.environ['DATABASE_URL'],
        row_factory=dict_row
    )
    cur = db.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS departments (
            id SERIAL PRIMARY KEY,
            name VARCHAR(100) NOT NULL UNIQUE
        );

        CREATE TABLE IF NOT EXISTS classes (
            id SERIAL PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            department_id INT NOT NULL REFERENCES departments(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS students (
            id SERIAL PRIMARY KEY,
            admission_number VARCHAR(50) UNIQUE,
            full_name VARCHAR(200),
            email VARCHAR(100),
            password VARCHAR(255),
            class_id INT REFERENCES classes(id) ON DELETE CASCADE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS units (
            id SERIAL PRIMARY KEY,
            code VARCHAR(50) NOT NULL UNIQUE,
            name VARCHAR(200) NOT NULL
        );

        CREATE TABLE IF NOT EXISTS trainers (
            id SERIAL PRIMARY KEY,
            name VARCHAR(200) NOT NULL,
            username VARCHAR(100) NOT NULL UNIQUE,
            password VARCHAR(255) NOT NULL,
            department_id INT REFERENCES departments(id) ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS class_units (
            id SERIAL PRIMARY KEY,
            class_id INT NOT NULL REFERENCES classes(id) ON DELETE CASCADE,
            unit_id INT NOT NULL REFERENCES units(id) ON DELETE CASCADE,
            trainer_id INT NOT NULL REFERENCES trainers(id) ON DELETE CASCADE,
            UNIQUE(class_id, unit_id, trainer_id)
        );

        CREATE TABLE IF NOT EXISTS attendance (
            id SERIAL PRIMARY KEY,
            student_id INT NOT NULL REFERENCES students(id) ON DELETE CASCADE,
            unit_id INT NOT NULL REFERENCES units(id) ON DELETE CASCADE,
            unit_code VARCHAR(50),
            trainer_id INT NOT NULL REFERENCES trainers(id) ON DELETE CASCADE,
            lesson VARCHAR(10) NOT NULL,
            week INT NOT NULL,
            status VARCHAR(10) NOT NULL,
            attendance_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS admins (
            id SERIAL PRIMARY KEY,
            username VARCHAR(100) NOT NULL UNIQUE,
            password VARCHAR(255) NOT NULL
        );
    """)

    # Seed default admin if not exists
    cur.execute("SELECT id FROM admins WHERE username='admin'")
    if not cur.fetchone():
        cur.execute("INSERT INTO admins (username, password) VALUES ('admin', 'admin123')")

    db.commit()
    cur.close()
    db.close()
