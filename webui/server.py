import argparse
import difflib
import json
import mimetypes
import os
import re
import socket
import subprocess
import sys
import tempfile
import threading
import traceback
import urllib.error
import urllib.parse
import urllib.request
import uuid
from dataclasses import asdict, dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Dict, List, Optional, Tuple


ROOT_DIR = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = ROOT_DIR / "scripts"
STATIC_DIR = Path(__file__).resolve().parent / "static"
CONFIG_DIR = ROOT_DIR / "config"
BOOTSTRAP_MANIFEST_PATH = CONFIG_DIR / "bootstrap.manifest.json"
MAX_SCAN_FILES = 800
MAX_TREE_ITEMS = 400
MAX_CONTEXT_FILES = 4
MAX_FILE_CHARS = 3600
MAX_TOTAL_CONTEXT = 12000
MAX_FOCUSED_CHAT_FILE_CHARS = 22000
MAX_FOCUSED_CHAT_TOTAL_CHARS = 22000
MAX_PREVIEW_CHAT_CHARS = 22000
MAX_TREE_CONTEXT_ITEMS = 30
MAX_CHAT_HISTORY_ITEMS = 4
ATTACH_PROJECT_TIMEOUT_SECONDS = 180
START_SERVER_TIMEOUT_SECONDS = 120
MODEL_PORTS = {
    "qwen": 8080,
    "gemma4": 8081,
}
MODEL_DEFAULT_CONTEXT = {
    "qwen": 16384,
    "gemma4": 4096,
}
MODEL_CHAT_MAX_TOKENS = {
    "qwen": 1400,
    "gemma4": 3200,
}
MODEL_ANALYZE_MAX_TOKENS = {
    "qwen": 1600,
    "gemma4": 2800,
}
MODEL_CHAT_TIMEOUT_SECONDS = {
    "qwen": 180,
    "gemma4": 240,
}
MODEL_ANALYZE_TIMEOUT_SECONDS = {
    "qwen": 180,
    "gemma4": 240,
}
MODEL_HISTORY_LIMIT = {
    "qwen": 4,
    "gemma4": 1,
}
MODEL_CONTEXT_LIMITS = {
    "qwen": {"max_files": 4, "file_chars": 3600, "total_chars": 12000, "single_file_chars": 22000, "single_total_chars": 22000},
    "gemma4": {"max_files": 2, "file_chars": 2600, "total_chars": 9000, "single_file_chars": 18000, "single_total_chars": 18000},
}
IGNORED_DIRS = {
    ".git", ".hg", ".svn", "node_modules", ".venv", "venv", "__pycache__",
    "dist", "build", "target", "out", ".idea", ".vscode", ".next", ".nuxt", ".cache", "coverage",
}
IGNORED_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".ico", ".pdf", ".zip", ".7z", ".gz",
    ".tar", ".rar", ".exe", ".dll", ".so", ".dylib", ".class", ".jar", ".pyc", ".pyo", ".db",
    ".sqlite", ".mp3", ".mp4", ".mov", ".avi",
}
LANGUAGE_BY_EXTENSION = {
    ".py": "Python", ".js": "JavaScript", ".jsx": "JavaScript", ".ts": "TypeScript", ".tsx": "TypeScript",
    ".java": "Java", ".kt": "Kotlin", ".go": "Go", ".rs": "Rust", ".php": "PHP", ".rb": "Ruby", ".cs": "C#",
    ".cpp": "C++", ".cc": "C++", ".cxx": "C++", ".c": "C", ".h": "C/C++ Header", ".hpp": "C/C++ Header",
    ".swift": "Swift", ".m": "Objective-C", ".mm": "Objective-C++", ".scala": "Scala", ".sql": "SQL",
    ".html": "HTML", ".css": "CSS", ".scss": "SCSS", ".vue": "Vue", ".svelte": "Svelte", ".json": "JSON",
    ".yml": "YAML", ".yaml": "YAML", ".toml": "TOML", ".xml": "XML", ".sh": "Shell", ".bat": "Batch",
    ".cmd": "Batch", ".ps1": "PowerShell", ".md": "Markdown",
}
DEFAULT_ANALYSIS_PROMPT = (
    "請先分析這個專案架構，說明入口、核心模組、主要流程、設定檔、測試位置，"
    "並指出你判斷依據來自哪些檔案。若資訊不足，請明確標示不確定。"
)
TASK_OPEN_PROJECT = "open-project"
TASK_REDOWNLOAD_MODEL = "redownload-model"
MAX_EDIT_FILES = 3
MAX_EDIT_FILE_CHARS = 4200
MAX_EDIT_TOTAL_CHARS = 14000
MAX_EDIT_SINGLE_FILE_CHARS = 22000
MAX_ADVISORY_FILE_CHARS = 18000
EDIT_PLAN_TIMEOUT_SECONDS = 300
GEMMA4_LOCATOR_MAX_TOKENS = 320
GEMMA4_PATCH_MAX_TOKENS = 700
GEMMA4_PRECISE_MAX_TOKENS = 720
GEMMA4_ADVISORY_MAX_TOKENS = 820
CSHARP_RESERVED_IDENTIFIERS = {
    "if", "else", "switch", "case", "break", "return", "true", "false", "null",
    "new", "var", "int", "long", "short", "byte", "float", "double", "decimal",
    "bool", "string", "char", "object", "void", "public", "private", "protected",
    "internal", "static", "readonly", "async", "await", "foreach", "for", "while",
    "do", "try", "catch", "finally", "using", "namespace", "class", "struct",
    "partial", "this", "base", "out", "ref", "in", "params",
}
CSHARP_ALLOWED_GLOBAL_IDENTIFIERS = {
    "Keys", "Math", "Color", "Point", "Path", "AppContext", "Form",
    "EventArgs", "KeyEventArgs", "Enumerable", "Array", "Task", "List",
    "Dictionary", "HashSet",
}


@dataclass
class ProjectFile:
    path: str
    size: int
    language: str


@dataclass
class SessionState:
    project_path: Optional[str] = None
    model_key: str = "qwen"
    model_alias: str = "qwen-local"
    summary: str = ""
    tree: List[str] = field(default_factory=list)
    files: List[ProjectFile] = field(default_factory=list)
    entrypoints: List[str] = field(default_factory=list)
    tests: List[str] = field(default_factory=list)
    pinned_files: List[str] = field(default_factory=list)
    current_preview_path: Optional[str] = None
    history: List[Dict[str, str]] = field(default_factory=list)
    pending_edit: Optional[Dict[str, object]] = None
    ui_state: str = "idle"


@dataclass
class TaskState:
    id: str
    kind: str
    status: str = "pending"
    progress: int = 0
    step: str = ""
    message: str = ""
    error: Optional[Dict[str, object]] = None
    result: Optional[Dict[str, object]] = None


STATE = SessionState()
TASKS: Dict[str, TaskState] = {}
STATE_LOCK = threading.Lock()
TASK_LOCK = threading.Lock()
HF_API_HEADERS = {
    "User-Agent": "CodeWorkerWebUI/2.0",
    "Accept": "application/json",
}
DETACHED_FLAGS = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
MODEL_SERVER_PROCESSES: Dict[Tuple[str, int], subprocess.Popen] = {}
MODEL_SERVER_LOG_HANDLES: Dict[Tuple[str, int], Tuple[object, object]] = {}


def get_model_key_from_alias(model_alias: str) -> str:
    lowered = (model_alias or "").lower()
    if lowered.startswith("gemma4"):
        return "gemma4"
    return "qwen"


def get_model_port(model_name: str) -> int:
    model_key = get_model_key_from_alias(model_name)
    return MODEL_PORTS.get(model_key, MODEL_PORTS["qwen"])


def get_model_endpoint(model_name: str) -> str:
    return f"http://127.0.0.1:{get_model_port(model_name)}/v1/chat/completions"


def get_model_context_limit(model_key: str) -> int:
    return MODEL_DEFAULT_CONTEXT.get(model_key, MODEL_DEFAULT_CONTEXT["qwen"])


def get_chat_history_limit(model_key: str) -> int:
    return MODEL_HISTORY_LIMIT.get(model_key, MODEL_HISTORY_LIMIT["qwen"])


def get_chat_max_tokens(model_key: str) -> int:
    return MODEL_CHAT_MAX_TOKENS.get(model_key, MODEL_CHAT_MAX_TOKENS["qwen"])


def get_analyze_max_tokens(model_key: str) -> int:
    return MODEL_ANALYZE_MAX_TOKENS.get(model_key, MODEL_ANALYZE_MAX_TOKENS["qwen"])


def get_chat_timeout_seconds(model_key: str) -> int:
    return MODEL_CHAT_TIMEOUT_SECONDS.get(model_key, MODEL_CHAT_TIMEOUT_SECONDS["qwen"])


def get_analyze_timeout_seconds(model_key: str) -> int:
    return MODEL_ANALYZE_TIMEOUT_SECONDS.get(model_key, MODEL_ANALYZE_TIMEOUT_SECONDS["qwen"])


def get_context_limits(model_key: str, single_file_focus: bool) -> Dict[str, int]:
    limits = MODEL_CONTEXT_LIMITS.get(model_key, MODEL_CONTEXT_LIMITS["qwen"]).copy()
    if single_file_focus:
        limits["file_chars"] = limits["single_file_chars"]
        limits["total_chars"] = limits["single_total_chars"]
    return limits


def make_error(
    code: str,
    message: str,
    details: str = "",
    action: Optional[str] = None,
    log_path: Optional[str] = None,
    extra: Optional[Dict[str, object]] = None,
) -> Dict[str, object]:
    payload: Dict[str, object] = {
        "code": code,
        "message": message,
        "details": details,
    }
    if action:
        payload["action"] = action
    if log_path:
        payload["logPath"] = log_path
    if extra:
        payload.update(extra)
    return payload


def json_response(handler: BaseHTTPRequestHandler, payload: Dict, status: int = 200) -> None:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
    handler.send_header("Pragma", "no-cache")
    handler.send_header("Expires", "0")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def error_response(handler: BaseHTTPRequestHandler, error: Dict[str, object], status: int = 400) -> None:
    json_response(handler, {"ok": False, "error": error}, status=status)


def text_response(handler: BaseHTTPRequestHandler, body: str, status: int = 200, content_type: str = "text/plain; charset=utf-8") -> None:
    data = body.encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", content_type)
    handler.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
    handler.send_header("Pragma", "no-cache")
    handler.send_header("Expires", "0")
    handler.send_header("Content-Length", str(len(data)))
    handler.end_headers()
    handler.wfile.write(data)


def normalize_path(input_path: str) -> Path:
    return Path(os.path.expandvars(input_path)).expanduser().resolve()


def create_task(kind: str) -> TaskState:
    task = TaskState(id=uuid.uuid4().hex, kind=kind)
    with TASK_LOCK:
        TASKS[task.id] = task
    return task


def update_task(task_id: str, **changes: object) -> None:
    with TASK_LOCK:
        task = TASKS[task_id]
        for key, value in changes.items():
            setattr(task, key, value)


def get_task(task_id: str) -> Optional[TaskState]:
    with TASK_LOCK:
        return TASKS.get(task_id)


def clear_session(ui_state: str = "idle") -> None:
    with STATE_LOCK:
        STATE.project_path = None
        STATE.model_key = "qwen"
        STATE.model_alias = "qwen-local"
        STATE.summary = ""
        STATE.tree = []
        STATE.files = []
        STATE.entrypoints = []
        STATE.tests = []
        STATE.pinned_files = []
        STATE.current_preview_path = None
        STATE.history = []
        STATE.pending_edit = None
        STATE.ui_state = ui_state


def run_script(script_name: str, *args: str, timeout_seconds: Optional[int] = None) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GCM_INTERACTIVE"] = "Never"
    return subprocess.run(
        ["cmd", "/c", str(SCRIPTS_DIR / script_name), *args],
        cwd=str(ROOT_DIR),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        timeout=timeout_seconds,
        env=env,
    )


def run_script_via_log(script_name: str, *args: str, timeout_seconds: Optional[int] = None) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GCM_INTERACTIVE"] = "Never"
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w+b",
            suffix=".log",
            prefix=f"{Path(script_name).stem}-",
            dir=str(ROOT_DIR / "logs"),
            delete=False,
        ) as handle:
            temp_path = handle.name
            completed = subprocess.run(
                ["cmd", "/c", str(SCRIPTS_DIR / script_name), *args],
                cwd=str(ROOT_DIR),
                stdout=handle,
                stderr=subprocess.STDOUT,
                check=False,
                timeout=timeout_seconds,
                env=env,
            )
        stdout = Path(temp_path).read_text(encoding="utf-8", errors="replace")
        return subprocess.CompletedProcess(
            args=completed.args,
            returncode=completed.returncode,
            stdout=stdout,
            stderr="",
        )
    except subprocess.TimeoutExpired as exc:
        output = ""
        if temp_path and Path(temp_path).exists():
            output = Path(temp_path).read_text(encoding="utf-8", errors="replace")
        raise subprocess.TimeoutExpired(exc.cmd, exc.timeout, output=output, stderr="") from exc
    finally:
        if temp_path and Path(temp_path).exists():
            Path(temp_path).unlink()


def load_bootstrap_manifest() -> Dict[str, object]:
    return json.loads(BOOTSTRAP_MANIFEST_PATH.read_text(encoding="utf-8"))


def get_model_manifest(model_key: str) -> Dict[str, object]:
    manifest = load_bootstrap_manifest()
    models = manifest.get("models", {})
    model = models.get(model_key)
    if not isinstance(model, dict):
        raise ValueError(f"Model config not found: {model_key}")
    return model


def is_regex_pattern(pattern: str) -> bool:
    return bool(re.search(r"[\\^$*+?{}\[\]|()]", pattern))


def resolve_huggingface_filename(repo: str, file_pattern: str) -> str:
    if not is_regex_pattern(file_pattern):
        return file_pattern

    request = urllib.request.Request(
        f"https://huggingface.co/api/models/{repo}",
        headers=HF_API_HEADERS,
        method="GET",
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        body = json.loads(response.read().decode("utf-8"))
    siblings = body.get("siblings", [])
    candidates = [
        item.get("rfilename", "")
        for item in siblings
        if isinstance(item, dict) and re.fullmatch(file_pattern, item.get("rfilename", ""))
    ]
    if not candidates:
        raise ValueError(f"No Hugging Face file matched pattern: {file_pattern}")
    return sorted(candidates)[0]


def human_size(num_bytes: int) -> str:
    value = float(num_bytes)
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if value < 1024 or unit == "TB":
            if unit == "B":
                return f"{int(value)} {unit}"
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{int(num_bytes)} B"


def validate_model_file(model_path: Path) -> None:
    if not model_path.exists():
        raise ValueError(f"Model file not found: {model_path}")
    if not model_path.is_file():
        raise ValueError(f"Model path is not a file: {model_path}")
    size = model_path.stat().st_size
    if size <= 0:
        raise ValueError(f"Model file is empty: {model_path}")


def check_minimum_memory() -> None:
    if os.name != "nt":
        return
    command = "[int64](Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory"
    result = subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        timeout=15,
    )
    if result.returncode != 0:
        return
    try:
        total = int(result.stdout.strip())
    except ValueError:
        return
    if total <= 0:
        return
    if total < 16 * 1024 * 1024 * 1024:
        raise RuntimeError(
            json.dumps(
                make_error(
                    "RUNTIME_INVALID",
                    "Need at least 16GB RAM.",
                    f"Detected: {total / (1024 * 1024 * 1024):.1f} GB",
                )
            )
        )


