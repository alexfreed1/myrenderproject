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
            if request.form.get('remember'):
                session.permanent = True
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
def welcome():
    if not session.get('admin'):
        return redirect(url_for('admin.login'))
    db = get_db(); cur = db.cursor()
    cur.execute("SELECT COUNT(*) as c FROM departments"); depts_count = cur.fetchone()['c']
    cur.execute("SELECT COUNT(*) as c FROM trainers");    trainers_count = cur.fetchone()['c']
    cur.execute("SELECT COUNT(*) as c FROM classes");     classes_count = cur.fetchone()['c']
    cur.execute("SELECT COUNT(*) as c FROM students");    students_count = cur.fetchone()['c']
    cur.execute("SELECT COUNT(*) as c FROM units");       units_count = cur.fetchone()['c']
    # Per-department breakdown
    cur.execute("""
        SELECT d.id, d.name,
            COUNT(DISTINCT c.id) as class_count,
            COUNT(DISTINCT s.id) as student_count,
            COUNT(DISTINCT t.id) as trainer_count
        FROM departments d
        LEFT JOIN classes c ON c.department_id = d.id
        LEFT JOIN students s ON s.class_id = c.id
        LEFT JOIN trainers t ON t.department_id = d.id
        GROUP BY d.id, d.name
        ORDER BY d.name
    """)
    dept_stats = cur.fetchall()
    return render_template('admin/welcome.html',
        depts_count=depts_count, trainers_count=trainers_count,
        classes_count=classes_count, students_count=students_count,
        units_count=units_count, dept_stats=dept_stats)

# ── Departments ───────────────────────────────────────────────────────────────

@admin_bp.route('/departments', methods=['GET', 'POST'])
@admin_required
def departments():
    db = get_db(); cur = db.cursor()
    error = None
    success = None
    if request.method == 'POST' and request.form.get('add_dept'):
        name = request.form.get('name', '').strip().upper()
        if name:
            cur.execute("SELECT id FROM departments WHERE name=%s", (name,))
            if cur.fetchone():
                error = "Department already exists."
            else:
                cur.execute("INSERT INTO departments (name) VALUES (%s)", (name,))
                db.commit()
                flash("Department added successfully.", "success")
                return redirect(url_for('admin.departments'))
        else:
            error = "Department name cannot be empty."
    if request.args.get('delete'):
        cur.execute("DELETE FROM departments WHERE id=%s", (int(request.args['delete']),))
        db.commit()
        flash("Department deleted.", "info")
        return redirect(url_for('admin.departments'))
    cur.execute("SELECT * FROM departments ORDER BY name")
    depts = cur.fetchall()
    return render_template('admin/departments.html', depts=depts, error=error, success=success)

# ── Classes ───────────────────────────────────────────────────────────────────

