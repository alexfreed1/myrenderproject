import os
from flask import Flask
from dotenv import load_dotenv
from werkzeug.middleware.proxy_fix import ProxyFix

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key')
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = True

# Handle Render's reverse proxy
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

from db import get_db, close_db
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

@app.context_processor
def inject_globals():
    return {'LOGO_URL': '/static/assets/THIKATTILOGO.jpg'}

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
