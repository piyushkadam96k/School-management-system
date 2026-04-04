# 🎓 School ERP System

## 🚀 Pro Version Available

A small Flask-based School ERP app with core features for class management, students, exams, attendance, fees, and result exports.

---

## ✨ Highlights

- Login with roles (admin / teacher)
- Classes, students, and subjects
- Multi-exam support and weighted marks
- Attendance per class and per date
- Fee structures, payments, and student summaries
- Export: result PDF (ReportLab), class CSV exports
- Clean UI powered by Bootstrap and custom CSS in `static/css/styles.css`
- Uses SQLite (`school.db`) as the database (auto-initialized)

---

## 🧭 Quick Start (Windows PowerShell)

1) Create an isolated virtual environment (optional, but recommended):

```powershell
python -m venv venv
.\\venv\\Scripts\\Activate.ps1
```

2) Install dependencies:

```powershell
python -m pip install -r requirements.txt
```

3) Run the app:

```powershell
python app.py
```

Open http://127.0.0.1:5000 in your browser.

---

## 🔑 Default Admin

- Username: `admin`
- Password: `admin123`

> Note: The database will auto-create a default admin user if none exists on first run. Change the password for production.

---

## 🗂 File Structure

- `app.py` — Main Flask application and routes.
- `templates/base.html` — Common layout (header, navbar, flash messages and content area).
- `static/css/styles.css` — Styles extracted from inline HTML for easier customization.
- `school.db` — SQLite database (created on first run).
- `requirements.txt` — Project dependencies (Flask, Werkzeug, ReportLab).

---

## 🛠 Usage / Common Endpoints

- `/login` — Sign in (run as admin/teacher).
- `/logout` — Logout.
- `/` — Dashboard (requires login).
- `/classes` — View all classes.
- `/add_class` — (Admin) Add a class.
- `/class/<class_id>` — View class details (students, subjects, exams).
- `/add_student/<class_id>` — Add student to class.
- `/add_subject/<class_id>` — Add subject to class.
- `/exams/<class_id>` — Manage exams and weights for a class.
- `/enter_marks/<class_id>?exam_id=<exam_id>` — Enter marks for a selected exam.
- `/result/<student_id>` — View individual student's result (choose `exam_id` optionally).
- `/class/<class_id>/results` — View class results and export CSV via `/class/<class_id>/results/csv?exam_id=<exam_id>`.
- `/attendance/<class_id>` — Take attendance for a class for a specific date.
- `/fees` — Fees dashboard and management.

- `/howto` — In-app help page describing common workflows and usage (also see `HOWTO.md`).

---

## 🧩 Optional Features & Notes

- PDF generation for individual result card requires `reportlab` (already present in `requirements.txt`) — if missing, the app will show a flash message and suggest installation.
- By default, a dev `SECRET_KEY` is set in `app.py` (for sessions). Replace it with a secure value for production.
- SQLite DB path is `school.db` by default; change `DB_NAME` in `app.py` if you want a different file.

---

## ✅ What I changed (Templates & Static Files)

- Moved the shared base HTML into `templates/base.html` and made the routes render content via `render_template("base.html", content=content)`.
- Moved inline CSS into `static/css/styles.css` and included it from `base.html` via `url_for('static', filename='css/styles.css')`.

---

## 👩‍💻 Developer Tips

- To add a dedicated view template for a page, create a new template file (e.g., `templates/classes.html`) and replace `content` string with Jinja blocks in that file.
- To modularize DB helpers, you can move the `get_db()` and `init_db()` functions from `app.py` to a new `db_helpers.py` and import them back into `app.py` if you prefer a cleaner module separation.

---

## 🧪 Quick Troubleshooting

- If you run into DB issues, delete (or move) `school.db` to let the app reinitialize db tables and default admin.
- If PDF downloads produce errors, ensure `reportlab` installed. Install with:

```powershell
python -m pip install reportlab
```

---

## 📬 Contributions & Feedback

If you'd like the app further refactored (split each route into dedicated Jinja templates, move DB helpers to `db_helpers.py`, or convert to a package) — tell me what you'd like and I'll implement it.

---

Made with 💜 — enjoy managing your school! 🎒

---

---

## 🚀 Pro Version Available

If you need a more powerful solution, I offer a Pro version of this app with advanced features and additional integrations, such as:

- Role-based access control & advanced user management
- Scheduled reports, cron jobs & email notifications
- Import/export & backup/restore tools (CSV, XLSX, DB backups)
- Advanced analytics & dashboards
- API endpoints for integration with external systems
- Audit logs, security hardening, and deployment support
- Custom branding, multi-tenant support, and premium UI themes

---

## 🏷 License

All Rights Reserved © 2025 Amit Kadam. No part of this software may be copied, distributed, modified, or used in derivative works without written permission. For permission requests

See the full `LICENSE` file for details.