@admin_bp.route('/classes', methods=['GET', 'POST'])
@admin_required
def classes():
    db = get_db(); cur = db.cursor()
    error = success = None
    if request.method == 'POST':
        if request.form.get('add_class'):
            name = request.form.get('name', '').strip().upper()
            dept_id = request.form.get('department_id', 0, type=int)
            if name and dept_id:
                cur.execute("SELECT id FROM classes WHERE name=%s AND department_id=%s", (name, dept_id))
                if cur.fetchone():
                    error = "Class already exists in this department."
                else:
                    cur.execute("INSERT INTO classes (name, department_id) VALUES (%s,%s)", (name, dept_id))
                    db.commit()
                    flash('Class added successfully.', 'success')
                    return redirect(url_for('admin.classes'))
            else:
                error = "Please fill in all fields."
        elif request.form.get('import_csv'):
            f = request.files.get('csv_file')
            if f:
                count = 0
                stream = io.StringIO(f.stream.read().decode('utf-8', errors='ignore'))
                reader = csv.reader(stream)
                for row in reader:
                    if len(row) >= 2:
                        cname, dname = row[0].strip().upper(), row[1].strip().upper()
                        cur.execute("SELECT id FROM departments WHERE name=%s", (dname,))
                        dept = cur.fetchone()
                        if dept:
                            cur.execute("SELECT id FROM classes WHERE name=%s AND department_id=%s", (cname, dept['id']))
                            if not cur.fetchone():
                                cur.execute("INSERT INTO classes (name, department_id) VALUES (%s,%s)", (cname, dept['id']))
                                count += 1
                db.commit()
                success = f"Imported {count} classes successfully."
    if request.args.get('delete'):
        cur.execute("DELETE FROM classes WHERE id=%s", (int(request.args['delete']),))
        db.commit()
        flash('Class deleted.', 'info')
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
            code = request.form.get('code', '').strip().upper()
            name = request.form.get('name', '').strip().upper()
            dept_id = request.form.get('department_id', 0, type=int)
            if code and name:
                cur.execute("SELECT id FROM units WHERE code=%s", (code,))
                if cur.fetchone():
                    error = "Unit code already exists."
                else:
                    cur.execute("INSERT INTO units (code, name, department_id) VALUES (%s,%s,%s)", (code, name, dept_id or None))
                    db.commit()
                    flash('Unit added successfully.', 'success')
                    return redirect(url_for('admin.units'))
            else:
                error = "Code and Name are required."
        elif request.form.get('import_csv'):
            f = request.files.get('csv_file')
            if f:
                count = 0
                stream = io.StringIO(f.stream.read().decode('utf-8', errors='ignore'))
                reader = csv.reader(stream)
                for row in reader:
                    if len(row) >= 2:
                        code, name = row[0].strip().upper(), row[1].strip().upper()
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
        flash('Unit deleted.', 'info')
        return redirect(url_for('admin.units'))
    cur.execute("SELECT * FROM departments ORDER BY name")
    depts_list = cur.fetchall()
    filter_dept = request.args.get('filter_dept', 0, type=int)
    cur.execute("SELECT * FROM units ORDER BY code")
    units_list = cur.fetchall()
    return render_template('admin/units.html', units_list=units_list, depts_list=depts_list, filter_dept=filter_dept, error=error, success=success)

# ── Trainers ──────────────────────────────────────────────────────────────────

