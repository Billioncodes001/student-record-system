"""Registrar: a local Tkinter student-record workspace for macOS and Linux."""
import argparse
import os
import tempfile
import tkinter as tk
from datetime import date
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from records import DEPARTMENTS, LEVELS, RecordError, RecordStore

PAPER = "#f4f1e9"
INK = "#263d45"
MUTED = "#64777b"
LINE = "#d4dcd9"
ACCENT = "#315f65"


class Registrar(ttk.Frame):
    def __init__(self, root, store):
        super().__init__(root, padding=28)
        self.root = root
        self.store = store
        self.selected_id = None
        self.pack(fill="both", expand=True)
        root.title("Registrar | Student Record System")
        root.geometry("1180x780")
        root.minsize(980, 740)
        root.configure(bg=PAPER)
        self.configure_style()
        header = ttk.Frame(self)
        header.pack(fill="x")
        ttk.Label(header, text="Registrar /", style="Brand.TLabel").pack(side="left")
        ttk.Label(header, text="BILLIONCODES  /  STUDENT AFFAIRS", style="Eyebrow.TLabel").pack(side="right")
        ttk.Separator(self).pack(fill="x", pady=(14, 16))
        ttk.Label(self, text="A clear record.\nA brighter beginning.", style="Hero.TLabel").pack(anchor="w")
        ttk.Label(self, text="One thoughtful home for the people shaping tomorrow.", style="Muted.TLabel").pack(anchor="w", pady=(8, 14))
        self.summary = tk.StringVar()
        ttk.Label(self, textvariable=self.summary, style="Summary.TLabel").pack(anchor="w", pady=(0, 16))
        body = ttk.Frame(self)
        body.pack(fill="both", expand=True)
        form = ttk.Frame(body, style="Panel.TFrame", padding=20)
        form.pack(side="left", fill="y", padx=(0, 24))
        self.form_title = tk.StringVar(value="Start a new chapter.")
        ttk.Label(form, textvariable=self.form_title, style="PanelTitle.TLabel").pack(anchor="w", pady=(0, 14))
        self.values = {}
        fields = ttk.Frame(form, style="Panel.TFrame")
        fields.pack(fill="both", expand=True)
        fields.columnconfigure(0, weight=1)
        fields.columnconfigure(1, weight=1)
        for key, label, choices, row, column, span in [
            ("student_id", "Student ID", None, 0, 0, 1), ("level", "Study level", LEVELS, 0, 1, 1),
            ("name", "Full name", None, 1, 0, 2), ("email", "Email address", None, 2, 0, 2),
            ("department", "Department", DEPARTMENTS, 3, 0, 2),
            ("year", "Admission year", None, 4, 0, 1), ("gpa", "GPA / 4.00", None, 4, 1, 1),
        ]:
            group = ttk.Frame(fields, style="Panel.TFrame")
            group.grid(row=row, column=column, columnspan=span, sticky="ew", padx=(0, 8 if span == 1 and column == 0 else 0), pady=(0, 8))
            ttk.Label(group, text=label, style="PanelLabel.TLabel").pack(anchor="w", pady=(0, 4))
            variable = tk.StringVar()
            self.values[key] = variable
            width = 28 if span == 2 else 12
            widget = ttk.Combobox(group, textvariable=variable, values=choices, state="readonly", width=width) if choices else ttk.Entry(group, textvariable=variable, width=width)
            widget.pack(fill="x")
        self.save_button = ttk.Button(form, text="Save student record  →", command=self.save, style="Primary.TButton")
        self.save_button.pack(fill="x", pady=(8, 6))
        self.clear_button = ttk.Button(form, text="Clear / new student", command=self.clear)
        self.clear_button.pack(fill="x")
        library = ttk.Frame(body)
        library.pack(side="left", fill="both", expand=True)
        toolbar = ttk.Frame(library)
        toolbar.pack(fill="x", pady=(0, 12))
        ttk.Label(toolbar, text="Student directory", style="Section.TLabel").pack(side="left")
        ttk.Button(toolbar, text="Export CSV", command=self.export).pack(side="right")
        ttk.Button(toolbar, text="Reload", command=self.reload).pack(side="right", padx=6)
        ttk.Label(library, text="Search names, IDs, departments or levels", style="Muted.TLabel").pack(anchor="w", pady=(0, 6))
        self.query = tk.StringVar()
        ttk.Entry(library, textvariable=self.query).pack(fill="x", pady=(0, 14))
        self.query.trace_add("write", lambda *_: self.refresh())
        table = ttk.Frame(library)
        table.pack(fill="both", expand=True)
        columns = ("student_id", "name", "department", "level", "gpa")
        self.tree = ttk.Treeview(table, columns=columns, show="headings", selectmode="browse", height=5)
        for key, title, width in [("student_id", "STUDENT ID", 110), ("name", "NAME", 170), ("department", "DEPARTMENT", 155), ("level", "LEVEL", 65), ("gpa", "GPA", 50)]:
            self.tree.heading(key, text=title)
            self.tree.column(key, width=width, minwidth=50, anchor="w")
        vertical = ttk.Scrollbar(table, orient="vertical", command=self.tree.yview)
        horizontal = ttk.Scrollbar(table, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal.grid(row=1, column=0, sticky="ew")
        table.rowconfigure(0, weight=1)
        table.columnconfigure(0, weight=1)
        self.tree.bind("<<TreeviewSelect>>", self.select)
        bottom = ttk.Frame(library)
        bottom.pack(fill="x", pady=(12, 0))
        ttk.Label(bottom, text="Select a student to edit their record.", style="Muted.TLabel").pack(side="left")
        self.delete_button = ttk.Button(bottom, text="Delete selected", command=self.delete, state="disabled")
        self.delete_button.pack(side="right")
        self.status = tk.StringVar(value="Records stay on this device. Back up your data file regularly.")
        self.status_label = ttk.Label(self, textvariable=self.status, style="Muted.TLabel", wraplength=1000)
        self.status_label.pack(anchor="w", pady=(18, 0))
        self.clear()
        self.refresh()

    def configure_style(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure(".", background=PAPER, foreground=INK, font=("Trebuchet MS", 11))
        style.configure("TFrame", background=PAPER)
        style.configure("TLabel", background=PAPER)
        style.configure("Brand.TLabel", font=("Trebuchet MS", 24, "bold"))
        style.configure("Eyebrow.TLabel", font=("Menlo", 9), foreground=MUTED)
        style.configure("Hero.TLabel", font=("Georgia", 28), foreground=INK)
        style.configure("Muted.TLabel", foreground=MUTED, font=("Trebuchet MS", 10))
        style.configure("Summary.TLabel", font=("Trebuchet MS", 12, "bold"), foreground=ACCENT)
        style.configure("Section.TLabel", font=("Trebuchet MS", 17, "bold"))
        style.configure("Panel.TFrame", background="#fffdf8")
        style.configure("PanelTitle.TLabel", background="#fffdf8", font=("Georgia", 19))
        style.configure("PanelLabel.TLabel", background="#fffdf8", font=("Trebuchet MS", 10))
        style.configure("TEntry", fieldbackground="#fffdf8", padding=5, bordercolor=LINE)
        style.configure("TCombobox", padding=5, fieldbackground="#fffdf8")
        style.configure("TButton", padding=(12, 8), borderwidth=1, bordercolor=LINE, background=PAPER)
        style.configure("Primary.TButton", background=ACCENT, foreground="#ffffff")
        style.map("Primary.TButton", background=[("active", "#244c52")], foreground=[("active", "#ffffff")])
        style.configure("Treeview", background="#fffdf8", fieldbackground="#fffdf8", rowheight=39, bordercolor=LINE)
        style.configure("Treeview.Heading", background="#e5ece7", foreground=INK, font=("Trebuchet MS", 9, "bold"), padding=10)
        style.map("Treeview", background=[("selected", ACCENT)], foreground=[("selected", "#ffffff")])

    def refresh(self):
        for row in self.tree.get_children():
            self.tree.delete(row)
        records = self.store.all(self.query.get())
        for row in records:
            self.tree.insert("", "end", iid=row["student_id"], values=(row["student_id"], row["name"], row["department"], row["level"], f'{row["gpa"]:.2f}'))
        all_records = self.store.all()
        departments = len({row["department"] for row in all_records})
        self.summary.set(f"{len(all_records)} students registered     /     {departments} departments     /     {len(records)} matching your search")
        self.delete_button.configure(state="disabled")

    def clear(self):
        self.selected_id = None
        self.form_title.set("Start a new chapter.")
        for key, variable in self.values.items():
            variable.set({"department": DEPARTMENTS[0], "level": LEVELS[0], "year": str(date.today().year), "gpa": "0.00"}.get(key, ""))
        self.delete_button.configure(state="disabled")
        if self.tree.selection():
            self.tree.selection_remove(*self.tree.selection())

    def select(self, _event=None):
        selection = self.tree.selection()
        if not selection:
            self.delete_button.configure(state="disabled")
            return
        record = next((row for row in self.store.all() if row["student_id"] == selection[0]), None)
        if not record:
            return
        self.selected_id = record["student_id"]
        for key, variable in self.values.items():
            variable.set(str(record[key]))
        self.form_title.set("Refine their record.")
        self.delete_button.configure(state="normal")

    def save(self):
        try:
            saved = self.store.save({key: value.get() for key, value in self.values.items()}, self.selected_id)
            self.clear()
            self.refresh()
            self.status.set(f'Saved {saved["name"]}. Your record file is up to date.')
        except (RecordError, OSError) as error:
            messagebox.showerror("Could not save record", str(error), parent=self.root)

    def delete(self):
        if self.selected_id and messagebox.askyesno("Delete student?", "Permanently remove this student record?", parent=self.root):
            try:
                self.store.delete(self.selected_id)
                self.clear()
                self.refresh()
                self.status.set("Student record removed.")
            except (RecordError, OSError) as error:
                messagebox.showerror("Could not delete record", str(error), parent=self.root)

    def reload(self):
        try:
            self.store.reload()
            self.clear()
            self.refresh()
            self.status.set("Latest records loaded from disk.")
        except (RecordError, OSError) as error:
            messagebox.showerror("Could not load records", str(error), parent=self.root)

    def export(self):
        path = filedialog.asksaveasfilename(parent=self.root, title="Export student directory", defaultextension=".csv", filetypes=[("CSV spreadsheet", "*.csv")])
        if path:
            try:
                self.store.export_csv(path)
                self.status.set(f"Exported {len(self.store.all())} students to {path}.")
            except (RecordError, OSError) as error:
                messagebox.showerror("Could not export records", str(error), parent=self.root)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", default=os.getenv("RECORDS_FILE", str(Path(__file__).parent / "data/students.json")))
    parser.add_argument("--smoke-test", action="store_true", help="Exercise the actual GUI using temporary synthetic data.")
    args = parser.parse_args()
    root = tk.Tk()
    try:
        if args.smoke_test:
            with tempfile.TemporaryDirectory() as directory:
                app = Registrar(root, RecordStore(Path(directory) / "students.json"))
                sample = {"student_id": "TEST/001", "name": "Ada Example", "email": "ada@example.com", "department": DEPARTMENTS[0], "level": LEVELS[0], "year": date.today().year, "gpa": 3.75}
                for key, value in sample.items():
                    app.values[key].set(str(value))
                app.save()
                root.update()
                assert app.clear_button.winfo_rooty() + app.clear_button.winfo_height() < root.winfo_rooty() + root.winfo_height()
                assert app.delete_button.winfo_ismapped()
                assert app.status_label.winfo_ismapped()
                assert app.status_label.winfo_rooty() + app.status_label.winfo_height() <= root.winfo_rooty() + root.winfo_height()
                assert len(app.tree.get_children()) == 1
                app.tree.selection_set("TEST/001")
                app.select()
                assert app.values["name"].get() == "Ada Example"
                app.values["gpa"].set("3.90")
                app.save()
                assert app.store.all()[0]["gpa"] == 3.9
                app.query.set("missing")
                root.update()
                assert not app.tree.get_children()
                app.query.set("")
                app.store.delete("TEST/001")
                app.refresh()
                assert not app.tree.get_children()
                print("PASS: actual Tkinter window, save, selection, edit, search and delete refresh.")
            root.destroy()
            return
        Registrar(root, RecordStore(args.data))
        root.mainloop()
    except (RecordError, OSError) as error:
        messagebox.showerror("Records could not be opened", str(error), parent=root)
        root.destroy()
        raise SystemExit(1) from error


if __name__ == "__main__":
    main()
