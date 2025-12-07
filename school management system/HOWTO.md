# How to Use - School ERP System

This document covers the main workflows for using the app.

## 1. Login
- Open `http://127.0.0.1:5000/login` and login as the default admin (admin/admin123).
- For production, create a user or change admin password in the `users` table.

## 2. Dashboard
- The dashboard shows quick counts of Classes, Students, and Exams.
- Use the header navigation to go to Classes, Fees, or the Help page.

## 3. Manage Classes
- Go to `/classes` for a list of existing classes.
- Admins can add classes at `/add_class`.
- Click a class to view details and manage students and subjects.

## 4. Students & Subjects
- Add students to a class using the `+ Add Student` button. Fill name and roll number.
- Add class-specific subjects using `+ Add Subject`.

## 5. Exams and Entering Marks
- Create an exam from `/exams/{class_id}` for the selected class.
- Enter marks using `/enter_marks/{class_id}?exam_id={exam_id}` for each student.
- Marks are stored per student-per-subject-per-exam to support multiple exams.

## 6. Results and Exports (CSV & PDF)
- View individual results: `/result/{student_id}` (select `exam_id`)
- Class results: `/class/{class_id}/results?exam_id={exam_id}`.
- Download result PDF from `/result/{student_id}/pdf` (requires `reportlab` package).
- Export class results to CSV using the `Export CSV` button.

## 7. Attendance
- Take attendance per class and date at `/attendance/{class_id}`. Save the session.

## 8. Fees
- Use `/fees` for the fee dashboard.
- Manage class fee structure at `/fees/class/{class_id}`.
- Record student payments via the fees page.

## 9. Search
- Use the header search box or visit `/search?q=NAME_OR_ROLL`.

## 10. Permissions & Roles
- Admin users can manage classes, subjects, exams, and fees. Teachers are primarily limited to viewing and entering marks.

## Troubleshooting
- Delete `school.db` if you want to reset the data and reinitialize with the default admin.
- Ensure the `reportlab` package is installed for PDF generation:

```powershell
python -m pip install reportlab
```

## Author / Support
- Contact: amitkadam96k@gmail.com

---
