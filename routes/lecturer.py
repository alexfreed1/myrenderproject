from flask import Blueprint, render_template, request, session, redirect, url_for, jsonify
from db import get_db
from functools import wraps

lecturer_bp = Blueprint('lecturer', __name__)

def trainer_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('trainer'):
            return redirect(url_for('lecturer.login'))
        return f(*args, **kwargs)
    return decorated

def dept_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('trainer'):
            return redirect(url_for('lecturer.login'))
        if not session.get('selected_department'):
            return redirect(url_for('lecturer.select_department'))
        return f(*args, **kwargs)
    return decorated

# ── Auth ──────────────────────────────────────────────────────────────────────

@lecturer_bp.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        u = request.form.get('username', '').strip()
        p = request.form.get('password', '')
        db = get_db(); cur = db.cursor()
        cur.execute("SELECT * FROM trainers WHERE username=%s AND password=%s", (u, p))
        row = cur.fetchone()
        if row:
            session['trainer'] = {
                'id': row['id'],
                'name': row['name'],
                'username': row['username'],
                'department_id': row['department_id']
            }
            return redirect(url_for('lecturer.select_department'))
        error = "Invalid username or password"
    return render_template('lecturer/login.html', error=error)

@lecturer_bp.route('/logout')
def logout():
    session.pop('trainer', None)
    session.pop('selected_department', None)
    return redirect(url_for('main.index'))

# ── Department Selection ──────────────────────────────────────────────────────

@lecturer_bp.route('/select_department', methods=['GET', 'POST'])
@trainer_required
def select_department():
    db = get_db(); cur = db.cursor()
    if request.method == 'POST':
        dept_id = request.form.get('department_id', 0, type=int)
        if dept_id:
            session['selected_department'] = dept_id
            return redirect(url_for('lecturer.dashboard'))
    cur.execute("SELECT * FROM departments ORDER BY name")
    depts = cur.fetchall()
    return render_template('lecturer/select_department.html', depts=depts)

# ── Dashboard ─────────────────────────────────────────────────────────────────

@lecturer_bp.route('/dashboard')
@dept_required
def dashboard():
    db = get_db(); cur = db.cursor()
    trainer = session['trainer']
    dept_id = session['selected_department']
    cur.execute("SELECT name FROM departments WHERE id=%s", (dept_id,))
    dept = cur.fetchone()
    dept_name = dept['name'] if dept else ''
    cur.execute("""SELECT DISTINCT c.* FROM classes c
        JOIN class_units cu ON c.id=cu.class_id
        WHERE c.department_id=%s AND cu.trainer_id=%s ORDER BY c.name""", (dept_id, trainer['id']))
    class_list = cur.fetchall()
    class_id = request.args.get('class_id', 0, type=int)
    unit_id = request.args.get('unit_id', 0, type=int)
    week = request.args.get('week', 1, type=int)
    lesson = request.args.get('lesson', 'L1')
    units_list = []
    students_list = []
    attendance_submitted = False
    if class_id:
        cur.execute("""SELECT cu.*, u.code, u.name FROM class_units cu
            JOIN units u ON u.id=cu.unit_id
            WHERE cu.class_id=%s AND cu.trainer_id=%s""", (class_id, trainer['id']))
        units_list = cur.fetchall()
        cur.execute("SELECT * FROM students WHERE class_id=%s ORDER BY admission_number", (class_id,))
        students_list = cur.fetchall()
    if unit_id and week and lesson:
        cur.execute("SELECT id FROM attendance WHERE unit_id=%s AND trainer_id=%s AND week=%s AND lesson=%s LIMIT 1", (unit_id, trainer['id'], week, lesson))
        attendance_submitted = cur.fetchone() is not None
    return render_template('lecturer/dashboard.html', trainer=trainer, dept_name=dept_name, class_list=class_list, units_list=units_list, students_list=students_list, class_id=class_id, unit_id=unit_id, week=week, lesson=lesson, attendance_submitted=attendance_submitted)

# ── Submit Attendance ─────────────────────────────────────────────────────────

