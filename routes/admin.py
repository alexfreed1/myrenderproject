import csv, io
from flask import Blueprint, render_template, request, session, redirect, url_for, flash
from db import get_db
from functools import wraps

admin_bp = Blueprint('admin', __name__)

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('admin'):
            return redirect(url_for('admin.login'))
        return f(*args, **kwargs)
    return decorated

# ── Auth ──────────────────────────────────────────────────────────────────────

@admin_bp.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        u = request.form.get('username', '').strip()
        p = request.form.get('password', '')
        db = get_db(); cur = db.cursor()
        cur.execute("SELECT * FROM admins WHERE username=%s AND password=%s", (u, p))
        row = cur.fetchone()
        if row:
            session['admin'] = u
            return redirect(url_for('admin.dashboard'))
        error = 'Invalid credentials'
    return render_template('admin/login.html', error=error)

@admin_bp.route('/logout')
def logout():
    session.pop('admin', None)
    return redirect(url_for('main.index'))

# ── Dashboard ─────────────────────────────────────────────────────────────────

@admin_bp.route('/')
@admin_bp.route('/dashboard')
@admin_required
def dashboard():
    return render_template('admin/dashboard.html')

@admin_bp.route('/welcome')
@admin_required
def welcome():
    return render_template('admin/welcome.html')

# ── Departments ───────────────────────────────────────────────────────────────

@admin_bp.route('/departments', methods=['GET', 'POST'])
@admin_required
def departments():
    db = get_db(); cur = db.cursor()
    error = None
    if request.method == 'POST' and request.form.get('add_dept'):
        name = request.form.get('name', '').strip()
        if name:
            cur.execute("SELECT id FROM departments WHERE name=%s", (name,))
            if cur.fetchone():
                error = "Department already exists."
            else:
                cur.execute("INSERT INTO departments (name) VALUES (%s)", (name,))
                db.commit()
    if request.args.get('delete'):
        cur.execute("DELETE FROM departments WHERE id=%s", (int(request.args['delete']),))
        db.commit()
        return redirect(url_for('admin.departments'))
    cur.execute("SELECT * FROM departments ORDER BY name")
    depts = cur.fetchall()
    return render_template('admin/departments.html', depts=depts, error=error)

# ── Classes ───────────────────────────────────────────────────────────────────

@admin_bp.route('/classes', methods=['GET', 'POST'])
@admin_required
def classes():
    db = get_db(); cur = db.cursor()
    error = success = None
    if request.method == 'POST':
        if request.form.get('add_class'):
            name = request.form.get('name', '').strip()
            dept_id = request.form.get('department_id', 0, type=int)
            if name and dept_id:
                cur.execute("SELECT id FROM classes WHERE name=%s", (name,))
                if cur.fetchone():
                    error = "Class already exists."
                else:
                    cur.execute("INSERT INTO classes (name, department_id) VALUES (%s,%s)", (name, dept_id))
                    db.commit()
        elif request.form.get('import_csv'):
            f = request.files.get('csv_file')
            if f:
                count = 0
                stream = io.StringIO(f.stream.read().decode('utf-8', errors='ignore'))
                reader = csv.reader(stream)
                for row in reader:
                    if len(row) >= 2:
                        cname, dname = row[0].strip(), row[1].strip()
                        cur.execute("SELECT id FROM departments WHERE name=%s", (dname,))
                        dept = cur.fetchone()
                        if dept:
                            cur.execute("SELECT id FROM classes WHERE name=%s", (cname,))
                            if not cur.fetchone():
                                cur.execute("INSERT INTO classes (name, department_id) VALUES (%s,%s)", (cname, dept['id']))
                                count += 1
                db.commit()
                success = f"Imported {count} classes successfully."
    if request.args.get('delete'):
        cur.execute("DELETE FROM classes WHERE id=%s", (int(request.args['delete']),))
        db.commit()
        return redirect(url_for('admin.classes'))
    cur.execute("SELECT * FROM departments ORDER BY name")
    depts_list = cur.fetchall()
    filter_dept = request.args.get('filter_dept', 0, type=int)
    if filter_dept:
        cur.execute("SELECT c.*, d.name as dept_name FROM classes c LEFT JOIN departments d ON c.department_id=d.id WHERE c.department_id=%s ORDER BY c.name", (filter_dept,))
    else:
        cur.execute("SELECT c.*, d.name as dept_name FROM classes c LEFT JOIN departments d ON c.department_id=d.id ORDER BY c.name")
    classes_list = cur.fetchall()
    return render_template('admin/classes.html', classes_list=classes_list, depts_list=depts_list, filter_dept=filter_dept, error=error, success=success)

