import argparse
import json
import os
import queue
import re
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import END, DISABLED, NORMAL, StringVar, Tk, filedialog, messagebox
from tkinter import ttk
from tkinter.scrolledtext import ScrolledText

from PIL import Image, ImageTk

try:
    import psutil
except Exception:
    psutil = None


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
HEARTBEAT_INTERVAL_SECONDS = 60
FALLBACK_HEARTBEAT_INTERVAL_SECONDS = 10
CANCEL_TIMEOUT_SECONDS = 5


def ensure_workbench_dirs():
    ensure_runtime_dirs()


def open_path(path):
    path = Path(path)
    if os.name == "nt":
        os.startfile(str(path))
    else:
        subprocess.Popen(["xdg-open", str(path)])


def open_folder(path):
    open_path(path)


def rel(path):
    try:
        return str(Path(path).resolve().relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(Path(path).resolve())


def format_elapsed(seconds):
    seconds = max(0, int(seconds))
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def format_ram_mb(value):
    if value is None:
        return "-"
    return f"{value:.0f} MB"


def format_cpu_load(value):
    if value is None:
        return "-"
    return f"{value:.0f}%"


def format_process_cores(value):
    if value is None:
        return "-"
    return f"{value / 100.0:.1f} cores"


def workbench_status_text(info):
    return "Ready" if str(info.get("workbench", "")).lower() == "ready" else "Not ready"


def training_status_text(info):
    training = info.get("training_device", "CPU only")
    if str(training).lower().startswith("cpu"):
        return "Training: CPU"
    return f"Training: {training}"


def onnx_status_text(info):
    if info.get("directml_available") == "yes":
        return "DirectML ready"
    return "CPU only"


def environment_details_text(info):
    providers = ", ".join(info.get("providers") or []) or "none"
    return "\n".join(
        [
            info.get("pytorch", "PyTorch: not available"),
            f"ONNX Runtime providers: {providers}",
            f"WebP supported: {info.get('webp_supported', 'no')}",
            f"Python: {sys.version.split()[0]}",
        ]
    )


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
        self.env_info = environment_info()
        self.system_status = StringVar(value=f"Status: {workbench_status_text(self.env_info)}")
        self.progress_status = StringVar(value="State: Idle")
        self.current_job = StringVar(value="Job ID: -")
        self.current_style = StringVar(value="Style: -")
        self.current_stage = StringVar(value="Stage: Waiting")
        self.elapsed_time = StringVar(value="Elapsed: 00:00:00")
        self.style_progress = StringVar(value="Style progress: 0/0")
        self.process_pid = StringVar(value="PID: -")
        self.cpu_load = StringVar(value="CPU load: -")
        self.process_cpu = StringVar(value="Process CPU: -")
        self.process_ram = StringVar(value="RAM: -")
        directml_text = "yes" if self.env_info.get("directml_available") == "yes" else "no"
        self.gpu_status = StringVar(value=f"GPU status: DirectML available {directml_text}; usage unavailable")
        self.onnx_provider = StringVar(value="ONNX provider: -")
        self.last_apply_time = StringVar(value="Last ONNX apply: -")
        self.output_status = StringVar(value=f"Output: {rel(OUTPUTS_DIR)}")
        self.output_image_status = StringVar(value="Output image: -")
        self.preserve_status = StringVar(value="Preserves size: -")
        self.results_status = StringVar(value="Results: none yet")
        self.style_paths = []
        self.completed_dirs = []
        self.last_output_dir = None
        self.last_image_output = None
        self.last_onnx_path = None
        self.last_review_sheet = None
        self.current_backend_job_id = None
        self.current_process = None
        self.run_started_at = None
        self.cancel_requested = False
        self._last_cpu_sample = None
        self._last_heartbeat_at = 0.0
        self._details_visible = False
        self._monitor_details_visible = False
        self.monitor_details = StringVar(value="")
        self.running = False
        self.log_queue = queue.Queue()

        self._configure_style()
        self._build_ui()
        self._set_run_state(workbench_status_text(self.env_info))
        self._write_initial_log()
        self._update_start_state()
        self._poll_log_queue()

    def _configure_style(self):
        self.style = ttk.Style(self.root)
        self.style.configure("Title.TLabel", font=("Segoe UI", 18, "bold"))
        self.style.configure("Section.TLabelframe.Label", font=("Segoe UI", 9, "bold"))
        self.style.configure("Accent.TButton", font=("Segoe UI", 10, "bold"))
        self.style.configure("Small.TLabel", font=("Segoe UI", 8))
        self.style.configure("Ready.TLabel", foreground="#0B6B3A")
        self.style.configure("Running.TLabel", foreground="#1D5EA8")
        self.style.configure("Warning.TLabel", foreground="#8A5A00")
        self.style.configure("Failed.TLabel", foreground="#A32424")
        self.style.configure("Muted.TLabel", foreground="#586174")

    def _build_ui(self):
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        outer = ttk.Frame(self.root)
        outer.grid(row=0, column=0, sticky="nsew")
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(0, weight=1)

        self.main_canvas = tk.Canvas(outer, highlightthickness=0)
        self.main_canvas.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(outer, orient="vertical", command=self.main_canvas.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.main_canvas.configure(yscrollcommand=scrollbar.set)

        frame = ttk.Frame(self.main_canvas, padding=16)
        self.main_window = self.main_canvas.create_window((0, 0), window=frame, anchor="nw")
        frame.bind("<Configure>", lambda _event: self.main_canvas.configure(scrollregion=self.main_canvas.bbox("all")))
        self.main_canvas.bind("<Configure>", lambda event: self.main_canvas.itemconfigure(self.main_window, width=event.width))
        self.main_canvas.bind("<Enter>", lambda _event: self.main_canvas.bind_all("<MouseWheel>", self._on_mousewheel))
        self.main_canvas.bind("<Leave>", lambda _event: self.main_canvas.unbind_all("<MouseWheel>"))
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(4, weight=1)
        frame.rowconfigure(7, weight=2)

        title = ttk.Label(frame, text="ForJyn Workbench", style="Title.TLabel")
        title.grid(row=0, column=0, sticky="w")
        subtitle = ttk.Label(
            frame,
            text="Train one ONNX style model from one content photo and one or more style/reference images.",
        )
        subtitle.grid(row=1, column=0, sticky="w", pady=(2, 12))

        status_box = ttk.LabelFrame(frame, text="System", padding=10)
        status_box.grid(row=2, column=0, sticky="ew", pady=6)
        for column in range(6):
            status_box.columnconfigure(column, weight=1 if column == 5 else 0)
        self.status_indicator = tk.Canvas(status_box, width=14, height=14, highlightthickness=0)
        self.status_indicator.grid(row=0, column=0, sticky="w", padx=(0, 6))
        self.status_dot = self.status_indicator.create_oval(2, 2, 12, 12, fill="#80868B", outline="")
        self.system_status_label = ttk.Label(status_box, textvariable=self.system_status, style="Ready.TLabel", font=("Segoe UI", 9, "bold"))
        self.system_status_label.grid(row=0, column=1, sticky="w", padx=(0, 16))
        ttk.Label(status_box, text=training_status_text(self.env_info), style="Warning.TLabel").grid(row=0, column=2, sticky="w", padx=(0, 16))
        ttk.Label(status_box, text=f"ONNX apply: {onnx_status_text(self.env_info)}").grid(row=0, column=3, sticky="w", padx=(0, 16))
        ttk.Label(status_box, text=f"Output: {rel(OUTPUTS_DIR)}", style="Muted.TLabel").grid(row=0, column=4, sticky="w", padx=(0, 16))
        self.env_details_button = ttk.Button(status_box, text="Environment details", command=self.toggle_environment_details)
        self.env_details_button.grid(row=0, column=5, sticky="e")
        self.env_details_label = ttk.Label(
            status_box,
            text=environment_details_text(self.env_info),
            wraplength=760,
            foreground="#586174",
        )

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
        self.style_list = ttk.Treeview(style_box, columns=("file", "folder"), show="headings", height=4)
        self.style_list.heading("file", text="File")
        self.style_list.heading("folder", text="Folder")
        self.style_list.column("file", width=220, stretch=True)
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
        generate_box.columnconfigure(0, weight=1)
        actions = ttk.Frame(generate_box)
        actions.grid(row=0, column=0, sticky="ew")
        actions.columnconfigure(4, weight=1)
        self.start_button = ttk.Button(actions, text="Start", command=self.start_jobs, style="Accent.TButton")
        self.start_button.grid(row=0, column=0, padx=(0, 8))
        self.stop_button = ttk.Button(actions, text="Stop current job", command=self.cancel_current_job, state=DISABLED)
        self.stop_button.grid(row=0, column=1, padx=(0, 8))
        self.clean_temp_button = ttk.Button(actions, text="Clean temporary refs", command=self.clean_temp_references)
        self.clean_temp_button.grid(row=0, column=2, padx=(0, 8))
        self.open_workbench_button = ttk.Button(actions, text="Open workbench folder", command=lambda: open_folder(WORKBENCH))
        self.open_workbench_button.grid(row=0, column=3, padx=(0, 12))
        self.action_status_label = ttk.Label(actions, textvariable=self.progress_status, style="Muted.TLabel")
        self.action_status_label.grid(row=0, column=4, sticky="e")
        self.progress = ttk.Progressbar(generate_box, mode="indeterminate")
        self.progress.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        self.progress.grid_remove()

        ttk.Label(generate_box, text="Run Monitor", font=("Segoe UI", 10, "bold")).grid(row=2, column=0, sticky="w", pady=(10, 4))
        monitor = ttk.Frame(generate_box)
        monitor.grid(row=3, column=0, sticky="ew")
        for column in range(3):
            monitor.columnconfigure(column, weight=1)
        monitor_items = [
            self.progress_status,
            self.current_stage,
            self.elapsed_time,
            self.cpu_load,
            self.process_ram,
            self.style_progress,
        ]
        for index, variable in enumerate(monitor_items):
            row = index // 3
            column = index % 3
            ttk.Label(monitor, textvariable=variable).grid(row=row, column=column, sticky="w", padx=(0, 12), pady=2)
        ttk.Label(monitor, textvariable=self.output_status).grid(row=2, column=0, columnspan=3, sticky="w", padx=(0, 12), pady=2)
        self.monitor_details_button = ttk.Button(generate_box, text="Run details", command=self.toggle_monitor_details)
        self.monitor_details_button.grid(row=4, column=0, sticky="w", pady=(8, 0))
        self.monitor_details_label = ttk.Label(generate_box, textvariable=self.monitor_details, style="Muted.TLabel", wraplength=900)

        self.results_box = ttk.LabelFrame(generate_box, text="Results", padding=8)
        self.results_box.grid(row=6, column=0, sticky="ew", pady=(10, 0))
        self.results_box.columnconfigure(0, weight=1)
        results = ttk.Frame(self.results_box)
        results.grid(row=0, column=0, sticky="ew")
        self.open_result_image_button = ttk.Button(results, text="Open output image", command=self.open_output_image, state=DISABLED)
        self.open_result_image_button.grid(row=0, column=0, padx=(0, 8), pady=2)
        self.open_output_button = ttk.Button(results, text="Open output folder", command=self.open_output, state=DISABLED)
        self.open_output_button.grid(row=0, column=1, padx=(0, 8), pady=2)
        self.open_onnx_folder_button = ttk.Button(results, text="Open ONNX folder", command=self.open_onnx_folder, state=DISABLED)
        self.open_onnx_folder_button.grid(row=0, column=2, padx=(0, 8), pady=2)
        self.copy_onnx_button = ttk.Button(results, text="Copy ONNX path", command=self.copy_onnx_path, state=DISABLED)
        self.copy_onnx_button.grid(row=0, column=3, padx=(0, 8), pady=2)
        results_details = ttk.Frame(self.results_box)
        results_details.grid(row=1, column=0, sticky="ew", pady=(4, 0))
        for column in range(2):
            results_details.columnconfigure(column, weight=1)
        ttk.Label(results_details, textvariable=self.output_image_status, style="Muted.TLabel").grid(row=0, column=0, sticky="w", padx=(0, 12), pady=1)
        ttk.Label(results_details, textvariable=self.onnx_provider, style="Muted.TLabel").grid(row=0, column=1, sticky="w", pady=1)
        ttk.Label(results_details, textvariable=self.last_apply_time, style="Muted.TLabel").grid(row=1, column=0, sticky="w", padx=(0, 12), pady=1)
        ttk.Label(results_details, textvariable=self.preserve_status, style="Muted.TLabel").grid(row=1, column=1, sticky="w", pady=1)
        ttk.Label(self.results_box, textvariable=self.results_status, style="Muted.TLabel").grid(row=2, column=0, sticky="w", pady=(4, 0))
        self.results_box.grid_remove()

        log_box = ttk.LabelFrame(frame, text="Log", padding=8)
        log_box.grid(row=7, column=0, sticky="nsew", pady=(8, 0))
        log_box.columnconfigure(0, weight=1)
        log_box.rowconfigure(0, weight=1)
        self.log = ScrolledText(log_box, height=6, wrap="word", font=("Consolas", 10))
        self.log.grid(row=0, column=0, sticky="nsew")
        self.log.tag_configure("warning", foreground="#8A5A00")
        self.log.tag_configure("complete", foreground="#0B6B3A")
        self.log.tag_configure("cancelled", foreground="#7A4A00")
        self.log.tag_configure("error", foreground="#A32424")
        self.log.configure(state=DISABLED)

    def _on_mousewheel(self, event):
        if not hasattr(self, "main_canvas"):
            return
        delta = -1 if event.delta > 0 else 1
        self.main_canvas.yview_scroll(delta, "units")

    def _state_style(self, state):
        normalized = state.lower()
        if normalized in {"ready", "completed"}:
            return "Ready.TLabel", "#188038"
        if normalized in {"running", "cancelling"}:
            return "Running.TLabel", "#1D5EA8"
        if normalized in {"cancelled", "warning", "cpu only"}:
            return "Warning.TLabel", "#E37400"
        if normalized in {"failed", "not ready"}:
            return "Failed.TLabel", "#C5221F"
        return "Muted.TLabel", "#80868B"

    def _set_run_state(self, state):
        label_style, color = self._state_style(state)
        self.system_status.set(f"Status: {state}")
        self.progress_status.set(f"State: {state}")
        if hasattr(self, "system_status_label"):
            self.system_status_label.configure(style=label_style)
        if hasattr(self, "action_status_label"):
            self.action_status_label.configure(style=label_style)
        if hasattr(self, "status_indicator"):
            self.status_indicator.itemconfigure(self.status_dot, fill=color)

    def toggle_environment_details(self):
        self._details_visible = not self._details_visible
        if self._details_visible:
            self.env_details_label.grid(row=1, column=0, columnspan=6, sticky="w", pady=(8, 0))
            self.env_details_button.configure(text="Hide details")
        else:
            self.env_details_label.grid_remove()
            self.env_details_button.configure(text="Environment details")

    def _update_monitor_details(self):
        directml_text = "yes" if self.env_info.get("directml_available") == "yes" else "no"
        self.monitor_details.set(
            " | ".join(
                [
                    self.current_job.get(),
                    self.current_style.get(),
                    self.process_pid.get(),
                    self.process_cpu.get(),
                    self.onnx_provider.get(),
                    self.last_apply_time.get(),
                    f"DirectML available: {directml_text}",
                    "GPU usage: unavailable",
                ]
            )
        )

    def toggle_monitor_details(self):
        self._monitor_details_visible = not self._monitor_details_visible
        if self._monitor_details_visible:
            self._update_monitor_details()
            self.monitor_details_label.grid(row=5, column=0, sticky="ew", pady=(4, 0))
            self.monitor_details_button.configure(text="Hide run details")
        else:
            self.monitor_details_label.grid_remove()
            self.monitor_details_button.configure(text="Run details")

    def _write_initial_log(self):
        self._append_log("ForJyn Workbench ready.\n")
        self._append_log(f"{training_status_text(self.env_info)}\n")
        self._append_log(f"ONNX apply: {onnx_status_text(self.env_info)}\n")
        self._append_log(f"Output: {rel(OUTPUTS_DIR)}\n")
        self._append_log(environment_details_text(self.env_info) + "\n")
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
        stop_state = NORMAL if self.running and not self.cancel_requested else DISABLED
        self.stop_button.configure(state=stop_state)
        self._update_results_state()

    def _set_inputs_state(self, state):
        self.choose_content_button.configure(state=state)
        self.choose_styles_button.configure(state=state)
        self.generate_refs_button.configure(state=state)
        self.quality_menu.configure(state="readonly" if state == NORMAL else DISABLED)
        self.clean_temp_button.configure(state=state)
        self.open_workbench_button.configure(state=state)
        self._update_results_state()

    def _path_exists(self, path):
        try:
            return bool(path) and Path(path).exists()
        except Exception:
            return False

    def _update_results_state(self):
        if not hasattr(self, "open_output_button"):
            return
        ready = not self.running
        has_output_dir = self._path_exists(self.last_output_dir)
        has_image = self._path_exists(self.last_image_output)
        has_onnx = self._path_exists(self.last_onnx_path)
        has_completed = bool(self.completed_dirs or has_output_dir)

        self.open_result_image_button.configure(state=NORMAL if ready and has_image else DISABLED)
        self.open_output_button.configure(state=NORMAL if ready and has_output_dir else DISABLED)
        self.open_onnx_folder_button.configure(state=NORMAL if ready and has_onnx else DISABLED)
        self.copy_onnx_button.configure(state=NORMAL if ready and has_onnx else DISABLED)

        has_result = has_image or has_onnx or has_output_dir
        if ready and has_result:
            self.results_box.grid()
        else:
            self.results_box.grid_remove()

        if self.running:
            self.results_status.set("Results: running")
        elif has_result:
            self.results_status.set("Results: latest job output available")
        else:
            self.results_status.set("Results: none yet")

    def _update_elapsed_status(self):
        if self.run_started_at is None:
            self.elapsed_time.set("Elapsed: 00:00:00")
            return "00:00:00"
        elapsed = format_elapsed(time.monotonic() - self.run_started_at)
        self.elapsed_time.set(f"Elapsed: {elapsed}")
        return elapsed

    def _collect_process_metrics(self):
        process = self.current_process
        if process is None or process.poll() is not None:
            self._last_cpu_sample = None
            return None, None, None, None
        pid = process.pid
        if psutil is None:
            return pid, None, None, None
        try:
            system_cpu = psutil.cpu_percent(interval=None)
            parent = psutil.Process(pid)
            processes = [parent] + parent.children(recursive=True)
            total_cpu_seconds = 0.0
            total_rss = 0
            for item in processes:
                try:
                    with item.oneshot():
                        cpu_times = item.cpu_times()
                        total_cpu_seconds += float(cpu_times.user + cpu_times.system)
                        total_rss += int(item.memory_info().rss)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            now = time.monotonic()
            cpu_percent = None
            if self._last_cpu_sample is not None:
                previous_time, previous_cpu = self._last_cpu_sample
                elapsed = max(0.001, now - previous_time)
                cpu_percent = max(0.0, (total_cpu_seconds - previous_cpu) / elapsed * 100.0)
            self._last_cpu_sample = (now, total_cpu_seconds)
            return pid, system_cpu, cpu_percent, total_rss / (1024 * 1024)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            self._last_cpu_sample = None
            return pid, None, None, None

    def _refresh_run_monitor(self):
        if not self.running:
            return
        elapsed = self._update_elapsed_status()
        pid, system_cpu, process_cpu, ram_mb = self._collect_process_metrics()
        self.process_pid.set(f"PID: {pid}" if pid else "PID: -")
        cpu_load_text = format_cpu_load(system_cpu)
        process_cpu_text = format_process_cores(process_cpu)
        ram_text = format_ram_mb(ram_mb)
        self.cpu_load.set(f"CPU load: {cpu_load_text}")
        self.process_cpu.set(f"Process CPU: {process_cpu_text}")
        self.process_ram.set(f"RAM: {ram_text}")
        self._update_monitor_details()

        now = time.monotonic()
        heartbeat_interval = FALLBACK_HEARTBEAT_INTERVAL_SECONDS if system_cpu is None and ram_mb is None else HEARTBEAT_INTERVAL_SECONDS
        if pid and now - self._last_heartbeat_at >= heartbeat_interval:
            self._last_heartbeat_at = now
            stage = self.current_stage.get().replace("Stage: ", "").lower()
            self._append_log(
                f"Still running | elapsed {elapsed} | CPU {cpu_load_text} | RAM {ram_text} | stage {stage}\n"
            )
        self.root.after(1000, self._refresh_run_monitor)

    def _append_log(self, text):
        autoscroll = self.log.yview()[1] >= 0.999
        self.log.configure(state=NORMAL)
        for line in text.splitlines(True):
            prefix = f"[{short_time()}] " if line.strip() else ""
            tagged_line = prefix + line
            self.log.insert(END, tagged_line, self._log_tag(line))
        if autoscroll:
            self.log.see(END)
        self.log.configure(state=DISABLED)

    def _log_tag(self, line):
        lower = line.lower()
        if "warning" in lower:
            return "warning"
        if "cancel" in lower:
            return "cancelled"
        if "failed" in lower or "error" in lower:
            return "error"
        if "complete" in lower or "done" in lower:
            return "complete"
        return ()

    def _set_progress_status(self, value):
        self._set_run_state(value)

    def _stage_label(self, stage):
        return {
            "starting": "Starting",
            "training": "Training",
            "exporting": "Exporting ONNX",
            "validating": "Validating",
            "applying": "Applying",
            "done": "Done",
            "failed": "Failed",
            "cancelled": "Cancelled",
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
            self.log_queue.put(("current_job", f"Job ID: {value}"))
        elif key == "STYLE":
            self.log_queue.put(("current_style", f"Style: {value}"))
        elif key == "OUTPUT_DIR":
            self.log_queue.put(("output_dir", value))
        elif key == "ONNX_PATH":
            self.log_queue.put(("onnx_path", value))
        elif key == "IMAGE_OUTPUT":
            self.log_queue.put(("image_output", value))
        elif key in {"ONNX_PROVIDER", "PROVIDER"}:
            self.log_queue.put(("onnx_provider", value))
        elif key == "APPLY_SECONDS":
            self.log_queue.put(("apply_seconds", value))
        elif key == "PRESERVES_SIZE":
            self.log_queue.put(("preserves_size", value))
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
                    if payload not in self.completed_dirs:
                        self.completed_dirs.append(payload)
                    self.output_status.set(f"Output: {payload}")
                    self._update_results_state()
                elif kind == "status":
                    if payload in {"Failed", "Cancelled"}:
                        self._set_progress_status(payload)
                    elif payload == "Done":
                        self._set_progress_status("Completed")
                    elif self.running:
                        self._set_progress_status("Running")
                    self.current_stage.set(f"Stage: {payload}")
                elif kind == "current_job":
                    self.current_job.set(payload)
                    self._update_monitor_details()
                elif kind == "current_style":
                    self.current_style.set(payload)
                    self._update_monitor_details()
                elif kind == "style_progress":
                    self.style_progress.set(payload)
                elif kind == "runtime_output":
                    self.output_status.set(f"Output: {payload}")
                elif kind == "onnx_path":
                    self.last_onnx_path = payload
                    self._append_log(f"ONNX: {payload}\n")
                    self._update_results_state()
                elif kind == "image_output":
                    self.last_image_output = payload
                    self.output_image_status.set(f"Output image: {payload}")
                    self._append_log(f"Image output: {payload}\n")
                    self._update_results_state()
                elif kind == "onnx_provider":
                    self.onnx_provider.set(f"ONNX provider: {payload or 'unknown'}")
                    self.gpu_status.set(
                        f"GPU status: DirectML available {self.env_info.get('directml_available', 'no')}; usage unavailable"
                    )
                    self._update_monitor_details()
                elif kind == "apply_seconds":
                    self.last_apply_time.set(f"Last ONNX apply: {payload}s" if payload else "Last ONNX apply: -")
                    self._update_monitor_details()
                elif kind == "preserves_size":
                    value = "yes" if str(payload).strip().lower() in {"1", "true", "yes"} else "no"
                    self.preserve_status.set(f"Preserves size: {value}")
                elif kind == "process_pid":
                    self.process_pid.set(f"PID: {payload}" if payload else "PID: -")
                    self._update_monitor_details()
                elif kind == "done":
                    was_cancelled = payload == "cancelled"
                    was_successful = payload is True or payload == "completed"
                    self.running = False
                    self.current_process = None
                    self.progress.stop()
                    self.progress.configure(value=0)
                    self.progress.grid_remove()
                    self._set_inputs_state(NORMAL)
                    self.process_pid.set("PID: -")
                    self.cpu_load.set("CPU load: -")
                    self.process_cpu.set("Process CPU: -")
                    self.process_ram.set("RAM: -")
                    self._update_elapsed_status()
                    final_status = "Cancelled" if was_cancelled else "Completed" if was_successful else "Failed"
                    self._set_progress_status(final_status)
                    self.current_stage.set(f"Stage: {final_status}")
                    if was_cancelled:
                        self._append_log("Cancelled. The current job process was stopped.\n")
                    elif was_successful and self.last_output_dir:
                        self._append_log(f"Completed.\nONNX and outputs are in: {self.last_output_dir}\n")
                    elif self.last_output_dir:
                        self._append_log(f"Some jobs failed. Last completed output is in: {self.last_output_dir}\n")
                    elif not was_successful:
                        self._append_log("Failed. Review the log above.\n")
                    self.cancel_requested = False
                    self._update_start_state()
                    self._update_results_state()
                    self._update_monitor_details()
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
        self.last_image_output = None
        self.last_onnx_path = None
        self.last_review_sheet = None
        self.current_backend_job_id = None
        self.current_process = None
        self.cancel_requested = False
        self.run_started_at = time.monotonic()
        self._last_cpu_sample = None
        self._last_heartbeat_at = 0.0
        self.progress.configure(mode="indeterminate")
        self.progress.grid()
        self.progress.start(12)
        self._set_progress_status("Running")
        self.current_stage.set("Stage: Starting")
        self.current_job.set("Job ID: starting")
        self.current_style.set("Style: -")
        self.elapsed_time.set("Elapsed: 00:00:00")
        self.style_progress.set(f"Style progress: 0/{len(self.style_paths)}")
        self.process_pid.set("PID: -")
        self.cpu_load.set("CPU load: -")
        self.process_cpu.set("Process CPU: -")
        self.process_ram.set("RAM: -")
        directml_text = "yes" if self.env_info.get("directml_available") == "yes" else "no"
        self.gpu_status.set(f"GPU status: DirectML available {directml_text}; usage unavailable")
        self.onnx_provider.set("ONNX provider: -")
        self.last_apply_time.set("Last ONNX apply: -")
        self.output_status.set(f"Output: {rel(OUTPUTS_DIR)}")
        self.output_image_status.set("Output image: -")
        self.preserve_status.set("Preserves size: -")
        self._set_inputs_state(DISABLED)
        self._update_start_state()
        self._update_monitor_details()
        self._refresh_run_monitor()
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

    def cancel_current_job(self):
        if not self.running or self.current_process is None:
            return
        self.cancel_requested = True
        self._set_progress_status("Cancelling")
        self.current_stage.set("Stage: Cancelling")
        self.stop_button.configure(state=DISABLED)
        self._append_log("Cancellation requested.\n")
        thread = threading.Thread(target=self._terminate_process_tree, args=(self.current_process,), daemon=True)
        thread.start()

    def _terminate_process_tree(self, process):
        if process is None or process.poll() is not None:
            return
        if psutil is not None:
            try:
                parent = psutil.Process(process.pid)
                targets = parent.children(recursive=True) + [parent]
                unique_targets = []
                seen = set()
                for target in targets:
                    if target.pid in seen:
                        continue
                    seen.add(target.pid)
                    unique_targets.append(target)
                for target in unique_targets:
                    try:
                        target.terminate()
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        continue
                _gone, alive = psutil.wait_procs(unique_targets, timeout=CANCEL_TIMEOUT_SECONDS)
                if alive:
                    self.log_queue.put(("log", "Job did not stop in time; forcing process cleanup.\n"))
                    for target in alive:
                        try:
                            target.kill()
                        except (psutil.NoSuchProcess, psutil.AccessDenied):
                            continue
                    psutil.wait_procs(alive, timeout=2)
                return
            except psutil.NoSuchProcess:
                return
            except Exception as exc:
                self.log_queue.put(("log", f"Process tree cancellation issue: {exc}\n"))
        try:
            process.terminate()
            process.wait(timeout=CANCEL_TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired:
            self.log_queue.put(("log", "Job did not stop in time; forcing process cleanup.\n"))
            process.kill()
        except Exception as exc:
            self.log_queue.put(("log", f"Cancellation issue: {exc}\n"))

    def _run_jobs_worker(self):
        steps = QUALITY_MODES[self.quality.get()]
        all_ok = True
        cancelled = False
        for index, style_path in enumerate(self.style_paths, start=1):
            if self.cancel_requested:
                cancelled = True
                break
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
            self.log_queue.put(("style_progress", f"Style progress: {index}/{len(self.style_paths)}"))
            self.log_queue.put(("current_style", f"Style: {Path(style_path).name}"))
            try:
                env = os.environ.copy()
                env["PYTHONIOENCODING"] = "utf-8"
                env["PYTHONUTF8"] = "1"
                env["PYTHONUNBUFFERED"] = "1"
                creationflags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
                process = subprocess.Popen(
                    command,
                    cwd=str(ROOT),
                    env=env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    stdin=subprocess.DEVNULL,
                    text=True,
                    bufsize=1,
                    encoding="utf-8",
                    errors="replace",
                    creationflags=creationflags,
                )
                self.current_process = process
                self.log_queue.put(("process_pid", process.pid))
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
                if self.current_process is process:
                    self.current_process = None
                self.log_queue.put(("process_pid", None))
                if self.cancel_requested:
                    cancelled = True
                    all_ok = False
                    self.log_queue.put(("status", "Cancelled"))
                    self.log_queue.put(("log", "Job cancelled by user.\n"))
                    break
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
                if self.cancel_requested:
                    cancelled = True
                    all_ok = False
                    self.log_queue.put(("status", "Cancelled"))
                    self.log_queue.put(("log", "Job cancelled by user.\n"))
                    break
                all_ok = False
                self.log_queue.put(("status", "Failed"))
                self.log_queue.put(("log", f"Job failed: {exc}\n"))
            finally:
                process = self.current_process
                if process is not None and process.poll() is not None:
                    self.current_process = None
                    self.log_queue.put(("process_pid", None))
        self.log_queue.put(("done", "cancelled" if cancelled else all_ok))

    def open_output(self):
        target = self.last_output_dir or OUTPUTS_DIR
        if target:
            open_path(target)

    def open_output_image(self):
        if self._path_exists(self.last_image_output):
            open_path(self.last_image_output)

    def open_onnx_folder(self):
        if self._path_exists(self.last_onnx_path):
            open_path(Path(self.last_onnx_path).parent)

    def copy_onnx_path(self):
        if not self.last_onnx_path:
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(str(self.last_onnx_path))
        self.results_status.set("Results: ONNX path copied")
        self._append_log("ONNX path copied to clipboard.\n")

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
        self.last_review_sheet = str(sheet_path)
        self._append_log(f"Review sheet created: {rel(sheet_path)}\n")
        self._update_results_state()
        self.results_status.set(f"Results: review sheet created at {rel(sheet_path)}")
        if sheet_path.exists():
            open_path(sheet_path)

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
        self.generate_started_at = None
        self._last_generation_heartbeat_at = 0.0
        self.reference_state = StringVar(value="State: Ready")
        self.reference_elapsed = StringVar(value="Elapsed: 00:00:00")
        self.reference_cpu_load = StringVar(value="CPU load: -")
        self.reference_ram = StringVar(value="RAM: -")

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
        reference_monitor = ttk.Frame(controls)
        reference_monitor.grid(row=button_row + 4, column=0, columnspan=3, sticky="ew", pady=(12, 0))
        reference_monitor.columnconfigure(1, weight=1)
        self.reference_indicator = tk.Canvas(reference_monitor, width=14, height=14, highlightthickness=0)
        self.reference_indicator.grid(row=0, column=0, sticky="w", padx=(0, 6))
        self.reference_dot = self.reference_indicator.create_oval(2, 2, 12, 12, fill="#80868B", outline="")
        ttk.Label(reference_monitor, textvariable=self.reference_state, style="Muted.TLabel").grid(row=0, column=1, sticky="w")
        self.reference_progress = ttk.Progressbar(reference_monitor, mode="indeterminate")
        self.reference_progress.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(6, 2))
        self.reference_progress.grid_remove()
        ttk.Label(reference_monitor, textvariable=self.reference_elapsed, style="Muted.TLabel").grid(row=2, column=0, columnspan=2, sticky="w")
        ttk.Label(controls, textvariable=self.status, wraplength=290).grid(row=button_row + 5, column=0, columnspan=3, sticky="w", pady=(12, 0))

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
        if busy:
            self.reference_progress.grid()
            self.reference_progress.start(12)
            self._set_reference_state("Generating references")
        else:
            self.reference_progress.stop()
            self.reference_progress.configure(value=0)
            self.reference_progress.grid_remove()
        self._update_save_state()

    def _set_reference_state(self, state):
        self.reference_state.set(f"State: {state}")
        color = "#1D5EA8" if state.lower().startswith("generating") else "#188038" if state == "Ready" else "#80868B"
        if "failed" in state.lower():
            color = "#C5221F"
        if hasattr(self, "reference_indicator"):
            self.reference_indicator.itemconfigure(self.reference_dot, fill=color)

    def _reference_metrics(self):
        if psutil is None:
            return None, None
        try:
            cpu = psutil.cpu_percent(interval=None)
            ram_mb = psutil.Process(os.getpid()).memory_info().rss / (1024 * 1024)
            return cpu, ram_mb
        except Exception:
            return None, None

    def _refresh_reference_monitor(self):
        if self.closed or not self.busy:
            return
        elapsed = format_elapsed(time.monotonic() - self.generate_started_at) if self.generate_started_at else "00:00:00"
        cpu, ram_mb = self._reference_metrics()
        cpu_text = format_cpu_load(cpu)
        ram_text = format_ram_mb(ram_mb)
        self.reference_elapsed.set(f"Elapsed: {elapsed}")
        self.reference_cpu_load.set(f"CPU load: {cpu_text}")
        self.reference_ram.set(f"RAM: {ram_text}")
        now = time.monotonic()
        if now - self._last_generation_heartbeat_at >= HEARTBEAT_INTERVAL_SECONDS:
            self._last_generation_heartbeat_at = now
            self.log_callback(f"Generating references | elapsed {elapsed} | CPU load {cpu_text} | RAM {ram_text}\n")
        self.window.after(1000, self._refresh_reference_monitor)

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
        self.generate_started_at = time.monotonic()
        self._last_generation_heartbeat_at = self.generate_started_at
        self.reference_elapsed.set("Elapsed: 00:00:00")
        self.reference_cpu_load.set("CPU load: -")
        self.reference_ram.set("RAM: -")
        self.status.set("Generating references...")
        self.selection_status.set("Generating...")
        self.generated_paths = []
        self.selected_path = None
        self._render_previews([])
        self.selection_status.set("Generating...")
        self.log_callback(f"Generating references: {params['preset']} x{params['count']}\n")
        thread = threading.Thread(target=self._generate_worker, args=(params,), daemon=True)
        thread.start()
        self._refresh_reference_monitor()
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
                    elapsed = format_elapsed(time.monotonic() - self.generate_started_at) if self.generate_started_at else "00:00:00"
                    cpu, ram_mb = self._reference_metrics()
                    self.reference_elapsed.set(f"Elapsed: {elapsed}")
                    self.reference_cpu_load.set(f"CPU load: {format_cpu_load(cpu)}")
                    self.reference_ram.set(f"RAM: {format_ram_mb(ram_mb)}")
                    self.status.set(f"Generated {len(self.generated_paths)} variations. Contact sheet: {rel(payload['contact_sheet'])}")
                    if self.selected_path:
                        self.selection_status.set(f"Selected: {Path(self.selected_path).name}")
                    self.log_callback(f"Generated reference variations in {elapsed}: {rel(payload['temp_dir'])}\n")
                    if retry_total or quality_failures:
                        self.log_callback(f"Reference quality guard: retries {retry_total}, kept after failed checks {quality_failures}.\n")
                    self._set_busy(False)
                    self._set_reference_state("Ready")
                elif kind == "error":
                    self.status.set(f"Generation failed: {payload}")
                    self.selection_status.set("Generation failed")
                    self.log_callback(f"Reference generation failed: {payload}\n")
                    messagebox.showerror("Reference generation failed", str(payload))
                    self._set_busy(False)
                    self._set_reference_state("Failed")
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
    print("Run monitor: available")
    print("Stop/Cancel: available")
    print(f"Process metrics: {'psutil' if psutil is not None else 'basic'}")
    print("CPU load metric: available" if psutil is not None else "CPU load metric: unavailable")
    print("Process CPU units: cores")
    print("GPU usage: unavailable")
    print("Reference generation feedback: available")
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
