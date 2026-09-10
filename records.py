"""Validated student records with atomic JSON persistence and stale-write protection."""
import csv
import fcntl
import json
import math
import os
import re
import tempfile
from datetime import date
from pathlib import Path

DEPARTMENTS = ("Computer Science", "Business Administration", "Engineering", "Science Technology", "Mass Communication")
LEVELS = ("ND 1", "ND 2", "HND 1", "HND 2")


class RecordError(ValueError):
    pass


def validate(record):
    if not isinstance(record, dict):
        raise RecordError("A student record must be an object.")
    clean = {}
    for key in ("student_id", "name", "email", "department", "level"):
        value = record.get(key, "")
        if not isinstance(value, str) or not value.strip() or len(value.strip()) > 120:
            raise RecordError(f"Enter a valid {key.replace('_', ' ')}.")
        clean[key] = value.strip()
    clean["student_id"] = clean["student_id"].upper()
    if not re.fullmatch(r"[A-Z0-9][A-Z0-9/-]{1,29}", clean["student_id"]):
        raise RecordError("Student ID must be 2-30 letters, numbers, slashes or hyphens.")
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", clean["email"]):
        raise RecordError("Enter a valid email address.")
    if clean["department"] not in DEPARTMENTS or clean["level"] not in LEVELS:
        raise RecordError("Choose a valid department and level.")
    try:
        if isinstance(record.get("gpa"), bool):
            raise ValueError
        gpa = float(record.get("gpa", ""))
        if not math.isfinite(gpa) or not 0 <= gpa <= 4:
            raise ValueError
        clean["gpa"] = round(gpa, 2)
        year = str(record.get("year", ""))
        if not re.fullmatch(r"\d{4}", year) or not 1900 <= int(year) <= date.today().year + 1:
            raise ValueError
        clean["year"] = int(year)
    except (ValueError, TypeError):
        raise RecordError("Use a GPA from 0.00 to 4.00 and a valid four-digit admission year.") from None
    return clean


class RecordStore:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.revision, self._records = self._read()

    def _read(self):
        if not self.path.exists():
            return 0, []
        try:
            content = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(content, dict) or content.get("format") != 1:
                raise RecordError("Unsupported record-file format.")
            revision = content.get("revision")
            if isinstance(revision, bool) or not isinstance(revision, int) or revision < 0 or not isinstance(content.get("students"), list):
                raise RecordError("Invalid record-file structure.")
            records = [validate(record) for record in content["students"]]
            if len({record["student_id"] for record in records}) != len(records):
                raise RecordError("Duplicate IDs in the record file.")
            return revision, records
        except (json.JSONDecodeError, UnicodeDecodeError, TypeError, KeyError) as error:
            raise RecordError("The record file is damaged. Restore a backup; it has not been overwritten.") from error

    def all(self, query=""):
        query = query.casefold().strip()
        return [dict(record) for record in sorted(self._records, key=lambda row: row["name"].casefold())
                if query in " ".join(str(value) for value in record.values()).casefold()]

    def reload(self):
        self.revision, self._records = self._read()

    def _commit(self, records):
        temporary = None
        # Advisory process lock plus revision check prevents silent multi-window overwrites.
        with self.path.with_suffix(self.path.suffix + ".lock").open("a+b") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            try:
                revision, _current = self._read()
                if revision != self.revision:
                    raise RecordError("The file changed in another window. Reload records before saving.")
                fd, temporary = tempfile.mkstemp(dir=self.path.parent, prefix=".students-", suffix=".tmp")
                with os.fdopen(fd, "w", encoding="utf-8") as stream:
                    json.dump({"format": 1, "revision": revision + 1, "students": records}, stream, indent=2, ensure_ascii=False, allow_nan=False)
                    stream.write("\n")
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(temporary, self.path)
                self._records = records
                self.revision = revision + 1
            finally:
                if temporary and Path(temporary).exists():
                    Path(temporary).unlink()
                fcntl.flock(lock, fcntl.LOCK_UN)

    def save(self, values, original_id=None):
        record = validate(values)
        if original_id is not None and not any(item["student_id"] == original_id for item in self._records):
            raise RecordError("The selected student no longer exists.")
        if any(item["student_id"] == record["student_id"] and item["student_id"] != original_id for item in self._records):
            raise RecordError("That student ID is already registered.")
        records = [dict(item) for item in self._records if item["student_id"] != original_id]
        self._commit([*records, record])
        return dict(record)

    def delete(self, student_id):
        records = [dict(item) for item in self._records if item["student_id"] != student_id]
        if len(records) == len(self._records):
            raise RecordError("The selected student no longer exists.")
        self._commit(records)

    def export_csv(self, path):
        target = Path(path)
        if target.resolve() in {self.path.resolve(), self.path.with_suffix(self.path.suffix + ".lock").resolve()}:
            raise RecordError("Export to a different file, not the record database.")
        fields = ("student_id", "name", "email", "department", "level", "year", "gpa")
        with target.open("w", newline="", encoding="utf-8-sig") as stream:
            writer = csv.writer(stream)
            writer.writerow(fields)
            for record in self.all():
                row = []
                for field in fields:
                    value = str(record[field])
                    row.append("'" + value if re.match(r"^\s*[=+\-@]", value) else value)
                writer.writerow(row)
