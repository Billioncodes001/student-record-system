import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from records import RecordError, RecordStore, validate

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


if __name__ == "__main__":
    unittest.main()
