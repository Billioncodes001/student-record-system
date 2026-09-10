"""Open the real desktop UI with disposable, fictional screenshot data."""
import tempfile
import tkinter as tk
from pathlib import Path

from app import Registrar
from records import DEPARTMENTS, LEVELS, RecordStore


def main():
    with tempfile.TemporaryDirectory(prefix="registrar-preview-") as directory:
        store = RecordStore(Path(directory) / "students.json")
        names = ("Ada Example", "Tunde Sample", "Mina Demo", "Daniel Example",
                 "Zara Sample", "Emeka Demo", "Ruth Example", "Tomi Sample")
        for index, name in enumerate(names):
            store.save({
                "student_id": f"DEMO/2025/{index + 1:03d}",
                "name": name,
                "email": f"student{index + 1}@example.com",
                "department": DEPARTMENTS[index % len(DEPARTMENTS)],
                "level": LEVELS[index % len(LEVELS)],
                "year": 2025,
                "gpa": round(3.1 + index / 10, 2),
            })
        root = tk.Tk()
        app = Registrar(root, store)
        app.status.set("SCREENSHOT DEMO / All eight records are fictional. Temporary data is removed when this window closes.")
        app.tree.selection_set("DEMO/2025/001")
        app.select()
        root.lift()
        root.mainloop()


if __name__ == "__main__":
    main()