def resolve_model_details(model_key: str) -> Tuple[Path, str]:
    if model_key == "gemma4":
        return ROOT_DIR / "models" / "gemma4-e4b-it-q4", "gemma4-local"
    return ROOT_DIR / "models" / "qwen2.5-coder-7b-instruct-q4", "qwen-local"


def find_model_file(model_dir: Path) -> Optional[Path]:
    matches = sorted(model_dir.glob("*.gguf"))
    return matches[0] if matches else None


def query_models(port: int, timeout_sec: int = 2) -> Optional[Dict[str, object]]:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/v1/models", timeout=timeout_sec) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception:
        return None


def is_model_ready(model_alias: str, port: int) -> bool:
    payload = query_models(port)
    if not payload:
        return False
    data = payload.get("data", [])
    return any(isinstance(item, dict) and item.get("id") == model_alias for item in data)


def is_port_listening(port: int) -> bool:
    if os.name != "nt":
        return False
    result = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            f"try {{ $listener = Get-NetTCPConnection -LocalPort {port} -State Listen -ErrorAction Stop; if ($listener) {{ exit 0 }} else {{ exit 1 }} }} catch {{ exit 1 }}",
        ],
        check=False,
        timeout=10,
    )
    return result.returncode == 0


def get_listening_pid(port: int) -> Optional[int]:
    if os.name != "nt":
        return None
    result = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            f"try {{ (Get-NetTCPConnection -LocalPort {port} -State Listen -ErrorAction Stop | Select-Object -First 1 -ExpandProperty OwningProcess) }} catch {{ '' }}",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        timeout=10,
    )
    text = result.stdout.strip()
    if text.isdigit():
        return int(text)
    return None


def get_process_commandline(pid: int) -> str:
    result = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            f"try {{ (Get-CimInstance Win32_Process -Filter \"ProcessId = {pid}\" -ErrorAction Stop).CommandLine }} catch {{ '' }}",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        timeout=15,
    )
    return result.stdout.strip()


def kill_process(pid: int) -> bool:
    result = subprocess.run(
        ["taskkill", "/PID", str(pid), "/F"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        timeout=15,
    )
    return result.returncode == 0


def try_reclaim_codeworker_port(port: int) -> Optional[str]:
    pid = get_listening_pid(port)
    if not pid:
        return None
    commandline = get_process_commandline(pid)
    lowered = commandline.lower()
    if "codeworker" in lowered and ("launch_llama_server.py" in lowered or "llama-server.exe" in lowered):
        if kill_process(pid):
            for _ in range(10):
                if not is_port_listening(port):
                    return f"Reclaimed CodeWorker model port {port} by stopping PID {pid}."
                threading.Event().wait(1)
            return f"Attempted to reclaim CodeWorker model port {port}, but it is still listening."
        return f"Failed to stop stale CodeWorker model server on PID {pid}."
    return f"Port {port} is occupied by PID {pid}: {commandline or 'unknown process'}"


def ensure_runtime_and_model(model_key: str) -> Tuple[Path, str]:
    llama_server = ROOT_DIR / "runtime" / "llama.cpp" / "llama-server.exe"
    if not llama_server.exists():
        runtime = run_script("bootstrap.cmd", "-SkipModels", timeout_seconds=300)
        if runtime.returncode != 0 or not llama_server.exists():
            raise RuntimeError(
                json.dumps(
                    make_error(
                        "RUNTIME_MISSING",
                        "Failed to prepare llama.cpp runtime.",
                        runtime.stdout + runtime.stderr,
                    )
                )
            )

    model_dir, model_alias = resolve_model_details(model_key)
    model_file = find_model_file(model_dir)
    if model_file is None:
        bootstrap = run_script("bootstrap.cmd", "-SkipRuntime", "-Models", model_key, timeout_seconds=1800)
        model_file = find_model_file(model_dir)
        if bootstrap.returncode != 0 or model_file is None:
            raise RuntimeError(
                json.dumps(
                    make_error(
                        "MODEL_MISSING",
                        "Failed to prepare model.",
                        bootstrap.stdout + bootstrap.stderr,
                        extra={"modelKey": model_key},
                    )
                )
            )
    validate_model_file(model_file)
    return model_file, model_alias


def ensure_local_model_server(model_key: str, port: Optional[int] = None) -> Dict[str, object]:
    if model_key not in {"qwen", "gemma4"}:
        raise RuntimeError(json.dumps(make_error("MODEL_START_FAILED", "Unknown model.", model_key)))
    port = port or get_model_port(model_key)

    check_minimum_memory()
    model_file, model_alias = ensure_runtime_and_model(model_key)
    llama_server = ROOT_DIR / "runtime" / "llama.cpp" / "llama-server.exe"

    if is_model_ready(model_alias, port):
        return {"modelAlias": model_alias, "logPath": None, "alreadyRunning": True}

    if is_port_listening(port):
        reclaim_details = try_reclaim_codeworker_port(port)
        if is_model_ready(model_alias, port):
            return {"modelAlias": model_alias, "logPath": None, "alreadyRunning": True}
        if is_port_listening(port):
            raise RuntimeError(
                json.dumps(
                    make_error(
                        "MODEL_START_FAILED",
                        "Port is already in use.",
                        reclaim_details or f"Port {port} is occupied by another process.",
                        extra={"modelKey": model_key},
                    )
                )
            )

    stamp = subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", "[DateTime]::Now.ToString('yyyyMMdd-HHmmss')"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        timeout=10,
    ).stdout.strip() or "unknown"
    log_path = ROOT_DIR / "logs" / f"llama-server-{model_key}-{stamp}.log"
    err_path = ROOT_DIR / "logs" / f"llama-server-{model_key}-{stamp}.err.log"
    subprocess.Popen(
        [
            sys.executable,
            str(SCRIPTS_DIR / "launch_llama_server.py"),
            "--server", str(llama_server),
            "--host", "127.0.0.1",
            "--port", str(port),
            "--alias", model_alias,
            "--model", str(model_file),
            "--context", str(get_model_context_limit(model_key)),
            "--threads", str(os.cpu_count() or 4),
            "--log", str(log_path),
            "--err", str(err_path),
        ],
        cwd=str(ROOT_DIR),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=DETACHED_FLAGS,
        close_fds=True,
    )

    for _ in range(60):
        if is_model_ready(model_alias, port):
            return {"modelAlias": model_alias, "logPath": str(log_path), "alreadyRunning": False}
        threading.Event().wait(2)

    details = ""
    if log_path.exists():
        details = log_path.read_text(encoding="utf-8", errors="replace")[-6000:]
    raise RuntimeError(
        json.dumps(
            make_error(
                "MODEL_START_FAILED",
                "Server failed to become ready.",
                details or str(log_path),
                log_path=str(log_path),
                extra={"modelKey": model_key},
            )
        )
    )