# ── Units ─────────────────────────────────────────────────────────────────────

@admin_bp.route('/units', methods=['GET', 'POST'])
@admin_required
def units():
    db = get_db(); cur = db.cursor()
    error = success = None
    if request.method == 'POST':
        if request.form.get('add_unit'):
            code = request.form.get('code', '').strip()
            name = request.form.get('name', '').strip()
            if code and name:
                cur.execute("SELECT id FROM units WHERE code=%s", (code,))
                if cur.fetchone():
                    error = "Unit code already exists."
                else:
                    cur.execute("INSERT INTO units (code, name) VALUES (%s,%s)", (code, name))
                    db.commit()
        elif request.form.get('import_csv'):
            f = request.files.get('csv_file')
            if f:
                count = 0
                stream = io.StringIO(f.stream.read().decode('utf-8', errors='ignore'))
                reader = csv.reader(stream)
                for row in reader:
                    if len(row) >= 2:
                        code, name = row[0].strip(), row[1].strip()
                        if code and name:
                            cur.execute("SELECT id FROM units WHERE code=%s", (code,))
                            if not cur.fetchone():
                                cur.execute("INSERT INTO units (code, name) VALUES (%s,%s)", (code, name))
                                count += 1
                db.commit()
                success = f"Imported {count} units successfully."
    if request.args.get('delete'):
        cur.execute("DELETE FROM units WHERE id=%s", (int(request.args['delete']),))
        db.commit()
        return redirect(url_for('admin.units'))
    cur.execute("SELECT * FROM units ORDER BY code")
    units_list = cur.fetchall()
    return render_template('admin/units.html', units_list=units_list, error=error, success=success)

# ── Trainers ──────────────────────────────────────────────────────────────────

@admin_bp.route('/trainers', methods=['GET', 'POST'])
@admin_required
def trainers():
    db = get_db(); cur = db.cursor()
    error = success = None
    if request.method == 'POST':
        if request.form.get('add_trainer'):
            name = request.form.get('name', '').strip()
            username = request.form.get('username', '').strip()
            password = request.form.get('password', '')
            dept_id = request.form.get('department_id', 0, type=int)
            if name and username and password and dept_id:
                cur.execute("INSERT INTO trainers (name, username, password, department_id) VALUES (%s,%s,%s,%s) ON CONFLICT (username) DO NOTHING", (name, username, password, dept_id))
                db.commit()
                success = "Trainer added successfully."
        elif request.form.get('import_csv'):
            f = request.files.get('csv_file')
            if f:
                count = 0
                stream = io.StringIO(f.stream.read().decode('utf-8', errors='ignore'))
                reader = csv.reader(stream)
                for row in reader:
                    if len(row) >= 4:
                        tname, uname, pwd, dname = [x.strip() for x in row[:4]]
                        if not uname: continue
                        cur.execute("SELECT id FROM departments WHERE name=%s", (dname,))
                        dept = cur.fetchone()
                        if dept:
                            cur.execute("INSERT INTO trainers (name, username, password, department_id) VALUES (%s,%s,%s,%s) ON CONFLICT (username) DO NOTHING", (tname, uname, pwd, dept['id']))
                            count += 1
                db.commit()
                success = f"Imported {count} trainers successfully."
    if request.args.get('delete'):
        cur.execute("DELETE FROM trainers WHERE id=%s", (int(request.args['delete']),))
        db.commit()
        return redirect(url_for('admin.trainers'))
    search = request.args.get('search', '').strip()
    if search:
        cur.execute("SELECT t.*, d.name as dept_name FROM trainers t LEFT JOIN departments d ON t.department_id=d.id WHERE t.name ILIKE %s OR t.username ILIKE %s OR d.name ILIKE %s ORDER BY t.name", (f'%{search}%', f'%{search}%', f'%{search}%'))
    else:
        cur.execute("SELECT t.*, d.name as dept_name FROM trainers t LEFT JOIN departments d ON t.department_id=d.id ORDER BY t.name")
    trainers_list = cur.fetchall()
    cur.execute("SELECT * FROM departments ORDER BY name")
    departments = cur.fetchall()
    return render_template('admin/trainers.html', trainers_list=trainers_list, departments=departments, search=search, error=error, success=success)

