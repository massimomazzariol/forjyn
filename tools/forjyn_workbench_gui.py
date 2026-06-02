import argparse
import os
import queue
import subprocess
import sys
import threading
from pathlib import Path
from tkinter import END, DISABLED, NORMAL, StringVar, Tk, filedialog, messagebox
from tkinter import ttk
from tkinter.scrolledtext import ScrolledText


ROOT = Path(__file__).resolve().parents[1]
WORKBENCH = ROOT / "ForJyn_Workbench"
INPUTS_DIR = WORKBENCH / "inputs"
REFERENCES_DIR = WORKBENCH / "references"
OUTPUTS_DIR = WORKBENCH / "outputs"
TECHNICAL_DIR = WORKBENCH / "technical"
BACKEND = ROOT / "tools" / "forjyn_workbench.py"

IMAGE_FILETYPES = [
    ("Image files", "*.jpg *.jpeg *.png *.webp"),
    ("JPEG", "*.jpg *.jpeg"),
    ("PNG", "*.png"),
    ("WebP", "*.webp"),
    ("All files", "*.*"),
]

QUALITY_MODES = {
    "Quick test - 200 steps": 200,
    "Normal - 800 steps": 800,
    "Better quality - 2000 steps": 2000,
}


def ensure_workbench_dirs():
    for path in [WORKBENCH, INPUTS_DIR, REFERENCES_DIR, OUTPUTS_DIR, TECHNICAL_DIR]:
        path.mkdir(parents=True, exist_ok=True)


def open_folder(path):
    path = Path(path)
    if os.name == "nt":
        os.startfile(str(path))
    else:
        subprocess.Popen(["xdg-open", str(path)])


