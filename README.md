# Registrar / Polytechnic Student Record System

A local Python/Tkinter desktop workspace for student records: create, edit, delete, search and export a directory.

This is a new implementation of the student-record concept in Josiah Adeyemo's portfolio, not recovered code. No real student data is included.

## Run

Python 3.11+ with Tkinter is required on macOS or Linux. Tkinter is included with Python.org macOS installations; Linux may require the system python3-tk package. POSIX file locking is used; Windows is not currently supported.

```sh
python3 app.py
python3 -m unittest -v
python3 app.py --smoke-test
```

The smoke test opens the actual GUI and exercises save, edit, search and removal with temporary synthetic records. A graphical desktop is required.

## Data

The default file is data/students.json. Override it with --data /path/to/students.json or RECORDS_FILE.

Validated records include a unique student ID, name, email, department, study level, admission year and GPA (0-4). Writes are atomic, file-locked and revision-checked. A damaged file is reported, never silently reset; a stale window must reload before saving. CSV export guards against formula injection and cannot overwrite the JSON database.

Keep backups, restrict your OS account and disk access, and handle exports as personal data. This desktop application does not encrypt records, authenticate users or synchronize with an institution. It is a standalone local demo, not a certified student-information system.