def download_model_with_progress(task_id: str, model_key: str) -> Tuple[Path, int]:
    model_config = get_model_manifest(model_key)
    if not model_config.get("enabled", False):
        raise RuntimeError(
            json.dumps(
                make_error(
                    "MODEL_INVALID",
                    "Model is disabled in bootstrap manifest.",
                    f"modelKey={model_key}",
                    extra={"modelKey": model_key},
                )
            )
        )
    if model_config.get("provider") != "huggingface":
        raise RuntimeError(
            json.dumps(
                make_error(
                    "MODEL_DOWNLOAD_FAILED",
                    "Only Hugging Face model downloads are supported in the web UI.",
                    f"provider={model_config.get('provider', '')}",
                    extra={"modelKey": model_key},
                )
            )
        )

    repo = str(model_config.get("repo", "")).strip()
    file_pattern = str(model_config.get("filePattern", "")).strip()
    target_dir = ROOT_DIR / str(model_config.get("targetDir", "")).strip()
    if not repo or not file_pattern or not str(model_config.get("targetDir", "")).strip():
        raise RuntimeError(
            json.dumps(
                make_error(
                    "MODEL_INVALID",
                    "Model manifest is incomplete.",
                    f"repo={repo}, filePattern={file_pattern}, targetDir={model_config.get('targetDir', '')}",
                    extra={"modelKey": model_key},
                )
            )
        )

    update_task(task_id, progress=8, step="解析模型來源", message="正在取得模型檔資訊")
    filename = resolve_huggingface_filename(repo, file_pattern)
    download_url = f"https://huggingface.co/{repo}/resolve/main/{urllib.parse.quote(filename)}?download=true"

    target_dir.mkdir(parents=True, exist_ok=True)
    final_path = target_dir / Path(filename).name
    part_path = final_path.with_suffix(final_path.suffix + ".part")
    if part_path.exists():
        part_path.unlink()

    update_task(task_id, progress=12, step="準備下載", message=f"即將下載 {final_path.name}")
    request = urllib.request.Request(download_url, headers=HF_API_HEADERS, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            content_length = response.headers.get("Content-Length")
            total_bytes = int(content_length) if content_length and content_length.isdigit() else 0
            bytes_written = 0
            chunk_size = 1024 * 1024
            with open(part_path, "wb") as handle:
                while True:
                    chunk = response.read(chunk_size)
                    if not chunk:
                        break
                    handle.write(chunk)
                    bytes_written += len(chunk)
                    if total_bytes > 0:
                        progress = 12 + int((bytes_written / total_bytes) * 83)
                        progress = max(12, min(progress, 95))
                        message = f"已下載 {human_size(bytes_written)} / {human_size(total_bytes)}"
                    else:
                        progress = 12
                        message = f"已下載 {human_size(bytes_written)}"
                    update_task(task_id, progress=progress, step="重新下載模型", message=message)

        if final_path.exists():
            final_path.unlink()
        os.replace(part_path, final_path)
        validate_model_file(final_path)
        return final_path, final_path.stat().st_size
    except Exception:
        if part_path.exists():
            part_path.unlink()
        raise


def choose_folder() -> Dict[str, object]:
    tkinter_script = """
import json
import tkinter as tk
from tkinter import filedialog

root = tk.Tk()
root.withdraw()
root.attributes("-topmost", True)
root.lift()
root.update()
selected = filedialog.askdirectory(
    parent=root,
    title="選擇專案資料夾",
    mustexist=True,
) or ""
print(json.dumps({"path": selected}))
root.destroy()
"""
    picker_env = os.environ.copy()
    picker_env["PYTHONIOENCODING"] = "utf-8"
    picker_env["PYTHONUTF8"] = "1"
    result = subprocess.run(
        [sys.executable, "-c", tkinter_script],
        cwd=str(ROOT_DIR),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        timeout=300,
        env=picker_env,
    )
    if result.returncode != 0:
        details = (result.stderr or result.stdout).strip()
        raise RuntimeError(details or "Folder picker process failed.")
    try:
        payload = json.loads(result.stdout.strip() or "{}")
    except json.JSONDecodeError as exc:
        raise RuntimeError(result.stdout.strip() or "Folder picker returned invalid payload.") from exc
    selected = str(payload.get("path", "")).strip()
    return {"canceled": not bool(selected), "path": selected}


def collect_project_files(project_root: Path) -> List[ProjectFile]:
    results: List[ProjectFile] = []
    ignored_dirs = {item.lower() for item in IGNORED_DIRS}
    for root, dirs, files in os.walk(project_root):
        dirs[:] = [item for item in dirs if item.lower() not in ignored_dirs]
        for filename in files:
            path = Path(root) / filename
            if path.suffix.lower() in IGNORED_EXTENSIONS:
                continue
            try:
                stat = path.stat()
            except OSError:
                continue
            if stat.st_size > 512_000:
                continue
            results.append(
                ProjectFile(
                    path=path.relative_to(project_root).as_posix(),
                    size=stat.st_size,
                    language=LANGUAGE_BY_EXTENSION.get(path.suffix.lower(), "Other"),
                )
            )
            if len(results) >= MAX_SCAN_FILES:
                return sorted(results, key=lambda item: item.path.lower())
    return sorted(results, key=lambda item: item.path.lower())


def detect_entrypoints(file_paths: List[str]) -> List[str]:
    patterns = [
        r"(^|/)(package\.json|pyproject\.toml|requirements\.txt|go\.mod|cargo\.toml|pom\.xml|build\.gradle|build\.gradle\.kts)$",
        r"(^|/)(app|main|index|server|manage)\.(py|js|ts|tsx|jsx|go|rs|php|rb|cs|java)$",
        r"(^|/)src/(main|index|app|server)\.(ts|tsx|js|jsx|py|go|rs)$",
    ]
    return [path for path in file_paths if any(re.search(pattern, path.lower()) for pattern in patterns)][:12]


def detect_test_locations(file_paths: List[str]) -> List[str]:
    return [
        path for path in file_paths
        if any(token in path.lower() for token in ["/test", "/tests", "__tests__", ".spec.", ".test."])
    ][:20]


def language_breakdown(files: List[ProjectFile]) -> List[str]:
    counts: Dict[str, int] = {}
    for file in files:
        counts[file.language] = counts.get(file.language, 0) + 1
    ordered = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    return [f"{name}: {count}" for name, count in ordered[:10]]


def build_summary(project_root: Path, files: List[ProjectFile], entrypoints: List[str], tests: List[str]) -> str:
    total_size = sum(file.size for file in files)
    lines = [
        f"專案路徑: {project_root}",
        f"檔案數量(已掃描): {len(files)}",
        f"估計文字檔總大小: {total_size} bytes",
        "主要語言: " + (", ".join(language_breakdown(files)) if files else "無"),
        "可能入口檔案: " + (", ".join(entrypoints[:8]) if entrypoints else "未明確找到"),
        "測試相關檔案: " + (", ".join(tests[:8]) if tests else "未明確找到"),
    ]
    return "\n".join(lines)


def read_file_excerpt(project_root: Path, relative_path: str, max_chars: int = MAX_FILE_CHARS) -> str:
    target = (project_root / relative_path).resolve()
    try:
        target.relative_to(project_root)
    except ValueError as exc:
        raise ValueError("Invalid file path.") from exc
    content = target.read_text(encoding="utf-8", errors="replace")
    return content[:max_chars] + ("\n... [truncated]" if len(content) > max_chars else "")


def read_file_full(project_root: Path, relative_path: str) -> str:
    target = (project_root / relative_path).resolve()
    try:
        target.relative_to(project_root)
    except ValueError as exc:
        raise ValueError("Invalid file path.") from exc
    return target.read_text(encoding="utf-8", errors="replace")


def truncate_middle(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    if max_chars < 64:
        return text[:max_chars]
    keep_each_side = (max_chars - 24) // 2
    return f"{text[:keep_each_side]}\n... [truncated] ...\n{text[-keep_each_side:]}"


def char_index_to_line(content: str, index: int) -> int:
    if index <= 0:
        return 1
    return content.count("\n", 0, min(index, len(content))) + 1


def slice_lines(content: str, start_line: int, end_line: int) -> str:
    lines = content.splitlines()
    if not lines:
        return ""
    start = max(1, start_line)
    end = min(len(lines), end_line)
    return "\n".join(lines[start - 1:end])


def find_matching_brace(content: str, brace_start: int) -> Optional[int]:
    depth = 0
    for index in range(brace_start, len(content)):
        char = content[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return index + 1
    return None


def detect_csharp_regions(content: str) -> List[Dict[str, object]]:
    patterns = [
        re.compile(
            r"(?m)^[ \t]*(?:public|private|protected|internal)(?:\s+static)?(?:\s+async)?\s+[A-Za-z_][\w<>\[\],?. ]*\s+([A-Za-z_][A-Za-z0-9_]*)\s*\([^;\n{}]*\)\s*\{"
        ),
        re.compile(
            r"(?m)^[ \t]*(?:public|private|protected|internal)\s+([A-Za-z_][A-Za-z0-9_]*)\s*\([^;\n{}]*\)\s*\{"
        ),
    ]
    regions: List[Dict[str, object]] = []
    seen_starts = set()
    for pattern in patterns:
        for match in pattern.finditer(content):
            start = match.start()
            if start in seen_starts:
                continue
            brace_start = content.find("{", match.end() - 1)
            if brace_start < 0:
                continue
            end = find_matching_brace(content, brace_start)
            if end is None or end <= start:
                continue
            seen_starts.add(start)
            start_line = char_index_to_line(content, start)
            end_line = char_index_to_line(content, end)
            regions.append(
                {
                    "name": match.group(1),
                    "start": start,
                    "end": end,
                    "start_line": start_line,
                    "end_line": end_line,
                    "text": content[start:end].strip(),
                }
            )
    regions.sort(key=lambda item: int(item["start"]))
    return regions


def build_query_terms(message: str) -> List[str]:
    terms: List[str] = []
    seen = set()

    def add(term: str) -> None:
        key = term.lower()
        if term and key not in seen:
            seen.add(key)
            terms.append(term)

    for ident in re.findall(r"[A-Za-z_][A-Za-z0-9_]{1,}", message):
        add(ident)

    lowered = message.lower()
    if "ctrl" in lowered or "control" in lowered or "鍵盤" in message or "按鍵" in message:
        for term in ("KeyDown", "Form1_KeyDown", "KeyPreview", "Control", "Ctrl", "Keys.M"):
            add(term)
    if "按下 m" in lowered or "keys.m" in lowered or " m 鍵" in message.lower():
        for term in ("Keys.M", "Form1_KeyDown", "KeyDown"):
            add(term)
    if "落到底" in message or "落到底部" in message or "直接落下" in message or "快速落下" in message:
        for term in ("HardDrop", "LockPiece", "MovePiece", "GameTick"):
            add(term)
    if "背景音樂" in message or "音樂" in message or "靜音" in message or "mute" in lowered:
        for term in ("audioManager", "StartBackgroundMusic", "StopBackgroundMusic", "TogglePause", "Form1_KeyDown", "Keys.M"):
            add(term)
    if "旋轉" in message:
        for term in ("RotatePiece", "kicks"):
            add(term)
    if "暫停" in message:
        add("TogglePause")
    return terms


def parse_forbidden_identifiers(message: str) -> List[str]:
    identifiers: List[str] = []
    seen = set()
    patterns = [
        re.compile(r"\b([A-Za-z_][A-Za-z0-9_]*)\b\s*不存在"),
        re.compile(r"\b([A-Za-z_][A-Za-z0-9_]*)\b\s*不要用"),
        re.compile(r"\b([A-Za-z_][A-Za-z0-9_]*)\b\s*不能用"),
        re.compile(r"不要使用\s*\b([A-Za-z_][A-Za-z0-9_]*)\b"),
    ]
    for pattern in patterns:
        for match in pattern.finditer(message):
            identifier = match.group(1)
            key = identifier.lower()
            if key not in seen:
                seen.add(key)
                identifiers.append(identifier)
    return identifiers


def extract_free_identifiers(text: str) -> List[str]:
    identifiers: List[str] = []
    for match in re.finditer(r"\b[A-Za-z_][A-Za-z0-9_]*\b", text):
        start = match.start()
        if start > 0 and text[start - 1] == ".":
            continue
        identifiers.append(match.group(0))
    return identifiers


def extract_declared_identifiers(text: str) -> List[str]:
    declared: List[str] = []
    patterns = [
        re.compile(r"\b(?:var|int|long|short|byte|float|double|decimal|bool|string|char|object)\s+([A-Za-z_][A-Za-z0-9_]*)\b"),
        re.compile(r"\b(?:Point|Color|Path|Form|EventArgs|KeyEventArgs|List|Dictionary|HashSet)\s+([A-Za-z_][A-Za-z0-9_]*)\b"),
    ]
    for pattern in patterns:
        for match in pattern.finditer(text):
            declared.append(match.group(1))
    return declared


def collect_edit_safety_issues(before_snippet: str, after_snippet: str, full_content: str, message: str) -> List[str]:
    issues: List[str] = []
    forbidden = {item.lower(): item for item in parse_forbidden_identifiers(message)}
    after_identifiers = extract_free_identifiers(after_snippet)
    before_identifiers = set(item.lower() for item in extract_free_identifiers(before_snippet))
    declared_identifiers = set(item.lower() for item in extract_declared_identifiers(after_snippet))
    full_identifiers = set(item.lower() for item in extract_free_identifiers(full_content))

    forbidden_hits = sorted({identifier for identifier in after_identifiers if identifier.lower() in forbidden})
    if forbidden_hits:
        issues.append(f"建議片段仍引用被明確否定的 identifier：{', '.join(forbidden_hits)}")

    unknown_identifiers: List[str] = []
    for identifier in after_identifiers:
        lowered = identifier.lower()
        if lowered in before_identifiers or lowered in declared_identifiers:
            continue
        if identifier in CSHARP_RESERVED_IDENTIFIERS or identifier in CSHARP_ALLOWED_GLOBAL_IDENTIFIERS:
            continue
        if lowered in full_identifiers:
            continue
        unknown_identifiers.append(identifier)
    if unknown_identifiers:
        issues.append(f"建議片段引入未在目標檔案中出現的 identifier：{', '.join(sorted(set(unknown_identifiers)))}")

    return issues


def build_line_window_from_index(content: str, index: int, before_lines: int = 10, after_lines: int = 20) -> Dict[str, object]:
    line_count = max(1, len(content.splitlines()))
    target_line = char_index_to_line(content, index)
    start_line = max(1, target_line - before_lines)
    end_line = min(line_count, target_line + after_lines)
    snippet = slice_lines(content, start_line, end_line)
    return {
        "name": f"line {target_line}",
        "start_line": start_line,
        "end_line": end_line,
        "text": snippet.strip(),
    }


def select_relevant_sections(content: str, relative_path: str, message: str, max_sections: int = 3) -> List[Dict[str, object]]:
    suffix = Path(relative_path).suffix.lower()
    terms = build_query_terms(message)
    if not terms:
        return []

    regions = detect_csharp_regions(content) if suffix == ".cs" else []
    ranked: List[Tuple[int, Dict[str, object]]] = []
    lowered_message = message.lower()

    for region in regions:
        region_name = str(region["name"]).lower()
        region_text = str(region["text"]).lower()
        score = 0
        for term in terms:
            term_lower = term.lower()
            if term_lower == region_name:
                score += 30
            elif term_lower in region_name:
                score += 20
            count = region_text.count(term_lower)
            if count:
                score += min(count, 4) * 6
        if "keydown" in region_name and ("ctrl" in lowered_message or "鍵盤" in message):
            score += 18
        if "harddrop" in region_name and ("ctrl" in lowered_message or "落到底" in message):
            score += 20
        if score > 0:
            ranked.append((score, region))

    if ranked:
        ranked.sort(key=lambda item: (-item[0], int(item[1]["start"])))
        return [item[1] for item in ranked[:max_sections]]

    fallback_sections: List[Dict[str, object]] = []
    lowered_content = content.lower()
    seen_lines = set()
    for term in terms:
        index = lowered_content.find(term.lower())
        if index < 0:
            continue
        section = build_line_window_from_index(content, index)
        marker = (section["start_line"], section["end_line"])
        if marker in seen_lines:
            continue
        seen_lines.add(marker)
        fallback_sections.append(section)
        if len(fallback_sections) >= max_sections:
            break
    return fallback_sections


def score_file_relevance(content: str, relative_path: str, message: str) -> int:
    terms = build_query_terms(message)
    if not terms:
        return 0
    lowered_content = content.lower()
    score = 0
    for term in terms:
        term_lower = term.lower()
        score += min(lowered_content.count(term_lower), 6) * 4
    lowered_message = message.lower()
    if Path(relative_path).suffix.lower() == ".cs":
        if any(token in lowered_message for token in ("ctrl", "control", "keydown", "keys.", " m 鍵", "按鍵")):
            if "keydown" in lowered_content or "form1_keydown" in lowered_content:
                score += 28
            if "case keys." in lowered_content:
                score += 18
        if any(token in lowered_message for token in ("背景音樂", "音樂", "mute", "靜音")):
            if "audiomanager" in lowered_content:
                score += 16
            if "startbackgroundmusic" in lowered_content or "stopbackgroundmusic" in lowered_content:
                score += 18
    if Path(relative_path).suffix.lower() == ".cs":
        for region in detect_csharp_regions(content):
            region_name = str(region["name"]).lower()
            for term in terms:
                term_lower = term.lower()
                if term_lower == region_name:
                    score += 24
                elif term_lower in region_name:
                    score += 12
    return score


def rank_paths_for_message(project_root: Path, paths: List[str], message: str) -> List[str]:
    ranked: List[Tuple[int, str]] = []
    for path in paths:
        try:
            content = read_file_full(project_root, path)
        except (OSError, ValueError):
            ranked.append((0, path))
            continue
        ranked.append((score_file_relevance(content, path, message), path))
    ranked.sort(key=lambda item: (-item[0], item[1]))
    positive = [path for score, path in ranked if score > 0]
    if positive:
        remainder = [path for score, path in ranked if score <= 0]
        return positive + remainder
    return [path for _, path in ranked]


def build_excerpt_for_message(
    project_root: Path,
    relative_path: str,
    message: str,
    max_chars: int,
    max_sections: int = 3,
) -> str:
    content = read_file_full(project_root, relative_path)
    sections = select_relevant_sections(content, relative_path, message, max_sections=max_sections)
    if not sections:
        return read_file_excerpt(project_root, relative_path, max_chars=max_chars)

    blocks: List[str] = []
    total_chars = 0
    for section in sections:
        header = f"區段: {section['name']} (約第 {section['start_line']}-{section['end_line']} 行)"
        block = f"{header}\n{section['text']}"
        if total_chars + len(block) > max_chars:
            if not blocks:
                blocks.append(truncate_middle(block, max_chars))
            break
        blocks.append(block)
        total_chars += len(block)
    return "\n\n".join(blocks)


def locate_change_region(content: str, match_index: int) -> Dict[str, object]:
    regions = detect_csharp_regions(content)
    for region in regions:
        if int(region["start"]) <= match_index < int(region["end"]):
            return region
    return build_line_window_from_index(content, match_index)


def derive_local_target_hint(project_root: Path, relative_path: str, message: str) -> Dict[str, str]:
    content = read_file_full(project_root, relative_path)
    sections = select_relevant_sections(content, relative_path, message, max_sections=1)
    if sections:
        section = sections[0]
        return {
            "path": relative_path,
            "target": str(section["name"]),
            "location": f"約第 {section['start_line']}-{section['end_line']} 行",
            "before": truncate_middle(str(section["text"]).strip(), 2200),
        }
    excerpt = read_file_excerpt(project_root, relative_path, max_chars=1600)
    return {
        "path": relative_path,
        "target": "未提供",
        "location": "未提供",
        "before": excerpt,
    }


def choose_context_files(
    message: str,
    files: List[ProjectFile],
    entrypoints: List[str],
    tests: List[str],
    pinned: List[str],
    preview_path: Optional[str] = None,
) -> List[str]:
    allowed = {file.path for file in files}
    unique: List[str] = []
    seen = set()
    for path in pinned:
        if path in allowed and path not in seen:
            unique.append(path)
            seen.add(path)
        if len(unique) >= MAX_CONTEXT_FILES:
            break
    return unique


def normalize_preview_path(raw_preview_path: object, files: List[ProjectFile]) -> Optional[str]:
    if not isinstance(raw_preview_path, str):
        return None
    preview_path = raw_preview_path.strip()
    if not preview_path:
        return None
    allowed = {file.path for file in files}
    return preview_path if preview_path in allowed else None


def require_pinned_context(state: SessionState) -> List[str]:
    allowed = {file.path for file in state.files}
    pinned = [path for path in state.pinned_files if path in allowed]
    if not pinned:
        raise ValueError("請先在檔案樹勾選並套用至少一個檔案，模型才會根據這些檔案分析。")
    return pinned


def iter_pending_edit_items(pending_edit: Optional[Dict[str, object]]) -> List[Dict[str, object]]:
    if not isinstance(pending_edit, dict):
        return []
    edits = pending_edit.get("edits")
    if isinstance(edits, list) and edits:
        return [item for item in edits if isinstance(item, dict)]
    suggestions = pending_edit.get("suggestions")
    if isinstance(suggestions, list) and suggestions:
        return [item for item in suggestions if isinstance(item, dict)]
    return []


def is_refinement_request(message: str, pending_edit: Optional[Dict[str, object]]) -> bool:
    if not pending_edit:
        return False
    lowered = message.lower()
    correction_tokens = (
        "不存在", "不對", "錯", "錯誤", "有問題", "不該", "不是", "不要", "不能",
        "請用", "改用", "改成", "改為", "應該", "應改", "上一版", "前一版",
        "這份建議", "這個建議", "請改", "請修正",
    )
    english_tokens = ("wrong", "incorrect", "doesn't exist", "not exist", "use existing", "replace with")
    return any(token in message for token in correction_tokens) or any(token in lowered for token in english_tokens)


def build_refinement_ranking_message(message: str, pending_edit: Optional[Dict[str, object]]) -> str:
    if not pending_edit:
        return message
    parts = [message]
    summary = str(pending_edit.get("summary", "")).strip()
    if summary:
        parts.append(summary)
    for item in iter_pending_edit_items(pending_edit)[:3]:
        path = str(item.get("path", "")).strip()
        target = str(item.get("target", "")).strip()
        location = str(item.get("location", "")).strip()
        if path:
            parts.append(path)
        if target:
            parts.append(target)
        if location:
            parts.append(location)
    return "\n".join(part for part in parts if part)


def build_pending_edit_prompt_block(pending_edit: Optional[Dict[str, object]]) -> str:
    if not pending_edit:
        return ""
    mode = str(pending_edit.get("mode", "precise")).strip() or "precise"
    lines = [
        "上一版修改建議如下：",
        f"- 摘要：{str(pending_edit.get('summary', '')).strip() or '未提供'}",
        f"- 模式：{'文字模式' if mode == 'advisory' else '精準模式'}",
    ]
    failure_reason = str(pending_edit.get("failureReason", "")).strip()
    if failure_reason:
        lines.append(f"- 精準模式未套用原因：{failure_reason}")
    for item in iter_pending_edit_items(pending_edit)[:3]:
        lines.extend([
            "",
            f"檔案：{str(item.get('path', '')).strip() or '(未指定檔案)'}",
            f"修改位置：{str(item.get('location', '')).strip() or '未提供'}",
            f"命中函式/區塊：{str(item.get('target', '')).strip() or '未提供'}",
            f"原因：{str(item.get('reason', item.get('whyHere', ''))).strip() or '未提供'}",
            "上一版建議替換前片段：",
            truncate_middle(str(item.get('beforeSnippet', item.get('before', ''))).strip() or "未提供", 1000),
            "",
            "上一版建議替換後片段：",
            truncate_middle(str(item.get('afterSnippet', item.get('after', ''))).strip() or "未提供", 1000),
        ])
    need_more_context = pending_edit.get("needMoreContext")
    if isinstance(need_more_context, list):
        visible = [str(item).strip() for item in need_more_context if str(item).strip()]
        if visible:
            lines.extend(["", "上一版需要補充：", *[f"- {item}" for item in visible]])
    return "\n".join(lines).strip()


def normalize_message_roles(messages: List[Dict[str, str]]) -> List[Dict[str, str]]:
    normalized: List[Dict[str, str]] = []
    for message in messages:
        role = str(message.get("role", "")).strip()
        content = str(message.get("content", "")).strip()
        if not content:
            continue
        if role not in {"system", "user", "assistant"}:
            role = "user"
        normalized.append({"role": role, "content": content})
    return normalized


def sanitize_gemma_reply(content: str) -> str:
    cleaned = content.strip()
    cleaned = re.sub(r"^\s*根據您提供的[^\n。！？]*[。！？]?\s*", "", cleaned)
    cleaned = re.sub(r"^\s*以下是根據[^\n。！？]*[。！？]?\s*", "", cleaned)
    cleaned = re.sub(r"^\s*以下為[^\n。！？]*[。！？]?\s*", "", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def sanitize_qwen_reply(content: str) -> str:
    cleaned = content.strip()
    cleaned = re.sub(r"^\s*以下是根據[^\n。！？]*[。！？]?\s*", "", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def sanitize_model_reply(model_alias: str, content: str, raw_mode: bool = False) -> str:
    if raw_mode:
        return str(content or "").strip()
    if model_alias.startswith("gemma4"):
        return sanitize_gemma_reply(content)
    if model_alias.startswith("qwen"):
        return sanitize_qwen_reply(content)
    return content.strip()


def get_continue_on_length(model_key: str) -> int:
    if model_key == "gemma4":
        return 2
    if model_key == "qwen":
        return 1
    return 0


def build_chat_system_prompt(model_key: str) -> str:
    if model_key == "gemma4":
        return (
            "你是本機離線 code assistant。請使用繁體中文直接回答重點。"
            "第一段先給結論，不要重述問題、不要說『根據您提供』、不要做長篇鋪陳。"
            "若需要列點，最多 5 點。若資訊不足，直接回答不確定。"
        )
    return (
        "你是本機離線 code assistant。請使用繁體中文回答，並只根據目前已套用釘選檔案回答。"
        "檔案預覽僅供閱讀，不是模型上下文來源。若資訊不足請直接回答不確定。"
        "若問題是在問函式名稱、方法名稱、類別名稱、變數名稱、檔案名稱或事件處理函式，"
        "請先從上下文找出精確 identifier，再直接回覆該名稱與所在檔案；若上下文已經有明確名稱，禁止改寫成泛化的可能性清單。"
    )


def build_analyze_system_prompt(model_key: str) -> str:
    if model_key == "gemma4":
        return (
            "你是本機離線 code assistant。請使用繁體中文分析，先給結論，再補依據。"
            "不要重述問題或專案背景，不要用 markdown 表格。若資訊不足請直接說不確定。"
        )
    return "你是本機離線 code assistant。請使用繁體中文回答，並只根據目前已套用釘選檔案分析；若資訊不足請直接說不確定。"


def build_raw_chat_user_message(context: str, message: str) -> str:
    return (
        "以下是目前已套用釘選檔案的上下文：\n"
        f"{context}\n\n"
        "請只根據上面內容回答。\n"
        f"使用者問題：\n{message}"
    )


def build_raw_analyze_user_message(prompt: str, context: str) -> str:
    return (
        f"{prompt}\n\n"
        "以下是目前已套用釘選檔案的上下文：\n"
        f"{context}"
    )


def build_gemma_locator_messages(
    message: str,
    context: str,
    allowed_files: List[str],
    pending_edit: Optional[Dict[str, object]] = None,
    refine_mode: bool = False,
) -> List[Dict[str, str]]:
    allowed_block = "\n".join(f"- {path}" for path in allowed_files) if allowed_files else "- (無候選檔案)"
    forbidden_identifiers = parse_forbidden_identifiers(message)
    forbidden_block = (
        "\n不得使用以下 identifier:\n" + "\n".join(f"- {item}" for item in forbidden_identifiers)
        if forbidden_identifiers else ""
    )
    pending_edit_block = build_pending_edit_prompt_block(pending_edit)
    refine_block = (
        "這一輪是在修正上一版建議。你只能沿用上一版已命中的同一個 path 附近重新定位，不可擴張到其他檔案。"
        if refine_mode else
        "這一輪是新的修改需求。請只從候選檔案中選出一個最適合修改的 path。"
    )
    schema = (
        '{\n'
        '  "summary": "一句話說明修改目的",\n'
        '  "needMoreContext": ["若定位不唯一，列出需要補看的檔案或函式"],\n'
        '  "path": "單一最佳相對路徑，若無法判定則留空",\n'
        '  "target": "命中的函式、方法或區塊名稱",\n'
        '  "locationHint": "大致位置，例如 約第 120-160 行",\n'
        '  "reason": "為何判斷應在這裡修改"\n'
        '}'
    )
    system_prompt = (
        "你是本機離線 code assistant，目前只負責定位修改位置，不負責產生 patch。"
        "請使用 Gemma 4 標準 chat roles；本輪不要啟用 thinking，不要輸出思考過程，不要在 JSON 外加任何說明。"
        "你只能在提供的候選檔案中選一個最佳 path。"
        "若定位不唯一或資訊不足，path 必須留空，並把需要補看的檔案或函式寫到 needMoreContext。"
        "禁止輸出多個候選 path。"
        "請只輸出 JSON。"
    )
    return [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": (
                f"使用者需求:\n{message}\n\n"
                f"本輪任務說明:\n{refine_block}\n\n"
                f"候選檔案:\n{allowed_block}\n"
                f"{forbidden_block}\n\n"
                f"{pending_edit_block}\n\n"
                f"以下是專案上下文:\n{context}\n\n"
                f"回傳格式必須符合這個 JSON schema:\n{schema}"
            ),
        },
    ]


def build_gemma_patch_messages(
    message: str,
    context: str,
    path: str,
    target: str,
    pending_edit: Optional[Dict[str, object]] = None,
    refine_mode: bool = False,
) -> List[Dict[str, str]]:
    forbidden_identifiers = parse_forbidden_identifiers(message)
    forbidden_block = (
        "\n不得使用以下 identifier:\n" + "\n".join(f"- {item}" for item in forbidden_identifiers)
        if forbidden_identifiers else ""
    )
    pending_edit_block = build_pending_edit_prompt_block(pending_edit)
    refine_block = (
        "這一輪是在修正上一版建議。你只能在同一個 path 與 target 附近重試，若仍無法安全修改就回 needMoreContext。"
        if refine_mode else
        "這一輪是新的修改需求。請只對這個已定位區段提出最小修改。"
    )
    schema = (
        '{\n'
        '  "summary": "一句話說明修改目的",\n'
        '  "needMoreContext": ["若仍需要補充檔案或函式請列出"],\n'
        '  "path": "必須與已定位 path 相同",\n'
        '  "target": "命中的函式、方法或區塊名稱",\n'
        '  "reason": "修改原因",\n'
        '  "search": "要被精確取代的原始片段",\n'
        '  "replace": "修改後的新片段",\n'
        '  "notes": ["補充說明"]\n'
        '}'
    )
    system_prompt = (
        "你是本機離線 code assistant，目前只負責對單一已定位區段產生最小 patch。"
        "請使用 Gemma 4 標準 chat roles；本輪不要啟用 thinking，不要輸出思考過程，不要在 JSON 外加任何說明。"
        "只允許輸出一個 path 與一組 search/replace。"
        "禁止重寫整份檔案，禁止輸出多個候選方案。"
        "search 必須是提供節錄中的原文，replace 只放修改後的新片段。"
        "若資訊不足或無法安全修改，請把 search/replace 留空，並把需要補看的函式或檔案寫到 needMoreContext。"
        "請只輸出 JSON。"
    )
    return [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": (
                f"使用者需求:\n{message}\n\n"
                f"已定位 path:\n- {path}\n\n"
                f"已定位 target:\n- {target or '未提供'}\n\n"
                f"本輪任務說明:\n{refine_block}\n"
                f"{forbidden_block}\n\n"
                f"{pending_edit_block}\n\n"
                f"以下是已定位區段上下文:\n{context}\n\n"
                f"回傳格式必須符合這個 JSON schema:\n{schema}"
            ),
        },
    ]


def build_project_context(project_root: Path, state: SessionState, message: str) -> str:
    selected_paths = rank_paths_for_message(project_root, require_pinned_context(state), message)
    single_file_focus = len(selected_paths) == 1
    limits = get_context_limits(state.model_key, single_file_focus)
    selected_paths = selected_paths[: limits["max_files"]]
    chunks = ["已套用釘選檔案:\n" + "\n".join(selected_paths)]
    total_limit = limits["total_chars"]
    total_chars = sum(len(chunk) for chunk in chunks)
    for relative_path in selected_paths:
        try:
            excerpt = build_excerpt_for_message(
                project_root,
                relative_path,
                message,
                max_chars=limits["file_chars"],
                max_sections=3 if single_file_focus else 2,
            )
        except (OSError, ValueError):
            continue
        block = f"\n檔案: {relative_path}\n```\n{excerpt}\n```"
        if total_chars + len(block) > total_limit:
            break
        chunks.append(block)
        total_chars += len(block)
    return "\n\n".join(chunks)


def build_edit_context(project_root: Path, state: SessionState, message: str) -> Tuple[str, List[str]]:
    selected_paths = rank_paths_for_message(project_root, require_pinned_context(state), message)[:MAX_EDIT_FILES]
    single_file_focus = len(selected_paths) == 1
    total_limit = MAX_EDIT_SINGLE_FILE_CHARS if single_file_focus else MAX_EDIT_TOTAL_CHARS
    chunks = [
        "可編輯候選檔案:\n" + "\n".join(selected_paths) if selected_paths else "可編輯候選檔案:\n(無)",
    ]
    total_chars = sum(len(chunk) for chunk in chunks)
    for relative_path in selected_paths:
        try:
            excerpt = build_excerpt_for_message(
                project_root,
                relative_path,
                message,
                max_chars=MAX_EDIT_SINGLE_FILE_CHARS if single_file_focus else MAX_EDIT_FILE_CHARS,
                max_sections=3 if single_file_focus else 2,
            )
        except (OSError, ValueError):
            continue
        block = f"\n檔案: {relative_path}\n```\n{excerpt}\n```"
        if total_chars + len(block) > total_limit:
            break
        chunks.append(block)
        total_chars += len(block)
    return "\n\n".join(chunks), selected_paths


def build_advisory_context(project_root: Path, state: SessionState, message: str, allowed_files: List[str]) -> str:
    allowed_files = rank_paths_for_message(project_root, allowed_files, message)
    chunks = [
        "建議優先參考檔案:\n" + "\n".join(allowed_files) if allowed_files else "建議優先參考檔案:\n(無)",
    ]
    total_chars = sum(len(chunk) for chunk in chunks)
    total_limit = min(MAX_EDIT_SINGLE_FILE_CHARS, 20000)
    for relative_path in allowed_files[:MAX_EDIT_FILES]:
        try:
            excerpt = build_excerpt_for_message(
                project_root,
                relative_path,
                message,
                max_chars=MAX_ADVISORY_FILE_CHARS,
                max_sections=3,
            )
        except (OSError, ValueError):
            continue
        block = f"\n檔案: {relative_path}\n```\n{excerpt}\n```"
        if total_chars + len(block) > total_limit:
            break
        chunks.append(block)
        total_chars += len(block)
    return "\n\n".join(chunks)


def try_resolve_identifier_question(project_root: Path, state: SessionState, message: str) -> Optional[str]:
    lowered = message.lower()
    is_identifier_question = any(token in message for token in ("函式名稱", "方法名稱", "事件處理函式")) or "function name" in lowered
    if not is_identifier_question:
        return None

    selected_paths = require_pinned_context(state)
    if "鍵盤" in message or "keydown" in lowered:
        for relative_path in selected_paths:
            try:
                content = read_file_full(project_root, relative_path)
            except (OSError, ValueError):
                continue
            event_match = re.search(r"KeyDown\s*\+=\s*([A-Za-z_][A-Za-z0-9_]*)\s*;", content)
            if event_match:
                handler = event_match.group(1)
                return f"在 {relative_path} 中，鍵盤事件處理函式名稱是 `{handler}`。對應綁定寫法是 `KeyDown += {handler};`。"
            method_match = re.search(
                r"\b(?:private|protected|public|internal)\s+\w+\s+([A-Za-z_][A-Za-z0-9_]*KeyDown[A-Za-z0-9_]*)\s*\(",
                content,
            )
            if method_match:
                handler = method_match.group(1)
                return f"在 {relative_path} 中，鍵盤事件處理函式名稱是 `{handler}`。"
    return None


def is_code_change_request(message: str) -> bool:
    lowered = message.lower()
    keywords = (
        "修改", "修正", "新增", "增加", "改成", "改為", "實作", "達到這個功能",
        "請幫我修改", "請幫我修正", "替換", "patch", "refactor",
    )
    return any(token in message for token in keywords) or any(token in lowered for token in ("modify", "change", "fix", "implement"))


def format_notes(value: object) -> List[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def normalize_need_more_context(value: object) -> List[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def is_gemma4_state(state: SessionState) -> bool:
    return state.model_key == "gemma4"


def write_model_debug_log(kind: str, model_key: str, content: str) -> str:
    stamp = subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", "[DateTime]::Now.ToString('yyyyMMdd-HHmmss')"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        timeout=10,
    ).stdout.strip() or "unknown"
    path = ROOT_DIR / "logs" / f"{kind}-{model_key}-{stamp}.log"
    path.write_text(content[-12000:], encoding="utf-8", errors="replace")
    return str(path)


def resolve_primary_target_path(allowed_files: List[str], pending_edit: Optional[Dict[str, object]], refine_mode: bool) -> Optional[str]:
    if refine_mode and pending_edit:
        for item in iter_pending_edit_items(pending_edit):
            path = str(item.get("path", "")).strip()
            if path in allowed_files:
                return path
    return allowed_files[0] if allowed_files else None


def build_gemma_locator_context(
    project_root: Path,
    allowed_files: List[str],
    message: str,
) -> str:
    ranked_files = rank_paths_for_message(project_root, allowed_files, message)[:MAX_EDIT_FILES]
    return build_context_for_paths(
        project_root,
        ranked_files,
        message,
        "Gemma 4 定位候選檔案",
        file_char_limit=min(12000, MAX_EDIT_SINGLE_FILE_CHARS),
        total_limit=min(18000, MAX_EDIT_SINGLE_FILE_CHARS),
        max_sections=3,
    )


def create_gemma_locator(
    project_root: Path,
    state: SessionState,
    message: str,
    allowed_files: List[str],
    pending_edit: Optional[Dict[str, object]] = None,
    refine_mode: bool = False,
) -> Dict[str, object]:
    context = build_gemma_locator_context(project_root, allowed_files, message)
    raw_reply = call_local_model(
        state.model_alias,
        build_gemma_locator_messages(
            message,
            context,
            allowed_files,
            pending_edit=pending_edit,
            refine_mode=refine_mode,
        ),
        timeout_seconds=EDIT_PLAN_TIMEOUT_SECONDS,
        max_tokens=GEMMA4_LOCATOR_MAX_TOKENS,
    )
    try:
        payload = extract_json_payload(raw_reply)
    except Exception as exc:
        log_path = write_model_debug_log("gemma4-locator", state.model_key, raw_reply)
        return build_gemma_local_locator_fallback(
            project_root,
            allowed_files,
            message,
            failure_reason=f"EDIT_PLAN_SCHEMA_INVALID: Gemma 4 locator 回傳不合法 JSON。{exc}。原始回覆尾段已寫入 {log_path}",
        )

    path = str(payload.get("path", "")).strip()
    need_more_context = normalize_need_more_context(payload.get("needMoreContext"))
    if path and path not in allowed_files:
        raise RuntimeError(f"Gemma 4 locator 指向未允許的檔案：{path}")

    if not path:
        if len(allowed_files) == 1:
            return build_gemma_local_locator_fallback(
                project_root,
                allowed_files,
                message,
                failure_reason="Gemma 4 locator 未提供 path，已改用本地區段定位。",
            )
        return {
            "summary": str(payload.get("summary", "")).strip() or "Gemma 4 無法唯一定位修改區段",
            "needMoreContext": need_more_context,
            "path": "",
            "target": str(payload.get("target", "")).strip(),
            "locationHint": str(payload.get("locationHint", "")).strip(),
            "reason": str(payload.get("reason", "")).strip(),
        }

    hint = derive_local_target_hint(project_root, path, "\n".join(part for part in [message, str(payload.get("target", ""))] if part))
    return {
        "summary": str(payload.get("summary", "")).strip() or "已定位修改區段",
        "needMoreContext": need_more_context,
        "path": path,
        "target": str(payload.get("target", "")).strip() or hint.get("target", ""),
        "locationHint": str(payload.get("locationHint", "")).strip() or hint.get("location", ""),
        "reason": str(payload.get("reason", "")).strip() or "Gemma 4 已定位到單一最佳區段",
        "before": hint.get("before", ""),
    }


def build_gemma_patch_context(
    project_root: Path,
    path: str,
    message: str,
    target: str,
    locator_reason: str = "",
) -> str:
    ranking_message = "\n".join(part for part in [message, target, locator_reason] if part)
    return build_context_for_paths(
        project_root,
        [path],
        ranking_message,
        "Gemma 4 已定位區段",
        file_char_limit=min(14000, MAX_EDIT_SINGLE_FILE_CHARS),
        total_limit=min(18000, MAX_EDIT_SINGLE_FILE_CHARS),
        max_sections=2,
    )


def build_gemma_local_locator_fallback(
    project_root: Path,
    allowed_files: List[str],
    message: str,
    failure_reason: str = "",
) -> Dict[str, object]:
    ranked = rank_paths_for_message(project_root, allowed_files, message)
    if not ranked:
        return {
            "summary": "Gemma 4 無法唯一定位修改區段",
            "needMoreContext": [],
            "path": "",
            "target": "",
            "locationHint": "",
            "reason": failure_reason or "目前沒有可用的候選檔案。",
            "before": "",
        }
    primary_path = ranked[0]
    hint = derive_local_target_hint(project_root, primary_path, message)
    return {
        "summary": "Gemma 4 locator 未回合法 JSON，已改用本地區段定位",
        "needMoreContext": [],
        "path": primary_path,
        "target": hint.get("target", ""),
        "locationHint": hint.get("location", ""),
        "reason": failure_reason or "Gemma 4 locator 未回合法 JSON，已改用本地規則定位。",
        "before": hint.get("before", ""),
    }


def build_context_for_paths(
    project_root: Path,
    selected_paths: List[str],
    message: str,
    heading: str,
    file_char_limit: int,
    total_limit: int,
    max_sections: int = 3,
) -> str:
    chunks = [f"{heading}:\n" + ("\n".join(selected_paths) if selected_paths else "(無)")]
    total_chars = sum(len(chunk) for chunk in chunks)
    for relative_path in selected_paths:
        try:
            excerpt = build_excerpt_for_message(
                project_root,
                relative_path,
                message,
                max_chars=file_char_limit,
                max_sections=max_sections,
            )
        except (OSError, ValueError):
            continue
        block = f"\n檔案: {relative_path}\n```\n{excerpt}\n```"
        if total_chars + len(block) > total_limit:
            if len(chunks) == 1:
                chunks.append(truncate_middle(block, max(500, total_limit - total_chars)))
            break
        chunks.append(block)
        total_chars += len(block)
    return "\n\n".join(chunks)


def build_fallback_advisory_plan(
    project_root: Path,
    state: SessionState,
    message: str,
    allowed_files: List[str],
    failure_reason: str,
    pending_edit: Optional[Dict[str, object]] = None,
    refine_mode: bool = False,
    raw_reply: str = "",
) -> Dict[str, object]:
    target_item = next(iter(iter_pending_edit_items(pending_edit)), {}) if pending_edit else {}
    target_path = resolve_primary_target_path(allowed_files, pending_edit, refine_mode) or str(target_item.get("path", "")).strip() or "(未指定檔案)"
    target_name = str(target_item.get("target", "")).strip() or "請補充要修改的函式或區塊"
    location = str(target_item.get("location", "")).strip() or "未提供"
    before_snippet = ""
    if target_path and target_path != "(未指定檔案)":
        try:
            local_hint = derive_local_target_hint(project_root, target_path, message)
            if target_name == "請補充要修改的函式或區塊":
                target_name = local_hint.get("target", target_name)
            location = local_hint.get("location", location)
            before_snippet = local_hint.get("before", "")
        except (OSError, ValueError):
            pass
    notes = [
        "Gemma 4 目前未能穩定輸出合法的結構化 JSON，已改用保守文字 fallback。",
        failure_reason or "模型沒有產生可解析的修改建議。",
    ]
    if raw_reply.strip():
        notes.append("模型原始回覆已截斷保留於 logs，可供後續比對。")
    suggestion = {
        "path": target_path,
        "location": location,
        "target": target_name,
        "whyHere": "目前只能確認應在這個檔案或區塊附近重新檢查，無法安全產出精準替換片段。",
        "before": before_snippet,
        "after": "",
        "diffWindow": before_snippet or "Gemma 4 本輪未能產生可解析的結構化建議。請補充更明確的函式名稱、現有欄位名稱，或直接指出上一版建議哪裡錯。",
        "notes": notes,
    }
    display_text = format_plan_for_chat(
        {
            "mode": "advisory",
            "summary": "已產生保守文字建議",
            "failureReason": failure_reason,
            "suggestions": [suggestion],
        }
    )
    return {
        "mode": "advisory",
        "request": message,
        "refineMode": refine_mode,
        "summary": "已產生保守文字建議",
        "needMoreContext": [target_path] if target_path and target_path != "(未指定檔案)" else [],
        "edits": [],
        "suggestions": [suggestion],
        "displayText": display_text,
        "failureReason": failure_reason,
    }


def build_diff_window(relative_path: str, before: str, after: str) -> str:
    return generate_diff(relative_path, before, after)


def format_plan_for_chat(plan: Dict[str, object]) -> str:
    sections = [f"修改目的：{str(plan.get('summary', '')).strip() or '未提供'}"]
    mode = plan.get("mode", "precise")
    if plan.get("failureReason"):
        sections.append(f"精準模式未套用原因：{plan['failureReason']}")

    if mode == "precise":
        for item in plan.get("edits", []):
            parts = [
                f"檔案：{item.get('path', '(未指定檔案)')}",
                f"修改位置：{item.get('location', '未提供')}",
                f"命中函式/區塊：{item.get('target', '未提供')}",
                f"原因：{item.get('reason', '未提供')}",
                "建議替換區塊：",
                item.get("diffWindow") or item.get("diff") or "(無)",
            ]
            notes = format_notes(item.get("notes"))
            if notes:
                parts.extend(["補充說明：", "\n".join(f"- {note}" for note in notes)])
            sections.append("\n".join(str(part) for part in parts))
    else:
        for item in plan.get("suggestions", []):
            parts = [
                f"檔案：{item.get('path', '(未指定檔案)')}",
                f"修改位置：{item.get('location', '未提供')}",
                f"命中函式/區塊：{item.get('target', '未提供')}",
                f"原因：{item.get('whyHere', item.get('reason', '未提供'))}",
                "建議替換前片段：",
                item.get("before") or "(未提供)",
                "建議替換後片段：",
                item.get("after") or "(未提供)",
                "Diff 視窗：",
                item.get("diffWindow") or "(未提供)",
            ]
            notes = format_notes(item.get("notes"))
            if notes:
                parts.extend(["補充說明：", "\n".join(f"- {note}" for note in notes)])
            sections.append("\n".join(str(part) for part in parts))
    return "\n\n".join(sections)


def build_public_plan(plan: Dict[str, object]) -> Dict[str, object]:
    return {
        "mode": plan.get("mode", "precise"),
        "request": plan["request"],
        "refineMode": bool(plan.get("refineMode")),
        "summary": plan["summary"],
        "needMoreContext": plan.get("needMoreContext", []),
        "failureReason": plan.get("failureReason", ""),
        "edits": [
            {
                "path": item["path"],
                "target": item.get("target", ""),
                "location": item.get("location", ""),
                "reason": item["reason"],
                "notes": item.get("notes", []),
                "beforeSnippet": item.get("beforeSnippet", ""),
                "afterSnippet": item.get("afterSnippet", ""),
                "diff": item["diff"],
                "diffWindow": item.get("diffWindow", item["diff"]),
            }
            for item in plan.get("edits", [])
        ],
        "suggestions": plan.get("suggestions", []),
        "displayText": plan.get("displayText", ""),
    }


def extract_json_payload(raw: str) -> Dict[str, object]:
    cleaned = raw.strip()
    attempts: List[str] = []
    if cleaned:
        attempts.append(cleaned)

    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if lines:
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        stripped = "\n".join(lines).strip()
        if stripped:
            attempts.append(stripped)

    extracted = cleaned
    start = extracted.find("{")
    end = extracted.rfind("}")
    if start >= 0 and end > start:
        extracted = extracted[start:end + 1].strip()
        if extracted:
            attempts.append(extracted)

    repaired = extracted
    repaired = repaired.replace("```json", "").replace("```JSON", "").replace("```", "").strip()
    repaired = re.sub(r"^\s*json\s*", "", repaired, flags=re.IGNORECASE)
    repaired = re.sub(r"^[^{]*(\{)", r"\1", repaired, count=1, flags=re.DOTALL)
    repaired = re.sub(r"(\})[^}]*$", r"\1", repaired, count=1, flags=re.DOTALL)
    repaired = re.sub(r",(\s*[}\]])", r"\1", repaired)
    repaired = repaired.strip()
    if repaired:
        attempts.append(repaired)

    compact = "\n".join(
        line for line in repaired.splitlines()
        if line.strip() and not re.match(r"^(說明|Explanation|Here is|以下是)", line.strip(), flags=re.IGNORECASE)
    ).strip()
    if compact:
        attempts.append(compact)

    brace_candidate = compact or repaired or cleaned
    if brace_candidate:
        first_brace = brace_candidate.find("{")
        if first_brace >= 0:
            depth = 0
            end_index = -1
            for index in range(first_brace, len(brace_candidate)):
                char = brace_candidate[index]
                if char == "{":
                    depth += 1
                elif char == "}":
                    depth -= 1
                    if depth == 0:
                        end_index = index
                        break
            if end_index > first_brace:
                balanced = brace_candidate[first_brace:end_index + 1].strip()
                balanced = re.sub(r",(\s*[}\]])", r"\1", balanced)
                if balanced:
                    attempts.append(balanced)

    last_error: Optional[Exception] = None
    seen = set()
    for candidate in attempts:
        if not candidate:
            continue
        if candidate in seen:
            continue
        seen.add(candidate)
        try:
            return json.loads(candidate)
        except Exception as exc:
            last_error = exc
    raise ValueError(str(last_error) if last_error else "JSON payload is empty.")


def generate_diff(relative_path: str, before: str, after: str) -> str:
    diff = difflib.unified_diff(
        before.splitlines(),
        after.splitlines(),
        fromfile=f"a/{relative_path}",
        tofile=f"b/{relative_path}",
        lineterm="",
    )
    return "\n".join(diff)


def resolve_git_executable() -> str:
    candidates = [
        ROOT_DIR / "runtime" / "PortableGit" / "cmd" / "git.exe",
        ROOT_DIR / "runtime" / "PortableGit" / "bin" / "git.exe",
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return "git"


def run_git(project_root: Path, *args: str, timeout_seconds: int = 60) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GCM_INTERACTIVE"] = "Never"
    return subprocess.run(
        [resolve_git_executable(), "-C", str(project_root), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        timeout=timeout_seconds,
        env=env,
    )


def build_edit_messages(
    message: str,
    context: str,
    allowed_files: List[str],
    pending_edit: Optional[Dict[str, object]] = None,
    refine_mode: bool = False,
    model_key: str = "qwen",
) -> List[Dict[str, str]]:
    allowed_block = "\n".join(f"- {path}" for path in allowed_files) if allowed_files else "- (無可編輯檔案)"
    forbidden_identifiers = parse_forbidden_identifiers(message)
    forbidden_block = (
        "\n不得使用以下 identifier:\n" + "\n".join(f"- {item}" for item in forbidden_identifiers)
        if forbidden_identifiers else ""
    )
    pending_edit_block = build_pending_edit_prompt_block(pending_edit)
    refine_block = (
        "這一輪不是全新需求，而是在修正上一版修改建議。"
        "你必須先理解上一版哪裡錯，再只針對同一批已釘選檔案與已命中的區塊重新提出較正確的最小修改。"
        if refine_mode else
        "這一輪是新的修改需求，請直接根據目前已套用的釘選檔案提出最小修改。"
    )
    if model_key == "gemma4":
        schema = (
            '{\n'
            '  "summary": "一句話說明修改目的",\n'
            '  "needMoreContext": ["若需要更多檔案請列出"],\n'
            '  "path": "相對路徑",\n'
            '  "target": "命中的函式、方法或區塊名稱",\n'
            '  "reason": "修改原因",\n'
            '  "search": "要被精確取代的原始片段",\n'
            '  "replace": "修改後的新片段",\n'
            '  "notes": ["補充說明"]\n'
            '}'
        )
        system_prompt = (
            "你是本機離線 code assistant，現在要產生可供人工參考的修改建議。"
            "請全程使用繁體中文說明，但 JSON key 與檔案內容保留原文。"
            "你只能修改提供給你的單一最佳候選檔案，不可新增檔案、不可刪除檔案。"
            "這一輪只允許輸出一個 path，且只允許輸出一組 search/replace。"
            "請優先做最小修改，避免重寫整個檔案。"
            "search 必須是提供給你的檔案節錄中的原文片段，且必須可唯一定位。"
            "replace 只放修改後的新片段，不要重複整份檔案。"
            "若資訊不足或無法安全修改，請把 path 留空，並把需要補看的函式或檔案寫到 needMoreContext。"
            "若需求明確指出某個名稱不存在或不可用，禁止在 target、search、replace 中繼續使用該名稱。"
            "禁止輸出多個候選方案、禁止在 JSON 外加任何自然語言說明、禁止重寫整份檔案。"
            "請只輸出 JSON。"
        )
    else:
        schema = (
            '{\n'
            '  "summary": "一句話說明修改目的",\n'
            '  "needMoreContext": ["若需要更多檔案請列出"],\n'
            '  "edits": [\n'
            '    {\n'
            '      "path": "相對路徑",\n'
            '      "target": "命中的函式、方法或區塊名稱",\n'
            '      "reason": "修改原因",\n'
            '      "notes": ["補充說明"],\n'
            '      "operations": [\n'
            '        {\n'
            '          "search": "要被精確取代的原始片段",\n'
            '          "replace": "修改後的新片段"\n'
            '        }\n'
            '      ]\n'
            '    }\n'
            '  ]\n'
            '}'
        )
        system_prompt = (
            "你是本機離線 code assistant，現在要產生可供人工參考的修改建議。"
            "請全程使用繁體中文說明，但 JSON key 與檔案內容保留原文。"
            "你只能修改提供給你的候選檔案，不可新增檔案、不可刪除檔案。"
            "請優先做最小修改，避免重寫整個檔案。"
            "請優先鎖定真正需要修改的函式或區塊，避免從檔案開頭輸出整份檔案。"
            "operations.search 必須是提供給你的檔案節錄中的原文片段，且必須可唯一定位。"
            "operations.replace 只放修改後的片段，不要重複整份檔案。"
            "若資訊不足或無法安全修改，請回傳 edits 為空陣列，並把需要補看的檔案寫到 needMoreContext。"
            "若需求是改功能，請務必指出 target 與修改原因。"
            "若需求明確指出某個名稱不存在或不可用，禁止在 target、search、replace 中繼續使用該名稱。"
            "若這一輪是在修正上一版建議，請先修正上一版的錯誤，再輸出新的最小修改，不要忽略使用者指出的問題。"
            "請只輸出 JSON，不要加 markdown 或其他文字。"
        )
    return [
        {
            "role": "system",
            "content": system_prompt,
        },
        {
            "role": "user",
            "content": (
                f"使用者需求:\n{message}\n\n"
                f"本輪任務說明:\n{refine_block}\n\n"
                f"只允許修改以下檔案:\n{allowed_block}\n\n"
                f"{forbidden_block}\n\n"
                f"{pending_edit_block}\n\n"
                f"以下是專案上下文:\n{context}\n\n"
                f"回傳格式必須符合這個 JSON schema:\n{schema}"
            ),
        },
    ]


def build_advisory_edit_messages(
    message: str,
    context: str,
    allowed_files: List[str],
    failure_reason: str = "",
    pending_edit: Optional[Dict[str, object]] = None,
    refine_mode: bool = False,
    model_key: str = "qwen",
) -> List[Dict[str, str]]:
    allowed_block = "\n".join(f"- {path}" for path in allowed_files) if allowed_files else "- (無候選檔案)"
    forbidden_identifiers = parse_forbidden_identifiers(message)
    forbidden_block = (
        "\n不得使用以下 identifier:\n" + "\n".join(f"- {item}" for item in forbidden_identifiers)
        if forbidden_identifiers else ""
    )
    pending_edit_block = build_pending_edit_prompt_block(pending_edit)
    if model_key == "gemma4":
        schema = (
            '{\n'
            '  "summary": "一句話說明修改目的",\n'
            '  "needMoreContext": ["若需要更多檔案請列出"],\n'
            '  "path": "相對路徑",\n'
            '  "target": "應修改的函式、方法或區塊名稱",\n'
            '  "whyHere": "為什麼判斷這裡要修改",\n'
            '  "before": "建議替換前片段，請只放局部原始碼",\n'
            '  "after": "建議替換後片段，請只放局部原始碼",\n'
            '  "notes": ["補充說明"]\n'
            '}'
        )
        system_prompt = (
            "你是本機離線 code assistant，現在要產生可手動複製的修改建議。"
            "請全程使用繁體中文說明，但檔案路徑、程式碼與 JSON key 保留原文。"
            "你只能針對單一最佳候選檔案提出建議，不可虛構不存在的檔案。"
            "這一輪禁止輸出多個候選方案，禁止在 JSON 外加任何自然語言說明。"
            "若無法安全給出精準 search/replace，請改用人工可操作的局部替換片段。"
            "你必須具體指出 path、target、whyHere、before、after。"
            "before 與 after 只放局部片段，不要輸出整份檔案。"
            "若需求明確指出某個名稱不存在或不可用，禁止在 target、before、after 中繼續使用該名稱。"
            "請只輸出 JSON。"
        )
    else:
        schema = (
            '{\n'
            '  "summary": "一句話說明修改目的",\n'
            '  "needMoreContext": ["若需要更多檔案請列出"],\n'
            '  "suggestions": [\n'
            '    {\n'
            '      "path": "相對路徑",\n'
            '      "target": "應修改的函式、方法或區塊名稱",\n'
            '      "whyHere": "為什麼判斷這裡要修改",\n'
            '      "before": "建議替換前片段，請只放局部原始碼",\n'
            '      "after": "建議替換後片段，請只放局部原始碼",\n'
            '      "notes": ["補充說明"]\n'
            '    }\n'
            '  ]\n'
            '}'
        )
        system_prompt = (
            "你是本機離線 code assistant，現在要產生可手動複製的修改建議。"
            "請全程使用繁體中文說明，但檔案路徑、程式碼與 JSON key 保留原文。"
            "你只能針對提供的候選檔案提出建議，不可虛構不存在的檔案。"
            "若無法安全給出精準 search/replace，請改用人工可操作的局部替換片段。"
            "你必須具體指出 target、whyHere、before、after。"
            "before 與 after 只放需要修改的局部片段，不要輸出整份檔案。"
            "若需求明確指出某個名稱不存在或不可用，禁止在 target、before、after 中繼續使用該名稱。"
            "notes 用來補充風險、前置條件或需要人工確認的地方。"
            "若這一輪是在修正上一版建議，請直接說明上一版錯在哪裡，並給出新的局部替換片段。"
            "請只輸出 JSON，不要加 markdown 或其他前後文。"
        )
    failure_block = f"\n上一輪精準修改失敗原因:\n{failure_reason}\n" if failure_reason else ""
    refine_block = (
        "這一輪是在修正上一版修改建議。請明確指出上一版哪裡錯，並根據使用者新意見提出新的局部替換片段。"
        if refine_mode else
        "這一輪是新的修改需求。請提供人工可操作的局部替換片段。"
    )
    return [
        {
            "role": "system",
            "content": system_prompt,
        },
        {
            "role": "user",
            "content": (
                f"使用者需求:\n{message}\n\n"
                f"本輪任務說明:\n{refine_block}\n\n"
                f"可參考檔案:\n{allowed_block}\n"
                f"{forbidden_block}\n"
                f"{failure_block}\n"
                f"{pending_edit_block}\n\n"
                f"以下是專案上下文:\n{context}\n\n"
                f"回傳格式必須符合這個 JSON schema:\n{schema}"
            ),
        },
    ]


def prepare_messages_for_model(model_alias: str, messages: List[Dict[str, str]]) -> List[Dict[str, str]]:
    if model_alias.startswith("gemma4"):
        return normalize_message_roles(messages)
    return messages


def create_precise_edit_plan(
    project_root: Path,
    state: SessionState,
    message: str,
    context_message: Optional[str] = None,
    pending_edit: Optional[Dict[str, object]] = None,
    refine_mode: bool = False,
) -> Dict[str, object]:
    context_message = context_message or message
    context, allowed_files = build_edit_context(project_root, state, context_message)
    if not allowed_files:
        raise RuntimeError("目前沒有可用的候選檔案可修改。請先釘選目標檔案或確認專案已正確載入。")
    if is_gemma4_state(state):
        locator = create_gemma_locator(
            project_root,
            state,
            context_message,
            allowed_files,
            pending_edit=pending_edit,
            refine_mode=refine_mode,
        )
        primary_path = str(locator.get("path", "")).strip()
        if not primary_path:
            need_more = normalize_need_more_context(locator.get("needMoreContext"))
            raise RuntimeError(
                "Gemma 4 無法唯一定位修改區段。"
                + (f"需要補充：{', '.join(need_more)}" if need_more else "請補充更明確的函式名稱、區塊名稱，或增加釘選檔案。")
            )
        allowed_files = [primary_path]
        context = build_gemma_patch_context(
            project_root,
            primary_path,
            context_message,
            str(locator.get("target", "")).strip(),
            str(locator.get("reason", "")).strip(),
        )
        raw_reply = call_local_model(
            state.model_alias,
            build_gemma_patch_messages(
                message,
                context,
                primary_path,
                str(locator.get("target", "")).strip(),
                pending_edit=pending_edit,
                refine_mode=refine_mode,
            ),
            timeout_seconds=EDIT_PLAN_TIMEOUT_SECONDS,
            max_tokens=GEMMA4_PATCH_MAX_TOKENS,
        )
        try:
            patch_payload = extract_json_payload(raw_reply)
        except Exception as exc:
            log_path = write_model_debug_log("gemma4-patch", state.model_key, raw_reply)
            raise RuntimeError(
                f"EDIT_PLAN_SCHEMA_INVALID: Gemma 4 patch 回傳不合法 JSON。{exc}。原始回覆尾段已寫入 {log_path}"
            ) from exc
        payload = {
            "summary": patch_payload.get("summary", "") or locator.get("summary", ""),
            "needMoreContext": normalize_need_more_context(patch_payload.get("needMoreContext")) or normalize_need_more_context(locator.get("needMoreContext")),
            "edits": [
                {
                    "path": str(patch_payload.get("path", "")).strip() or primary_path,
                    "target": str(patch_payload.get("target", "")).strip() or str(locator.get("target", "")).strip(),
                    "reason": str(patch_payload.get("reason", "")).strip() or str(locator.get("reason", "")).strip(),
                    "notes": patch_payload.get("notes", []),
                    "operations": [
                        {
                            "search": str(patch_payload.get("search", "")),
                            "replace": str(patch_payload.get("replace", "")),
                        }
                    ],
                }
            ],
        }
    else:
        raw_reply = call_local_model(
            state.model_alias,
            build_edit_messages(
                message,
                context,
                allowed_files,
                pending_edit=pending_edit,
                refine_mode=refine_mode,
                model_key=state.model_key,
            ),
            timeout_seconds=EDIT_PLAN_TIMEOUT_SECONDS,
            max_tokens=900,
        )
        try:
            payload = extract_json_payload(raw_reply)
        except Exception as exc:
            log_path = write_model_debug_log("edit-plan-raw", state.model_key, raw_reply)
            raise RuntimeError(f"EDIT_PLAN_SCHEMA_INVALID: 模型回傳不合法 JSON。{exc}。原始回覆尾段已寫入 {log_path}") from exc
    edits = payload.get("edits", [])
    if not isinstance(edits, list):
        raise RuntimeError("模型回傳的 edits 格式不正確。")

    normalized_edits: List[Dict[str, object]] = []
    for item in edits[:MAX_EDIT_FILES]:
        if not isinstance(item, dict):
            continue
        path = str(item.get("path", "")).strip()
        target = str(item.get("target", "")).strip()
        reason = str(item.get("reason", "")).strip()
        notes = format_notes(item.get("notes"))
        operations = item.get("operations")
        if path not in allowed_files or not isinstance(operations, list):
            continue
        before = read_file_full(project_root, path)
        after = before
        normalized_operations: List[Dict[str, str]] = []
        first_match_index: Optional[int] = None
        for operation in operations[:8]:
            if not isinstance(operation, dict):
                continue
            search = str(operation.get("search", ""))
            replace = str(operation.get("replace", ""))
            if not search:
                continue
            occurrences = after.count(search)
            if occurrences != 1:
                raise RuntimeError(
                    f"修改建議無法安全定位到 {path}：search 片段必須剛好匹配 1 次，目前匹配到 {occurrences} 次。"
                )
            if first_match_index is None:
                first_match_index = after.find(search)
            after = after.replace(search, replace, 1)
            normalized_operations.append({"search": search, "replace": replace})
        if before == after or not normalized_operations:
            continue
        before_snippet = normalized_operations[0]["search"]
        after_snippet = normalized_operations[0]["replace"]
        if is_gemma4_state(state) and (not before_snippet.strip() or not after_snippet.strip()):
            raise RuntimeError(f"Gemma 4 未提供有效的 search/replace 片段：{path}")
        safety_issues = collect_edit_safety_issues(before_snippet, after_snippet, before, message)
        if safety_issues:
            raise RuntimeError("精準修改未通過安全檢查：" + "；".join(safety_issues))
        diff_text = generate_diff(path, before, after)
        if not diff_text.strip():
            continue
        location = "未提供"
        diff_window = truncate_middle(diff_text, 12000)
        if first_match_index is not None:
            region = locate_change_region(before, first_match_index)
            location = f"約第 {region['start_line']}-{region['end_line']} 行"
            if not target:
                target = str(region["name"])
        normalized_edits.append(
            {
                "path": path,
                "target": target or path,
                "location": location,
                "reason": reason or "模型未提供原因",
                "notes": notes,
                "before": before,
                "after": after,
                "beforeSnippet": before_snippet,
                "afterSnippet": after_snippet,
                "operations": normalized_operations,
                "diff": diff_text,
                "diffWindow": diff_window,
            }
        )

    need_more_context = normalize_need_more_context(payload.get("needMoreContext"))

    plan = {
        "mode": "precise",
        "request": message,
        "refineMode": refine_mode,
        "summary": str(payload.get("summary", "")).strip() or "已產生修改建議",
        "needMoreContext": need_more_context,
        "edits": normalized_edits,
    }
    return plan


def create_advisory_edit_plan(
    project_root: Path,
    state: SessionState,
    message: str,
    allowed_files: List[str],
    failure_reason: str = "",
    pending_edit: Optional[Dict[str, object]] = None,
    refine_mode: bool = False,
    context_message: Optional[str] = None,
) -> Dict[str, object]:
    primary_path = resolve_primary_target_path(allowed_files, pending_edit, refine_mode) or ""
    effective_pending_edit = pending_edit
    if is_gemma4_state(state):
        try:
            locator = create_gemma_locator(
                project_root,
                state,
                context_message or message,
                allowed_files,
                pending_edit=pending_edit,
                refine_mode=refine_mode,
            )
        except RuntimeError as exc:
            locator = {
                "summary": "Gemma 4 無法唯一定位修改區段",
                "needMoreContext": allowed_files[:1],
                "path": "",
                "target": "",
                "locationHint": "",
                "reason": str(exc),
            }

        primary_path = str(locator.get("path", "")).strip()
        if primary_path:
            allowed_files = [primary_path]
            effective_pending_edit = effective_pending_edit or {
                "summary": str(locator.get("summary", "")).strip() or "Gemma 4 已定位區段",
                "mode": "precise",
                "failureReason": failure_reason,
                "edits": [
                    {
                        "path": primary_path,
                        "target": str(locator.get("target", "")).strip(),
                        "location": str(locator.get("locationHint", "")).strip(),
                        "reason": str(locator.get("reason", "")).strip(),
                        "beforeSnippet": str(locator.get("before", "")).strip(),
                        "afterSnippet": "",
                        "diffWindow": str(locator.get("before", "")).strip(),
                        "notes": [],
                    }
                ],
            }
        else:
            summary = str(locator.get("summary", "")).strip() or "Gemma 4 無法唯一定位修改區段"
            need_more = normalize_need_more_context(locator.get("needMoreContext")) or allowed_files[:1]
            suggestion = {
                "path": "(未指定檔案)",
                "location": str(locator.get("locationHint", "")).strip() or "未提供",
                "target": str(locator.get("target", "")).strip() or "請補充要修改的函式或區塊",
                "whyHere": str(locator.get("reason", "")).strip() or "目前無法唯一定位修改區段。",
                "before": "",
                "after": "",
                "diffWindow": "Gemma 4 目前無法唯一定位修改區段。請補充更明確的函式名稱、區塊名稱，或增加釘選檔案。",
                "notes": [
                    failure_reason or "精準模式未能提供可安全套用的修改。",
                    "目前已改為保守建議；請補充更多上下文後再試。",
                ],
            }
            return {
                "mode": "advisory",
                "request": message,
                "refineMode": refine_mode,
                "summary": summary,
                "needMoreContext": need_more,
                "edits": [],
                "suggestions": [suggestion],
                "displayText": format_plan_for_chat(
                    {
                        "mode": "advisory",
                        "summary": summary,
                        "failureReason": failure_reason,
                        "suggestions": [suggestion],
                    }
                ),
                "failureReason": failure_reason,
            }

    advisory_message = context_message or message
    if is_gemma4_state(state) and effective_pending_edit:
        advisory_message = build_refinement_ranking_message(advisory_message, effective_pending_edit)
    context = build_advisory_context(project_root, state, advisory_message, allowed_files)
    raw_reply = call_local_model(
        state.model_alias,
        build_advisory_edit_messages(
            message,
            context,
            allowed_files,
            failure_reason,
            pending_edit=effective_pending_edit,
            refine_mode=refine_mode,
            model_key=state.model_key,
        ),
        timeout_seconds=EDIT_PLAN_TIMEOUT_SECONDS,
        max_tokens=GEMMA4_ADVISORY_MAX_TOKENS if is_gemma4_state(state) else 1200,
    )
    try:
        payload = extract_json_payload(raw_reply)
    except Exception as exc:
        log_kind = "gemma4-advisory" if is_gemma4_state(state) else "edit-plan-raw"
        log_path = write_model_debug_log(log_kind, state.model_key, raw_reply)
        schema_reason = f"{failure_reason + '；' if failure_reason else ''}EDIT_PLAN_SCHEMA_INVALID: 模型回傳不合法 JSON。{exc}。原始回覆尾段已寫入 {log_path}"
        return build_fallback_advisory_plan(
            project_root,
            state,
            message,
            allowed_files,
            schema_reason,
            pending_edit=effective_pending_edit,
            refine_mode=refine_mode,
            raw_reply=raw_reply,
        )
    if is_gemma4_state(state):
        payload = {
            "summary": payload.get("summary", ""),
            "needMoreContext": normalize_need_more_context(payload.get("needMoreContext")),
            "suggestions": [
                {
                    "path": str(payload.get("path", "")).strip() or (primary_path or ""),
                    "target": str(payload.get("target", "")).strip(),
                    "whyHere": str(payload.get("whyHere", "")).strip(),
                    "before": str(payload.get("before", "")).strip(),
                    "after": str(payload.get("after", "")).strip(),
                    "notes": payload.get("notes", []),
                }
            ],
        }

    suggestions = payload.get("suggestions", [])
    if not isinstance(suggestions, list):
        suggestions = []
    normalized_suggestions: List[Dict[str, str]] = []
    display_blocks: List[str] = []
    for item in suggestions[:MAX_EDIT_FILES]:
        if not isinstance(item, dict):
            continue
        path = str(item.get("path", "")).strip()
        target = str(item.get("target", "")).strip() or "未提供"
        why_here = str(item.get("whyHere", "")).strip() or "模型未提供原因"
        before_snippet = str(item.get("before", "")).strip()
        after_snippet = str(item.get("after", "")).strip()
        notes = format_notes(item.get("notes"))
        if not path and primary_path:
            path = primary_path
        if path and path not in allowed_files:
            continue
        display_path = path or "(未指定檔案)"
        location = "未提供"
        diff_window = build_diff_window(display_path, before_snippet or "(未提供)", after_snippet or "(未提供)")
        if path:
            try:
                full_before = read_file_full(project_root, path)
                if before_snippet:
                    occurrences = full_before.count(before_snippet)
                    if occurrences == 1:
                        match_index = full_before.find(before_snippet)
                        full_after = full_before.replace(before_snippet, after_snippet, 1)
                        region = locate_change_region(full_before, match_index)
                        location = f"約第 {region['start_line']}-{region['end_line']} 行"
                        if target == "未提供":
                            target = str(region["name"])
                        diff_window = truncate_middle(generate_diff(path, full_before, full_after), 12000)
            except (OSError, ValueError):
                pass
        if path:
            try:
                full_before = read_file_full(project_root, path)
                safety_issues = collect_edit_safety_issues(before_snippet, after_snippet, full_before, message)
            except (OSError, ValueError):
                safety_issues = []
        else:
            safety_issues = []
        if safety_issues:
            notes = notes + [f"保守檢查：{'；'.join(safety_issues)}", "請補充正確的函式、欄位或變數名稱後再重新產生建議。"]
            before_snippet = ""
            after_snippet = ""
            diff_window = "模型建議引用未確認或被否定的 identifier，已停止輸出具體替換片段。"
        if is_gemma4_state(state) and not before_snippet and not after_snippet:
            notes = notes + ["Gemma 4 未提供足夠的局部替換片段，已保留為保守文字建議。"]
        normalized_suggestions.append(
            {
                "path": display_path,
                "location": location,
                "target": target,
                "whyHere": why_here,
                "before": before_snippet,
                "after": after_snippet,
                "diffWindow": diff_window,
                "notes": notes,
            }
        )
        block = [
            f"檔案：{display_path}",
            f"修改位置：{location}",
            f"命中函式/區塊：{target}",
            f"原因：{why_here}",
            "建議替換前片段：",
            before_snippet or "模型未提供原始片段。",
            "",
            "建議替換後片段：",
            after_snippet or "模型未提供建議片段。",
            "",
            "Diff 視窗：",
            diff_window,
        ]
        if notes:
            block.extend(["", "補充說明：", "\n".join(f"- {note}" for note in notes)])
        display_blocks.append("\n".join(block))

    need_more_context = normalize_need_more_context(payload.get("needMoreContext"))
    display_text = "\n\n---\n\n".join(display_blocks).strip()
    if not display_text:
        display_text = raw_reply.strip() or "模型未提供可用內容。"

    return {
        "mode": "advisory",
        "request": message,
        "refineMode": refine_mode,
        "summary": str(payload.get("summary", "")).strip() or "已產生文字建議",
        "needMoreContext": need_more_context,
        "edits": [],
        "suggestions": normalized_suggestions,
        "displayText": display_text,
        "failureReason": failure_reason,
    }


def create_edit_plan(project_root: Path, state: SessionState, message: str) -> Dict[str, object]:
    refine_mode = is_refinement_request(message, state.pending_edit)
    effective_message = build_refinement_ranking_message(message, state.pending_edit) if refine_mode else message
    context, allowed_files = build_edit_context(project_root, state, effective_message)
    if not allowed_files:
        raise RuntimeError("目前沒有可用的候選檔案可修改。請先釘選目標檔案或確認專案已正確載入。")
    try:
        plan = create_precise_edit_plan(
            project_root,
            state,
            message,
            context_message=effective_message,
            pending_edit=state.pending_edit,
            refine_mode=refine_mode,
        )
        if plan.get("edits"):
            return plan
        failure_reason = "模型沒有產生可安全套用的精準修改。"
    except RuntimeError as exc:
        failure_reason = str(exc)
    return create_advisory_edit_plan(
        project_root,
        state,
        message,
        allowed_files,
        failure_reason,
        pending_edit=state.pending_edit,
        refine_mode=refine_mode,
        context_message=effective_message,
    )


def call_local_model(
    model_alias: str,
    messages: List[Dict[str, str]],
    timeout_seconds: int = 180,
    max_tokens: int = 600,
    continue_on_length: int = 0,
    raw_mode: bool = False,
) -> str:
    endpoint = get_model_endpoint(model_alias)
    working_messages = list(messages)
    parts: List[str] = []
    remaining_continuations = max(0, continue_on_length)
    while True:
        prepared_messages = prepare_messages_for_model(model_alias, working_messages)
        payload = json.dumps(
            {
                "model": model_alias,
                "messages": prepared_messages,
                "temperature": 0.2,
                "stream": False,
                "max_tokens": max_tokens,
            },
            ensure_ascii=False,
        ).encode("utf-8")
        request = urllib.request.Request(
            endpoint,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
                body = json.loads(response.read().decode("utf-8"))
        except (TimeoutError, socket.timeout) as exc:
            raise RuntimeError(
                f"本地模型回應逾時。模型可能正在生成過長內容、主機效能不足，或需要縮小上下文。timeout={timeout_seconds}s"
            ) from exc
        except urllib.error.HTTPError as exc:
            details = ""
            try:
                details = exc.read().decode("utf-8", errors="replace")
            except Exception:
                details = str(exc)
            if exc.code == 400 and "exceeds the available context size" in details:
                raise RuntimeError(
                    "目前送給模型的專案上下文太大，超過這台機器目前可用的 context 上限。請縮小對話歷史、減少釘選檔案，或重新開啟專案後再試。"
                ) from exc
            raise RuntimeError(f"Failed to call local model endpoint: HTTP {exc.code}: {details}") from exc
        except urllib.error.URLError as exc:
            reason = getattr(exc, "reason", "")
            if isinstance(reason, (TimeoutError, socket.timeout)) or "timed out" in str(reason).lower():
                raise RuntimeError(
                    f"本地模型回應逾時。模型可能正在生成過長內容、主機效能不足，或需要縮小上下文。timeout={timeout_seconds}s"
                ) from exc
            raise RuntimeError(f"Failed to call local model endpoint: {exc}") from exc
        try:
            choice = body["choices"][0]
            raw_content = str(choice["message"]["content"])
            finish_reason = str(choice.get("finish_reason", "") or "")
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError("Unexpected model response format.") from exc
        parts.append(raw_content)
        if finish_reason != "length" or remaining_continuations <= 0:
            break
        remaining_continuations -= 1
        working_messages.append({"role": "assistant", "content": raw_content})
        working_messages.append({"role": "user", "content": "請直接從上一句繼續回答，不要重複前文，不要重新開場。"})
    return sanitize_model_reply(model_alias, "\n".join(part for part in parts if part.strip()), raw_mode=raw_mode)


def parse_script_output(output: str) -> Dict[str, str]:
    metadata: Dict[str, str] = {}
    for line in output.splitlines():
        if line.startswith("[ERROR_CODE] "):
            metadata["code"] = line[len("[ERROR_CODE] "):].strip()
        elif line.startswith("[ERROR_MESSAGE] "):
            metadata["message"] = line[len("[ERROR_MESSAGE] "):].strip()
        elif line.startswith("[ERROR_DETAILS] "):
            metadata["details"] = line[len("[ERROR_DETAILS] "):].strip()
        elif line.startswith("[LOG_FILE] "):
            metadata["logPath"] = line[len("[LOG_FILE] "):].strip()
    return metadata


def classify_start_server_error(output: str, model_key: str) -> Dict[str, object]:
    info = parse_script_output(output)
    code = info.get("code", "MODEL_START_FAILED")
    message = info.get("message", "Failed to start model service.")
    details = info.get("details", output.strip())
    action = None
    if code == "MODEL_INVALID":
        action = "redownload-model"
    return make_error(
        code=code,
        message=message,
        details=details,
        action=action,
        log_path=info.get("logPath"),
        extra={"modelKey": model_key},
    )


def build_session_payload(
    project_root: Path,
    model_key: str,
    preserve_history: bool = False,
    preserve_pins: bool = False,
) -> Dict[str, object]:
    files = collect_project_files(project_root)
    file_paths = [file.path for file in files]
    entrypoints = detect_entrypoints(file_paths)
    tests = detect_test_locations(file_paths)
    summary = build_summary(project_root, files, entrypoints, tests)
    tree = file_paths[:MAX_TREE_ITEMS]
    _, model_alias = resolve_model_details(model_key)
    with STATE_LOCK:
        existing_history = list(STATE.history)
        existing_pins = [path for path in STATE.pinned_files if path in file_paths]
        existing_preview = STATE.current_preview_path if STATE.current_preview_path in file_paths else None
        STATE.project_path = str(project_root)
        STATE.model_key = model_key
        STATE.model_alias = model_alias
        STATE.summary = summary
        STATE.tree = tree
        STATE.files = files
        STATE.entrypoints = entrypoints
        STATE.tests = tests
        STATE.pinned_files = existing_pins if preserve_pins else []
        STATE.current_preview_path = existing_preview if preserve_history or preserve_pins else None
        STATE.history = existing_history if preserve_history else []
        STATE.pending_edit = None
        STATE.ui_state = "ready"
    return {
        "projectPath": str(project_root),
        "modelKey": model_key,
        "modelAlias": model_alias,
        "summary": summary,
        "tree": tree,
        "entrypoints": entrypoints,
        "tests": tests,
        "fileCount": len(files),
        "uiState": "ready",
    }


def open_project_worker(task_id: str, project_path: str, model_key: str) -> None:
    clear_session(ui_state="opening")
    try:
        update_task(task_id, status="running", progress=10, step="驗證專案路徑", message="正在檢查專案路徑")
        project_root = normalize_path(project_path)
        if not project_root.exists() or not project_root.is_dir():
            raise ValueError(f"Project directory not found: {project_root}")

        update_task(task_id, progress=25, step="準備 Git 工作區", message="正在初始化或檢查 git repository")
        attach = run_script("attach-project.cmd", str(project_root), timeout_seconds=ATTACH_PROJECT_TIMEOUT_SECONDS)
        if attach.returncode != 0:
            raise RuntimeError(json.dumps(make_error("GIT_INIT_FAILED", "Failed to prepare git repository.", attach.stdout + attach.stderr)))

        update_task(task_id, progress=45, step="Git 工作區完成", message="已完成 git 初始化與基線快照")
        update_task(task_id, progress=55, step="啟動本地模型", message="正在驗證模型並啟動 llama-server")
        ensure_local_model_server(model_key, port=get_model_port(model_key))

        update_task(task_id, progress=85, step="索引專案", message="正在掃描檔案、入口與測試位置")
        result = build_session_payload(project_root, model_key)
        update_task(task_id, status="completed", progress=100, step="完成", message="專案已開啟", result=result)
    except ValueError as exc:
        clear_session(ui_state="error")
        update_task(
            task_id,
            status="failed",
            progress=100,
            step="失敗",
            message="開啟專案失敗",
            error=make_error("PROJECT_PATH_INVALID", "Project path is invalid.", str(exc)),
        )
    except RuntimeError as exc:
        clear_session(ui_state="error")
        error_payload: Dict[str, object]
        try:
            error_payload = json.loads(str(exc))
        except json.JSONDecodeError:
            error_payload = make_error("MODEL_START_FAILED", "Open project failed.", str(exc))
        update_task(task_id, status="failed", progress=100, step="失敗", message="開啟專案失敗", error=error_payload)
    except subprocess.TimeoutExpired as exc:
        clear_session(ui_state="error")
        command = " ".join(str(part) for part in exc.cmd) if exc.cmd else ""
        stdout = exc.stdout if isinstance(exc.stdout, str) else ""
        stderr = exc.stderr if isinstance(exc.stderr, str) else ""
        if "attach-project.cmd" in command:
            error_payload = make_error(
                "GIT_INIT_FAILED",
                "Preparing git repository timed out.",
                "attach-project.cmd 超過等待時間。資料夾可能過大、含大量資源檔，或 git commit 被互動式設定卡住。\n\n"
                + (stdout + stderr).strip(),
            )
        else:
            error_payload = make_error(
                "MODEL_START_FAILED",
                "Starting local model timed out.",
                "start-server.cmd 超過等待時間。請檢查 logs 目錄中的 llama-server log。\n\n"
                + (stdout + stderr).strip(),
            )
        update_task(task_id, status="failed", progress=100, step="失敗", message="開啟專案失敗", error=error_payload)
    except Exception as exc:
        clear_session(ui_state="error")
        update_task(
            task_id,
            status="failed",
            progress=100,
            step="失敗",
            message="開啟專案失敗",
            error=make_error("INDEX_FAILED", "Unexpected error while opening project.", traceback.format_exc()),
        )


def redownload_model_worker(task_id: str, model_key: str) -> None:
    try:
        update_task(task_id, status="running", progress=3, step="驗證模型", message="正在確認模型設定")
        if model_key not in {"qwen", "gemma4"}:
            raise RuntimeError(json.dumps(make_error("MODEL_INVALID", "Unsupported model.", model_key)))

        model_path, model_size = download_model_with_progress(task_id, model_key)

        update_task(
            task_id,
            status="completed",
            progress=100,
            step="完成",
            message="模型重新下載完成",
            result={
                "modelKey": model_key,
                "modelPath": str(model_path),
                "modelSize": model_size,
            },
        )
    except ValueError as exc:
        update_task(
            task_id,
            status="failed",
            progress=100,
            step="失敗",
            message="模型重新下載失敗",
            error=make_error("MODEL_INVALID", "Model validation failed.", str(exc), extra={"modelKey": model_key}),
        )
    except urllib.error.HTTPError as exc:
        details = ""
        try:
            details = exc.read().decode("utf-8", errors="replace")
        except Exception:
            details = str(exc)
        update_task(
            task_id,
            status="failed",
            progress=100,
            step="失敗",
            message="模型重新下載失敗",
            error=make_error("MODEL_DOWNLOAD_FAILED", "Failed to download model.", details or str(exc), extra={"modelKey": model_key}),
        )
    except RuntimeError as exc:
        try:
            error_payload = json.loads(str(exc))
        except json.JSONDecodeError:
            error_payload = make_error("MODEL_DOWNLOAD_FAILED", "Failed to redownload model.", str(exc))
        update_task(task_id, status="failed", progress=100, step="失敗", message="模型重新下載失敗", error=error_payload)
    except Exception:
        update_task(
            task_id,
            status="failed",
            progress=100,
            step="失敗",
            message="模型重新下載失敗",
            error=make_error("MODEL_DOWNLOAD_FAILED", "Unexpected error while redownloading model.", traceback.format_exc(), extra={"modelKey": model_key}),
        )


def start_background_task(kind: str, worker, *args: str) -> TaskState:
    task = create_task(kind)
    thread = threading.Thread(target=worker, args=(task.id, *args), daemon=True)
    thread.start()
    return task


def get_status_payload() -> Dict[str, object]:
    with STATE_LOCK:
        return {
            "projectPath": STATE.project_path,
            "modelKey": STATE.model_key,
            "modelAlias": STATE.model_alias,
            "summary": STATE.summary,
            "tree": STATE.tree,
            "entrypoints": STATE.entrypoints,
            "tests": STATE.tests,
            "pinnedFiles": STATE.pinned_files,
            "currentPreviewPath": STATE.current_preview_path,
            "history": STATE.history[-20:],
            "pendingEdit": STATE.pending_edit,
            "uiState": STATE.ui_state,
        }


class WebUIHandler(BaseHTTPRequestHandler):
    server_version = "CodeWorkerWebUI/2.0"

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/":
            self.serve_static("index.html")
            return
        if parsed.path == "/api/status":
            json_response(self, {"ok": True, "data": get_status_payload()})
            return
        if parsed.path == "/api/file":
            self.handle_file_request(parsed)
            return
        if parsed.path.startswith("/api/tasks/"):
            self.handle_task_status(parsed.path)
            return
        self.serve_static(parsed.path.lstrip("/"))

    def do_POST(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/pick-folder":
            self.handle_pick_folder()
            return
        if parsed.path == "/api/tasks/open-project":
            self.handle_open_project_task()
            return
        if parsed.path == "/api/models/redownload":
            self.handle_redownload_model()
            return
        if parsed.path == "/api/analyze":
            self.handle_analyze()
            return
        if parsed.path == "/api/chat":
            self.handle_chat()
            return
        if parsed.path == "/api/edit/plan":
            self.handle_edit_plan()
            return
        if parsed.path == "/api/edit/discard":
            self.handle_discard_edit()
            return
        if parsed.path == "/api/pin-files":
            self.handle_pin_files()
            return
        if parsed.path == "/api/reset-history":
            self.handle_reset_history()
            return
        error_response(self, make_error("NOT_FOUND", "Not found."), status=404)

    def log_message(self, format: str, *args) -> None:
        return

    def serve_static(self, relative_path: str) -> None:
        safe_path = (STATIC_DIR / relative_path).resolve()
        if not str(safe_path).startswith(str(STATIC_DIR)) or not safe_path.exists() or safe_path.is_dir():
            error_response(self, make_error("NOT_FOUND", "Not found."), status=404)
            return
        content_type, _ = mimetypes.guess_type(str(safe_path))
        text_response(self, safe_path.read_text(encoding="utf-8"), 200, (content_type or "text/plain") + "; charset=utf-8")

    def read_json_body(self) -> Dict[str, object]:
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length) if length else b"{}"
        return json.loads(raw.decode("utf-8"))

    def handle_task_status(self, path: str) -> None:
        task_id = path.rsplit("/", 1)[-1]
        task = get_task(task_id)
        if not task:
            error_response(self, make_error("TASK_NOT_FOUND", "Task not found."), status=404)
            return
        json_response(self, {"ok": True, "data": asdict(task)})

    def handle_pick_folder(self) -> None:
        try:
            result = choose_folder()
            json_response(self, {"ok": True, "data": result})
        except Exception as exc:
            error_response(self, make_error("PICK_FOLDER_FAILED", "Failed to open folder picker.", str(exc)))

    def handle_open_project_task(self) -> None:
        try:
            payload = self.read_json_body()
            project_path = str(payload.get("projectPath", "")).strip()
            model_key = str(payload.get("modelKey", "qwen")).strip().lower()
            if model_key not in {"qwen", "gemma4"}:
                raise ValueError("Unsupported model. Use qwen or gemma4.")
            if not project_path:
                raise ValueError("Project path is required.")
            setattr(self.server, "_pending_edit_internal", None)
            task = start_background_task(TASK_OPEN_PROJECT, open_project_worker, project_path, model_key)
            json_response(self, {"ok": True, "data": {"taskId": task.id, "kind": task.kind}})
        except ValueError as exc:
            error_response(self, make_error("PROJECT_PATH_INVALID", "Project path is invalid.", str(exc)))

    def handle_redownload_model(self) -> None:
        try:
            payload = self.read_json_body()
            model_key = str(payload.get("modelKey", "qwen")).strip().lower()
            task = start_background_task(TASK_REDOWNLOAD_MODEL, redownload_model_worker, model_key)
            json_response(self, {"ok": True, "data": {"taskId": task.id, "kind": task.kind}})
        except Exception as exc:
            error_response(self, make_error("MODEL_DOWNLOAD_FAILED", "Failed to start model redownload.", str(exc)))

    def handle_analyze(self) -> None:
        try:
            payload = self.read_json_body()
            prompt = str(payload.get("prompt", DEFAULT_ANALYSIS_PROMPT)).strip() or DEFAULT_ANALYSIS_PROMPT
            with STATE_LOCK:
                if STATE.ui_state != "ready" or not STATE.project_path:
                    raise ValueError("請先完成開啟專案。")
                require_pinned_context(STATE)
                project_root = Path(STATE.project_path)
                context = build_project_context(project_root, STATE, prompt)
                model_alias = STATE.model_alias
                model_key = STATE.model_key
            messages = [
                {"role": "user", "content": build_raw_analyze_user_message(prompt, context)},
            ]
            reply = call_local_model(
                model_alias,
                messages,
                max_tokens=get_analyze_max_tokens(model_key),
                timeout_seconds=get_analyze_timeout_seconds(model_key),
                continue_on_length=0,
                raw_mode=True,
            )
            with STATE_LOCK:
                STATE.history.append({"role": "assistant", "content": reply, "kind": "analysis"})
            json_response(self, {"ok": True, "data": {"reply": reply}})
        except ValueError as exc:
            details = str(exc)
            code = "PROJECT_NOT_READY" if details == "請先完成開啟專案。" else "PINNED_CONTEXT_REQUIRED"
            message = "Project is not ready." if code == "PROJECT_NOT_READY" else "請先套用釘選檔案。"
            error_response(self, make_error(code, message, details))
        except Exception as exc:
            error_response(self, make_error("MODEL_START_FAILED", "Analyze failed.", str(exc)))

    def handle_chat(self) -> None:
        try:
            payload = self.read_json_body()
            message = str(payload.get("message", "")).strip()
            if not message:
                raise ValueError("message is required.")
            with STATE_LOCK:
                if STATE.ui_state != "ready" or not STATE.project_path:
                    raise ValueError("請先完成開啟專案。")
                require_pinned_context(STATE)
                project_root = Path(STATE.project_path)
                snapshot = SessionState(
                    project_path=STATE.project_path,
                    model_key=STATE.model_key,
                    model_alias=STATE.model_alias,
                    summary=STATE.summary,
                    tree=list(STATE.tree),
                    files=list(STATE.files),
                    entrypoints=list(STATE.entrypoints),
                    tests=list(STATE.tests),
                    pinned_files=list(STATE.pinned_files),
                    current_preview_path=None,
                    history=list(STATE.history),
                    pending_edit=STATE.pending_edit,
                    ui_state=STATE.ui_state,
                )
                context = build_project_context(project_root, snapshot, message)
                model_alias = STATE.model_alias
            messages = [
                {"role": "user", "content": build_raw_chat_user_message(context, message)},
            ]
            reply = call_local_model(
                model_alias,
                messages,
                max_tokens=get_chat_max_tokens(snapshot.model_key),
                timeout_seconds=get_chat_timeout_seconds(snapshot.model_key),
                continue_on_length=0,
                raw_mode=True,
            )
            with STATE_LOCK:
                STATE.history.append({"role": "user", "content": message, "kind": "chat"})
                STATE.history.append({"role": "assistant", "content": reply, "kind": "chat"})
            json_response(self, {"ok": True, "data": {"reply": reply}})
        except ValueError as exc:
            details = str(exc)
            code = "PROJECT_NOT_READY" if details == "請先完成開啟專案。" else "PINNED_CONTEXT_REQUIRED"
            message = "Project is not ready." if code == "PROJECT_NOT_READY" else "請先套用釘選檔案。"
            error_response(self, make_error(code, message, details))
        except Exception as exc:
            error_response(self, make_error("MODEL_START_FAILED", "Chat failed.", str(exc)))

    def handle_edit_plan(self) -> None:
        try:
            payload = self.read_json_body()
            message = str(payload.get("message", "")).strip()
            if not message:
                raise ValueError("message is required.")
            with STATE_LOCK:
                if STATE.ui_state != "ready" or not STATE.project_path:
                    raise ValueError("請先完成開啟專案。")
                require_pinned_context(STATE)
                project_root = Path(STATE.project_path)
                snapshot = SessionState(
                    project_path=STATE.project_path,
                    model_key=STATE.model_key,
                    model_alias=STATE.model_alias,
                    summary=STATE.summary,
                    tree=list(STATE.tree),
                    files=list(STATE.files),
                    entrypoints=list(STATE.entrypoints),
                    tests=list(STATE.tests),
                    pinned_files=list(STATE.pinned_files),
                    current_preview_path=None,
                    history=list(STATE.history),
                    pending_edit=STATE.pending_edit,
                    ui_state=STATE.ui_state,
                )
            plan = create_edit_plan(project_root, snapshot, message)
            public_plan = build_public_plan(plan)
            reply_text = format_plan_for_chat(public_plan)
            with STATE_LOCK:
                STATE.pending_edit = public_plan
                STATE.history.append({"role": "user", "content": message, "kind": "edit-request"})
                STATE.history.append({"role": "assistant", "content": reply_text, "kind": "edit-plan"})
            setattr(self.server, "_pending_edit_internal", plan)
            json_response(self, {"ok": True, "data": {"plan": public_plan}})
        except ValueError as exc:
            details = str(exc)
            code = "PROJECT_NOT_READY" if details == "請先完成開啟專案。" else "PINNED_CONTEXT_REQUIRED"
            message = "Project is not ready." if code == "PROJECT_NOT_READY" else "請先套用釘選檔案。"
            error_response(self, make_error(code, message, details))
        except RuntimeError as exc:
            try:
                error_payload = json.loads(str(exc))
            except json.JSONDecodeError:
                details = str(exc)
                code = "EDIT_PLAN_TIMEOUT" if "逾時" in details or "timeout=" in details else "EDIT_PLAN_FAILED"
                message = "產生修改建議逾時。" if code == "EDIT_PLAN_TIMEOUT" else "Generate edit plan failed."
                error_payload = make_error(code, message, details)
            error_response(self, error_payload)
        except Exception as exc:
            error_response(self, make_error("EDIT_PLAN_FAILED", "Generate edit plan failed.", str(exc)))

    def handle_discard_edit(self) -> None:
        with STATE_LOCK:
            STATE.pending_edit = None
        setattr(self.server, "_pending_edit_internal", None)
        json_response(self, {"ok": True, "data": {"discarded": True}})

    def handle_pin_files(self) -> None:
        try:
            payload = self.read_json_body()
            files = payload.get("files", [])
            if not isinstance(files, list):
                raise ValueError("files must be a list.")
            with STATE_LOCK:
                if STATE.ui_state != "ready":
                    raise ValueError("Project is not ready.")
                allowed = {file.path for file in STATE.files}
                pinned = [path for path in files if isinstance(path, str) and path in allowed][:8]
                STATE.pinned_files = pinned
            json_response(self, {"ok": True, "data": {"pinnedFiles": pinned}})
        except ValueError as exc:
            error_response(self, make_error("PROJECT_NOT_READY", "Project is not ready.", str(exc)))

    def handle_reset_history(self) -> None:
        with STATE_LOCK:
            STATE.history = []
            STATE.pending_edit = None
        setattr(self.server, "_pending_edit_internal", None)
        json_response(self, {"ok": True, "data": {"history": [], "pendingEdit": None}})

    def handle_file_request(self, parsed: urllib.parse.ParseResult) -> None:
        try:
            query = urllib.parse.parse_qs(parsed.query)
            relative_path = query.get("path", [""])[0]
            if not relative_path:
                raise ValueError("path is required.")
            with STATE_LOCK:
                if STATE.ui_state != "ready" or not STATE.project_path:
                    raise ValueError("Project is not ready.")
                project_root = Path(STATE.project_path)
                if relative_path not in {file.path for file in STATE.files}:
                    raise ValueError("File is not part of the indexed project.")
                STATE.current_preview_path = relative_path
            content = read_file_full(project_root, relative_path)
            json_response(self, {"ok": True, "data": {"path": relative_path, "content": content}})
        except ValueError as exc:
            error_response(self, make_error("PROJECT_NOT_READY", "Cannot preview file.", str(exc)))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8764, type=int)
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), WebUIHandler)
    print(f"CodeWorker Web UI running at http://{args.host}:{args.port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