# ── Students ──────────────────────────────────────────────────────────────────

@admin_bp.route('/students', methods=['GET', 'POST'])
@admin_required
def students():
    db = get_db(); cur = db.cursor()
    error = success = None
    if request.method == 'POST':
        if request.form.get('add_student'):
            name = request.form.get('name', '').strip()
            adm = request.form.get('admission_number', '').strip()
            class_id = request.form.get('class_id', 0, type=int)
            if name and adm and class_id:
                cur.execute("SELECT id FROM students WHERE admission_number=%s", (adm,))
                if cur.fetchone():
                    error = "Admission number already exists."
                else:
                    cur.execute("INSERT INTO students (full_name, admission_number, class_id, password) VALUES (%s,%s,%s,'123456')", (name, adm, class_id))
                    db.commit()
        elif request.form.get('import_csv'):
            f = request.files.get('csv_file')
            if f:
                count = 0
                stream = io.StringIO(f.stream.read().decode('utf-8', errors='ignore'))
                reader = csv.reader(stream)
                for row in reader:
                    if len(row) >= 3:
                        sname, adm, class_ref = row[0].strip(), row[1].strip(), row[2].strip()
                        class_id = 0
                        if class_ref.isdigit():
                            cur.execute("SELECT id FROM classes WHERE id=%s", (int(class_ref),))
                            c = cur.fetchone()
                            if c: class_id = c['id']
                        if not class_id:
                            cur.execute("SELECT id FROM classes WHERE name=%s", (class_ref,))
                            c = cur.fetchone()
                            if c: class_id = c['id']
                        if class_id:
                            cur.execute("SELECT id FROM students WHERE admission_number=%s", (adm,))
                            if not cur.fetchone():
                                cur.execute("INSERT INTO students (full_name, admission_number, class_id, password) VALUES (%s,%s,%s,'123456')", (sname, adm, class_id))
                                count += 1
                db.commit()
                success = f"Imported {count} students successfully."
    if request.args.get('delete'):
        cur.execute("DELETE FROM students WHERE id=%s", (int(request.args['delete']),))
        db.commit()
        return redirect(url_for('admin.students'))
    cur.execute("SELECT * FROM classes ORDER BY name")
    classes_list = cur.fetchall()
    filter_class = request.args.get('filter_class', 0, type=int)
    filter_adm = request.args.get('filter_adm', '').strip()
    conditions = []
    params = []
    if filter_class:
        conditions.append("s.class_id=%s"); params.append(filter_class)
    if filter_adm:
        conditions.append("s.admission_number ILIKE %s"); params.append(f'%{filter_adm}%')
    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    cur.execute(f"SELECT s.*, c.name as class_name FROM students s LEFT JOIN classes c ON s.class_id=c.id {where} ORDER BY s.admission_number", params)
    students_list = cur.fetchall()
    return render_template('admin/students.html', students_list=students_list, classes_list=classes_list, filter_class=filter_class, filter_adm=filter_adm, error=error, success=success)

# ── Assign Units ──────────────────────────────────────────────────────────────

