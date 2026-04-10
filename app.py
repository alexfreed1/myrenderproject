import os
from flask import Flask, jsonify
from dotenv import load_dotenv
from werkzeug.middleware.proxy_fix import ProxyFix

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'supersecretkey123')
app.config['SESSION_COOKIE_SAMESITE'] = 'None'
app.config['SESSION_COOKIE_SECURE'] = True

app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

from db import close_db
app.teardown_appcontext(close_db)

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

@app.errorhandler(500)
def internal_error(e):
    return f"<h2>Server Error</h2><p>{e}</p>", 500

@app.errorhandler(404)
def not_found(e):
    return "<h2>Page not found</h2><a href='/'>Go Home</a>", 404

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