class ForJynWorkbenchApp:
    def __init__(self, root):
        self.root = root
        self.root.title("ForJyn Workbench")
        self.root.minsize(780, 620)

        ensure_workbench_dirs()

        self.content_path = StringVar()
        self.quality = StringVar(value="Normal - 800 steps")
        self.style_paths = []
        self.completed_dirs = []
        self.last_output_dir = None
        self.running = False
        self.log_queue = queue.Queue()

        self._build_ui()
        self._update_start_state()
        self._poll_log_queue()

    def _build_ui(self):
        frame = ttk.Frame(self.root, padding=16)
        frame.pack(fill="both", expand=True)
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(5, weight=1)

        title = ttk.Label(frame, text="ForJyn Workbench", font=("Segoe UI", 16, "bold"))
        title.grid(row=0, column=0, sticky="w", pady=(0, 12))

        content_box = ttk.LabelFrame(frame, text="Content photo", padding=10)
        content_box.grid(row=1, column=0, sticky="ew", pady=6)
        content_box.columnconfigure(0, weight=1)
        self.content_entry = ttk.Entry(content_box, textvariable=self.content_path, state="readonly")
        self.content_entry.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self.choose_content_button = ttk.Button(content_box, text="Choose content photo", command=self.choose_content)
        self.choose_content_button.grid(row=0, column=1)

        style_box = ttk.LabelFrame(frame, text="Style/reference images", padding=10)
        style_box.grid(row=2, column=0, sticky="nsew", pady=6)
        style_box.columnconfigure(0, weight=1)
        self.style_list = ttk.Treeview(style_box, columns=("path",), show="headings", height=5)
        self.style_list.heading("path", text="Selected files")
        self.style_list.column("path", stretch=True)
        self.style_list.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        self.choose_styles_button = ttk.Button(style_box, text="Choose style/reference images", command=self.choose_styles)
        self.choose_styles_button.grid(row=0, column=1, sticky="n")

        controls = ttk.Frame(frame)
        controls.grid(row=3, column=0, sticky="ew", pady=10)
        controls.columnconfigure(1, weight=1)
        ttk.Label(controls, text="Quality").grid(row=0, column=0, sticky="w", padx=(0, 8))
        self.quality_menu = ttk.Combobox(
            controls,
            textvariable=self.quality,
            values=list(QUALITY_MODES.keys()),
            state="readonly",
            width=28,
        )
        self.quality_menu.grid(row=0, column=1, sticky="w")
        self.start_button = ttk.Button(controls, text="Start", command=self.start_jobs)
        self.start_button.grid(row=0, column=2, padx=(12, 0))

        progress_box = ttk.Frame(frame)
        progress_box.grid(row=4, column=0, sticky="ew", pady=(0, 8))
        progress_box.columnconfigure(0, weight=1)
        self.progress = ttk.Progressbar(progress_box, mode="determinate")
        self.progress.grid(row=0, column=0, sticky="ew")

        self.log = ScrolledText(frame, height=16, wrap="word")
        self.log.grid(row=5, column=0, sticky="nsew", pady=6)
        self.log.configure(state=DISABLED)

        footer = ttk.Frame(frame)
        footer.grid(row=6, column=0, sticky="ew", pady=(10, 0))
        self.open_output_button = ttk.Button(footer, text="Open output folder", command=self.open_output, state=DISABLED)
        self.open_output_button.pack(side="left")
        self.open_workbench_button = ttk.Button(footer, text="Open workbench folder", command=lambda: open_folder(WORKBENCH))
        self.open_workbench_button.pack(side="left", padx=(8, 0))

    def choose_content(self):
        path = filedialog.askopenfilename(
            title="Choose content photo",
            initialdir=str(INPUTS_DIR),
            filetypes=IMAGE_FILETYPES,
        )
        if path:
            self.content_path.set(path)
            self._update_start_state()

    def choose_styles(self):
        paths = filedialog.askopenfilenames(
            title="Choose style/reference images",
            initialdir=str(REFERENCES_DIR),
            filetypes=IMAGE_FILETYPES,
        )
        if paths:
            self.style_paths = list(paths)
            self.style_list.delete(*self.style_list.get_children())
            for path in self.style_paths:
                self.style_list.insert("", END, values=(path,))
            self._update_start_state()

    def _update_start_state(self):
        can_start = bool(self.content_path.get()) and bool(self.style_paths) and not self.running
        self.start_button.configure(state=NORMAL if can_start else DISABLED)

    def _set_inputs_state(self, state):
        self.choose_content_button.configure(state=state)
        self.choose_styles_button.configure(state=state)
        self.quality_menu.configure(state="readonly" if state == NORMAL else DISABLED)
        self.open_workbench_button.configure(state=state)

    def _append_log(self, text):
        self.log.configure(state=NORMAL)
        self.log.insert(END, text)
        self.log.see(END)
        self.log.configure(state=DISABLED)

    def _poll_log_queue(self):
        try:
            while True:
                kind, payload = self.log_queue.get_nowait()
                if kind == "log":
                    self._append_log(payload)
                elif kind == "output_dir":
                    self.last_output_dir = payload
                    self.completed_dirs.append(payload)
                    self.open_output_button.configure(state=NORMAL)
                elif kind == "progress":
                    self.progress.configure(value=payload)
                elif kind == "done":
                    self.running = False
                    self._set_inputs_state(NORMAL)
                    self._update_start_state()
                    self._append_log("\nAll selected jobs finished.\n")
        except queue.Empty:
            pass
        self.root.after(100, self._poll_log_queue)

    def start_jobs(self):
        if self.running:
            return
        if not self.content_path.get() or not self.style_paths:
            messagebox.showerror("Missing files", "Choose one content photo and at least one style/reference image.")
            return
        self.running = True
        self.completed_dirs = []
        self.last_output_dir = None
        self.progress.configure(maximum=len(self.style_paths), value=0)
        self.open_output_button.configure(state=DISABLED)
        self._set_inputs_state(DISABLED)
        self._update_start_state()
        self._append_log("Starting ForJyn jobs...\n")
        thread = threading.Thread(target=self._run_jobs_worker, daemon=True)
        thread.start()

    def _run_jobs_worker(self):
        steps = QUALITY_MODES[self.quality.get()]
        for index, style_path in enumerate(self.style_paths, start=1):
            style_name = Path(style_path).stem
            command = [
                sys.executable,
                str(BACKEND),
                "run-job",
                "--content",
                self.content_path.get(),
                "--style",
                style_path,
                "--name",
                style_name,
                "--steps",
                str(steps),
                "--output-root",
                str(OUTPUTS_DIR),
            ]
            self.log_queue.put(("log", f"\n[{index}/{len(self.style_paths)}] {style_name}\n"))
            self.log_queue.put(("log", subprocess.list2cmdline(command) + "\n"))
            try:
                process = subprocess.Popen(
                    command,
                    cwd=str(ROOT),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    encoding="utf-8",
                    errors="replace",
                )
                assert process.stdout is not None
                for line in process.stdout:
                    self.log_queue.put(("log", line))
                    if line.startswith("FORJYN_OUTPUT_DIR="):
                        self.log_queue.put(("output_dir", line.split("=", 1)[1].strip()))
                returncode = process.wait()
                if returncode != 0:
                    self.log_queue.put(("log", f"Job failed with exit code {returncode}.\n"))
                else:
                    self.log_queue.put(("log", "Job completed.\n"))
            except Exception as exc:
                self.log_queue.put(("log", f"Job failed: {exc}\n"))
            self.log_queue.put(("progress", index))
        self.log_queue.put(("done", None))

    def open_output(self):
        target = self.last_output_dir or OUTPUTS_DIR
        if target:
            open_folder(target)


def parse_args():
    parser = argparse.ArgumentParser(description="ForJyn Workbench GUI")
    parser.add_argument("--check", action="store_true", help="Validate that the GUI script imports without opening a window")
    return parser.parse_args()


def main():
    args = parse_args()
    if args.check:
        ensure_workbench_dirs()
        print("ForJyn Workbench GUI import check passed")
        return
    root = Tk()
    app = ForJynWorkbenchApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