@admin_bp.route('/assign_units', methods=['GET', 'POST'])
@admin_required
def assign_units():
    db = get_db(); cur = db.cursor()
    error = success = None
    if request.method == 'POST':
        if request.form.get('assign'):
            class_id = request.form.get('class_id', 0, type=int)
            unit_id = request.form.get('unit_id', 0, type=int)
            trainer_id = request.form.get('trainer_id', 0, type=int)
            if class_id and unit_id and trainer_id:
                cur.execute("SELECT id FROM class_units WHERE class_id=%s AND unit_id=%s AND trainer_id=%s", (class_id, unit_id, trainer_id))
                if cur.fetchone():
                    error = "This assignment already exists."
                else:
                    cur.execute("INSERT INTO class_units (class_id, unit_id, trainer_id) VALUES (%s,%s,%s)", (class_id, unit_id, trainer_id))
                    db.commit()
            else:
                error = "Please select Class, Unit, and Trainer."
        elif request.form.get('import_csv'):
            f = request.files.get('csv_file')
            if f:
                count = 0
                stream = io.StringIO(f.stream.read().decode('utf-8', errors='ignore'))
                reader = csv.reader(stream)
                for row in reader:
                    if len(row) >= 3:
                        cname, ucode, tuname = row[0].strip(), row[1].strip(), row[2].strip()
                        cur.execute("SELECT id FROM classes WHERE name=%s", (cname,))
                        c = cur.fetchone()
                        cur.execute("SELECT id FROM units WHERE code=%s", (ucode,))
                        u = cur.fetchone()
                        cur.execute("SELECT id FROM trainers WHERE username=%s", (tuname,))
                        t = cur.fetchone()
                        if c and u and t:
                            cur.execute("INSERT INTO class_units (class_id, unit_id, trainer_id) VALUES (%s,%s,%s) ON CONFLICT DO NOTHING", (c['id'], u['id'], t['id']))
                            count += 1
                db.commit()
                success = f"Imported {count} assignments successfully."
    if request.args.get('delete'):
        cur.execute("DELETE FROM class_units WHERE id=%s", (int(request.args['delete']),))
        db.commit()
        return redirect(url_for('admin.assign_units'))
    cur.execute("SELECT * FROM classes ORDER BY name")
    classes = cur.fetchall()
    cur.execute("SELECT * FROM units ORDER BY code")
    units = cur.fetchall()
    cur.execute("SELECT * FROM trainers ORDER BY name")
    trainers = cur.fetchall()
    filter_class = request.args.get('filter_class', 0, type=int)
    filter_trainer = request.args.get('filter_trainer', 0, type=int)
    conditions = []; params = []
    if filter_class:
        conditions.append("cu.class_id=%s"); params.append(filter_class)
    if filter_trainer:
        conditions.append("cu.trainer_id=%s"); params.append(filter_trainer)
    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    cur.execute(f"SELECT cu.id, c.name as class_name, u.code, u.name as unit_name, t.name as trainer_name FROM class_units cu JOIN classes c ON cu.class_id=c.id JOIN units u ON cu.unit_id=u.id JOIN trainers t ON cu.trainer_id=t.id {where} ORDER BY c.name, u.code", params)
    assignments = cur.fetchall()
    return render_template('admin/assign_units.html', classes=classes, units=units, trainers=trainers, assignments=assignments, filter_class=filter_class, filter_trainer=filter_trainer, error=error, success=success)

# ── View Attendance ───────────────────────────────────────────────────────────

@admin_bp.route('/view_attendance')
@admin_required
def view_attendance():
    db = get_db(); cur = db.cursor()
    class_id = request.args.get('class_id', 0, type=int)
    unit_id = request.args.get('unit_id', 0, type=int)
    week = request.args.get('week', 0, type=int)
    lesson = request.args.get('lesson', '')
    cur.execute("SELECT * FROM classes ORDER BY name")
    classes = cur.fetchall()
    cur.execute("SELECT * FROM units ORDER BY code")
    units = cur.fetchall()
    attendance = []
    if class_id and unit_id and week and lesson:
        cur.execute("""SELECT a.*, s.admission_number, s.full_name
            FROM attendance a JOIN students s ON a.student_id=s.id
            WHERE a.unit_id=%s AND a.week=%s AND a.lesson=%s AND s.class_id=%s
            ORDER BY s.admission_number""", (unit_id, week, lesson, class_id))
        attendance = cur.fetchall()
    return render_template('admin/view_attendance.html', classes=classes, units=units, attendance=attendance, class_id=class_id, unit_id=unit_id, week=week, lesson=lesson)

# ── Download Attendance PDF ───────────────────────────────────────────────────