@lecturer_bp.route('/submit_attendance', methods=['POST'])
@trainer_required
def submit_attendance():
    if not session.get('trainer'):
        return jsonify({'success': False, 'message': 'Unauthorized'})
    trainer_id = session['trainer']['id']
    db = get_db(); cur = db.cursor()
    class_id = request.form.get('class_id', 0, type=int)
    unit_id = request.form.get('unit_id', 0, type=int)
    week = request.form.get('week', 0, type=int)
    lesson = request.form.get('lesson', '')
    statuses = {}
    for key, val in request.form.items():
        if key.startswith('status[') and key.endswith(']'):
            sid = key[7:-1]
            statuses[sid] = val
    if not (class_id and unit_id and week and lesson and statuses):
        return jsonify({'success': False, 'message': 'Missing required fields or no students marked.'})
    cur.execute("SELECT code FROM units WHERE id=%s", (unit_id,))
    u = cur.fetchone()
    if not u:
        return jsonify({'success': False, 'message': 'Invalid Unit'})
    unit_code = u['code']
    try:
        for sid, status_val in statuses.items():
            student_id = int(sid)
            status = 'Present' if status_val == 'present' else 'Absent'
            cur.execute("SELECT id FROM attendance WHERE student_id=%s AND unit_id=%s AND week=%s AND lesson=%s", (student_id, unit_id, week, lesson))
            existing = cur.fetchone()
            if existing:
                cur.execute("UPDATE attendance SET status=%s, trainer_id=%s, attendance_date=NOW() WHERE id=%s", (status, trainer_id, existing['id']))
            else:
                cur.execute("INSERT INTO attendance (student_id, unit_id, unit_code, trainer_id, week, lesson, status, attendance_date) VALUES (%s,%s,%s,%s,%s,%s,%s,NOW())", (student_id, unit_id, unit_code, trainer_id, week, lesson, status))
        db.commit()
        return jsonify({'success': True, 'message': 'Attendance submitted successfully.'})
    except Exception as e:
        db.rollback()
        return jsonify({'success': False, 'message': f'Database error: {str(e)}'})

# ── View Attendance ───────────────────────────────────────────────────────────

@lecturer_bp.route('/view_attendance')
@dept_required
def view_attendance():
    db = get_db(); cur = db.cursor()
    trainer = session['trainer']
    class_id = request.args.get('class_id', 0, type=int)
    unit_id = request.args.get('unit_id', 0, type=int)
    week = request.args.get('week', 0, type=int)
    lesson = request.args.get('lesson', '')
    cls = unit = dept = None
    records = []
    # Fetch all students in class to show unmarked ones too
    all_students = []
    if class_id and unit_id and week and lesson:
        cur.execute("SELECT c.*, d.name as dept_name FROM classes c JOIN departments d ON c.department_id=d.id WHERE c.id=%s", (class_id,))
        cls = cur.fetchone()
        cur.execute("SELECT * FROM units WHERE id=%s", (unit_id,))
        unit = cur.fetchone()
        cur.execute("""SELECT a.*, s.admission_number, s.full_name FROM attendance a
            JOIN students s ON s.id=a.student_id
            WHERE a.unit_id=%s AND a.week=%s AND a.lesson=%s AND a.trainer_id=%s
            ORDER BY s.admission_number""", (unit_id, week, lesson, trainer['id']))
        records = cur.fetchall()
        if cls:
            dept = {'name': cls['dept_name']}
        # Students not yet marked
        marked_ids = [r['student_id'] for r in records]
        cur.execute("SELECT * FROM students WHERE class_id=%s ORDER BY admission_number", (class_id,))
        all_students = [s for s in cur.fetchall() if s['id'] not in marked_ids]
    return render_template('lecturer/view_attendance.html', trainer=trainer, cls=cls, unit=unit,
        dept=dept, records=records, all_students=all_students,
        class_id=class_id, unit_id=unit_id, week=week, lesson=lesson)


# ── Update single attendance record ──────────────────────────────────────────

@lecturer_bp.route('/update_attendance', methods=['POST'])
@trainer_required
def update_attendance():
    trainer_id = session['trainer']['id']
    db = get_db(); cur = db.cursor()
    att_id = request.form.get('att_id', 0, type=int)
    new_status = request.form.get('status', '')
    class_id = request.form.get('class_id', 0)
    unit_id = request.form.get('unit_id', 0)
    week = request.form.get('week', 0)
    lesson = request.form.get('lesson', '')
    if att_id and new_status in ('Present', 'Absent'):
        cur.execute("UPDATE attendance SET status=%s, attendance_date=NOW() WHERE id=%s AND trainer_id=%s",
                    (new_status, att_id, trainer_id))
        db.commit()
    return redirect(f'/lecturer/view_attendance?class_id={class_id}&unit_id={unit_id}&week={week}&lesson={lesson}')


# ── Add missed student attendance ─────────────────────────────────────────────

