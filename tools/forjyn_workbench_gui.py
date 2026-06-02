import argparse
import os
import queue
import subprocess
import sys
import threading
from datetime import datetime
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


def rel(path):
    try:
        return str(Path(path).resolve().relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(Path(path).resolve())


def environment_info():
    info = {
        "workbench": "Ready" if WORKBENCH.exists() else "Not ready",
        "device": "Device: unknown",
        "pytorch": "PyTorch: not available",
        "onnxruntime": "ONNX Runtime: not available",
        "providers": [],
        "errors": [],
    }
    try:
        import torch

        info["pytorch"] = f"PyTorch: {torch.__version__}"
        if torch.cuda.is_available():
            name = torch.cuda.get_device_name(0)
            info["device"] = f"GPU: {name} available"
        else:
            info["device"] = "Device: CPU only"
    except Exception as exc:
        info["device"] = "Device: CPU only"
        info["errors"].append(f"PyTorch environment issue: {exc}")

    try:
        import onnxruntime as ort

        providers = list(ort.get_available_providers())
        info["providers"] = providers
        info["onnxruntime"] = "ONNX Runtime: " + (", ".join(providers) if providers else "no providers reported")
    except Exception as exc:
        info["errors"].append(f"ONNX Runtime environment issue: {exc}")

    return info


def short_time():
    return datetime.now().strftime("%H:%M:%S")


class ForJynWorkbenchApp:
    def __init__(self, root):
        self.root = root
        self.root.title("ForJyn Workbench")
        self.root.minsize(860, 720)

        ensure_workbench_dirs()

        self.content_path = StringVar()
        self.content_label = StringVar(value="No content photo selected")
        self.styles_summary = StringVar(value="No style/reference images selected")
        self.quality = StringVar(value="Normal - 800 steps")
        self.progress_status = StringVar(value="Waiting")
        self.env_info = environment_info()
        self.style_paths = []
        self.completed_dirs = []
        self.last_output_dir = None
        self.running = False
        self.log_queue = queue.Queue()

        self._build_ui()
        self._write_initial_log()
        self._update_start_state()
        self._poll_log_queue()

    def _build_ui(self):
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        frame = ttk.Frame(self.root, padding=16)
        frame.grid(row=0, column=0, sticky="nsew")
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(7, weight=1)

        title = ttk.Label(frame, text="ForJyn Workbench", font=("Segoe UI", 18, "bold"))
        title.grid(row=0, column=0, sticky="w")
        subtitle = ttk.Label(
            frame,
            text="Train one ONNX style model from one content photo and one or more style/reference images.",
        )
        subtitle.grid(row=1, column=0, sticky="w", pady=(2, 12))

        status_box = ttk.LabelFrame(frame, text="Status", padding=10)
        status_box.grid(row=2, column=0, sticky="ew", pady=6)
        status_box.columnconfigure(1, weight=1)
        status_items = [
            ("Workbench", self.env_info["workbench"]),
            ("Device", self.env_info["device"].replace("Device: ", "")),
            ("PyTorch", self.env_info["pytorch"].replace("PyTorch: ", "")),
            ("ONNX Runtime", self.env_info["onnxruntime"].replace("ONNX Runtime: ", "")),
            ("Output folder", rel(OUTPUTS_DIR)),
        ]
        for index, (label, value) in enumerate(status_items):
            row = index // 2
            col = (index % 2) * 2
            ttk.Label(status_box, text=f"{label}:", font=("Segoe UI", 9, "bold")).grid(row=row, column=col, sticky="w", padx=(0, 6), pady=2)
            ttk.Label(status_box, text=value).grid(row=row, column=col + 1, sticky="w", padx=(0, 16), pady=2)

        content_box = ttk.LabelFrame(frame, text="Step 1 - Choose content photo", padding=10)
        content_box.grid(row=3, column=0, sticky="ew", pady=6)
        content_box.columnconfigure(0, weight=1)
        ttk.Label(content_box, text="This is the photo ForJyn will transform.").grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 6))
        self.content_entry = ttk.Entry(content_box, textvariable=self.content_path, state="readonly")
        self.content_entry.grid(row=1, column=0, sticky="ew", padx=(0, 8))
        self.choose_content_button = ttk.Button(content_box, text="Choose content photo", command=self.choose_content)
        self.choose_content_button.grid(row=1, column=1)
        ttk.Label(content_box, textvariable=self.content_label).grid(row=2, column=0, columnspan=2, sticky="w", pady=(6, 0))

        style_box = ttk.LabelFrame(frame, text="Step 2 - Choose style/reference images", padding=10)
        style_box.grid(row=4, column=0, sticky="nsew", pady=6)
        style_box.columnconfigure(0, weight=1)
        ttk.Label(style_box, text="ForJyn will train one model for each selected style image.").grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 6))
        self.style_list = ttk.Treeview(style_box, columns=("file", "folder"), show="headings", height=5)
        self.style_list.heading("file", text="File")
        self.style_list.heading("folder", text="Folder")
        self.style_list.column("file", width=190, stretch=False)
        self.style_list.column("folder", stretch=True)
        self.style_list.grid(row=1, column=0, sticky="nsew", padx=(0, 8))
        self.choose_styles_button = ttk.Button(style_box, text="Choose style/reference images", command=self.choose_styles)
        self.choose_styles_button.grid(row=1, column=1, sticky="n")
        ttk.Label(style_box, textvariable=self.styles_summary).grid(row=2, column=0, columnspan=2, sticky="w", pady=(6, 0))

        quality_box = ttk.LabelFrame(frame, text="Step 3 - Quality", padding=10)
        quality_box.grid(row=5, column=0, sticky="ew", pady=6)
        quality_box.columnconfigure(1, weight=1)
        ttk.Label(quality_box, text="Quality").grid(row=0, column=0, sticky="w", padx=(0, 8))
        self.quality_menu = ttk.Combobox(
            quality_box,
            textvariable=self.quality,
            values=list(QUALITY_MODES.keys()),
            state="readonly",
            width=30,
        )
        self.quality_menu.grid(row=0, column=1, sticky="w")
        ttk.Label(
            quality_box,
            text="Quick is only for checking the pipeline. Better quality can take much longer.",
        ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(6, 0))

        generate_box = ttk.LabelFrame(frame, text="Step 4 - Generate", padding=10)
        generate_box.grid(row=6, column=0, sticky="ew", pady=6)
        generate_box.columnconfigure(3, weight=1)
        self.start_button = ttk.Button(generate_box, text="Start", command=self.start_jobs)
        self.start_button.grid(row=0, column=0, padx=(0, 8))
        self.open_output_button = ttk.Button(generate_box, text="Open output folder", command=self.open_output, state=DISABLED)
        self.open_output_button.grid(row=0, column=1, padx=(0, 8))
        self.open_workbench_button = ttk.Button(generate_box, text="Open workbench folder", command=lambda: open_folder(WORKBENCH))
        self.open_workbench_button.grid(row=0, column=2, padx=(0, 12))
        ttk.Label(generate_box, textvariable=self.progress_status).grid(row=0, column=3, sticky="e")
        self.progress = ttk.Progressbar(generate_box, mode="indeterminate")
        self.progress.grid(row=1, column=0, columnspan=4, sticky="ew", pady=(10, 0))

        log_box = ttk.LabelFrame(frame, text="Log", padding=8)
        log_box.grid(row=7, column=0, sticky="nsew", pady=(8, 0))
        log_box.columnconfigure(0, weight=1)
        log_box.rowconfigure(0, weight=1)
        self.log = ScrolledText(log_box, height=13, wrap="word", font=("Consolas", 10))
        self.log.grid(row=0, column=0, sticky="nsew")
        self.log.configure(state=DISABLED)

    def _write_initial_log(self):
        self._append_log("ForJyn Workbench ready.\n")
        self._append_log(f"{self.env_info['device']}\n")
        self._append_log(f"{self.env_info['pytorch']}\n")
        self._append_log(f"{self.env_info['onnxruntime']}\n")
        for error in self.env_info["errors"]:
            self._append_log(f"Warning: {error}\n")

    def choose_content(self):
        path = filedialog.askopenfilename(
            title="Choose content photo",
            initialdir=str(INPUTS_DIR),
            filetypes=IMAGE_FILETYPES,
        )
        if path:
            self.content_path.set(path)
            self.content_label.set(f"Selected: {Path(path).name}")
            self._append_log(f"Selected content photo: {Path(path).name}\n")
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
                item = Path(path)
                self.style_list.insert("", END, values=(item.name, str(item.parent)))
            count = len(self.style_paths)
            self.styles_summary.set(f"{count} style/reference image{'s' if count != 1 else ''} selected")
            self._append_log(f"Selected {count} style/reference image{'s' if count != 1 else ''}.\n")
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
        for line in text.splitlines(True):
            prefix = f"[{short_time()}] " if line.strip() else ""
            self.log.insert(END, prefix + line)
        self.log.see(END)
        self.log.configure(state=DISABLED)

    def _set_progress_status(self, value):
        self.progress_status.set(value)

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
                elif kind == "status":
                    self._set_progress_status(payload)
                elif kind == "done":
                    self.running = False
                    self.progress.stop()
                    self._set_inputs_state(NORMAL)
                    self._update_start_state()
                    final_status = "Done" if payload else "Failed"
                    self._set_progress_status(final_status)
                    if payload and self.last_output_dir:
                        self._append_log(f"Done.\nONNX and outputs are in: {self.last_output_dir}\n")
                    elif self.last_output_dir:
                        self._append_log(f"Some jobs failed. Last completed output is in: {self.last_output_dir}\n")
                    elif not payload:
                        self._append_log("Failed. Review the log above.\n")
        except queue.Empty:
            pass
        self.root.after(100, self._poll_log_queue)

    def _confirm_start(self):
        steps = QUALITY_MODES[self.quality.get()]
        content = Path(self.content_path.get()).name
        message = (
            "This will train 1 model per style image. Training can take time. Continue?\n\n"
            f"Content photo: {content}\n"
            f"Style images: {len(self.style_paths)}\n"
            f"Quality steps: {steps}\n"
            f"Output root: {rel(OUTPUTS_DIR)}"
        )
        return messagebox.askyesno("Start ForJyn job", message)

    def start_jobs(self):
        if self.running:
            return
        if not self.content_path.get() or not self.style_paths:
            messagebox.showerror("Missing files", "Choose one content photo and at least one style/reference image.")
            return
        if not self._confirm_start():
            return
        self.running = True
        self.completed_dirs = []
        self.last_output_dir = None
        self.progress.configure(mode="indeterminate")
        self.progress.start(12)
        self._set_progress_status("Training")
        self.open_output_button.configure(state=DISABLED)
        self._set_inputs_state(DISABLED)
        self._update_start_state()
        steps = QUALITY_MODES[self.quality.get()]
        self._append_log(
            "Starting ForJyn jobs...\n"
            f"Content photo: {Path(self.content_path.get()).name}\n"
            f"Style images: {len(self.style_paths)}\n"
            f"Quality steps: {steps}\n"
            f"Output root: {rel(OUTPUTS_DIR)}\n"
        )
        thread = threading.Thread(target=self._run_jobs_worker, daemon=True)
        thread.start()

    def _update_status_from_line(self, line):
        lower = line.lower()
        if "training pytorch" in lower or "training model" in lower:
            self.log_queue.put(("status", "Training"))
        elif "exporting" in lower or "export onnx" in lower:
            self.log_queue.put(("status", "Exporting ONNX"))
        elif "validating" in lower or "validation" in lower:
            self.log_queue.put(("status", "Validating"))
        elif "applying" in lower or "apply" in lower:
            self.log_queue.put(("status", "Applying"))
        elif "phase: complete" in lower:
            self.log_queue.put(("status", "Done"))

    def _run_jobs_worker(self):
        steps = QUALITY_MODES[self.quality.get()]
        all_ok = True
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
                "--device",
                "auto",
            ]
            self.log_queue.put(("log", f"\n[{index}/{len(self.style_paths)}] {Path(style_path).name}\n"))
            self.log_queue.put(("status", "Training"))
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
                suppress_traceback_frames = False
                for line in process.stdout:
                    if line.startswith("Traceback (most recent call last):"):
                        self.log_queue.put(("log", "Backend error traceback omitted. Final error line follows if available.\n"))
                        suppress_traceback_frames = True
                        continue
                    if suppress_traceback_frames and (line.startswith("  File ") or line.startswith("    ")):
                        continue
                    suppress_traceback_frames = False
                    self._update_status_from_line(line)
                    self.log_queue.put(("log", line))
                    if line.startswith("FORJYN_OUTPUT_DIR="):
                        self.log_queue.put(("output_dir", line.split("=", 1)[1].strip()))
                returncode = process.wait()
                if returncode != 0:
                    all_ok = False
                    self.log_queue.put(("status", "Failed"))
                    self.log_queue.put(("log", f"Job failed with exit code {returncode}.\n"))
                else:
                    self.log_queue.put(("log", "Job completed.\n"))
            except Exception as exc:
                all_ok = False
                self.log_queue.put(("status", "Failed"))
                self.log_queue.put(("log", f"Job failed: {exc}\n"))
        self.log_queue.put(("done", all_ok))

    def open_output(self):
        target = self.last_output_dir or OUTPUTS_DIR
        if target:
            open_folder(target)


def parse_args():
    parser = argparse.ArgumentParser(description="ForJyn Workbench GUI")
    parser.add_argument("--check", action="store_true", help="Validate imports, backend path, and environment info without opening a window")
    return parser.parse_args()


def run_check():
    ensure_workbench_dirs()
    info = environment_info()
    print("ForJyn Workbench GUI check")
    print(f"Tkinter: available")
    print(f"Backend: {'found' if BACKEND.exists() else 'missing'} ({BACKEND})")
    print(f"Workbench: {info['workbench']} ({WORKBENCH})")
    print(info["device"])
    print(info["pytorch"])
    print(info["onnxruntime"])
    if info["errors"]:
        for error in info["errors"]:
            print(f"Warning: {error}")
    if not BACKEND.exists():
        raise SystemExit(1)


def main():
    args = parse_args()
    if args.check:
        run_check()
        return
    root = Tk()
    ForJynWorkbenchApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