@admin_bp.route('/download_attendance_pdf')
@admin_required
def download_attendance_pdf():
    db = get_db(); cur = db.cursor()
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
    cur.execute("""SELECT a.*, s.admission_number, s.full_name
        FROM attendance a JOIN students s ON a.student_id=s.id
        WHERE a.unit_id=%s AND a.week=%s AND a.lesson=%s AND s.class_id=%s
        ORDER BY s.admission_number""", (unit_id, week, lesson, class_id))
    records = cur.fetchall()
    trainer_name = '_______________'
    if records and records[0].get('trainer_id'):
        cur.execute("SELECT name FROM trainers WHERE id=%s", (records[0]['trainer_id'],))
        t = cur.fetchone()
        if t: trainer_name = t['name']
    from datetime import datetime
    date_gen = datetime.now().strftime('%d %b %Y, %H:%M')
    attendance_date = records[0]['attendance_date'].strftime('%d %b %Y') if records else '-'
    return render_template('admin/download_attendance_pdf.html', cls=cls, unit=unit, records=records, week=week, lesson=lesson, trainer_name=trainer_name, date_gen=date_gen, attendance_date=attendance_date)

# ── Import Data ───────────────────────────────────────────────────────────────

@admin_bp.route('/import_data', methods=['GET', 'POST'])
@admin_required
def import_data():
    db = get_db(); cur = db.cursor()
    message = error = None
    if request.method == 'POST' and request.form.get('import'):
        f = request.files.get('file')
        dtype = request.form.get('type', '')
        if not f or not f.filename.endswith('.csv'):
            error = "Invalid format. Please upload a CSV file."
        else:
            stream = io.StringIO(f.stream.read().decode('utf-8', errors='ignore'))
            reader = csv.reader(stream)
            next(reader, None)  # skip header
            count = err_count = 0
            for row in reader:
                if not any(row): continue
                try:
                    ok = False
                    if dtype == 'departments' and row:
                        name = row[0].strip()
                        if name:
                            cur.execute("INSERT INTO departments (name) VALUES (%s) ON CONFLICT (name) DO NOTHING", (name,))
                            ok = True
                    elif dtype == 'classes' and len(row) >= 2:
                        cname, dname = row[0].strip(), row[1].strip()
                        cur.execute("SELECT id FROM departments WHERE name=%s", (dname,))
                        d = cur.fetchone()
                        if d:
                            cur.execute("INSERT INTO classes (name, department_id) VALUES (%s,%s) ON CONFLICT DO NOTHING", (cname, d['id']))
                            ok = True
                    elif dtype == 'units' and len(row) >= 2:
                        code, name = row[0].strip(), row[1].strip()
                        cur.execute("INSERT INTO units (code, name) VALUES (%s,%s) ON CONFLICT (code) DO NOTHING", (code, name))
                        ok = True
                    elif dtype == 'trainers' and len(row) >= 4:
                        tname, uname, pwd, dname = [x.strip() for x in row[:4]]
                        cur.execute("SELECT id FROM departments WHERE name=%s", (dname,))
                        d = cur.fetchone()
                        if d:
                            cur.execute("INSERT INTO trainers (name, username, password, department_id) VALUES (%s,%s,%s,%s) ON CONFLICT (username) DO NOTHING", (tname, uname, pwd, d['id']))
                            ok = True
                    elif dtype == 'students' and len(row) >= 3:
                        adm, sname, cls = row[0].strip(), row[1].strip(), row[2].strip()
                        cur.execute("SELECT id FROM classes WHERE name=%s", (cls,))
                        c = cur.fetchone()
                        if c:
                            cur.execute("INSERT INTO students (admission_number, full_name, class_id) VALUES (%s,%s,%s) ON CONFLICT (admission_number) DO NOTHING", (adm, sname, c['id']))
                            ok = True
                    if ok: count += 1
                    else: err_count += 1
                except Exception:
                    err_count += 1
            db.commit()
            message = f"Import complete. Successfully imported: {count}. Failed/Skipped: {err_count}."
            if count == 0 and err_count > 0:
                error = "No records were imported. Check your CSV format and ensure referenced data exists."
    return render_template('admin/import_data.html', message=message, error=error)