@lecturer_bp.route('/add_attendance', methods=['POST'])
@trainer_required
def add_attendance():
    trainer_id = session['trainer']['id']
    db = get_db(); cur = db.cursor()
    student_id = request.form.get('student_id', 0, type=int)
    unit_id = request.form.get('unit_id', 0, type=int)
    week = request.form.get('week', 0, type=int)
    lesson = request.form.get('lesson', '')
    status = request.form.get('status', 'Present')
    class_id = request.form.get('class_id', 0)
    if student_id and unit_id and week and lesson and status in ('Present', 'Absent'):
        cur.execute("SELECT code FROM units WHERE id=%s", (unit_id,))
        u = cur.fetchone()
        unit_code = u['code'] if u else ''
        cur.execute("SELECT id FROM attendance WHERE student_id=%s AND unit_id=%s AND week=%s AND lesson=%s",
                    (student_id, unit_id, week, lesson))
        existing = cur.fetchone()
        if existing:
            cur.execute("UPDATE attendance SET status=%s, trainer_id=%s, attendance_date=NOW() WHERE id=%s",
                        (status, trainer_id, existing['id']))
        else:
            cur.execute("""INSERT INTO attendance (student_id, unit_id, unit_code, trainer_id, week, lesson, status, attendance_date)
                VALUES (%s,%s,%s,%s,%s,%s,%s,NOW())""", (student_id, unit_id, unit_code, trainer_id, week, lesson, status))
        db.commit()
    return redirect(f'/lecturer/view_attendance?class_id={class_id}&unit_id={unit_id}&week={week}&lesson={lesson}')


# ── Delete single attendance record ──────────────────────────────────────────

@lecturer_bp.route('/delete_attendance', methods=['POST'])
@trainer_required
def delete_attendance():
    trainer_id = session['trainer']['id']
    db = get_db(); cur = db.cursor()
    att_id = request.form.get('att_id', 0, type=int)
    class_id = request.form.get('class_id', 0)
    unit_id = request.form.get('unit_id', 0)
    week = request.form.get('week', 0)
    lesson = request.form.get('lesson', '')
    if att_id:
        cur.execute("DELETE FROM attendance WHERE id=%s AND trainer_id=%s", (att_id, trainer_id))
        db.commit()
    return redirect(f'/lecturer/view_attendance?class_id={class_id}&unit_id={unit_id}&week={week}&lesson={lesson}')


# ── Delete entire lesson attendance ──────────────────────────────────────────

@lecturer_bp.route('/delete_lesson_attendance', methods=['POST'])
@trainer_required
def delete_lesson_attendance():
    trainer_id = session['trainer']['id']
    db = get_db(); cur = db.cursor()
    unit_id = request.form.get('unit_id', 0, type=int)
    week = request.form.get('week', 0, type=int)
    lesson = request.form.get('lesson', '')
    class_id = request.form.get('class_id', 0)
    if unit_id and week and lesson:
        cur.execute("""DELETE FROM attendance WHERE unit_id=%s AND week=%s AND lesson=%s AND trainer_id=%s""",
                    (unit_id, week, lesson, trainer_id))
        db.commit()
    return redirect(f'/lecturer/view_attendance?class_id={class_id}&unit_id={unit_id}&week={week}&lesson={lesson}')

# ── Trainee Attendance Search ─────────────────────────────────────────────────