@admin_bp.route('/trainers', methods=['GET', 'POST'])
@admin_required
def trainers():
    db = get_db(); cur = db.cursor()
    error = success = None
    if request.method == 'POST':
        if request.form.get('add_trainer'):
            name = request.form.get('name', '').strip().upper()
            username = request.form.get('username', '').strip()
            password = request.form.get('password', '')
            dept_id = request.form.get('department_id', 0, type=int)
            if name and username and password and dept_id:
                cur.execute("INSERT INTO trainers (name, username, password, department_id) VALUES (%s,%s,%s,%s) ON CONFLICT (username) DO NOTHING", (name, username, password, dept_id))
                db.commit()
                flash('Trainer added successfully.', 'success')
                return redirect(url_for('admin.trainers'))
        elif request.form.get('import_csv'):
            f = request.files.get('csv_file')
            if f:
                count = 0
                stream = io.StringIO(f.stream.read().decode('utf-8', errors='ignore'))
                reader = csv.reader(stream)
                for row in reader:
                    if len(row) >= 4:
                        tname, uname, pwd, dname = [x.strip() for x in row[:4]]; tname = tname.upper(); dname = dname.upper()
                        if not uname: continue
                        cur.execute("SELECT id FROM departments WHERE name=%s", (dname,))
                        dept = cur.fetchone()
                        if dept:
                            cur.execute("INSERT INTO trainers (name, username, password, department_id) VALUES (%s,%s,%s,%s) ON CONFLICT (username) DO NOTHING", (tname, uname, pwd, dept['id']))
                            count += 1
                db.commit()
                return redirect(url_for('admin.trainers') + '?imported=1')
    if request.args.get('delete'):
        cur.execute("DELETE FROM trainers WHERE id=%s", (int(request.args['delete']),))
        db.commit()
        flash('Trainer deleted.', 'info')
        return redirect(url_for('admin.trainers'))
    search = request.args.get('search', '').strip()
    imported = request.args.get('imported')
    if imported:
        success = "Trainers imported successfully."
    if search:
        cur.execute("SELECT t.*, d.name as dept_name FROM trainers t LEFT JOIN departments d ON t.department_id=d.id WHERE t.name ILIKE %s OR t.username ILIKE %s OR d.name ILIKE %s ORDER BY t.name ASC", (f'%{search}%', f'%{search}%', f'%{search}%'))
    else:
        cur.execute("SELECT t.*, d.name as dept_name FROM trainers t LEFT JOIN departments d ON t.department_id=d.id ORDER BY t.name ASC")
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
            name = request.form.get('name', '').strip().upper()
            adm = request.form.get('admission_number', '').strip()
            class_id = request.form.get('class_id', 0, type=int)
            if name and adm and class_id:
                cur.execute("SELECT id FROM students WHERE admission_number=%s", (adm,))
                if cur.fetchone():
                    error = "Admission number already exists."
                else:
                    cur.execute("INSERT INTO students (full_name, admission_number, class_id, password) VALUES (%s,%s,%s,'123456')", (name, adm, class_id))
                    db.commit()
                    flash('Student added successfully.', 'success')
                    return redirect(url_for('admin.students'))
            else:
                error = "All fields are required."
        elif request.form.get('import_csv'):
            f = request.files.get('csv_file')
            if f:
                count = 0
                stream = io.StringIO(f.stream.read().decode('utf-8', errors='ignore'))
                reader = csv.reader(stream)
                for row in reader:
                    if len(row) >= 3:
                        sname, adm, class_ref = row[0].strip().upper(), row[1].strip(), row[2].strip().upper()
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
        flash('Student deleted.', 'info')
        return redirect(url_for('admin.students'))
    cur.execute("SELECT * FROM departments ORDER BY name")
    depts_list = cur.fetchall()
    filter_dept = request.args.get('filter_dept', 0, type=int)
    # Classes filtered by dept for the add form
    if filter_dept:
        cur.execute("SELECT * FROM classes WHERE department_id=%s ORDER BY name", (filter_dept,))
    else:
        cur.execute("SELECT * FROM classes ORDER BY name")
    classes_list = cur.fetchall()
    filter_class = request.args.get('filter_class', 0, type=int)
    filter_adm = request.args.get('filter_adm', '').strip()
    conditions = []; params = []
    if filter_dept:
        conditions.append("c.department_id=%s"); params.append(filter_dept)
    if filter_class:
        conditions.append("s.class_id=%s"); params.append(filter_class)
    if filter_adm:
        conditions.append("s.admission_number ILIKE %s"); params.append(f'%{filter_adm}%')
    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    cur.execute(f"SELECT s.*, c.name as class_name FROM students s LEFT JOIN classes c ON s.class_id=c.id {where} ORDER BY s.admission_number ASC", params)
    students_list = cur.fetchall()
    return render_template('admin/students.html', students_list=students_list, classes_list=classes_list, depts_list=depts_list, filter_dept=filter_dept, filter_class=filter_class, filter_adm=filter_adm, error=error, success=success)

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
            year = request.form.get('year', 2026, type=int)
            term = request.form.get('term', 1, type=int)
            if class_id and unit_id and trainer_id:
                cur.execute("SELECT id FROM class_units WHERE class_id=%s AND unit_id=%s AND trainer_id=%s AND year=%s AND term=%s",
                            (class_id, unit_id, trainer_id, year, term))
                if cur.fetchone():
                    error = "This assignment already exists for this term/year."
                else:
                    cur.execute("INSERT INTO class_units (class_id, unit_id, trainer_id, year, term) VALUES (%s,%s,%s,%s,%s)",
                                (class_id, unit_id, trainer_id, year, term))
                    db.commit()
                    flash('Assignment added successfully.', 'success')
                    return redirect(url_for('admin.assign_units'))
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
                        year = int(row[3].strip()) if len(row) > 3 and row[3].strip().isdigit() else 2026
                        term = int(row[4].strip()) if len(row) > 4 and row[4].strip().isdigit() else 1
                        cur.execute("SELECT id FROM classes WHERE name=%s", (cname,))
                        c = cur.fetchone()
                        cur.execute("SELECT id FROM units WHERE code=%s", (ucode,))
                        u = cur.fetchone()
                        cur.execute("SELECT id FROM trainers WHERE username=%s", (tuname,))
                        t = cur.fetchone()
                        if c and u and t:
                            cur.execute("INSERT INTO class_units (class_id, unit_id, trainer_id, year, term) VALUES (%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING",
                                        (c['id'], u['id'], t['id'], year, term))
                            count += 1
                db.commit()
                success = f"Imported {count} assignments successfully."
    if request.args.get('delete'):
        cur.execute("DELETE FROM class_units WHERE id=%s", (int(request.args['delete']),))
        db.commit()
        flash('Assignment removed.', 'info')
        return redirect(url_for('admin.assign_units'))
    cur.execute("SELECT * FROM departments ORDER BY name")
    depts_list = cur.fetchall()
    filter_dept = request.args.get('filter_dept', 0, type=int)
    filter_year = request.args.get('filter_year', 0, type=int)
    filter_term = request.args.get('filter_term', 0, type=int)
    if filter_dept:
        cur.execute("SELECT * FROM classes WHERE department_id=%s ORDER BY name", (filter_dept,))
    else:
        cur.execute("SELECT * FROM classes ORDER BY name")
    classes = cur.fetchall()
    # Filter units by department_id when department is selected
    if filter_dept:
        cur.execute("SELECT * FROM units WHERE department_id=%s ORDER BY code", (filter_dept,))
        units = cur.fetchall()
        # Fallback: if no units have department_id set, show all units
        if not units:
            cur.execute("SELECT * FROM units ORDER BY code")
            units = cur.fetchall()
    else:
        cur.execute("SELECT * FROM units ORDER BY code")
        units = cur.fetchall()
    filter_units = units
    if filter_dept:
        cur.execute("SELECT * FROM trainers WHERE department_id=%s ORDER BY name", (filter_dept,))
    else:
        cur.execute("SELECT * FROM trainers ORDER BY name")
    trainers = cur.fetchall()
    filter_class = request.args.get('filter_class', 0, type=int)
    filter_trainer = request.args.get('filter_trainer', 0, type=int)
    conditions = []; params = []
    if filter_dept:
        conditions.append("c.department_id=%s"); params.append(filter_dept)
    if filter_class:
        conditions.append("cu.class_id=%s"); params.append(filter_class)
    if filter_trainer:
        conditions.append("cu.trainer_id=%s"); params.append(filter_trainer)
    if filter_year:
        conditions.append("cu.year=%s"); params.append(filter_year)
    if filter_term:
        conditions.append("cu.term=%s"); params.append(filter_term)
    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    cur.execute(f"""SELECT cu.id, c.name as class_name, u.code, u.name as unit_name,
        t.name as trainer_name, cu.year, cu.term
        FROM class_units cu JOIN classes c ON cu.class_id=c.id
        JOIN units u ON cu.unit_id=u.id JOIN trainers t ON cu.trainer_id=t.id
        {where} ORDER BY cu.year DESC, cu.term, c.name, u.code""", params)
    assignments = cur.fetchall()
    return render_template('admin/assign_units.html', depts_list=depts_list, classes=classes,
        units=units, filter_units=filter_units, trainers=trainers, assignments=assignments,
        filter_dept=filter_dept, filter_class=filter_class, filter_trainer=filter_trainer,
        filter_year=filter_year, filter_term=filter_term, error=error, success=success)

