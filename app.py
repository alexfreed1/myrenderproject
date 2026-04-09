import os
from flask import Flask
from dotenv import load_dotenv
from db import get_db, close_db, init_db

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key')
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = True

app.teardown_appcontext(close_db)

# Register blueprints
from routes.main import main_bp
from routes.admin import admin_bp
from routes.lecturer import lecturer_bp
from routes.student import student_bp

app.register_blueprint(main_bp)
app.register_blueprint(admin_bp, url_prefix='/admin')
app.register_blueprint(lecturer_bp, url_prefix='/lecturer')
app.register_blueprint(student_bp, url_prefix='/student')

# Initialize DB on startup (works with gunicorn too)
with app.app_context():
    try:
        init_db()
    except Exception as e:
        print(f"DB init warning: {e}")

if __name__ == '__main__':
    app.run(debug=False)