@lecturer_bp.route('/trainee_search')
@dept_required
def trainee_search():
    db = get_db(); cur = db.cursor()
    trainer = session['trainer']
    dept_id = session['selected_department']
    query = request.args.get('q', '').strip()
    unit_id = request.args.get('unit_id', 0, type=int)
    students = []
    student = None
    records = []
    summary = []

    # Get units this trainer teaches
    cur.execute("""SELECT DISTINCT u.id, u.code, u.name FROM class_units cu
        JOIN units u ON cu.unit_id=u.id
        JOIN classes c ON cu.class_id=c.id
        WHERE cu.trainer_id=%s AND c.department_id=%s
        ORDER BY u.code""", (trainer['id'], dept_id))
    units_list = cur.fetchall()

    if query:
        cur.execute("""SELECT s.* FROM students s
            JOIN classes c ON s.class_id=c.id
            WHERE c.department_id=%s AND (s.admission_number ILIKE %s OR s.full_name ILIKE %s)
            ORDER BY s.full_name""", (dept_id, f'%{query}%', f'%{query}%'))
        students = cur.fetchall()

    student_id = request.args.get('student_id', 0, type=int)
    if student_id and unit_id:
        cur.execute("SELECT * FROM students WHERE id=%s", (student_id,))
        student = cur.fetchone()
        cur.execute("SELECT * FROM units WHERE id=%s", (unit_id,))
        selected_unit = cur.fetchone()
        cur.execute("""SELECT a.week, a.lesson, a.status, a.attendance_date
            FROM attendance a
            WHERE a.student_id=%s AND a.unit_id=%s AND a.trainer_id=%s
            ORDER BY a.week, a.lesson""", (student_id, unit_id, trainer['id']))
        records = cur.fetchall()
        total = len(records)
        present = sum(1 for r in records if r['status'] == 'Present')
        absent = total - present
        pct = round((present / total) * 100, 1) if total > 0 else 0
        summary = {'total': total, 'present': present, 'absent': absent, 'pct': pct, 'unit': selected_unit}

    return render_template('lecturer/trainee_search.html',
        trainer=trainer, units_list=units_list, query=query,
        students=students, student=student, student_id=student_id,
        unit_id=unit_id, records=records, summary=summary)


# ── Trainee Attendance PDF ────────────────────────────────────────────────────

@lecturer_bp.route('/trainee_report_pdf')
@dept_required
def trainee_report_pdf():
    db = get_db(); cur = db.cursor()
    trainer = session['trainer']
    student_id = request.args.get('student_id', 0, type=int)
    unit_id = request.args.get('unit_id', 0, type=int)
    if not (student_id and unit_id):
        return 'Missing parameters.', 400
    cur.execute("SELECT * FROM students WHERE id=%s", (student_id,))
    student = cur.fetchone()
    cur.execute("SELECT * FROM units WHERE id=%s", (unit_id,))
    unit = cur.fetchone()
    cur.execute("""SELECT c.name as class_name, d.name as dept_name
        FROM students s JOIN classes c ON s.class_id=c.id
        JOIN departments d ON c.department_id=d.id WHERE s.id=%s""", (student_id,))
    info = cur.fetchone()
    cur.execute("""SELECT a.week, a.lesson, a.status, a.attendance_date
        FROM attendance a
        WHERE a.student_id=%s AND a.unit_id=%s AND a.trainer_id=%s
        ORDER BY a.week, a.lesson""", (student_id, unit_id, trainer['id']))
    records = cur.fetchall()
    total = len(records)
    present = sum(1 for r in records if r['status'] == 'Present')
    absent = total - present
    pct = round((present / total) * 100, 1) if total > 0 else 0
    from datetime import datetime
    date_gen = datetime.now().strftime('%d %b %Y, %H:%M')
    return render_template('lecturer/trainee_report_pdf.html',
        trainer=trainer, student=student, unit=unit, info=info,
        records=records, total=total, present=present, absent=absent,
        pct=pct, date_gen=date_gen)

@lecturer_bp.route('/download_attendance_pdf')
@dept_required
def download_attendance_pdf():
    db = get_db(); cur = db.cursor()
    trainer = session['trainer']
    class_id = request.args.get('class_id', 0, type=int)
    unit_id = request.args.get('unit_id', 0, type=int)
    week = request.args.get('week', 0, type=int)
    lesson = request.args.get('lesson', '')
    if not (class_id and unit_id and week and lesson):
        return 'Missing parameters.', 400
    cur.execute("SELECT c.*, d.name as dept_name FROM classes c JOIN departments d ON c.department_id=d.id WHERE c.id=%s", (class_id,))
    cls = cur.fetchone()
    cur.execute("SELECT * FROM units WHERE id=%s", (unit_id,))
    unit = cur.fetchone()
    cur.execute("""SELECT a.*, s.admission_number, s.full_name FROM attendance a
        JOIN students s ON s.id=a.student_id
        WHERE a.unit_id=%s AND a.week=%s AND a.lesson=%s AND a.trainer_id=%s
        ORDER BY s.admission_number""", (unit_id, week, lesson, trainer['id']))
    records = cur.fetchall()
    from datetime import datetime
    date_gen = datetime.now().strftime('%d %b %Y, %H:%M')
    attendance_date = records[0]['attendance_date'].strftime('%d %b %Y') if records else '-'
    return render_template('lecturer/download_attendance_pdf.html', trainer=trainer, cls=cls, unit=unit, records=records, week=week, lesson=lesson, date_gen=date_gen, attendance_date=attendance_date)