# ── Credentials Management ────────────────────────────────────────────────────

@admin_bp.route('/credentials', methods=['GET', 'POST'])
@admin_required
def credentials():
    db = get_db(); cur = db.cursor()
    success = error = None
    tab = request.args.get('tab', 'trainers')  # 'trainers' or 'students'

    if request.method == 'POST':
        action = request.form.get('action')

        # ── Update trainer credentials ──
        if action == 'update_trainer':
            tid = request.form.get('trainer_id', 0, type=int)
            new_user = request.form.get('username', '').strip()
            new_pass = request.form.get('password', '').strip()
            if tid and new_user:
                if new_pass:
                    cur.execute("UPDATE trainers SET username=%s, password=%s WHERE id=%s", (new_user, new_pass, tid))
                else:
                    cur.execute("UPDATE trainers SET username=%s WHERE id=%s", (new_user, tid))
                db.commit()
                success = "Trainer credentials updated."
            else:
                error = "Trainer ID and username are required."
            tab = 'trainers'

        # ── Update student credentials ──
        elif action == 'update_student':
            sid = request.form.get('student_id', 0, type=int)
            new_pass = request.form.get('password', '').strip()
            if sid and new_pass:
                from routes.student import validate_password
                pwd_error = validate_password(new_pass)
                if pwd_error:
                    error = pwd_error
                    tab = 'students'
                else:
                    cur.execute("UPDATE students SET password=%s WHERE id=%s", (new_pass, sid))
                    db.commit()
                    success = "Student password updated."
            else:
                error = "Student ID and new password are required."
            tab = 'students'

        # ── Reset student password to default ──
        elif action == 'reset_student':
            sid = request.form.get('student_id', 0, type=int)
            if sid:
                cur.execute("UPDATE students SET password='123456' WHERE id=%s", (sid,))
                db.commit()
                success = "Student password reset to 123456."
            tab = 'students'

        return redirect(url_for('admin.credentials') + f'?tab={tab}&msg=' + (success or error or ''))

    msg = request.args.get('msg', '')

    # Fetch trainers
    search_t = request.args.get('search_t', '').strip()
    if search_t:
        cur.execute("""SELECT t.*, d.name as dept_name FROM trainers t
            LEFT JOIN departments d ON t.department_id=d.id
            WHERE t.name ILIKE %s OR t.username ILIKE %s ORDER BY t.name ASC""",
            (f'%{search_t}%', f'%{search_t}%'))
    else:
        cur.execute("""SELECT t.*, d.name as dept_name FROM trainers t
            LEFT JOIN departments d ON t.department_id=d.id ORDER BY t.name ASC""")
    trainers_list = cur.fetchall()

    # Fetch students
    search_s = request.args.get('search_s', '').strip()
    filter_class = request.args.get('filter_class', 0, type=int)
    conditions = []; params = []
    if search_s:
        conditions.append("(s.full_name ILIKE %s OR s.admission_number ILIKE %s)")
        params += [f'%{search_s}%', f'%{search_s}%']
    if filter_class:
        conditions.append("s.class_id=%s"); params.append(filter_class)
    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    cur.execute(f"""SELECT s.*, c.name as class_name FROM students s
        LEFT JOIN classes c ON s.class_id=c.id {where} ORDER BY s.admission_number ASC""", params)
    students_list = cur.fetchall()

    cur.execute("SELECT * FROM classes ORDER BY name")
    classes_list = cur.fetchall()

    return render_template('admin/credentials.html',
        tab=tab, msg=msg, trainers_list=trainers_list,
        students_list=students_list, classes_list=classes_list,
        search_t=search_t, search_s=search_s, filter_class=filter_class)

