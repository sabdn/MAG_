import pathlib
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

import main as core


BASE = pathlib.Path(__file__).resolve().parent
INPUT_DIR = BASE / "INPUT"
OUTPUT_DIR = BASE / "OUTPUT"


def list_input_txt():
    if not INPUT_DIR.exists():
        return []
    return sorted([p for p in INPUT_DIR.iterdir() if p.is_file() and p.suffix.lower() == ".txt"])


def run_on_file(path: pathlib.Path) -> pathlib.Path:
    OUTPUT_DIR.mkdir(exist_ok=True)
    return core.process_file(path, OUTPUT_DIR)


def run_on_text(text: str) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if len(lines) < 4:
        raise ValueError("Not enough data (need at least 4 non-empty lines)")
    curve, tasks = core.parse_curve(lines)
    results = [core.handle_task(curve, task) for task in tasks]
    return "\n".join(results)


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("ECC Calculator")
        self.geometry("980x680")

        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=10, pady=10)

        self.tab_files = ttk.Frame(nb)
        self.tab_custom = ttk.Frame(nb)

        nb.add(self.tab_files, text="Files in INPUT")
        nb.add(self.tab_custom, text="Custom input")

        self._build_files_tab()
        self._build_custom_tab()

    def _build_files_tab(self):
        left = ttk.Frame(self.tab_files)
        left.pack(side="left", fill="y", padx=(0, 10))

        right = ttk.Frame(self.tab_files)
        right.pack(side="left", fill="both", expand=True)

        ttk.Label(left, text="INPUT/*.txt").pack(anchor="w")

        self.files_list = tk.Listbox(left, width=40, height=25)
        self.files_list.pack(fill="y", expand=False)

        btns = ttk.Frame(left)
        btns.pack(fill="x", pady=8)

        ttk.Button(btns, text="Refresh", command=self._refresh_files).pack(side="left")
        ttk.Button(btns, text="Open INPUT folder", command=self._open_input_folder).pack(side="left", padx=6)
        ttk.Button(btns, text="Run selected", command=self._run_selected_file).pack(side="left")

        ttk.Label(right, text="File content").pack(anchor="w")
        self.file_text = tk.Text(right, wrap="none", height=18)
        self.file_text.pack(fill="both", expand=False)

        ttk.Label(right, text="Output (will be written to OUTPUT/...)").pack(anchor="w", pady=(10, 0))
        self.file_out = tk.Text(right, wrap="none")
        self.file_out.pack(fill="both", expand=True)

        self._refresh_files()
        self.files_list.bind("<<ListboxSelect>>", lambda e: self._preview_selected())

    def _build_custom_tab(self):
        top = ttk.Frame(self.tab_custom)
        top.pack(fill="both", expand=True)

        ttk.Label(top, text="Paste full input file content here:").pack(anchor="w")
        self.custom_in = tk.Text(top, wrap="none", height=18)
        self.custom_in.pack(fill="both", expand=False)

        btns = ttk.Frame(top)
        btns.pack(fill="x", pady=8)

        ttk.Button(btns, text="Run", command=self._run_custom).pack(side="left")
        ttk.Button(btns, text="Load from file...", command=self._load_custom_from_file).pack(side="left", padx=6)
        ttk.Button(btns, text="Save output as...", command=self._save_custom_output).pack(side="left", padx=6)

        ttk.Label(top, text="Output:").pack(anchor="w", pady=(10, 0))
        self.custom_out = tk.Text(top, wrap="none")
        self.custom_out.pack(fill="both", expand=True)

    def _refresh_files(self):
        self.files_list.delete(0, tk.END)
        self._files = list_input_txt()
        for p in self._files:
            self.files_list.insert(tk.END, p.name)
        self.file_text.delete("1.0", tk.END)
        self.file_out.delete("1.0", tk.END)

    def _open_input_folder(self):
        messagebox.showinfo("INPUT folder", str(INPUT_DIR))

    def _get_selected_path(self):
        sel = self.files_list.curselection()
        if not sel:
            return None
        return self._files[sel[0]]

    def _preview_selected(self):
        p = self._get_selected_path()
        if not p:
            return
        self.file_text.delete("1.0", tk.END)
        self.file_text.insert(tk.END, p.read_text(encoding="utf-8", errors="replace"))

    def _run_selected_file(self):
        p = self._get_selected_path()
        if not p:
            messagebox.showwarning("No file", "Select a .txt file in the list first.")
            return
        try:
            out_path = run_on_file(p)
            self.file_out.delete("1.0", tk.END)
            self.file_out.insert(tk.END, out_path.read_text(encoding="utf-8", errors="replace"))
            messagebox.showinfo("Done", f"Saved: {out_path}")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _run_custom(self):
        text = self.custom_in.get("1.0", tk.END)
        try:
            out = run_on_text(text)
            self.custom_out.delete("1.0", tk.END)
            self.custom_out.insert(tk.END, out)
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _load_custom_from_file(self):
        path = filedialog.askopenfilename(filetypes=[("Text files", "*.txt"), ("All files", "*.*")])
        if not path:
            return
        p = pathlib.Path(path)
        self.custom_in.delete("1.0", tk.END)
        self.custom_in.insert(tk.END, p.read_text(encoding="utf-8", errors="replace"))

    def _save_custom_output(self):
        out_text = self.custom_out.get("1.0", tk.END).strip()
        if not out_text:
            messagebox.showwarning("Empty", "No output to save.")
            return
        path = filedialog.asksaveasfilename(defaultextension=".txt", filetypes=[("Text files", "*.txt")])
        if not path:
            return
        pathlib.Path(path).write_text(out_text, encoding="utf-8")
        messagebox.showinfo("Saved", path)


if __name__ == "__main__":
    App().mainloop()
