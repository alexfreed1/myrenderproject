from flask import Blueprint, render_template, request, session, redirect, url_for
from db import get_db

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index():
    return render_template('main/index.html')

@main_bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('main.index'))

@main_bp.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    msg = ''
    if request.method == 'POST':
        msg = "If an account exists for this email address, a password reset link has been sent to it."
    return render_template('main/forgot_password.html', msg=msg)