# ── Class List ────────────────────────────────────────────────────────────────

@admin_bp.route('/class_list')
@admin_required
def class_list():
    db = get_db(); cur = db.cursor()
    dept_id  = request.args.get('dept_id',  0, type=int)
    class_id = request.args.get('class_id', 0, type=int)
    cur.execute("SELECT * FROM departments ORDER BY name")
    departments = cur.fetchall()
    if dept_id:
        cur.execute("SELECT * FROM classes WHERE department_id=%s ORDER BY name", (dept_id,))
    else:
        cur.execute("SELECT * FROM classes ORDER BY name")
    classes = cur.fetchall()
    students = []
    cls = None
    if class_id:
        cur.execute("""SELECT s.admission_number, s.full_name
            FROM students s WHERE s.class_id=%s
            ORDER BY s.admission_number ASC""", (class_id,))
        students = cur.fetchall()
        cur.execute("SELECT c.*, d.name as dept_name FROM classes c JOIN departments d ON c.department_id=d.id WHERE c.id=%s", (class_id,))
        cls = cur.fetchone()
    return render_template('admin/class_list.html',
        departments=departments, classes=classes, students=students,
        dept_id=dept_id, class_id=class_id, cls=cls)


@admin_bp.route('/class_list_pdf')
@admin_required
def class_list_pdf():
    db = get_db(); cur = db.cursor()
    class_id = request.args.get('class_id', 0, type=int)
    if not class_id:
        return redirect('/admin/class_list')
    cur.execute("""SELECT s.admission_number, s.full_name
        FROM students s WHERE s.class_id=%s
        ORDER BY s.admission_number ASC""", (class_id,))
    students = cur.fetchall()
    cur.execute("SELECT c.*, d.name as dept_name FROM classes c JOIN departments d ON c.department_id=d.id WHERE c.id=%s", (class_id,))
    cls = cur.fetchone()
    from datetime import datetime
    date_gen = datetime.now().strftime('%d %b %Y, %H:%M')
    return render_template('admin/class_list_pdf.html', students=students, cls=cls, date_gen=date_gen)


