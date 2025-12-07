"""
Copyright (c) 2025 Amit Kadam

All Rights Reserved. No part of this software may be copied, reproduced, distributed, or used in derivative works without the prior written permission of the copyright holder.

For permission requests, contact: amitkadam96k@gmail.com
"""

from flask import (
    Flask, render_template, request, redirect,
    flash, abort, session, g, send_file, Response
)
import sqlite3
from markupsafe import escape
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from datetime import date, datetime
import io
import csv

app = Flask(__name__)
app.secret_key = "school2025"
DB_NAME = "school.db"


# ---------- DB HELPERS ----------

def get_db():
    conn = sqlite3.connect(DB_NAME, timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db():
    with get_db() as db:
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS classes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                class_name TEXT NOT NULL,
                section TEXT NOT NULL,
                UNIQUE(class_name, section)
            );

            CREATE TABLE IF NOT EXISTS subjects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                class_id INTEGER NOT NULL,
                subject_name TEXT NOT NULL,
                FOREIGN KEY(class_id) REFERENCES classes(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS students (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                roll_no TEXT NOT NULL,
                class_id INTEGER NOT NULL,
                FOREIGN KEY(class_id) REFERENCES classes(id) ON DELETE CASCADE,
                UNIQUE(class_id, roll_no)
            );

            -- Multi-exam support
            CREATE TABLE IF NOT EXISTS exams (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                class_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                exam_type TEXT,
                weight REAL DEFAULT 1.0,
                FOREIGN KEY(class_id) REFERENCES classes(id) ON DELETE CASCADE
            );

            -- Marks now tied to exam
            CREATE TABLE IF NOT EXISTS marks (
                student_id INTEGER NOT NULL,
                subject_id INTEGER NOT NULL,
                exam_id INTEGER NOT NULL,
                marks_obtained REAL DEFAULT 0,
                PRIMARY KEY(student_id, subject_id, exam_id),
                FOREIGN KEY(student_id) REFERENCES students(id) ON DELETE CASCADE,
                FOREIGN KEY(subject_id) REFERENCES subjects(id) ON DELETE CASCADE,
                FOREIGN KEY(exam_id) REFERENCES exams(id) ON DELETE CASCADE
            );

            -- Users for login/roles
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL CHECK (role IN ('admin', 'teacher'))
            );

            -- Attendance
            CREATE TABLE IF NOT EXISTS attendance_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                class_id INTEGER NOT NULL,
                date TEXT NOT NULL,
                UNIQUE(class_id, date),
                FOREIGN KEY(class_id) REFERENCES classes(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS attendance_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                student_id INTEGER NOT NULL,
                status TEXT NOT NULL CHECK(status IN ('P', 'A')),
                UNIQUE(session_id, student_id),
                FOREIGN KEY(session_id) REFERENCES attendance_sessions(id) ON DELETE CASCADE,
                FOREIGN KEY(student_id) REFERENCES students(id) ON DELETE CASCADE
            );

            -- Fees
            CREATE TABLE IF NOT EXISTS fee_structures (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                class_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                amount REAL NOT NULL,
                due_date TEXT,
                FOREIGN KEY(class_id) REFERENCES classes(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS fee_payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL,
                fee_id INTEGER NOT NULL,
                paid_amount REAL NOT NULL,
                paid_on TEXT NOT NULL,
                mode TEXT,
                FOREIGN KEY(student_id) REFERENCES students(id) ON DELETE CASCADE,
                FOREIGN KEY(fee_id) REFERENCES fee_structures(id) ON DELETE CASCADE
            );
            """
        )

        # Create default admin if not exists
        cur = db.execute("SELECT id FROM users WHERE username = 'admin'")
        if cur.fetchone() is None:
            db.execute(
                "INSERT INTO users (username, password_hash, role) VALUES (?,?,?)",
                (
                    "admin",
                    generate_password_hash("admin123"),
                    "admin",
                ),
            )
            db.commit()
            print("Default admin created: username=admin, password=admin123")

    print("Database ready with Users, Exams, Attendance, Fees & Marks!")


init_db()


# ---------- AUTH HELPERS ----------

@app.before_request
def load_logged_in_user():
    user_id = session.get("user_id")
    if user_id is None:
        g.user = None
    else:
        with get_db() as db:
            g.user = db.execute(
                "SELECT id, username, role FROM users WHERE id=?",
                (user_id,),
            ).fetchone()


def login_required(view):
    @wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None:
            flash("Login required.", "danger")
            return redirect("/login")
        return view(**kwargs)

    return wrapped_view


def require_role(*roles):
    def decorator(view):
        @wraps(view)
        def wrapped_view(**kwargs):
            if g.user is None:
                flash("Login required.", "danger")
                return redirect("/login")
            if g.user["role"] not in roles:
                abort(403)
            return view(**kwargs)

        return wrapped_view

    return decorator


# ---------- BASE HTML moved to templates/base.html ----------


# ---------- AUTH ROUTES ----------

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"].strip()

        with get_db() as db:
            user = db.execute(
                "SELECT * FROM users WHERE username = ?",
                (username,),
            ).fetchone()

        if user is None or not check_password_hash(user["password_hash"], password):
            flash("Invalid username or password.", "danger")
        else:
            session.clear()
            session["user_id"] = user["id"]
            flash("Logged in successfully.", "s")
            return redirect("/")

    content = """
    <h2>Login</h2>
    <form method="post" class="mt-3" style="max-width:400px;">
        <input name="username" class="form-control mb-3" placeholder="Username" required>
        <input name="password" type="password" class="form-control mb-3" placeholder="Password" required>
        <button class="btn btn-primary w-100">Login</button>
        <p class="mt-3 text-muted">
            Default admin: <b>admin / admin123</b> (change in DB for real use)
        </p>
    </form>
    """
    return render_template("base.html", content=content)


@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out.", "s")
    return redirect("/login")


# ---------- HOME ----------

@app.route("/")
@login_required
def home():
    with get_db() as db:
        c = db.execute("SELECT COUNT(*) FROM classes").fetchone()[0]
        s = db.execute("SELECT COUNT(*) FROM students").fetchone()[0]
        ex = db.execute("SELECT COUNT(*) FROM exams").fetchone()[0]
    content = f"""
    <h1 class="text-center mb-5">School Management System</h1>
    <div class="row text-center g-4">
        <div class="col-md-4">
            <div class="card bg-primary text-white p-4">
                <h2>{c}</h2><p>Classes</p>
            </div>
        </div>
        <div class="col-md-4">
            <div class="card bg-success text-white p-4">
                <h2>{s}</h2><p>Students</p>
            </div>
        </div>
        <div class="col-md-4">
            <div class="card bg-warning text-dark p-4">
                <h2>{ex}</h2><p>Exams</p>
            </div>
        </div>
    </div>
    <div class="text-center mt-5">
        <a href="/classes" class="btn btn-light btn-lg px-5 me-2">Go to Classes</a>
        <a href="/fees" class="btn btn-outline-light btn-lg px-5">Fees Dashboard</a>
    </div>
    """
    return render_template("base.html", content=content)


# ---------- CLASSES ----------

@app.route("/classes")
@login_required
def classes():
    with get_db() as db:
        rows = db.execute(
            "SELECT id, class_name, section FROM classes ORDER BY class_name, section"
        ).fetchall()
    if rows:
        list_items = "".join(
            [
                f'<a href="/class/{r["id"]}" '
                f'class="list-group-item list-group-item-action py-3">'
                f'{escape(r["class_name"])} - {escape(r["section"])}</a>'
                for r in rows
            ]
        )
        class_div = f'<div class="list-group mb-4">{list_items}</div>'
    else:
        class_div = '<p class="text-muted">No classes yet</p>'

    add_btn = (
        '<a href="/add_class" class="btn btn-success btn-lg">+ Add Class</a>'
        if g.user["role"] == "admin"
        else ""
    )

    content = f"""
    <div class="d-flex justify-content-between align-items-center mb-3">
        <h2>All Classes</h2>
        {add_btn}
    </div>
    {class_div}
    """
    return render_template("base.html", content=content)


@app.route("/add_class", methods=["GET", "POST"])
@login_required
@require_role("admin")
def add_class():
    if request.method == "POST":
        c = request.form["class_name"].strip()
        s = request.form["section"].strip().upper()
        if not c or not s:
            flash("Class name and section are required.", "danger")
        else:
            try:
                with get_db() as db:
                    db.execute(
                        "INSERT INTO classes (class_name, section) VALUES (?,?)",
                        (c, s),
                    )
                    db.commit()
                flash(f"Class {c}-{s} added!", "s")
                return redirect("/classes")
            except sqlite3.IntegrityError:
                flash("Class with this name and section already exists!", "danger")

    content = """
    <h2>Add Class</h2>
    <form method="post">
        <input name="class_name" class="form-control mb-3" placeholder="e.g. 10th" required>
        <input name="section" class="form-control mb-4" placeholder="A, B..." required>
        <button class="btn btn-primary btn-lg w-100">Add Class</button>
    </form>
    """
    return render_template("base.html", content=content)


@app.route("/class/<int:class_id>")
@login_required
def class_detail(class_id):
    with get_db() as db:
        cls = db.execute("SELECT * FROM classes WHERE id=?", (class_id,)).fetchone()
        if cls is None:
            abort(404)
        students = db.execute(
            "SELECT id,name,roll_no FROM students WHERE class_id=? ORDER BY roll_no",
            (class_id,),
        ).fetchall()
        subjects = db.execute(
            "SELECT id,subject_name FROM subjects WHERE class_id=? ORDER BY subject_name",
            (class_id,),
        ).fetchall()
        exams = db.execute(
            "SELECT id, name, exam_type FROM exams WHERE class_id=? ORDER BY id DESC",
            (class_id,),
        ).fetchall()

    stu = "".join(
        [
            "<li class='list-group-item d-flex justify-content-between align-items-center'>"
            f"<div>{escape(s['roll_no'])} — {escape(s['name'])}</div>"
            f"<div>"
            f"<a href='/result/{s['id']}' class='btn btn-sm btn-info me-1'>Result</a>"
            f"<a href='/fees/student/{s['id']}' class='btn btn-sm btn-outline-primary me-1'>Fees</a>"
        +
            (
                f"<a href='/student/{s['id']}/edit' class='btn btn-sm btn-warning me-1'>Edit</a>"
                f"<form method='post' action='/student/{s['id']}/delete' class='d-inline' "
                f"onsubmit=\"return confirm('Delete this student and all marks?');\">"
                f"<button class='btn btn-sm btn-danger'>Delete</button></form>"
                if g.user["role"] == "admin"
                else ""
            )
            +
            "</div></li>"
            for s in students
        ]
    )

    sub = "".join(
        [
            "<div class='d-flex align-items-center mb-1'>"
            f"<span class='badge bg-secondary me-2'>{escape(sub['subject_name'])}</span>"
            +
            (
                f"<a href='/subject/{sub['id']}/edit' class='btn btn-sm btn-outline-warning me-1'>Edit</a>"
                f"<form method='post' action='/subject/{sub['id']}/delete' class='d-inline' "
                f"onsubmit=\"return confirm('Delete this subject and all marks?');\">"
                f"<button class='btn btn-sm btn-outline-danger'>Delete</button></form>"
                if g.user["role"] == "admin"
                else ""
            )
            +
            "</div>"
            for sub in subjects
        ]
    )

    exams_html = "".join(
        [
            "<tr>"
            f"<td>{escape(e['name'])}</td>"
            f"<td>{escape(e['exam_type'] or '')}</td>"
            f"<td>"
            f"<a href='/enter_marks/{class_id}?exam_id={e['id']}' "
            f"class='btn btn-sm btn-primary me-2'>Enter Marks</a>"
            f"<a href='/class/{class_id}/results?exam_id={e['id']}' "
            f"class='btn btn-sm btn-outline-info'>View Results</a>"
            f"</td>"
            "</tr>"
            for e in exams
        ]
    )

    admin_controls = ""
    if g.user["role"] == "admin":
        admin_controls = f"""
        <a href="/class/{class_id}/edit" class="btn btn-outline-secondary me-2">Edit Class</a>
        <a href="/promote/{class_id}" class="btn btn-outline-success me-2">Promote Students</a>
        <form method="post" action="/class/{class_id}/delete" class="d-inline"
              onsubmit="return confirm('Delete this class and ALL its students, subjects, marks, etc.?');">
            <button class="btn btn-outline-danger">Delete Class</button>
        </form>
        """

    content = f"""
    <div class="d-flex justify-content-between align-items-center mb-2">
        <h2>{escape(cls['class_name'])} - {escape(cls['section'])}</h2>
        <div>
            <a href="/class/{class_id}/results" class="btn btn-outline-info me-2">Class Results</a>
            <a href="/attendance/{class_id}" class="btn btn-outline-warning me-2">Attendance</a>
            <a href="/fees/class/{class_id}" class="btn btn-outline-primary me-2">Fees</a>
            <a href="/classes" class="btn btn-secondary">Back</a>
        </div>
    </div>

    <div class="mb-3">
        <a href="/add_student/{class_id}" class="btn btn-success me-2">+ Add Student</a>
        <a href="/add_subject/{class_id}" class="btn btn-warning me-2">+ Add Subject</a>
        <a href="/exams/{class_id}" class="btn btn-primary me-2">Exams & Marks</a>
        {admin_controls}
    </div>

    <h4 class="mt-4">Subjects</h4>
    <div>{sub or "No subjects added yet"}</div>

    <h4 class="mt-4">Exams</h4>
    <table class="table table-sm table-bordered">
        <tr class="table-light"><th>Name</th><th>Type</th><th>Actions</th></tr>
        {exams_html or "<tr><td colspan='3' class='text-muted'>No exams yet.</td></tr>"}
    </table>

    <h4 class="mt-4">Students ({len(students)})</h4>
    <ul class="list-group">{stu or "<li class='list-group-item'>No students</li>"}</ul>
    """
    return render_template("base.html", content=content)


@app.route("/class/<int:class_id>/edit", methods=["GET", "POST"])
@login_required
@require_role("admin")
def edit_class(class_id):
    with get_db() as db:
        cls = db.execute("SELECT * FROM classes WHERE id=?", (class_id,)).fetchone()
        if cls is None:
            abort(404)

    if request.method == "POST":
        c = request.form["class_name"].strip()
        s = request.form["section"].strip().upper()
        if not c or not s:
            flash("Class name and section are required.", "danger")
        else:
            try:
                with get_db() as db:
                    db.execute(
                        "UPDATE classes SET class_name=?, section=? WHERE id=?",
                        (c, s, class_id),
                    )
                    db.commit()
                flash("Class updated successfully!", "s")
                return redirect(f"/class/{class_id}")
            except sqlite3.IntegrityError:
                flash(
                    "Another class with same name & section already exists!", "danger"
                )

    content = f"""
    <h2>Edit Class</h2>
    <form method="post">
        <input name="class_name" class="form-control mb-3" value="{escape(cls['class_name'])}" required>
        <input name="section" class="form-control mb-4" value="{escape(cls['section'])}" required>
        <button class="btn btn-primary btn-lg w-100">Save Changes</button>
    </form>
    """
    return render_template("base.html", content=content)


@app.route("/class/<int:class_id>/delete", methods=["POST"])
@login_required
@require_role("admin")
def delete_class(class_id):
    with get_db() as db:
        cls = db.execute("SELECT * FROM classes WHERE id=?", (class_id,)).fetchone()
        if cls is None:
            abort(404)
        # Foreign keys will cascade
        db.execute("DELETE FROM classes WHERE id=?", (class_id,))
        db.commit()
    flash("Class and all related data deleted.", "s")
    return redirect("/classes")


# ---------- PROMOTION ----------

@app.route("/promote/<int:class_id>", methods=["GET", "POST"])
@login_required
@require_role("admin")
def promote_class(class_id):
    with get_db() as db:
        source = db.execute(
            "SELECT * FROM classes WHERE id=?", (class_id,)
        ).fetchone()
        if source is None:
            abort(404)
        classes = db.execute(
            "SELECT id, class_name, section FROM classes WHERE id != ? ORDER BY class_name, section",
            (class_id,),
        ).fetchall()
        students = db.execute(
            "SELECT id, name, roll_no FROM students WHERE class_id=? ORDER BY roll_no",
            (class_id,),
        ).fetchall()

    if request.method == "POST":
        target_id = request.form.get("target_class")
        move = request.form.get("move") == "on"
        if not target_id:
            flash("Select a target class.", "danger")
        else:
            target_id = int(target_id)
            with get_db() as db:
                for stu in students:
                    try:
                        db.execute(
                            "INSERT INTO students (name, roll_no, class_id) VALUES (?,?,?)",
                            (stu["name"], stu["roll_no"], target_id),
                        )
                    except sqlite3.IntegrityError:
                        # skip duplicate roll
                        continue
                if move:
                    db.execute(
                        "DELETE FROM students WHERE class_id=?",
                        (class_id,),
                    )
                db.commit()
            flash("Promotion completed.", "s")
            return redirect(f"/class/{target_id}")

    options = "".join(
        [
            f"<option value='{c['id']}'>{escape(c['class_name'])} - {escape(c['section'])}</option>"
            for c in classes
        ]
    )

    content = f"""
    <h2>Promote Students</h2>
    <p>Source class: <b>{escape(source['class_name'])} - {escape(source['section'])}</b></p>
    <p>Students in class: {len(students)}</p>
    <form method="post" style="max-width:500px;">
        <div class="mb-3">
            <label class="form-label">Target Class</label>
            <select name="target_class" class="form-select" required>
                <option value="">Select class</option>
                {options}
            </select>
        </div>
        <div class="form-check mb-3">
            <input class="form-check-input" type="checkbox" name="move" id="moveCheck">
            <label class="form-check-label" for="moveCheck">
                Move students (remove from current class after promotion)
            </label>
        </div>
        <button class="btn btn-success">Promote</button>
    </form>
    <a href="/class/{class_id}" class="btn btn-secondary mt-3">Back</a>
    """
    return render_template("base.html", content=content)


# ---------- SUBJECTS ----------

@app.route("/add_subject/<int:class_id>", methods=["GET", "POST"])
@login_required
@require_role("admin")
def add_subject(class_id):
    with get_db() as db:
        cls = db.execute("SELECT * FROM classes WHERE id=?", (class_id,)).fetchone()
        if cls is None:
            abort(404)

    if request.method == "POST":
        sub = request.form["subject"].strip()
        if not sub:
            flash("Subject name is required.", "danger")
        else:
            with get_db() as db:
                db.execute(
                    "INSERT INTO subjects (class_id, subject_name) VALUES (?,?)",
                    (class_id, sub),
                )
                db.commit()
            flash("Subject added!", "s")
            return redirect(f"/class/{class_id}")

    content = f"""
    <h3>Add Subject</h3>
    <form method="post">
        <input name="subject" class="form-control mb-3" placeholder="e.g. Mathematics" required>
        <button class="btn btn-success">Add Subject</button>
    </form>
    <a href="/class/{class_id}" class="btn btn-secondary mt-3">Back</a>
    """
    return render_template("base.html", content=content)


@app.route("/subject/<int:subject_id>/edit", methods=["GET", "POST"])
@login_required
@require_role("admin")
def edit_subject(subject_id):
    with get_db() as db:
        sub = db.execute(
            "SELECT subjects.*, classes.class_name, classes.section "
            "FROM subjects JOIN classes ON subjects.class_id=classes.id "
            "WHERE subjects.id=?",
            (subject_id,),
        ).fetchone()
        if sub is None:
            abort(404)

    class_id = sub["class_id"]

    if request.method == "POST":
        name = request.form["subject"].strip()
        if not name:
            flash("Subject name is required.", "danger")
        else:
            with get_db() as db:
                db.execute(
                    "UPDATE subjects SET subject_name=? WHERE id=?",
                    (name, subject_id),
                )
                db.commit()
            flash("Subject updated!", "s")
            return redirect(f"/class/{class_id}")

    content = f"""
    <h3>Edit Subject ({escape(sub['class_name'])} - {escape(sub['section'])})</h3>
    <form method="post">
        <input name="subject" class="form-control mb-3" value="{escape(sub['subject_name'])}" required>
        <button class="btn btn-primary">Save Changes</button>
    </form>
    <a href="/class/{class_id}" class="btn btn-secondary mt-3">Back</a>
    """
    return render_template("base.html", content=content)


@app.route("/subject/<int:subject_id>/delete", methods=["POST"])
@login_required
@require_role("admin")
def delete_subject(subject_id):
    with get_db() as db:
        sub = db.execute("SELECT * FROM subjects WHERE id=?", (subject_id,)).fetchone()
        if sub is None:
            abort(404)
        class_id = sub["class_id"]
        db.execute("DELETE FROM subjects WHERE id=?", (subject_id,))
        db.commit()
    flash("Subject and all related marks deleted.", "s")
    return redirect(f"/class/{class_id}")


# ---------- STUDENTS ----------

@app.route("/add_student/<int:class_id>", methods=["GET", "POST"])
@login_required
def add_student(class_id):
    with get_db() as db:
        cls = db.execute("SELECT * FROM classes WHERE id=?", (class_id,)).fetchone()
        if cls is None:
            abort(404)

    if request.method == "POST":
        name = request.form["name"].strip()
        roll = request.form["roll_no"].strip()
        if not name or not roll:
            flash("Name and roll number are required.", "danger")
        else:
            try:
                with get_db() as db:
                    db.execute(
                        "INSERT INTO students (name, roll_no, class_id) VALUES (?,?,?)",
                        (name, roll, class_id),
                    )
                    db.commit()
                flash("Student added!", "s")
            except sqlite3.IntegrityError:
                flash("Roll number already exists in this class!", "danger")
            return redirect(f"/class/{class_id}")

    content = f"""
    <h3>Add Student</h3>
    <form method="post">
        <input name="name" class="form-control mb-3" placeholder="Name" required>
        <input name="roll_no" class="form-control" placeholder="Roll No" required>
        <button class="btn btn-success mt-3">Add</button>
    </form>
    <a href="/class/{class_id}" class="btn btn-secondary mt-3">Back</a>
    """
    return render_template("base.html", content=content)


@app.route("/student/<int:student_id>/edit", methods=["GET", "POST"])
@login_required
def edit_student(student_id):
    with get_db() as db:
        stu = db.execute(
            "SELECT students.*, classes.class_name, classes.section "
            "FROM students JOIN classes ON students.class_id=classes.id "
            "WHERE students.id=?",
            (student_id,),
        ).fetchone()
        if stu is None:
            abort(404)

    class_id = stu["class_id"]

    if request.method == "POST":
        name = request.form["name"].strip()
        roll = request.form["roll_no"].strip()
        if not name or not roll:
            flash("Name and roll number are required.", "danger")
        else:
            try:
                with get_db() as db:
                    db.execute(
                        "UPDATE students SET name=?, roll_no=? WHERE id=?",
                        (name, roll, student_id),
                    )
                    db.commit()
                flash("Student updated.", "s")
                return redirect(f"/class/{class_id}")
            except sqlite3.IntegrityError:
                flash("Roll number already exists in this class!", "danger")

    content = f"""
    <h3>Edit Student ({escape(stu['class_name'])} - {escape(stu['section'])})</h3>
    <form method="post">
        <input name="name" class="form-control mb-3" value="{escape(stu['name'])}" required>
        <input name="roll_no" class="form-control" value="{escape(stu['roll_no'])}" required>
        <button class="btn btn-primary mt-3">Save Changes</button>
    </form>
    <a href="/class/{class_id}" class="btn btn-secondary mt-3">Back</a>
    """
    return render_template("base.html", content=content)


@app.route("/student/<int:student_id>/delete", methods=["POST"])
@login_required
@require_role("admin")
def delete_student(student_id):
    with get_db() as db:
        stu = db.execute("SELECT * FROM students WHERE id=?", (student_id,)).fetchone()
        if stu is None:
            abort(404)
        class_id = stu["class_id"]
        db.execute("DELETE FROM students WHERE id=?", (student_id,))
        db.commit()
    flash("Student and all marks deleted.", "s")
    return redirect(f"/class/{class_id}")


# ---------- EXAMS & MARKS (MULTI-EXAM) ----------

@app.route("/exams/<int:class_id>", methods=["GET", "POST"])
@login_required
def exams(class_id):
    with get_db() as db:
        cls = db.execute("SELECT * FROM classes WHERE id=?", (class_id,)).fetchone()
        if cls is None:
            abort(404)

        exams = db.execute(
            "SELECT * FROM exams WHERE class_id=? ORDER BY id DESC",
            (class_id,),
        ).fetchall()

    if request.method == "POST":
        name = request.form["name"].strip()
        exam_type = request.form["exam_type"].strip()
        weight_str = request.form.get("weight", "1").strip()
        try:
            weight = float(weight_str) if weight_str else 1.0
        except ValueError:
            weight = 1.0
        if not name:
            flash("Exam name is required.", "danger")
        else:
            with get_db() as db:
                db.execute(
                    "INSERT INTO exams (class_id, name, exam_type, weight) VALUES (?,?,?,?)",
                    (class_id, name, exam_type, weight),
                )
                db.commit()
            flash("Exam added.", "s")
            return redirect(f"/exams/{class_id}")

    rows = "".join(
        [
            "<tr>"
            f"<td>{escape(e['name'])}</td>"
            f"<td>{escape(e['exam_type'] or '')}</td>"
            f"<td>{e['weight']}</td>"
            f"<td>"
            f"<a href='/enter_marks/{class_id}?exam_id={e['id']}' class='btn btn-sm btn-primary me-2'>Enter Marks</a>"
            f"<a href='/class/{class_id}/results?exam_id={e['id']}' class='btn btn-sm btn-outline-info'>Results</a>"
            f"</td>"
            "</tr>"
            for e in exams
        ]
    )

    content = f"""
    <h2>Exams - {escape(cls['class_name'])} {escape(cls['section'])}</h2>
    <table class="table table-bordered mt-3">
        <tr class="table-light">
            <th>Name</th><th>Type</th><th>Weight</th><th>Actions</th>
        </tr>
        {rows or "<tr><td colspan='4' class='text-muted'>No exams yet.</td></tr>"}
    </table>

    <h4 class="mt-4">Add Exam</h4>
    <form method="post" class="row g-3">
        <div class="col-md-4">
            <input name="name" class="form-control" placeholder="e.g. Mid Term" required>
        </div>
        <div class="col-md-3">
            <input name="exam_type" class="form-control" placeholder="Theory/Practical">
        </div>
        <div class="col-md-2">
            <input name="weight" class="form-control" placeholder="Weight" value="1">
        </div>
        <div class="col-md-3">
            <button class="btn btn-success w-100">Add Exam</button>
        </div>
    </form>

    <a href="/class/{class_id}" class="btn btn-secondary mt-4">Back</a>
    """
    return render_template("base.html", content=content)


@app.route("/enter_marks/<int:class_id>", methods=["GET", "POST"])
@login_required
def enter_marks(class_id):
    exam_id = request.args.get("exam_id") or request.form.get("exam_id")
    if not exam_id:
        flash("Exam not selected. Open from Exams page.", "danger")
        return redirect(f"/exams/{class_id}")

    exam_id = int(exam_id)

    with get_db() as db:
        cls = db.execute("SELECT * FROM classes WHERE id=?", (class_id,)).fetchone()
        if cls is None:
            abort(404)
        exam = db.execute(
            "SELECT * FROM exams WHERE id=? AND class_id=?",
            (exam_id, class_id),
        ).fetchone()
        if exam is None:
            abort(404)

        students = db.execute(
            "SELECT id,name FROM students WHERE class_id=? ORDER BY roll_no",
            (class_id,),
        ).fetchall()
        subjects = db.execute(
            "SELECT id,subject_name FROM subjects WHERE class_id=? ORDER BY subject_name",
            (class_id,),
        ).fetchall()

        marks_map = {}
        if students and subjects:
            student_ids = [s["id"] for s in students]
            placeholders = ",".join("?" * len(student_ids))
            rows = db.execute(
                f"SELECT student_id, subject_id, marks_obtained "
                f"FROM marks WHERE exam_id=? AND student_id IN ({placeholders})",
                [exam_id] + student_ids,
            ).fetchall()
            marks_map = {
                (r["student_id"], r["subject_id"]): r["marks_obtained"] for r in rows
            }

    if request.method == "POST":
        student_id = int(request.form["student_id"])
        with get_db() as db:
            for sub in subjects:
                marks_str = request.form.get(f"marks_{sub['id']}", "")
                try:
                    marks = float(marks_str) if marks_str != "" else 0.0
                except ValueError:
                    marks = 0.0
                db.execute(
                    "INSERT OR REPLACE INTO marks (student_id, subject_id, exam_id, marks_obtained) "
                    "VALUES (?,?,?,?)",
                    (student_id, sub["id"], exam_id, marks),
                )
            db.commit()
        flash("Marks saved successfully!", "s")
        return redirect(f"/enter_marks/{class_id}?exam_id={exam_id}")

    if not students:
        forms = "<p class='text-muted'>No students in this class.</p>"
    elif not subjects:
        forms = "<p class='text-muted'>No subjects in this class.</p>"
    else:
        forms = ""
        for stu in students:
            forms += (
                f"<h5 class='mt-4'>{escape(stu['name'])}</h5>"
                f"<form method='post'>"
                f"<input type='hidden' name='exam_id' value='{exam_id}'>"
                f"<input type='hidden' name='student_id' value='{stu['id']}'>"
            )
            for sub in subjects:
                existing = marks_map.get((stu["id"], sub["id"]), 0)
                forms += (
                    "<div class='mb-1'>"
                    f"<label>{escape(sub['subject_name'])}: </label>"
                    f"<input name='marks_{sub['id']}' type='number' min='0' max='100' "
                    f"value='{existing}' "
                    "class='form-control d-inline-block w-auto mx-2' style='width:100px;'>"
                    "</div>"
                )
            forms += "<button class='btn btn-primary btn-sm mt-2'>Save Marks</button></form><hr>"

    content = f"""
    <h2>Enter Marks - {escape(cls['class_name'])} {escape(cls['section'])}</h2>
    <p>Exam: <b>{escape(exam['name'])}</b> ({escape(exam['exam_type'] or '')})</p>
    {forms}
    <a href='/exams/{class_id}' class='btn btn-secondary mt-3'>Back</a>
    """
    return render_template("base.html", content=content)


# ---------- INDIVIDUAL RESULT (PER EXAM) + PDF ----------

@app.route("/result/<int:student_id>")
@login_required
def result(student_id):
    exam_id = request.args.get("exam_id")
    with get_db() as db:
        student = db.execute(
            "SELECT s.id, s.name, s.roll_no, c.class_name, c.section, c.id as class_id "
            "FROM students s JOIN classes c ON s.class_id=c.id "
            "WHERE s.id=?",
            (student_id,),
        ).fetchone()
        if student is None:
            abort(404)

        # Default to latest exam if not specified
        if exam_id is None:
            ex = db.execute(
                "SELECT id FROM exams WHERE class_id=? ORDER BY id DESC LIMIT 1",
                (student["class_id"],),
            ).fetchone()
            if ex is None:
                flash("No exams for this class.", "danger")
                return redirect(f"/class/{student['class_id']}")
            exam_id = ex["id"]
        else:
            exam_id = int(exam_id)

        exam = db.execute(
            "SELECT * FROM exams WHERE id=? AND class_id=?",
            (exam_id, student["class_id"]),
        ).fetchone()
        if exam is None:
            abort(404)

        results = db.execute(
            """
            SELECT sub.subject_name, COALESCE(m.marks_obtained, 0) as marks
            FROM subjects sub
            LEFT JOIN marks m ON m.subject_id = sub.id AND m.student_id = ? AND m.exam_id = ?
            WHERE sub.class_id = ?
            ORDER BY sub.subject_name
        """,
            (student_id, exam_id, student["class_id"]),
        ).fetchall()

    total = sum(r["marks"] for r in results)
    max_total = len(results) * 100
    percentage = (total / max_total * 100) if max_total else 0.0
    status = "PASS" if percentage >= 33 else "FAIL"
    if percentage >= 90:
        grade = "A+"
    elif percentage >= 80:
        grade = "A"
    elif percentage >= 60:
        grade = "B"
    elif percentage >= 33:
        grade = "C"
    else:
        grade = "F"

    rows = "".join(
        [
            f"<tr><td>{escape(r['subject_name'])}</td>"
            f"<td class='text-center'><b>{r['marks']}</b></td></tr>"
            for r in results
        ]
    )

    content = f"""
    <h2 class="text-center">Result Card</h2>
    <h5 class="text-center text-muted">
        Exam: {escape(exam['name'])} ({escape(exam['exam_type'] or '')})
    </h5>
    <h4 class="text-center">
        {escape(student['name'])} | {escape(student['roll_no'])} |
        {escape(student['class_name'])}-{escape(student['section'])}
    </h4>
    <table class="table table-bordered mt-4">
        <tr class="table-primary"><th>Subject</th><th class="text-center">Marks</th></tr>
        {rows}
    </table>
    <div class="text-center mt-4">
        <h3>Total: {total} / {max_total}</h3>
        <h2>Percentage:
            <span style="color: {'green' if status=='PASS' else 'red'}">
                {percentage:.2f}%
            </span>
        </h2>
        <h1><b>{status}</b> - Grade: {grade}</h1>
    </div>
    <div class="text-center mt-3">
        <a href="/result/{student_id}/pdf?exam_id={exam_id}" class="btn btn-sm btn-outline-secondary me-2">Download PDF</a>
        <a href="/class/{student['class_id']}" class="btn btn-secondary">Back to Class</a>
    </div>
    """
    return render_template("base.html", content=content)


@app.route("/result/<int:student_id>/pdf")
@login_required
def result_pdf(student_id):
    # Very basic PDF stub using reportlab; requires `pip install reportlab`
    exam_id = request.args.get("exam_id")
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas
    except ImportError:
        flash("PDF generation requires 'reportlab' package. Install it first.", "danger")
        return redirect(f"/result/{student_id}" + (f"?exam_id={exam_id}" if exam_id else ""))

    with get_db() as db:
        student = db.execute(
            "SELECT s.id, s.name, s.roll_no, c.class_name, c.section, c.id as class_id "
            "FROM students s JOIN classes c ON s.class_id=c.id "
            "WHERE s.id=?",
            (student_id,),
        ).fetchone()
        if student is None:
            abort(404)

        if exam_id is None:
            ex = db.execute(
                "SELECT id FROM exams WHERE class_id=? ORDER BY id DESC LIMIT 1",
                (student["class_id"],),
            ).fetchone()
            if ex is None:
                flash("No exams for this class.", "danger")
                return redirect(f"/class/{student['class_id']}")
            exam_id = ex["id"]
        else:
            exam_id = int(exam_id)

        exam = db.execute(
            "SELECT * FROM exams WHERE id=? AND class_id=?",
            (exam_id, student["class_id"]),
        ).fetchone()
        if exam is None:
            abort(404)

        results = db.execute(
            """
            SELECT sub.subject_name, COALESCE(m.marks_obtained, 0) as marks
            FROM subjects sub
            LEFT JOIN marks m ON m.subject_id = sub.id AND m.student_id = ? AND m.exam_id = ?
            WHERE sub.class_id = ?
            ORDER BY sub.subject_name
        """,
            (student_id, exam_id, student["class_id"]),
        ).fetchall()

    total = sum(r["marks"] for r in results)
    max_total = len(results) * 100
    percentage = (total / max_total * 100) if max_total else 0.0

    # Create PDF in memory
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    y = height - 50
    c.setFont("Helvetica-Bold", 16)
    c.drawCentredString(width / 2, y, "Result Card")
    y -= 20
    c.setFont("Helvetica", 12)
    c.drawCentredString(
        width / 2,
        y,
        f"Exam: {exam['name']} ({exam['exam_type'] or ''})",
    )
    y -= 30
    c.drawString(
        50,
        y,
        f"Name: {student['name']}    Roll: {student['roll_no']}    Class: {student['class_name']}-{student['section']}",
    )
    y -= 30
    c.drawString(50, y, "Subject")
    c.drawString(350, y, "Marks")
    y -= 15
    c.line(50, y, 550, y)
    y -= 20

    for r in results:
        c.drawString(50, y, r["subject_name"])
        c.drawRightString(550, y, f"{r['marks']}")
        y -= 20
        if y < 80:
            c.showPage()
            y = height - 80

    y -= 10
    c.line(50, y, 550, y)
    y -= 30
    c.drawString(50, y, f"Total: {total} / {max_total}")
    y -= 20
    c.drawString(50, y, f"Percentage: {percentage:.2f}%")

    c.showPage()
    c.save()
    buffer.seek(0)

    filename = f"result_{student_id}_exam_{exam_id}.pdf"
    return send_file(
        buffer,
        as_attachment=True,
        download_name=filename,
        mimetype="application/pdf",
    )


# ---------- CLASS RESULTS (PER EXAM) + CSV EXPORT ----------

@app.route("/class/<int:class_id>/results")
@login_required
def class_results(class_id):
    exam_id = request.args.get("exam_id")
    with get_db() as db:
        cls = db.execute("SELECT * FROM classes WHERE id=?", (class_id,)).fetchone()
        if cls is None:
            abort(404)

        if exam_id is None:
            ex = db.execute(
                "SELECT id FROM exams WHERE class_id=? ORDER BY id DESC LIMIT 1",
                (class_id,),
            ).fetchone()
            if ex is None:
                flash("No exams defined for this class.", "danger")
                return redirect(f"/class/{class_id}")
            exam_id = ex["id"]
        else:
            exam_id = int(exam_id)

        exam = db.execute(
            "SELECT * FROM exams WHERE id=? AND class_id=?",
            (exam_id, class_id),
        ).fetchone()
        if exam is None:
            abort(404)

        subject_count = db.execute(
            "SELECT COUNT(*) FROM subjects WHERE class_id=?",
            (class_id,),
        ).fetchone()[0]

        students = db.execute(
            """
            SELECT s.id, s.name, s.roll_no,
                   COALESCE(SUM(m.marks_obtained), 0) AS total
            FROM students s
            LEFT JOIN marks m ON m.student_id = s.id AND m.exam_id = ?
            WHERE s.class_id = ?
            GROUP BY s.id, s.name, s.roll_no
            ORDER BY total DESC, s.roll_no
        """,
            (exam_id, class_id),
        ).fetchall()

    if subject_count == 0:
        table_html = "<p class='text-muted'>No subjects in this class; cannot calculate results.</p>"
    elif not students:
        table_html = "<p class='text-muted'>No students in this class.</p>"
    else:
        max_total = subject_count * 100
        rows = ""
        for s in students:
            total = s["total"]
            percentage = (total / max_total * 100) if max_total else 0.0
            status = "PASS" if percentage >= 33 else "FAIL"
            if percentage >= 90:
                grade = "A+"
            elif percentage >= 80:
                grade = "A"
            elif percentage >= 60:
                grade = "B"
            elif percentage >= 33:
                grade = "C"
            else:
                grade = "F"
            rows += (
                "<tr>"
                f"<td>{escape(s['roll_no'])}</td>"
                f"<td>{escape(s['name'])}</td>"
                f"<td class='text-end'>{total}</td>"
                f"<td class='text-end'>{percentage:.2f}%</td>"
                f"<td>{grade}</td>"
                f"<td>{status}</td>"
                f"<td><a href='/result/{s['id']}?exam_id={exam_id}' class='btn btn-sm btn-outline-info'>View</a></td>"
                "</tr>"
            )

        table_html = f"""
        <table class="table table-striped table-bordered mt-3">
            <thead class="table-light">
                <tr>
                    <th>Roll No</th>
                    <th>Name</th>
                    <th class="text-end">Total ({max_total})</th>
                    <th class="text-end">Percentage</th>
                    <th>Grade</th>
                    <th>Status</th>
                    <th>Result Card</th>
                </tr>
            </thead>
            <tbody>{rows}</tbody>
        </table>
        """

    content = f"""
    <h2>Class Results - {escape(cls['class_name'])} {escape(cls['section'])}</h2>
    <p>Exam: <b>{escape(exam['name'])}</b> ({escape(exam['exam_type'] or '')})</p>
    <div class="mb-3">
        <a href="/class/{class_id}/results/csv?exam_id={exam_id}" class="btn btn-sm btn-outline-secondary me-2">
            Export CSV
        </a>
        <a href="/class/{class_id}" class="btn btn-secondary btn-sm">Back to Class</a>
    </div>
    {table_html}
    """
    return render_template("base.html", content=content)


@app.route("/class/<int:class_id>/results/csv")
@login_required
def class_results_csv(class_id):
    exam_id = request.args.get("exam_id")
    if exam_id is None:
        flash("Exam required for CSV export.", "danger")
        return redirect(f"/class/{class_id}/results")
    exam_id = int(exam_id)

    with get_db() as db:
        cls = db.execute("SELECT * FROM classes WHERE id=?", (class_id,)).fetchone()
        if cls is None:
            abort(404)
        subject_count = db.execute(
            "SELECT COUNT(*) FROM subjects WHERE class_id=?",
            (class_id,),
        ).fetchone()[0]
        max_total = subject_count * 100 if subject_count else 0

        students = db.execute(
            """
            SELECT s.id, s.name, s.roll_no,
                   COALESCE(SUM(m.marks_obtained), 0) AS total
            FROM students s
            LEFT JOIN marks m ON m.student_id = s.id AND m.exam_id = ?
            WHERE s.class_id = ?
            GROUP BY s.id, s.name, s.roll_no
            ORDER BY total DESC, s.roll_no
        """,
            (exam_id, class_id),
        ).fetchall()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        ["Roll No", "Name", "Total", f"Max ({max_total})", "Percentage", "Grade", "Status"]
    )
    for s in students:
        total = s["total"]
        percentage = (total / max_total * 100) if max_total else 0.0
        status = "PASS" if percentage >= 33 else "FAIL"
        if percentage >= 90:
            grade = "A+"
        elif percentage >= 80:
            grade = "A"
        elif percentage >= 60:
            grade = "B"
        elif percentage >= 33:
            grade = "C"
        else:
            grade = "F"
        writer.writerow(
            [s["roll_no"], s["name"], total, max_total, f"{percentage:.2f}", grade, status]
        )

    output.seek(0)
    filename = f"class_{class_id}_exam_{exam_id}_results.csv"
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment;filename={filename}"},
    )


# ---------- ATTENDANCE (PER CLASS, PER DATE) ----------

@app.route("/attendance/<int:class_id>", methods=["GET", "POST"])
@login_required
def attendance(class_id):
    date_str = request.args.get("date") or request.form.get("date")
    if not date_str:
        date_str = date.today().isoformat()

    with get_db() as db:
        cls = db.execute("SELECT * FROM classes WHERE id=?", (class_id,)).fetchone()
        if cls is None:
            abort(404)
        students = db.execute(
            "SELECT id, name, roll_no FROM students WHERE class_id=? ORDER BY roll_no",
            (class_id,),
        ).fetchall()

        session_row = db.execute(
            "SELECT * FROM attendance_sessions WHERE class_id=? AND date=?",
            (class_id, date_str),
        ).fetchone()

        if request.method == "POST":
            if session_row is None:
                db.execute(
                    "INSERT INTO attendance_sessions (class_id, date) VALUES (?,?)",
                    (class_id, date_str),
                )
                db.commit()
                session_row = db.execute(
                    "SELECT * FROM attendance_sessions WHERE class_id=? AND date=?",
                    (class_id, date_str),
                ).fetchone()

            session_id = session_row["id"]
            # Clear previous records
            db.execute(
                "DELETE FROM attendance_records WHERE session_id=?",
                (session_id,),
            )
            for stu in students:
                status = "P" if request.form.get(f"present_{stu['id']}") == "on" else "A"
                db.execute(
                    "INSERT INTO attendance_records (session_id, student_id, status) VALUES (?,?,?)",
                    (session_id, stu["id"], status),
                )
            db.commit()
            flash("Attendance saved.", "s")

        # Reload session & records
        session_row = db.execute(
            "SELECT * FROM attendance_sessions WHERE class_id=? AND date=?",
            (class_id, date_str),
        ).fetchone()
        records = {}
        if session_row:
            recs = db.execute(
                "SELECT student_id, status FROM attendance_records WHERE session_id=?",
                (session_row["id"],),
            ).fetchall()
            records = {r["student_id"]: r["status"] for r in recs}

    rows = ""
    for stu in students:
        checked = "checked" if records.get(stu["id"], "P") == "P" else ""
        rows += (
            "<tr>"
            f"<td>{escape(stu['roll_no'])}</td>"
            f"<td>{escape(stu['name'])}</td>"
            f"<td class='text-center'>"
            f"<input type='checkbox' name='present_{stu['id']}' {checked}>"
            f"</td>"
            "</tr>"
        )

    content = f"""
    <h2>Attendance - {escape(cls['class_name'])} {escape(cls['section'])}</h2>
    <form method="post" class="mb-3 d-flex align-items-center">
        <label class="me-2">Date:</label>
        <input type="date" name="date" value="{date_str}" class="form-control me-3" style="max-width:200px;">
        <button class="btn btn-primary">Save</button>
    </form>
    <form method="post">
        <input type="hidden" name="date" value="{date_str}">
        <table class="table table-bordered">
            <tr class="table-light">
                <th>Roll</th><th>Name</th><th class="text-center">Present</th>
            </tr>
            {rows or "<tr><td colspan='3' class='text-muted'>No students.</td></tr>"}
        </table>
        <button class="btn btn-success mt-2">Save Attendance</button>
    </form>
    <a href="/class/{class_id}" class="btn btn-secondary mt-3">Back</a>
    """
    return render_template("base.html", content=content)


# ---------- FEES MODULE ----------

@app.route("/fees")
@login_required
def fees_dashboard():
    with get_db() as db:
        rows = db.execute(
            """
            SELECT c.id, c.class_name, c.section,
                   COUNT(DISTINCT fs.id) AS fee_items,
                   COUNT(DISTINCT s.id) AS students
            FROM classes c
            LEFT JOIN fee_structures fs ON fs.class_id = c.id
            LEFT JOIN students s ON s.class_id = c.id
            GROUP BY c.id, c.class_name, c.section
            ORDER BY c.class_name, c.section
        """
        ).fetchall()

    table_rows = ""
    for r in rows:
        table_rows += (
            "<tr>"
            f"<td>{escape(r['class_name'])}-{escape(r['section'])}</td>"
            f"<td class='text-center'>{r['students']}</td>"
            f"<td class='text-center'>{r['fee_items']}</td>"
            f"<td><a href='/fees/class/{r['id']}' class='btn btn-sm btn-primary'>Open</a></td>"
            "</tr>"
        )

    content = f"""
    <h2>Fees Dashboard</h2>
    <table class="table table-bordered mt-3">
        <tr class="table-light">
            <th>Class</th><th class="text-center">Students</th>
            <th class="text-center">Fee Items</th><th>Actions</th>
        </tr>
        {table_rows or "<tr><td colspan='4' class='text-muted'>No classes defined.</td></tr>"}
    </table>
    """
    return render_template("base.html", content=content)


@app.route("/fees/class/<int:class_id>", methods=["GET", "POST"])
@login_required
def fees_class(class_id):
    with get_db() as db:
        cls = db.execute("SELECT * FROM classes WHERE id=?", (class_id,)).fetchone()
        if cls is None:
            abort(404)

        if request.method == "POST" and g.user["role"] == "admin":
            name = request.form["name"].strip()
            amount_str = request.form["amount"].strip()
            due_date = request.form["due_date"].strip()
            try:
                amount = float(amount_str)
            except ValueError:
                amount = 0.0
            if not name or amount <= 0:
                flash("Valid fee name and amount required.", "danger")
            else:
                db.execute(
                    "INSERT INTO fee_structures (class_id, name, amount, due_date) VALUES (?,?,?,?)",
                    (class_id, name, amount, due_date or None),
                )
                db.commit()
                flash("Fee item added.", "s")
            return redirect(f"/fees/class/{class_id}")

        fees = db.execute(
            "SELECT * FROM fee_structures WHERE class_id=? ORDER BY id",
            (class_id,),
        ).fetchall()
        students = db.execute(
            "SELECT id, name, roll_no FROM students WHERE class_id=? ORDER BY roll_no",
            (class_id,),
        ).fetchall()

        # For each student, compute due & paid
        fee_totals = db.execute(
            "SELECT COALESCE(SUM(amount),0) as total FROM fee_structures WHERE class_id=?",
            (class_id,),
        ).fetchone()["total"]

        student_rows = ""
        for s in students:
            paid = db.execute(
                """
                SELECT COALESCE(SUM(fp.paid_amount),0) as paid
                FROM fee_payments fp
                JOIN fee_structures fs ON fp.fee_id = fs.id
                WHERE fp.student_id=? AND fs.class_id=?
                """,
                (s["id"], class_id),
            ).fetchone()["paid"]
            balance = fee_totals - paid
            student_rows += (
                "<tr>"
                f"<td>{escape(s['roll_no'])}</td>"
                f"<td>{escape(s['name'])}</td>"
                f"<td class='text-end'>{fee_totals:.2f}</td>"
                f"<td class='text-end'>{paid:.2f}</td>"
                f"<td class='text-end'>{balance:.2f}</td>"
                f"<td><a href='/fees/student/{s['id']}' class='btn btn-sm btn-outline-primary'>View</a></td>"
                "</tr>"
            )

    fee_rows = "".join(
        [
            "<tr>"
            f"<td>{escape(f['name'])}</td>"
            f"<td class='text-end'>{f['amount']:.2f}</td>"
            f"<td>{escape(f['due_date'] or '-')}</td>"
            "</tr>"
            for f in fees
        ]
    )

    add_form = ""
    if g.user["role"] == "admin":
        add_form = f"""
        <h5 class="mt-4">Add Fee Item</h5>
        <form method="post" class="row g-2">
            <div class="col-md-4">
                <input name="name" class="form-control" placeholder="e.g. Tuition" required>
            </div>
            <div class="col-md-3">
                <input name="amount" class="form-control" placeholder="Amount" required>
            </div>
            <div class="col-md-3">
                <input type="date" name="due_date" class="form-control">
            </div>
            <div class="col-md-2">
                <button class="btn btn-success w-100">Add</button>
            </div>
        </form>
        """

    content = f"""
    <h2>Fees - {escape(cls['class_name'])} {escape(cls['section'])}</h2>

    <h4 class="mt-3">Fee Structure</h4>
    <table class="table table-sm table-bordered">
        <tr class="table-light"><th>Name</th><th class="text-end">Amount</th><th>Due Date</th></tr>
        {fee_rows or "<tr><td colspan='3' class='text-muted'>No fee items.</td></tr>"}
    </table>
    {add_form}

    <h4 class="mt-4">Students Fees Summary</h4>
    <table class="table table-bordered">
        <tr class="table-light">
            <th>Roll</th><th>Name</th>
            <th class="text-end">Total Due</th>
            <th class="text-end">Paid</th>
            <th class="text-end">Balance</th>
            <th>Actions</th>
        </tr>
        {student_rows or "<tr><td colspan='6' class='text-muted'>No students.</td></tr>"}
    </table>

    <a href="/fees" class="btn btn-secondary mt-3">Back</a>
    """
    return render_template("base.html", content=content)


@app.route("/fees/student/<int:student_id>", methods=["GET", "POST"])
@login_required
def fees_student(student_id):
    with get_db() as db:
        stu = db.execute(
            "SELECT s.*, c.class_name, c.section "
            "FROM students s JOIN classes c ON s.class_id=c.id WHERE s.id=?",
            (student_id,),
        ).fetchone()
        if stu is None:
            abort(404)

        fees = db.execute(
            "SELECT * FROM fee_structures WHERE class_id=? ORDER BY id",
            (stu["class_id"],),
        ).fetchall()

        if request.method == "POST":
            fee_id = int(request.form["fee_id"])
            amount_str = request.form["amount"].strip()
            mode = request.form["mode"].strip()
            try:
                paid_amount = float(amount_str)
            except ValueError:
                paid_amount = 0.0
            if paid_amount <= 0:
                flash("Payment amount must be positive.", "danger")
            else:
                db.execute(
                    "INSERT INTO fee_payments (student_id, fee_id, paid_amount, paid_on, mode) "
                    "VALUES (?,?,?,?,?)",
                    (
                        student_id,
                        fee_id,
                        paid_amount,
                        date.today().isoformat(),
                        mode or None,
                    ),
                )
                db.commit()
                flash("Payment recorded.", "s")
            return redirect(f"/fees/student/{student_id}")

        payments = db.execute(
            """
            SELECT fp.*, fs.name
            FROM fee_payments fp
            JOIN fee_structures fs ON fp.fee_id = fs.id
            WHERE fp.student_id=?
            ORDER BY fp.paid_on DESC, fp.id DESC
            """,
            (student_id,),
        ).fetchall()

        total_due = db.execute(
            "SELECT COALESCE(SUM(amount),0) as total FROM fee_structures WHERE class_id=?",
            (stu["class_id"],),
        ).fetchone()["total"]
        total_paid = db.execute(
            """
            SELECT COALESCE(SUM(fp.paid_amount),0) as paid
            FROM fee_payments fp
            JOIN fee_structures fs ON fp.fee_id = fs.id
            WHERE fp.student_id=? AND fs.class_id=?
            """,
            (student_id, stu["class_id"]),
        ).fetchone()["paid"]
        balance = total_due - total_paid

    fee_options = "".join(
        [
            f"<option value='{f['id']}'>{escape(f['name'])} ({f['amount']:.2f})</option>"
            for f in fees
        ]
    )

    payment_rows = "".join(
        [
            "<tr>"
            f"<td>{escape(p['name'])}</td>"
            f"<td class='text-end'>{p['paid_amount']:.2f}</td>"
            f"<td>{escape(p['paid_on'])}</td>"
            f"<td>{escape(p['mode'] or '')}</td>"
            "</tr>"
            for p in payments
        ]
    )

    add_payment_form = ""
    if fees:
        add_payment_form = f"""
        <h5 class="mt-4">Record Payment</h5>
        <form method="post" class="row g-2">
            <div class="col-md-4">
                <select name="fee_id" class="form-select" required>
                    {fee_options}
                </select>
            </div>
            <div class="col-md-3">
                <input name="amount" class="form-control" placeholder="Amount" required>
            </div>
            <div class="col-md-3">
                <input name="mode" class="form-control" placeholder="Mode (Cash/UPI/...)">
            </div>
            <div class="col-md-2">
                <button class="btn btn-success w-100">Add</button>
            </div>
        </form>
        """
    else:
        add_payment_form = "<p class='text-muted mt-3'>No fee items configured for this class.</p>"

    content = f"""
    <h2>Student Fees</h2>
    <p><b>{escape(stu['name'])}</b> ({escape(stu['roll_no'])}) -
       {escape(stu['class_name'])}-{escape(stu['section'])}</p>
    <p>Total Due: <b>{total_due:.2f}</b> |
       Paid: <b>{total_paid:.2f}</b> |
       Balance: <b>{balance:.2f}</b></p>

    {add_payment_form}

    <h5 class="mt-4">Payment History</h5>
    <table class="table table-sm table-bordered">
        <tr class="table-light">
            <th>Fee Item</th><th class="text-end">Amount</th><th>Date</th><th>Mode</th>
        </tr>
        {payment_rows or "<tr><td colspan='4' class='text-muted'>No payments yet.</td></tr>"}
    </table>

    <a href="/fees/class/{stu['class_id']}" class="btn btn-secondary mt-3">Back to Class Fees</a>
    """
    return render_template("base.html", content=content)


# ---------- SEARCH ----------

@app.route("/search")
@login_required
def search():
    q = request.args.get("q", "").strip()
    if not q:
        flash("Please enter name or roll number to search.", "danger")
        return redirect("/classes")

    like = f"%{q}%"
    with get_db() as db:
        results = db.execute(
            """
            SELECT s.id, s.name, s.roll_no, s.class_id, c.class_name, c.section
            FROM students s
            JOIN classes c ON s.class_id = c.id
            WHERE s.name LIKE ? OR s.roll_no LIKE ?
            ORDER BY c.class_name, c.section, s.roll_no
        """,
            (like, like),
        ).fetchall()

    if not results:
        content = f"""
        <h2>Search Results</h2>
        <p>No students found for "<b>{escape(q)}</b>".</p>
        <a href="/classes" class="btn btn-secondary mt-3">Back to Classes</a>
        """
    else:
        items = "".join(
            [
                "<li class='list-group-item d-flex justify-content-between align-items-center'>"
                f"<div><b>{escape(r['roll_no'])}</b> — {escape(r['name'])} "
                f"({escape(r['class_name'])}-{escape(r['section'])})</div>"
                f"<div>"
                f"<a href='/result/{r['id']}' class='btn btn-sm btn-info me-2'>Result</a>"
                f"<a href='/class/{r['class_id']}' class='btn btn-sm btn-secondary'>Class</a>"
                f"</div></li>"
                for r in results
            ]
        )
        content = f"""
        <h2>Search Results for "<span>{escape(q)}</span>"</h2>
        <ul class="list-group mt-3">
            {items}
        </ul>
        <a href="/classes" class="btn btn-secondary mt-3">Back to Classes</a>
        """

    return render_template("base.html", content=content)


@app.route("/howto")
def howto():
    return render_template('howto.html')


if __name__ == "__main__":
    print("\nSCHOOL SYSTEM UPGRADED: LOGIN, MULTI-EXAM, ATTENDANCE, FEES, CSV/PDF READY")
    print("Default admin: admin / admin123")
    print("Open: http://127.0.0.1:5000\n")
    app.run(port=5000, debug=True)
