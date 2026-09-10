import json
import csv
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from records import RecordError, RecordStore, validate, CSV_FIELDS

SAMPLE = {"student_id":"nd/001","name":"Ada Example","email":"ada@example.com","department":"Computer Science","level":"ND 1","gpa":3.75,"year":2026}


class RecordTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "students.json"
        self.store = RecordStore(self.path)

    def tearDown(self):
        self.temp.cleanup()

    def test_crud_persistence_and_search(self):
        record = self.store.save(SAMPLE)
        self.assertEqual(record["student_id"], "ND/001")
        self.assertEqual(len(RecordStore(self.path).all("ada")), 1)
        self.assertEqual(self.store.all("missing"), [])
        self.store.save({**SAMPLE, "gpa": 4, "student_id":"ND/002"}, "ND/001")
        self.assertEqual(self.store.all()[0]["gpa"], 4)
        self.store.delete("ND/002")
        self.assertEqual(RecordStore(self.path).all(), [])

    def test_duplicates_and_invalid_fields(self):
        self.store.save(SAMPLE)
        with self.assertRaises(RecordError):
            self.store.save(SAMPLE)
        for key, value in [("student_id","!"),("name",""),("email","invalid"),("department","Unknown"),("level","Unknown"),("gpa",float("nan")),("gpa",True),("gpa",4.1),("year","bad"),("year",1800)]:
            with self.subTest(key=key, value=value), self.assertRaises(RecordError):
                validate({**SAMPLE,key:value})

    def test_corrupt_input_is_never_overwritten(self):
        self.path.write_text("{broken", encoding="utf-8")
        with self.assertRaises(RecordError):
            RecordStore(self.path)
        self.assertEqual(self.path.read_text(), "{broken")
        self.path.write_text(json.dumps({"format":1,"revision":1,"students":[SAMPLE,SAMPLE]}))
        with self.assertRaises(RecordError):
            RecordStore(self.path)

    def test_stale_writer_and_reload(self):
        other = RecordStore(self.path)
        self.store.save(SAMPLE)
        with self.assertRaisesRegex(RecordError, "another window"):
            other.save({**SAMPLE, "student_id":"ND/002"})
        other.reload()
        other.save({**SAMPLE, "student_id":"ND/002"})
        self.assertEqual(len(RecordStore(self.path).all()), 2)

    def test_failed_atomic_replace_preserves_memory_and_disk(self):
        self.store.save(SAMPLE)
        before = self.path.read_bytes()
        with patch("records.os.replace", side_effect=OSError("disk failure")):
            with self.assertRaises(OSError):
                self.store.save({**SAMPLE, "gpa":1}, "ND/001")
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(self.store.all()[0]["gpa"], 3.75)
        self.assertEqual(list(self.path.parent.glob("*.tmp")), [])

    def test_csv_safety_and_database_protection(self):
        self.store.save({**SAMPLE, "name":"=DANGEROUS()"})
        output = self.path.parent / "export.csv"
        self.store.export_csv(output)
        self.assertIn("'=DANGEROUS()", output.read_text(encoding="utf-8-sig"))
        with self.assertRaises(RecordError):
            self.store.export_csv(self.path)

    def csv_file(self, records, headers=CSV_FIELDS):
        path = self.path.parent / "incoming.csv"
        with path.open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.writer(stream)
            writer.writerow(headers)
            for record in records:
                writer.writerow([record.get(field, "") for field in headers])
        return path

    def test_import_preview_atomic_commit_and_idempotent_reimport(self):
        path = self.csv_file([SAMPLE, {**SAMPLE, "student_id": "ND/002", "name": "Tunde Example"}])
        preview = self.store.preview_import(path)
        self.assertEqual((preview.additions, preview.unchanged, preview.errors), (2, 0, ()))
        self.assertFalse(self.path.exists())
        self.assertEqual(self.store.commit_import(preview), 2)
        self.assertEqual(len(RecordStore(self.path).all()), 2)
        next_preview = self.store.preview_import(path)
        revision = self.store.revision
        self.assertEqual((next_preview.additions, next_preview.unchanged), (0, 2))
        self.assertEqual(self.store.commit_import(next_preview), 0)
        self.assertEqual(self.store.revision, revision)

    def test_import_errors_never_write_partial_records(self):
        self.store.save(SAMPLE)
        before = self.path.read_bytes()
        path = self.csv_file([{**SAMPLE, "student_id": "ND/002"}, {**SAMPLE, "name": "Conflicting name"}, {**SAMPLE, "student_id": "ND/003", "gpa": "bad"}])
        preview = self.store.preview_import(path)
        self.assertEqual(len(preview.errors), 2)
        self.assertIn("Row 3", preview.errors[0])
        with self.assertRaises(RecordError):
            self.store.commit_import(preview)
        self.assertEqual(self.path.read_bytes(), before)

    def test_import_rejects_duplicate_ids_and_bad_headers(self):
        preview = self.store.preview_import(self.csv_file([SAMPLE, SAMPLE]))
        self.assertIn("Duplicate", preview.errors[0])
        for headers in [CSV_FIELDS[:-1], (*CSV_FIELDS[:-1], "name"), (*CSV_FIELDS, "extra")]:
            with self.subTest(headers=headers), self.assertRaises(RecordError):
                self.store.preview_import(self.csv_file([SAMPLE], headers))

    def test_import_snapshot_is_independent_of_subsequent_file_edits(self):
        path = self.csv_file([SAMPLE])
        preview = self.store.preview_import(path)
        path.write_text("invalid file after preview", encoding="utf-8")
        self.assertEqual(self.store.commit_import(preview), 1)

    def test_import_rejects_stale_preview_and_preserves_data_on_disk_failure(self):
        preview = self.store.preview_import(self.csv_file([SAMPLE]))
        other = RecordStore(self.path)
        other.save({**SAMPLE, "student_id": "ND/099"})
        with self.assertRaises(RecordError):
            self.store.commit_import(preview)
        self.store.reload()
        preview = self.store.preview_import(self.csv_file([SAMPLE]))
        before = self.path.read_bytes()
        with patch("records.os.replace", side_effect=OSError("disk full")), self.assertRaises(OSError):
            self.store.commit_import(preview)
        self.assertEqual(self.path.read_bytes(), before)
        self.store.save({**SAMPLE, "student_id": "ND/098"})
        with self.assertRaisesRegex(RecordError, "after this preview"):
            self.store.commit_import(preview)

    def test_import_size_row_encoding_and_empty_limits(self):
        path = self.csv_file([])
        self.assertTrue(self.store.preview_import(path).errors)
        path.write_bytes(b"\xff\xfe")
        with self.assertRaisesRegex(RecordError, "UTF-8"):
            self.store.preview_import(path)
        path.write_bytes(b"x" * (2 * 1024 * 1024 + 1))
        with self.assertRaisesRegex(RecordError, "2 MiB"):
            self.store.preview_import(path)
        path = self.csv_file([{**SAMPLE, "student_id": f"ND/{index}"} for index in range(2001)])
        with self.assertRaisesRegex(RecordError, "2,000"):
            self.store.preview_import(path)


if __name__ == "__main__":
    unittest.main()
