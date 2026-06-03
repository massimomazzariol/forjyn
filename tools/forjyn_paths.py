import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKBENCH_ENV_VAR = "FORJYN_WORKBENCH_ROOT"


def workbench_root():
    configured = os.environ.get(WORKBENCH_ENV_VAR)
    if not configured:
        return ROOT / "workbench"
    candidate = Path(configured).expanduser()
    if candidate.is_absolute():
        return candidate.resolve()
    return (ROOT / candidate).resolve()


WORKBENCH = workbench_root()
MANUAL_REFERENCES_DIR = WORKBENCH / "manual-references"
FINAL_CANDIDATES_DIR = WORKBENCH / "final-candidates"
GENERATED_REFERENCES_DIR = WORKBENCH / "generated-references"
SAVED_REFERENCES_DIR = GENERATED_REFERENCES_DIR / "saved"
CONTACT_SHEETS_DIR = GENERATED_REFERENCES_DIR / "contact-sheets"
OUTPUTS_DIR = WORKBENCH / "outputs"
REVIEWS_DIR = WORKBENCH / "reviews"

RUNTIME_DIR = WORKBENCH / "_runtime"
RUNTIME_CACHE_DIR = RUNTIME_DIR / "cache"
TORCH_CACHE_DIR = RUNTIME_CACHE_DIR / "torch"
RUNTIME_TORCH_DIR = RUNTIME_DIR / "torch"
RUNTIME_ONNX_DIR = RUNTIME_DIR / "onnx"
RUNTIME_MODELS_DIR = RUNTIME_DIR / "models"
RUNTIME_REPORTS_DIR = RUNTIME_DIR / "reports"
RUNTIME_LOGS_DIR = RUNTIME_DIR / "logs"

TEMP_REFERENCES_DIR = RUNTIME_CACHE_DIR / "generated-references-temp"
REFERENCE_METADATA_DIR = RUNTIME_REPORTS_DIR / "generated-reference-metadata"
REFERENCE_REVIEW_DIR = RUNTIME_REPORTS_DIR / "generated-reference-review"
STARTER_PACK_DIR = FINAL_CANDIDATES_DIR / "starter-pack"

WORKBENCH_DIRS = [
    WORKBENCH,
    MANUAL_REFERENCES_DIR,
    FINAL_CANDIDATES_DIR,
    GENERATED_REFERENCES_DIR,
    SAVED_REFERENCES_DIR,
    CONTACT_SHEETS_DIR,
    OUTPUTS_DIR,
    REVIEWS_DIR,
    RUNTIME_DIR,
    RUNTIME_CACHE_DIR,
    TORCH_CACHE_DIR,
    RUNTIME_TORCH_DIR,
    RUNTIME_ONNX_DIR,
    RUNTIME_MODELS_DIR,
    RUNTIME_REPORTS_DIR,
    RUNTIME_LOGS_DIR,
]


def ensure_workbench_dirs():
    for path in WORKBENCH_DIRS:
        path.mkdir(parents=True, exist_ok=True)
