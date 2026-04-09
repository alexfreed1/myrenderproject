import os
from flask import Flask
from dotenv import load_dotenv
from werkzeug.middleware.proxy_fix import ProxyFix
from db import get_db, close_db, init_db

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key')
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = True

# Fix URLs behind Render's reverse proxy
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

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

# Inject logo URL into every template automatically
@app.context_processor
def inject_globals():
    return {'LOGO_URL': '/static/assets/THIKATTILOGO.jpg'}

# Run DB init once on first request
_db_initialized = False

@app.before_request
def setup_db():
    global _db_initialized
    if not _db_initialized:
        try:
            init_db()
            _db_initialized = True
        except Exception as e:
            print(f"DB init error: {e}")

if __name__ == '__main__':
    app.run(debug=False)
