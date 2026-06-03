import argparse
import json
import os
import queue
import re
import subprocess
import sys
import threading
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import END, DISABLED, NORMAL, StringVar, Tk, filedialog, messagebox
from tkinter import ttk
from tkinter.scrolledtext import ScrolledText

from PIL import Image, ImageTk


TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from forjyn_reference_generator import (
    DEFAULTS as REFERENCE_DEFAULTS,
    PRESETS as REFERENCE_PRESETS,
    generate_references,
    save_reference,
)
from forjyn_paths import (
    MANUAL_REFERENCES_DIR,
    OUTPUTS_DIR,
    REVIEWS_DIR,
    RUNTIME_DIR,
    RUNTIME_MODELS_DIR,
    ROOT,
    WORKBENCH,
    ensure_workbench_dirs as ensure_runtime_dirs,
)

INPUTS_DIR = MANUAL_REFERENCES_DIR
REFERENCES_DIR = MANUAL_REFERENCES_DIR
TECHNICAL_DIR = RUNTIME_DIR
BACKEND = ROOT / "tools" / "forjyn_workbench.py"

IMAGE_FILETYPES = [
    ("Image files", "*.jpg *.jpeg *.png *.webp"),
    ("JPEG", "*.jpg *.jpeg"),
    ("PNG", "*.png"),
    ("WebP", "*.webp"),
    ("All files", "*.*"),
]

QUALITY_MODES = {
    "Draft screening - 300 steps": 300,
    "Normal candidate - 800 steps": 800,
    "Final quality - 2000 steps": 2000,
}

QUALITY_DESCRIPTIONS = {
    "Draft screening - 300 steps": "Fast screening. Use this to test multiple references before spending time.",
    "Normal candidate - 800 steps": "Good first candidate. Use this for promising references.",
    "Final quality - 2000 steps": "Slow. Use only for selected winners.",
}

IMAGE_EXTENSIONS = [".jpg", ".jpeg", ".png", ".webp"]
PERCENT_LINE_RE = re.compile(r"^\s*\d+(?:\.\d+)?%\s*$")


