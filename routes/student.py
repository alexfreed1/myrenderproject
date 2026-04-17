import re
from flask import Blueprint, render_template, request, session, redirect, url_for
from db import get_db
from functools import wraps
from utils import now_eat

student_bp = Blueprint('student', __name__)

EMAIL_RE = re.compile(r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$')

def validate_password(pwd):
    """Min 8 chars, at least one digit, at least one symbol."""
    if len(pwd) < 8:
        return "Password must be at least 8 characters."
    if not re.search(r'\d', pwd):
        return "Password must contain at least one number."
    if not re.search(r'[!@#$%^&*()_+\-=\[\]{};\':"\\|,.<>\/?]', pwd):
        return "Password must contain at least one symbol (e.g. @, #, !)."
    return None

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
                if request.form.get('remember'):
                    session.permanent = True
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
    dept_id = request.args.get('dept_id', 0, type=int)
    if request.method == 'POST':
        adm = request.form.get('admission_number', '').strip()
        pwd = request.form.get('password', '')
        fullname = request.form.get('fullname', '').strip().upper()
        email = request.form.get('email', '').strip().lower()
        class_id = request.form.get('class_id', 0, type=int)
        dept_id = request.form.get('dept_id', 0, type=int)
        if not (adm and pwd and fullname and email and class_id):
            error = "All fields are required."
        elif not EMAIL_RE.match(email):
            error = "Please enter a valid email address (e.g. name@example.com)."
        else:
            pwd_error = validate_password(pwd)
            if pwd_error:
                error = pwd_error
            else:
                cur.execute("SELECT id, email FROM students WHERE admission_number=%s", (adm,))
                row = cur.fetchone()
                if not row:
                    error = "Admission Number not found. Only students added by the Admin can register."
                elif row['email']:
                    error = "Account already registered. Please login."
                else:
                    cur.execute("UPDATE students SET full_name=%s, email=%s, password=%s, class_id=%s WHERE id=%s",
                                (fullname, email, pwd, class_id, row['id']))
                    db.commit()
                    return redirect(url_for('student.login') + '?registered=1')
    cur.execute("SELECT * FROM departments ORDER BY name")
    departments = cur.fetchall()
    if dept_id:
        cur.execute("SELECT id, name FROM classes WHERE department_id=%s ORDER BY name", (dept_id,))
    else:
        cur.execute("SELECT id, name FROM classes ORDER BY name")
    classes = cur.fetchall()
    return render_template('student/register.html', error=error, classes=classes,
                           departments=departments, dept_id=dept_id)

@student_bp.route('/dashboard')
@student_required
def dashboard():
    db = get_db(); cur = db.cursor()
    student = session['student']
    student_id = student['id']
    cur.execute("SELECT class_id FROM students WHERE id=%s", (student_id,))
    row = cur.fetchone()
    class_id = row['class_id'] if row else 0
    cur.execute("""SELECT u.id, u.code as unit_code, u.name as unit_name,
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
    current_month = now_eat().strftime('%B %Y')
    return render_template('student/dashboard.html', student=student, attendance_data=attendance_data, total_attended=total_attended, total_records=total_records, overall_pct=overall_pct, current_month=current_month)


@student_bp.route('/unit_detail')
@student_required
def unit_detail():
    db = get_db(); cur = db.cursor()
    student = session['student']
    student_id = student['id']
    unit_id = request.args.get('unit_id', 0, type=int)
    if not unit_id:
        return redirect(url_for('student.dashboard'))
    cur.execute("SELECT * FROM units WHERE id=%s", (unit_id,))
    unit = cur.fetchone()
    cur.execute("""SELECT s.*, c.name as class_name, d.name as dept_name
        FROM students s JOIN classes c ON s.class_id=c.id
        JOIN departments d ON c.department_id=d.id WHERE s.id=%s""", (student_id,))
    info = cur.fetchone()
    cur.execute("""SELECT a.week, a.lesson, a.status, a.attendance_date
        FROM attendance a WHERE a.student_id=%s AND a.unit_id=%s
        ORDER BY a.week, a.lesson""", (student_id, unit_id))
    records = cur.fetchall()
    total = len(records)
    present = sum(1 for r in records if r['status'] == 'Present')
    absent = total - present
    pct = round((present / total) * 100, 1) if total > 0 else 0
    return render_template('student/unit_detail.html', student=student, unit=unit,
        info=info, records=records, total=total, present=present, absent=absent, pct=pct)


@student_bp.route('/unit_report_pdf')
@student_required
def unit_report_pdf():
    db = get_db(); cur = db.cursor()
    student = session['student']
    student_id = student['id']
    unit_id = request.args.get('unit_id', 0, type=int)
    if not unit_id:
        return redirect(url_for('student.dashboard'))
    cur.execute("SELECT * FROM units WHERE id=%s", (unit_id,))
    unit = cur.fetchone()
    cur.execute("""SELECT s.*, c.name as class_name, d.name as dept_name
        FROM students s JOIN classes c ON s.class_id=c.id
        JOIN departments d ON c.department_id=d.id WHERE s.id=%s""", (student_id,))
    info = cur.fetchone()
    cur.execute("""SELECT a.week, a.lesson, a.status, a.attendance_date
        FROM attendance a WHERE a.student_id=%s AND a.unit_id=%s
        ORDER BY a.week, a.lesson""", (student_id, unit_id))
    records = cur.fetchall()
    total = len(records)
    present = sum(1 for r in records if r['status'] == 'Present')
    absent = total - present
    pct = round((present / total) * 100, 1) if total > 0 else 0
    date_gen = now_eat().strftime('%d %b %Y, %H:%M')
    return render_template('student/unit_report_pdf.html', student=student, unit=unit,
        info=info, records=records, total=total, present=present,
        absent=absent, pct=pct, date_gen=date_gen)
