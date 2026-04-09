from flask import Blueprint, render_template, request, session, redirect, url_for
from db import get_db
from functools import wraps

student_bp = Blueprint('student', __name__)

def student_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('student'):
            return redirect(url_for('student.login'))
        return f(*args, **kwargs)
    return decorated

@student_bp.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        adm = request.form.get('admission_number', '').strip()
        pwd = request.form.get('password', '')
        db = get_db(); cur = db.cursor()
        cur.execute("SELECT * FROM students WHERE admission_number=%s", (adm,))
        student = cur.fetchone()
        if student:
            if pwd == student['password']:
                session['student'] = dict(student)
                return redirect(url_for('student.dashboard'))
            else:
                error = "Invalid password."
        else:
            error = "Invalid admission number."
    registered = request.args.get('registered')
    return render_template('student/login.html', error=error, registered=registered)

@student_bp.route('/logout')
def logout():
    session.pop('student', None)
    return redirect(url_for('main.index'))

@student_bp.route('/register', methods=['GET', 'POST'])
def register():
    error = None
    db = get_db(); cur = db.cursor()
    if request.method == 'POST':
        adm = request.form.get('admission_number', '').strip()
        pwd = request.form.get('password', '')
        fullname = request.form.get('fullname', '').strip()
        email = request.form.get('email', '').strip()
        class_id = request.form.get('class_id', 0, type=int)
        if adm and pwd and fullname and email and class_id:
            cur.execute("SELECT id, email FROM students WHERE admission_number=%s", (adm,))
            row = cur.fetchone()
            if not row:
                error = "Admission Number not found. Only students added by the Admin can register."
            elif row['email']:
                error = "Account already registered. Please login."
            else:
                cur.execute("UPDATE students SET full_name=%s, email=%s, password=%s, class_id=%s WHERE id=%s", (fullname, email, pwd, class_id, row['id']))
                db.commit()
                return redirect(url_for('student.login') + '?registered=1')
        else:
            error = "All fields are required."
    cur.execute("SELECT id, name FROM classes ORDER BY name")
    classes = cur.fetchall()
    return render_template('student/register.html', error=error, classes=classes)

@student_bp.route('/dashboard')
@student_required
def dashboard():
    db = get_db(); cur = db.cursor()
    student = session['student']
    student_id = student['id']
    cur.execute("SELECT class_id FROM students WHERE id=%s", (student_id,))
    row = cur.fetchone()
    class_id = row['class_id'] if row else 0
    cur.execute("""SELECT u.code as unit_code, u.name as unit_name,
        COUNT(a.id) as total_records,
        SUM(CASE WHEN a.status='Present' THEN 1 ELSE 0 END) as attended,
        MAX(a.attendance_date) as last_update
        FROM class_units cu
        JOIN units u ON cu.unit_id=u.id
        LEFT JOIN attendance a ON a.unit_id=u.id AND a.student_id=%s
        WHERE cu.class_id=%s
        GROUP BY u.id, u.code, u.name""", (student_id, class_id))
    attendance_data = cur.fetchall()
    total_attended = sum(r['attended'] or 0 for r in attendance_data)
    total_records = sum(r['total_records'] or 0 for r in attendance_data)
    overall_pct = round((total_attended / total_records) * 100, 1) if total_records > 0 else 0
    from datetime import datetime
    current_month = datetime.now().strftime('%B %Y')
    return render_template('student/dashboard.html', student=student, attendance_data=attendance_data, total_attended=total_attended, total_records=total_records, overall_pct=overall_pct, current_month=current_month)