@admin_bp.route('/view_attendance')
@admin_required
def view_attendance():
    db = get_db(); cur = db.cursor()
    dept_id  = request.args.get('dept_id',  0, type=int)
    class_id = request.args.get('class_id', 0, type=int)
    unit_id  = request.args.get('unit_id',  0, type=int)
    week     = request.args.get('week',     0, type=int)
    lesson   = request.args.get('lesson',  '')
    year     = request.args.get('year',  0, type=int)
    term     = request.args.get('term',  0, type=int)
    cur.execute("SELECT * FROM departments ORDER BY name")
    departments = cur.fetchall()
    if dept_id:
        cur.execute("SELECT * FROM classes WHERE department_id=%s ORDER BY name", (dept_id,))
    else:
        cur.execute("SELECT * FROM classes ORDER BY name")
    classes = cur.fetchall()
    if dept_id:
        cur.execute("SELECT * FROM units WHERE department_id=%s ORDER BY code", (dept_id,))
        units = cur.fetchall()
        if not units:  # fallback if units don't have dept set
            cur.execute("SELECT * FROM units ORDER BY code")
            units = cur.fetchall()
    else:
        cur.execute("SELECT * FROM units ORDER BY code")
        units = cur.fetchall()
    attendance = []
    if class_id and unit_id and week and lesson:
        conditions = ["a.unit_id=%s", "a.week=%s", "a.lesson=%s", "s.class_id=%s"]
        params = [unit_id, week, lesson, class_id]
        if year:
            conditions.append("a.year=%s"); params.append(year)
        if term:
            conditions.append("a.term=%s"); params.append(term)
        cur.execute(f"""SELECT a.*, s.admission_number, s.full_name
            FROM attendance a JOIN students s ON a.student_id=s.id
            WHERE {' AND '.join(conditions)}
            ORDER BY s.admission_number ASC""", params)
        attendance = cur.fetchall()
    return render_template('admin/view_attendance.html',
        departments=departments, classes=classes, units=units,
        attendance=attendance, dept_id=dept_id,
        class_id=class_id, unit_id=unit_id, week=week, lesson=lesson,
        year=year, term=term)

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
                        name = row[0].strip().upper()
                        if name:
                            cur.execute("INSERT INTO departments (name) VALUES (%s) ON CONFLICT (name) DO NOTHING", (name,))
                            ok = True
                    elif dtype == 'classes' and len(row) >= 2:
                        cname, dname = row[0].strip().upper(), row[1].strip().upper()
                        cur.execute("SELECT id FROM departments WHERE name=%s", (dname,))
                        d = cur.fetchone()
                        if d:
                            cur.execute("INSERT INTO classes (name, department_id) VALUES (%s,%s) ON CONFLICT DO NOTHING", (cname, d['id']))
                            ok = True
                    elif dtype == 'units' and len(row) >= 2:
                        code, name = row[0].strip().upper(), row[1].strip().upper()
                        cur.execute("INSERT INTO units (code, name) VALUES (%s,%s) ON CONFLICT (code) DO NOTHING", (code, name))
                        ok = True
                    elif dtype == 'trainers' and len(row) >= 4:
                        tname, uname, pwd, dname = [x.strip() for x in row[:4]]; tname = tname.upper(); dname = dname.upper()
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