def ensure_workbench_dirs():
    ensure_runtime_dirs()


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
        "cuda_available": "no",
        "training_device": "CPU only",
        "pytorch": "PyTorch: not available",
        "onnxruntime": "ONNX Runtime: not available",
        "providers": [],
        "directml_available": "no",
        "inference_acceleration": "CPU",
        "webp_supported": "no",
        "errors": [],
    }
    try:
        import torch

        info["pytorch"] = f"PyTorch: {torch.__version__}"
        if torch.cuda.is_available():
            name = torch.cuda.get_device_name(0)
            info["device"] = f"GPU: {name} available"
            info["cuda_available"] = "yes"
            info["training_device"] = f"CUDA GPU ({name})"
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
        directml = "DmlExecutionProvider" in providers or "DirectMLExecutionProvider" in providers
        info["directml_available"] = "yes" if directml else "no"
        info["inference_acceleration"] = "DirectML available" if directml else "DirectML not installed"
    except Exception as exc:
        info["errors"].append(f"ONNX Runtime environment issue: {exc}")

    try:
        from PIL import features

        info["webp_supported"] = "yes" if features.check("webp") else "no"
    except Exception as exc:
        info["errors"].append(f"Pillow WebP check failed: {exc}")

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
        self.quality = StringVar(value="Normal candidate - 800 steps")
        self.quality_description = StringVar(value=QUALITY_DESCRIPTIONS[self.quality.get()])
        self.progress_status = StringVar(value="Waiting")
        self.current_job = StringVar(value="Current job: idle")
        self.current_stage = StringVar(value="Current stage: Waiting")
        self.style_progress = StringVar(value="Style progress: 0 of 0")
        self.output_status = StringVar(value=f"Output folder: {rel(OUTPUTS_DIR)}")
        self.env_info = environment_info()
        self.style_paths = []
        self.completed_dirs = []
        self.last_output_dir = None
        self.current_backend_job_id = None
        self.running = False
        self.log_queue = queue.Queue()

        self._configure_style()
        self._build_ui()
        self._write_initial_log()
        self._update_start_state()
        self._poll_log_queue()

    def _configure_style(self):
        self.style = ttk.Style(self.root)
        self.style.configure("Title.TLabel", font=("Segoe UI", 18, "bold"))
        self.style.configure("Section.TLabelframe.Label", font=("Segoe UI", 9, "bold"))
        self.style.configure("Accent.TButton", font=("Segoe UI", 10, "bold"))
        self.style.configure("Small.TLabel", font=("Segoe UI", 8))

    def _build_ui(self):
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        frame = ttk.Frame(self.root, padding=16)
        frame.grid(row=0, column=0, sticky="nsew")
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(7, weight=1)

        title = ttk.Label(frame, text="ForJyn Workbench", style="Title.TLabel")
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
            ("Training device", self.env_info["training_device"]),
            ("PyTorch", self.env_info["pytorch"].replace("PyTorch: ", "")),
            ("ONNX acceleration", self.env_info["inference_acceleration"]),
            ("ONNX providers", self.env_info["onnxruntime"].replace("ONNX Runtime: ", "")),
            ("WebP", self.env_info["webp_supported"]),
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
        style_box.rowconfigure(1, weight=1)
        ttk.Label(style_box, text="Reference images can be loaded from files or generated locally inside ForJyn.").grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 6))
        self.style_list = ttk.Treeview(style_box, columns=("file", "folder"), show="headings", height=5)
        self.style_list.heading("file", text="File")
        self.style_list.heading("folder", text="Folder")
        self.style_list.column("file", width=190, stretch=False)
        self.style_list.column("folder", stretch=True)
        self.style_list.grid(row=1, column=0, sticky="nsew", padx=(0, 8))
        style_actions = ttk.Frame(style_box)
        style_actions.grid(row=1, column=1, sticky="n")
        self.choose_styles_button = ttk.Button(style_actions, text="Choose style/reference images", command=self.choose_styles)
        self.choose_styles_button.grid(row=0, column=0, sticky="ew")
        self.generate_refs_button = ttk.Button(
            style_actions,
            text="Generate reference images",
            command=self.open_reference_generator,
        )
        self.generate_refs_button.grid(row=1, column=0, sticky="ew", pady=(8, 0))
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
            width=34,
        )
        self.quality_menu.grid(row=0, column=1, sticky="w")
        self.quality_menu.bind("<<ComboboxSelected>>", self._update_quality_description)
        ttk.Label(
            quality_box,
            textvariable=self.quality_description,
        ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(6, 0))
        ttk.Label(
            quality_box,
            text="Do not use Final quality for many references. First screen them with Draft or Normal.",
            foreground="#7A4A00",
        ).grid(row=2, column=0, columnspan=2, sticky="w", pady=(4, 0))

        generate_box = ttk.LabelFrame(frame, text="Step 4 - Generate", padding=10)
        generate_box.grid(row=6, column=0, sticky="ew", pady=6)
        generate_box.columnconfigure(5, weight=1)
        self.start_button = ttk.Button(generate_box, text="Start", command=self.start_jobs, style="Accent.TButton")
        self.start_button.grid(row=0, column=0, padx=(0, 8))
        self.open_output_button = ttk.Button(generate_box, text="Open output folder", command=self.open_output, state=DISABLED)
        self.open_output_button.grid(row=0, column=1, padx=(0, 8))
        self.review_sheet_button = ttk.Button(generate_box, text="Create review sheet", command=self.create_review_sheet)
        self.review_sheet_button.grid(row=0, column=2, padx=(0, 8))
        self.clean_temp_button = ttk.Button(generate_box, text="Clean temporary refs", command=self.clean_temp_references)
        self.clean_temp_button.grid(row=0, column=3, padx=(0, 8))
        self.open_workbench_button = ttk.Button(generate_box, text="Open workbench folder", command=lambda: open_folder(WORKBENCH))
        self.open_workbench_button.grid(row=0, column=4, padx=(0, 12))
        ttk.Label(generate_box, textvariable=self.progress_status).grid(row=0, column=5, sticky="e")
        self.progress = ttk.Progressbar(generate_box, mode="indeterminate")
        self.progress.grid(row=1, column=0, columnspan=6, sticky="ew", pady=(10, 0))
        ttk.Label(generate_box, textvariable=self.current_job).grid(row=2, column=0, columnspan=6, sticky="w", pady=(8, 0))
        ttk.Label(generate_box, textvariable=self.current_stage).grid(row=3, column=0, columnspan=3, sticky="w")
        ttk.Label(generate_box, textvariable=self.style_progress).grid(row=3, column=3, columnspan=3, sticky="e")
        ttk.Label(generate_box, textvariable=self.output_status).grid(row=4, column=0, columnspan=6, sticky="w")

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
        self._append_log(f"PyTorch CUDA available: {self.env_info['cuda_available']}\n")
        self._append_log(f"{self.env_info['pytorch']}\n")
        self._append_log(f"{self.env_info['onnxruntime']}\n")
        self._append_log(f"DirectMLExecutionProvider available: {self.env_info['directml_available']}\n")
        self._append_log(f"Supported image extensions: {', '.join(IMAGE_EXTENSIONS)}\n")
        self._append_log(f"WebP supported: {self.env_info['webp_supported']}\n")
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

    def _update_quality_description(self, _event=None):
        self.quality_description.set(QUALITY_DESCRIPTIONS.get(self.quality.get(), ""))

    def _refresh_style_list(self):
        self.style_list.delete(*self.style_list.get_children())
        for path in self.style_paths:
            item = Path(path)
            self.style_list.insert("", END, values=(item.name, str(item.parent)))
        count = len(self.style_paths)
        if count:
            self.styles_summary.set(f"{count} style/reference image{'s' if count != 1 else ''} selected")
        else:
            self.styles_summary.set("No style/reference images selected")

    def add_style_paths(self, paths, replace=False):
        if replace:
            self.style_paths = []
        seen = {str(Path(path).resolve()).casefold() for path in self.style_paths}
        added = 0
        for path in paths:
            resolved = str(Path(path).resolve())
            key = resolved.casefold()
            if key in seen:
                continue
            self.style_paths.append(resolved)
            seen.add(key)
            added += 1
        self._refresh_style_list()
        if added:
            self._append_log(f"Added {added} style/reference image{'s' if added != 1 else ''}. These will be used like normal references.\n")
        self._update_start_state()

    def choose_styles(self):
        paths = filedialog.askopenfilenames(
            title="Choose style/reference images",
            initialdir=str(REFERENCES_DIR),
            filetypes=IMAGE_FILETYPES,
        )
        if paths:
            self.add_style_paths(paths, replace=True)

    def open_reference_generator(self):
        ReferenceGeneratorWindow(self.root, self.add_style_paths, self._append_log)

    def _update_start_state(self):
        can_start = bool(self.content_path.get()) and bool(self.style_paths) and not self.running
        self.start_button.configure(state=NORMAL if can_start else DISABLED)

    def _set_inputs_state(self, state):
        self.choose_content_button.configure(state=state)
        self.choose_styles_button.configure(state=state)
        self.generate_refs_button.configure(state=state)
        self.quality_menu.configure(state="readonly" if state == NORMAL else DISABLED)
        self.review_sheet_button.configure(state=state)
        self.clean_temp_button.configure(state=state)
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

    def _stage_label(self, stage):
        return {
            "training": "Training",
            "exporting": "Exporting ONNX",
            "validating": "Validating",
            "applying": "Applying",
            "done": "Done",
            "failed": "Failed",
        }.get(stage.strip().lower(), stage.strip())

    def _is_progress_noise(self, line):
        stripped = line.strip()
        return bool(PERCENT_LINE_RE.match(stripped) or re.match(r"^\d+(?:\.\d+)?%\|", stripped))

    def _handle_structured_line(self, line):
        stripped = line.strip()
        if not stripped.startswith("FORJYN_") or "=" not in stripped:
            return False
        key, value = stripped.split("=", 1)
        key = key.removeprefix("FORJYN_")
        if key == "STAGE":
            self.log_queue.put(("status", self._stage_label(value)))
        elif key == "MESSAGE":
            self.log_queue.put(("log", value + "\n"))
        elif key == "JOB_ID":
            self.current_backend_job_id = value
            self.log_queue.put(("current_job", value))
        elif key == "STYLE":
            self.log_queue.put(("current_job", value))
        elif key == "OUTPUT_DIR":
            self.log_queue.put(("output_dir", value))
        elif key == "ONNX_PATH":
            self.log_queue.put(("onnx_path", value))
        elif key == "IMAGE_OUTPUT":
            self.log_queue.put(("image_output", value))
        elif key == "PROGRESS":
            pass
        return True

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
                    self.output_status.set(f"Output folder: {payload}")
                elif kind == "status":
                    self._set_progress_status(payload)
                    self.current_stage.set(f"Current stage: {payload}")
                elif kind == "current_job":
                    self.current_job.set(f"Current job: {payload}")
                elif kind == "style_progress":
                    self.style_progress.set(payload)
                elif kind == "runtime_output":
                    self.output_status.set(f"Output folder: {payload}")
                elif kind == "onnx_path":
                    self._append_log(f"ONNX: {payload}\n")
                elif kind == "image_output":
                    self._append_log(f"Image output: {payload}\n")
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
            f"Quality: {self.quality.get()} ({steps} steps)\n"
            f"{QUALITY_DESCRIPTIONS.get(self.quality.get(), '')}\n"
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
        self.current_backend_job_id = None
        self.progress.configure(mode="indeterminate")
        self.progress.start(12)
        self._set_progress_status("Training")
        self.current_stage.set("Current stage: Training")
        self.current_job.set("Current job: starting")
        self.style_progress.set(f"Style progress: 0 of {len(self.style_paths)}")
        self.output_status.set(f"Output folder: {rel(OUTPUTS_DIR)}")
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
            backend_job_id = None
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
            self.log_queue.put(("log", f"\nStarting style {index}/{len(self.style_paths)}: {Path(style_path).name}\n"))
            self.log_queue.put(("status", "Training"))
            self.log_queue.put(("style_progress", f"Style progress: {index} of {len(self.style_paths)}"))
            self.log_queue.put(("current_job", Path(style_path).name))
            try:
                env = os.environ.copy()
                env["PYTHONIOENCODING"] = "utf-8"
                env["PYTHONUTF8"] = "1"
                process = subprocess.Popen(
                    command,
                    cwd=str(ROOT),
                    env=env,
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
                    if line.startswith("FORJYN_JOB_ID="):
                        backend_job_id = line.split("=", 1)[1].strip()
                    if self._handle_structured_line(line):
                        continue
                    if self._is_progress_noise(line):
                        continue
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
                    checkpoint = RUNTIME_MODELS_DIR / backend_job_id / "checkpoint.pth" if backend_job_id else None
                    if checkpoint and checkpoint.exists():
                        self.log_queue.put((
                            "log",
                            "Training checkpoint was created, but export/apply failed. "
                            "You can recover this job without retraining after fixing the issue.\n",
                        ))
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

    def _run_backend_helper(self, args):
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUTF8"] = "1"
        return subprocess.run(
            [sys.executable, str(BACKEND), *args],
            cwd=str(ROOT),
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )

    def create_review_sheet(self):
        if self.running:
            return
        result = self._run_backend_helper(["create-review-sheet"])
        if result.returncode != 0:
            message = (result.stderr or result.stdout or "No outputs found yet. Generate at least one model first.").strip()
            if "No outputs found" in message:
                messagebox.showinfo("No outputs found", "No outputs found yet. Generate at least one model first.")
            else:
                messagebox.showerror("Review sheet failed", message)
            self._append_log(f"Review sheet not created: {message}\n")
            return
        sheet_path = REVIEWS_DIR / "latest-review-sheet.jpg"
        try:
            payload = json.loads(result.stdout)
            sheet_path = ROOT / payload.get("review_sheet", rel(sheet_path))
        except Exception:
            pass
        self._append_log(f"Review sheet created: {rel(sheet_path)}\n")
        self.output_status.set(f"Review sheet: {rel(sheet_path)}")
        if sheet_path.exists():
            open_folder(sheet_path)

    def clean_temp_references(self):
        if self.running:
            return
        if not messagebox.askyesno(
            "Clean temporary references",
            "Delete only temporary generated-reference files?\n\nThis keeps saved references, final candidates, contact sheets, outputs, models, and reports.",
        ):
            return
        result = self._run_backend_helper(["cleanup-temp"])
        if result.returncode != 0:
            message = (result.stderr or result.stdout or "Cleanup failed.").strip()
            messagebox.showerror("Cleanup failed", message)
            self._append_log(f"Temporary reference cleanup failed: {message}\n")
            return
        try:
            payload = json.loads(result.stdout)
            removed = payload.get("files_removed", 0)
            bytes_removed = payload.get("bytes_removed", 0)
            self._append_log(f"Temporary generated references cleaned: {removed} files, {bytes_removed} bytes.\n")
            self.output_status.set("Temporary generated references cleaned")
        except Exception:
            self._append_log("Temporary generated references cleaned.\n")


class ReferenceGeneratorWindow:
    def __init__(self, parent, add_paths_callback, log_callback):
        self.parent = parent
        self.add_paths_callback = add_paths_callback
        self.log_callback = log_callback
        self.generated_paths = []
        self.selected_path = None
        self.thumbnail_images = []
        self.thumbnail_widgets = {}
        self.result_queue = queue.Queue()
        self.closed = False
        self.busy = False

        self.window = tk.Toplevel(parent)
        self.window.title("ForJyn Reference Generator")
        self.window.minsize(920, 680)
        self.window.protocol("WM_DELETE_WINDOW", self.close)

        self.preset_options = {info["name"]: slug for slug, info in REFERENCE_PRESETS.items()}
        self.preset = StringVar(value=REFERENCE_PRESETS["neon-bloom"]["name"])
        self.seed_mode = StringVar(value="Random")
        self.seed_value = StringVar()
        self.status = StringVar(value="Ready")
        self.preset_description = StringVar(value=REFERENCE_PRESETS["neon-bloom"]["description"])
        self.selection_status = StringVar(value="No generated reference selected")
        self.count = tk.IntVar(value=REFERENCE_DEFAULTS["count"])
        self.width = tk.IntVar(value=REFERENCE_DEFAULTS["width"])
        self.height = tk.IntVar(value=REFERENCE_DEFAULTS["height"])
        self.intensity = tk.DoubleVar(value=REFERENCE_DEFAULTS["intensity"])
        self.glow = tk.DoubleVar(value=REFERENCE_DEFAULTS["glow"])
        self.contrast = tk.DoubleVar(value=REFERENCE_DEFAULTS["contrast"])
        self.texture = tk.DoubleVar(value=REFERENCE_DEFAULTS["texture"])
        self.complexity = tk.DoubleVar(value=REFERENCE_DEFAULTS["complexity"])

        self._build_ui()

    def _build_ui(self):
        self.window.columnconfigure(0, weight=0)
        self.window.columnconfigure(1, weight=1)
        self.window.rowconfigure(0, weight=1)

        controls = ttk.Frame(self.window, padding=16)
        controls.grid(row=0, column=0, sticky="ns")

        preview_box = ttk.Frame(self.window, padding=(0, 16, 16, 16))
        preview_box.grid(row=0, column=1, sticky="nsew")
        preview_box.columnconfigure(0, weight=1)
        preview_box.rowconfigure(1, weight=1)

        ttk.Label(controls, text="Reference Generator", style="Title.TLabel").grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 12))
        ttk.Label(controls, text="Preset").grid(row=1, column=0, sticky="w", pady=4)
        self.preset_menu = ttk.Combobox(
            controls,
            textvariable=self.preset,
            values=list(self.preset_options.keys()),
            state="readonly",
            width=28,
        )
        self.preset_menu.grid(row=1, column=1, columnspan=2, sticky="ew", pady=4)
        self.preset_menu.bind("<<ComboboxSelected>>", self._update_preset_description)
        ttk.Label(controls, textvariable=self.preset_description, wraplength=300, foreground="#586174").grid(
            row=2, column=0, columnspan=3, sticky="w", pady=(0, 10)
        )

        ttk.Label(controls, text="Count").grid(row=3, column=0, sticky="w", pady=4)
        self.count_spin = ttk.Spinbox(controls, from_=1, to=12, textvariable=self.count, width=8)
        self.count_spin.grid(row=3, column=1, sticky="w", pady=4)
        ttk.Label(controls, text="max 12", style="Small.TLabel").grid(row=3, column=2, sticky="w", padx=(6, 0))

        ttk.Label(controls, text="Width").grid(row=4, column=0, sticky="w", pady=4)
        self.width_spin = ttk.Spinbox(controls, from_=256, to=2048, increment=64, textvariable=self.width, width=8)
        self.width_spin.grid(row=4, column=1, sticky="w", pady=4)
        ttk.Label(controls, text="Height").grid(row=5, column=0, sticky="w", pady=4)
        self.height_spin = ttk.Spinbox(controls, from_=256, to=2048, increment=64, textvariable=self.height, width=8)
        self.height_spin.grid(row=5, column=1, sticky="w", pady=4)

        ttk.Label(controls, text="Seed").grid(row=6, column=0, sticky="w", pady=(12, 4))
        self.seed_menu = ttk.Combobox(controls, textvariable=self.seed_mode, values=["Random", "Numeric"], state="readonly", width=10)
        self.seed_menu.grid(row=6, column=1, sticky="w", pady=(12, 4))
        self.seed_entry = ttk.Entry(controls, textvariable=self.seed_value, width=12)
        self.seed_entry.grid(row=6, column=2, sticky="w", padx=(6, 0), pady=(12, 4))

        self.slider_widgets = []
        row = 7
        for label, variable in [
            ("Intensity", self.intensity),
            ("Glow", self.glow),
            ("Contrast", self.contrast),
            ("Texture", self.texture),
            ("Complexity", self.complexity),
        ]:
            row = self._add_slider(controls, row, label, variable)

        button_row = row + 1
        self.generate_button = ttk.Button(controls, text="Generate variations", command=self.generate, style="Accent.TButton")
        self.generate_button.grid(row=button_row, column=0, columnspan=3, sticky="ew", pady=(18, 6))
        self.save_selected_button = ttk.Button(controls, text="Save selected to references", command=self.save_selected, state=DISABLED)
        self.save_selected_button.grid(row=button_row + 1, column=0, columnspan=3, sticky="ew", pady=3)
        self.save_all_button = ttk.Button(controls, text="Save all to references", command=self.save_all, state=DISABLED)
        self.save_all_button.grid(row=button_row + 2, column=0, columnspan=3, sticky="ew", pady=3)
        self.close_button = ttk.Button(controls, text="Close", command=self.close)
        self.close_button.grid(row=button_row + 3, column=0, columnspan=3, sticky="ew", pady=(12, 0))
        ttk.Label(controls, textvariable=self.status, wraplength=290).grid(row=button_row + 4, column=0, columnspan=3, sticky="w", pady=(12, 0))

        ttk.Label(preview_box, text="Generated variations", font=("Segoe UI", 11, "bold")).grid(row=0, column=0, sticky="w", pady=(0, 8))
        self.preview_frame = ttk.Frame(preview_box)
        self.preview_frame.grid(row=1, column=0, sticky="nsew")
        ttk.Label(preview_box, textvariable=self.selection_status, foreground="#2F5E73").grid(row=2, column=0, sticky="w", pady=(8, 0))
        for index in range(4):
            self.preview_frame.columnconfigure(index, weight=1)
        self.empty_preview = ttk.Label(
            self.preview_frame,
            text="Generate variations to preview procedural reference images.",
            foreground="#586174",
        )
        self.empty_preview.grid(row=0, column=0, columnspan=4, sticky="n", pady=60)

    def _update_preset_description(self, _event=None):
        preset = self.preset_options.get(self.preset.get())
        if preset:
            self.preset_description.set(REFERENCE_PRESETS[preset]["description"])

    def _add_slider(self, parent, row, label, variable):
        value_label = StringVar(value=str(int(variable.get())))

        def on_change(value):
            value_label.set(str(int(float(value))))

        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=(10, 0))
        slider = ttk.Scale(parent, from_=0, to=100, variable=variable, command=on_change)
        slider.grid(row=row, column=1, sticky="ew", pady=(10, 0))
        ttk.Label(parent, textvariable=value_label, width=4).grid(row=row, column=2, sticky="e", pady=(10, 0))
        self.slider_widgets.append(slider)
        return row + 1

    def _params(self):
        preset = self.preset_options[self.preset.get()]
        count = max(1, min(12, int(self.count.get())))
        width = max(64, int(self.width.get()))
        height = max(64, int(self.height.get()))
        seed = "random"
        if self.seed_mode.get() == "Numeric" or self.seed_value.get().strip():
            seed = int(self.seed_value.get().strip())
        return {
            "preset": preset,
            "count": count,
            "seed": seed,
            "width": width,
            "height": height,
            "intensity": int(self.intensity.get()),
            "glow": int(self.glow.get()),
            "contrast": int(self.contrast.get()),
            "texture": int(self.texture.get()),
            "complexity": int(self.complexity.get()),
        }

    def _set_busy(self, busy):
        self.busy = busy
        state = DISABLED if busy else NORMAL
        readonly_state = DISABLED if busy else "readonly"
        self.generate_button.configure(state=state)
        self.count_spin.configure(state=state)
        self.width_spin.configure(state=state)
        self.height_spin.configure(state=state)
        self.seed_entry.configure(state=state)
        self.seed_menu.configure(state=readonly_state)
        self.preset_menu.configure(state=readonly_state)
        for widget in self.slider_widgets:
            widget.configure(state=state)
        self._update_save_state()

    def _update_save_state(self):
        if self.busy or not self.generated_paths:
            state = DISABLED
        else:
            state = NORMAL
        self.save_all_button.configure(state=state)
        self.save_selected_button.configure(state=NORMAL if state == NORMAL and self.selected_path else DISABLED)

    def generate(self):
        try:
            params = self._params()
        except Exception as exc:
            messagebox.showerror("Invalid generator settings", f"Check count, size, and seed values.\n\n{exc}")
            return
        self._set_busy(True)
        self.status.set("Generating variations...")
        self.selection_status.set("Generating...")
        self.generated_paths = []
        self.selected_path = None
        self._render_previews([])
        thread = threading.Thread(target=self._generate_worker, args=(params,), daemon=True)
        thread.start()
        self.window.after(100, self._poll_results)

    def _generate_worker(self, params):
        try:
            result = generate_references(**params)
            self.result_queue.put(("result", result))
        except Exception as exc:
            self.result_queue.put(("error", exc))

    def _poll_results(self):
        if self.closed:
            return
        try:
            while True:
                kind, payload = self.result_queue.get_nowait()
                if kind == "result":
                    self.generated_paths = payload["images"]
                    self.selected_path = self.generated_paths[0] if self.generated_paths else None
                    self._render_previews(self.generated_paths)
                    retry_total = sum(int(item.get("retry_count", 0)) for item in payload.get("quality", []))
                    quality_failures = sum(1 for item in payload.get("quality", []) if not item.get("final_quality_pass"))
                    self.status.set(f"Generated {len(self.generated_paths)} variations. Contact sheet: {rel(payload['contact_sheet'])}")
                    if self.selected_path:
                        self.selection_status.set(f"Selected: {Path(self.selected_path).name}")
                    self.log_callback(f"Generated reference variations: {rel(payload['temp_dir'])}\n")
                    if retry_total or quality_failures:
                        self.log_callback(f"Reference quality guard: retries {retry_total}, kept after failed checks {quality_failures}.\n")
                    self._set_busy(False)
                elif kind == "error":
                    self.status.set(f"Generation failed: {payload}")
                    self.selection_status.set("Generation failed")
                    self.log_callback(f"Reference generation failed: {payload}\n")
                    messagebox.showerror("Reference generation failed", str(payload))
                    self._set_busy(False)
        except queue.Empty:
            pass
        if self.busy:
            self.window.after(100, self._poll_results)

    def _render_previews(self, paths):
        for child in self.preview_frame.winfo_children():
            child.destroy()
        self.thumbnail_images = []
        self.thumbnail_widgets = {}
        if not paths:
            self.selection_status.set("No generated reference selected")
            self.empty_preview = ttk.Label(
                self.preview_frame,
                text="Generate variations to preview procedural reference images.",
                foreground="#586174",
            )
            self.empty_preview.grid(row=0, column=0, columnspan=4, sticky="n", pady=60)
            return
        for index, path in enumerate(paths):
            image = Image.open(path).convert("RGB")
            image.thumbnail((150, 150), Image.Resampling.LANCZOS)
            photo = ImageTk.PhotoImage(image)
            self.thumbnail_images.append(photo)
            button = tk.Button(
                self.preview_frame,
                image=photo,
                text=Path(path).name,
                compound="top",
                width=180,
                height=194,
                wraplength=160,
                command=lambda selected=path: self.select_image(selected),
            )
            button.grid(row=index // 4, column=index % 4, padx=6, pady=6, sticky="n")
            self.thumbnail_widgets[path] = button
        self._highlight_selection()

    def select_image(self, path):
        self.selected_path = path
        self.selection_status.set(f"Selected: {Path(path).name}")
        self._highlight_selection()
        self._update_save_state()

    def _highlight_selection(self):
        for path, widget in self.thumbnail_widgets.items():
            if path == self.selected_path:
                widget.configure(
                    relief="solid",
                    bd=4,
                    background="#E7F7FF",
                    activebackground="#D5F1FF",
                    highlightthickness=2,
                    highlightbackground="#00A6D6",
                )
            else:
                widget.configure(relief="flat", bd=1, background="#F2F4F8", activebackground="#EDF2F7", highlightthickness=0)

    def save_selected(self):
        if not self.selected_path:
            messagebox.showerror("No selection", "Select one generated reference image first.")
            return
        try:
            saved = save_reference(self.selected_path)
        except Exception as exc:
            messagebox.showerror("Save failed", str(exc))
            return
        self.add_paths_callback([saved["image"]])
        self.status.set(f"Saved to Step 2 references: {Path(saved['image']).name}")
        self.selection_status.set(f"Saved: {Path(saved['image']).name}")
        self.log_callback(f"Saved generated reference: {rel(saved['image'])}\n")

    def save_all(self):
        if not self.generated_paths:
            return
        saved_paths = []
        try:
            for path in self.generated_paths:
                saved_paths.append(save_reference(path)["image"])
        except Exception as exc:
            messagebox.showerror("Save failed", str(exc))
            return
        self.add_paths_callback(saved_paths)
        self.status.set(f"Saved {len(saved_paths)} references to Step 2 references.")
        self.selection_status.set(f"Saved all: {len(saved_paths)} references")
        self.log_callback(f"Saved {len(saved_paths)} generated references to {rel(Path(saved_paths[0]).parent)}\n")

    def close(self):
        self.closed = True
        self.window.destroy()


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
    print(info["pytorch"])
    print(f"PyTorch CUDA available: {info['cuda_available']}")
    print(f"Training device: {info['training_device']}")
    print("ONNX Runtime providers: " + (", ".join(info["providers"]) if info["providers"] else "none"))
    print(f"DirectMLExecutionProvider available: {info['directml_available']}")
    print("Supported image extensions: " + ", ".join(IMAGE_EXTENSIONS))
    print(f"WebP supported: {info['webp_supported']}")
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
