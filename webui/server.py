import argparse
import base64
import ctypes
import difflib
import fnmatch
import hashlib
import importlib.util
import json
import mimetypes
import os
import platform
import re
import shutil
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

from core.models import (
    get_model_config as get_registry_model_config,
    get_model_configs,
    match_first_model_file,
    public_model_capabilities,
)
from agent.runtime import confirm_action as confirm_agent_action
from agent.runtime import run_agent
from rag.index import impact_analysis, index_dir as rag_index_dir, index_is_stale, rebuild_index, search_index


ROOT_DIR = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = ROOT_DIR / "scripts"
STATIC_DIR = Path(__file__).resolve().parent / "static"
CONFIG_DIR = ROOT_DIR / "config"
BOOTSTRAP_MANIFEST_PATH = CONFIG_DIR / "bootstrap.manifest.json"
DATA_DIR = ROOT_DIR / "data"
MAX_SCAN_FILES = 8000
MAX_TREE_ITEMS = 400
MAX_CONTEXT_FILES = 4
MAX_FILE_CHARS = 3600
MAX_TOTAL_CONTEXT = 12000
MAX_FOCUSED_CHAT_FILE_CHARS = 22000
MAX_FOCUSED_CHAT_TOTAL_CHARS = 22000
MAX_PREVIEW_CHAT_CHARS = 22000
MAX_TREE_CONTEXT_ITEMS = 30
MAX_CHAT_HISTORY_ITEMS = 8
MAX_CHAT_HISTORY_ITEM_CHARS = 1800
MAX_CHAT_HISTORY_TOTAL_CHARS = 7200
MAX_MEMORY_SUMMARY_CHARS = 3200
MAX_MEMORY_SUMMARY_LINE_CHARS = 360
MEMORY_COMPACT_TRIGGER_ITEMS = 4
ATTACH_PROJECT_TIMEOUT_SECONDS = 180
START_SERVER_TIMEOUT_SECONDS = 120
DEFAULT_MODEL_KEY = "gemma4"
DEFAULT_MODEL_ALIAS = "gemma4-local"
MODEL_PORTS = {
    "gemma4": 8081,
    "qwen35": 8082,
}
MODEL_DEFAULT_CONTEXT = {
    "gemma4": 4096,
    "qwen35": 12288,
}
MODEL_CHAT_MAX_TOKENS = {
    "gemma4": 4096,
    "qwen35": 2048,
}
MODEL_ANALYZE_MAX_TOKENS = {
    "gemma4": 2800,
    "qwen35": 1200,
}
MODEL_CHAT_TIMEOUT_SECONDS = {
    "gemma4": 1200,
    "qwen35": 1200,
}
MODEL_ANALYZE_TIMEOUT_SECONDS = {
    "gemma4": 1200,
    "qwen35": 1200,
}
MODEL_HISTORY_LIMIT = {
    "gemma4": 4,
    "qwen35": 6,
}
MODEL_CONTEXT_LIMITS = {
    "gemma4": {"max_files": 2, "file_chars": 2600, "total_chars": 9000, "single_file_chars": 18000, "single_total_chars": 18000},
    "qwen35": {
        "max_files": 4,
        "file_chars": 6400,
        "total_chars": 26000,
        "single_file_chars": 26000,
        "single_total_chars": 30000,
        "full_max_files": 4,
        "full_total_chars": 32000,
        "full_file_chars": 22000,
    },
}
MODEL_ALIASES = {
    "gemma4": "gemma4-local",
    "qwen35": "qwen35-local",
}
MODEL_DIR_NAMES = {
    "gemma4": "gemma4-26b-unsloth-ud-q4-k-m",
    "qwen35": "qwen3.5-9b-q4-mmproj",
}
MODEL_FILE_PATTERNS = {
    "gemma4": "*gemma-4-26B-A4B-it*UD-Q4_K_M*.gguf",
    "qwen35": "Qwen3.5-9B-Q4_K_M.gguf",
}
MODEL_MMPROJ_PATTERNS = {
    "gemma4": "*mmproj-BF16*.gguf",
    "qwen35": "mmproj-BF16.gguf",
}
MODEL_GENERATION_OPTIONS = {
    "gemma4": {"temperature": 1.0, "top_p": 0.95, "top_k": 64},
    "qwen35": {"temperature": 0.2},
}
MODEL_CAPABILITIES = {
    "gemma4": {
        "display_name": "Gemma 4 26B",
        "supports_images": True,
        "requires_mmproj": True,
        "compact_image_context": True,
    },
    "qwen35": {
        "display_name": "Qwen 3.5 9B Vision",
        "supports_images": True,
        "requires_mmproj": True,
        "compact_image_context": True,
    },
}
try:
    SUPPORTED_MODEL_KEYS = {
        key for key, config in get_model_configs(ROOT_DIR).items()
        if config.enabled
    } or set(MODEL_PORTS.keys())
except Exception:
    SUPPORTED_MODEL_KEYS = set(MODEL_PORTS.keys())
UPLOAD_DIR = ROOT_DIR / ".tmp" / "chat-uploads"
IMAGE_UPLOAD_DIR = UPLOAD_DIR
MAX_UPLOAD_BYTES = 25 * 1024 * 1024
MAX_IMAGE_UPLOAD_BYTES = MAX_UPLOAD_BYTES
MAX_TEXT_ATTACHMENT_CHARS = 18000
MAX_MODEL_IMAGE_EDGE = 896
MAX_AUDIO_TRANSCRIPT_CHARS = 12000
DEFAULT_STT_MAX_SECONDS = 900
SUPPORTED_IMAGE_MIME_TYPES = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
}
TEXT_UPLOAD_EXTENSIONS = {
    ".pas", ".dfm", ".dpr", ".dproj", ".cpp", ".cc", ".cxx", ".c", ".h", ".hpp",
    ".java", ".kt", ".py", ".js", ".jsx", ".ts", ".tsx", ".go", ".rs", ".rust",
    ".swift", ".lua", ".sql", ".sh", ".bat", ".cmd", ".ps1", ".cs", ".html",
    ".css", ".scss", ".vue", ".svelte", ".json", ".yaml", ".yml", ".xml",
    ".toml", ".ini", ".csv", ".env", ".txt", ".md", ".tex", ".rtf",
}
DOCUMENT_UPLOAD_EXTENSIONS = {".pdf", ".doc", ".docx"}
AUDIO_UPLOAD_EXTENSIONS = {".mp3", ".wav", ".aac", ".flac", ".m4a", ".ogg"}
VIDEO_UPLOAD_EXTENSIONS = {".mp4", ".mov", ".avi", ".webm", ".mkv"}
IMAGE_UPLOAD_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".svg", ".gif", ".ico"}
SUPPORTED_FILE_EXTENSIONS = (
    TEXT_UPLOAD_EXTENSIONS
    | DOCUMENT_UPLOAD_EXTENSIONS
    | AUDIO_UPLOAD_EXTENSIONS
    | VIDEO_UPLOAD_EXTENSIONS
    | IMAGE_UPLOAD_EXTENSIONS
)
IGNORED_DIRS = {
    ".git", ".hg", ".svn", "node_modules", ".venv", "venv", "__pycache__",
    "dist", "build", "target", "out", ".idea", ".vscode", ".next", ".nuxt", ".cache", "coverage",
    ".tmp", ".codex-artifacts", "runtime", "models", "downloads",
}
GENERATED_PATH_PREFIXES = {
    ("data", "indexes"),
    ("logs",),
}
IGNORED_EXTENSIONS = {
    ".zip", ".7z", ".gz",
    ".tar", ".rar", ".exe", ".dll", ".so", ".dylib", ".class", ".jar", ".pyc", ".pyo", ".db",
    ".sqlite",
}
LANGUAGE_BY_EXTENSION = {
    ".py": "Python", ".js": "JavaScript", ".jsx": "JavaScript", ".ts": "TypeScript", ".tsx": "TypeScript",
    ".java": "Java", ".kt": "Kotlin", ".go": "Go", ".rs": "Rust", ".php": "PHP", ".rb": "Ruby", ".cs": "C#",
    ".cpp": "C++", ".cc": "C++", ".cxx": "C++", ".c": "C", ".h": "C/C++ Header", ".hpp": "C/C++ Header",
    ".swift": "Swift", ".m": "Objective-C", ".mm": "Objective-C++", ".scala": "Scala", ".sql": "SQL",
    ".html": "HTML", ".css": "CSS", ".scss": "SCSS", ".vue": "Vue", ".svelte": "Svelte", ".json": "JSON",
    ".yml": "YAML", ".yaml": "YAML", ".toml": "TOML", ".xml": "XML", ".sh": "Shell", ".bat": "Batch",
    ".cmd": "Batch", ".ps1": "PowerShell", ".md": "Markdown", ".txt": "Text",
    ".pdf": "PDF", ".doc": "Word", ".docx": "Word", ".rtf": "RTF", ".png": "Image", ".jpg": "Image",
    ".jpeg": "Image", ".webp": "Image", ".bmp": "Image", ".svg": "SVG", ".gif": "Image",
    ".mp3": "Audio", ".wav": "Audio", ".aac": "Audio", ".flac": "Audio", ".mp4": "Video",
    ".mov": "Video", ".avi": "Video", ".webm": "Video", ".mkv": "Video",
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
EDIT_PLAN_TIMEOUT_SECONDS = 1200
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
    model_key: str = DEFAULT_MODEL_KEY
    model_alias: str = DEFAULT_MODEL_ALIAS
    summary: str = ""
    tree: List[str] = field(default_factory=list)
    files: List[ProjectFile] = field(default_factory=list)
    entrypoints: List[str] = field(default_factory=list)
    tests: List[str] = field(default_factory=list)
    pinned_files: List[str] = field(default_factory=list)
    current_preview_path: Optional[str] = None
    history: List[Dict[str, object]] = field(default_factory=list)
    memory_summary: str = ""
    memory_compacted_count: int = 0
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
AGENT_RUNS: Dict[str, Dict[str, object]] = {}
STATE_LOCK = threading.Lock()
TASK_LOCK = threading.Lock()
HF_API_HEADERS = {
    "User-Agent": "CodeWorkerWebUI/2.0",
    "Accept": "application/json",
}
DETACHED_FLAGS = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
MODEL_SERVER_PROCESSES: Dict[Tuple[str, int], subprocess.Popen] = {}
MODEL_SERVER_LOG_HANDLES: Dict[Tuple[str, int], Tuple[object, object]] = {}
FILE_UPLOADS: Dict[str, Dict[str, object]] = {}
FILE_UPLOADS_LOCK = threading.Lock()
IMAGE_UPLOADS = FILE_UPLOADS
IMAGE_UPLOADS_LOCK = FILE_UPLOADS_LOCK
ANSWER_ONLY_SYSTEM_PROMPT = (
    "請只輸出最終答案，不要輸出 thinking、推理過程、分析步驟或 reasoning。"
    "若需要整理，直接給結論與可執行重點。"
)
ANSWER_ONLY_RETRY_PROMPT = (
    "上一輪只產生了 reasoning，沒有產生可顯示的 final answer。"
    "請重新回答同一個問題，只輸出最終答案，不要輸出 thinking、推理過程、分析步驟或 reasoning。"
)
CONTINUE_TOKENS = (
    "繼續", "續寫", "上一句", "剛剛", "前面", "接著", "未完成", "沒了",
    "continue", "go on", "keep going", "previous answer", "last answer",
)


class ModelReplyError(RuntimeError):
    def __init__(self, error: Dict[str, object]):
        super().__init__(str(error.get("message", "Model reply failed.")))
        self.error = error


def get_model_key_from_alias(model_alias: str) -> str:
    lowered = (model_alias or "").lower()
    for key, config in get_model_configs(ROOT_DIR).items():
        if lowered == config.alias.lower() or lowered == config.model_id.lower() or lowered.startswith(key):
            return key
    if lowered.startswith("qwen35"):
        return "qwen35"
    if lowered.startswith("gemma4"):
        return "gemma4"
    return DEFAULT_MODEL_KEY


def get_model_port(model_name: str) -> int:
    model_key = get_model_key_from_alias(model_name)
    config = get_registry_model_config(ROOT_DIR, model_key)
    if config and config.port:
        return config.port
    return MODEL_PORTS.get(model_key, MODEL_PORTS[DEFAULT_MODEL_KEY])


def get_model_alias(model_key: str) -> str:
    config = get_registry_model_config(ROOT_DIR, model_key)
    if config and config.alias:
        return config.alias
    return MODEL_ALIASES.get(model_key, MODEL_ALIASES[DEFAULT_MODEL_KEY])


def get_model_directory(model_key: str) -> Path:
    config = get_registry_model_config(ROOT_DIR, model_key)
    if config and config.target_dir:
        return ROOT_DIR / config.target_dir
    return ROOT_DIR / "models" / MODEL_DIR_NAMES.get(model_key, MODEL_DIR_NAMES[DEFAULT_MODEL_KEY])


def get_model_file_pattern(model_key: str) -> str:
    config = get_registry_model_config(ROOT_DIR, model_key)
    if config and config.file_pattern:
        return config.file_pattern
    return MODEL_FILE_PATTERNS.get(model_key, MODEL_FILE_PATTERNS[DEFAULT_MODEL_KEY])


def get_model_mmproj_pattern(model_key: str) -> Optional[str]:
    patterns = get_model_mmproj_patterns(model_key)
    return patterns[0] if patterns else None


def get_model_mmproj_patterns(model_key: str) -> List[str]:
    config = get_registry_model_config(ROOT_DIR, model_key)
    if config and config.mmproj_patterns:
        return config.mmproj_patterns
    pattern = MODEL_MMPROJ_PATTERNS.get(model_key)
    return [pattern] if pattern else []


def get_model_capabilities(model_key: str) -> Dict[str, object]:
    default = {
        "display_name": model_key,
        "supports_images": False,
        "requires_mmproj": False,
        "compact_image_context": False,
    }
    default.update(MODEL_CAPABILITIES.get(model_key, {}))
    config = get_registry_model_config(ROOT_DIR, model_key)
    if config:
        default.update({
            "display_name": config.display_name,
            "supports_images": config.supports_images,
            "requires_mmproj": bool(config.mmproj_patterns),
            "compact_image_context": config.compact_image_context,
        })
    return default


def get_public_model_capabilities() -> Dict[str, Dict[str, object]]:
    manifest_payload = public_model_capabilities(ROOT_DIR)
    if manifest_payload:
        return manifest_payload
    return {
        key: {
            "displayName": str(get_model_capabilities(key).get("display_name", key)),
            "supportsImages": bool(get_model_capabilities(key).get("supports_images")),
            "requiresMmproj": bool(get_model_capabilities(key).get("requires_mmproj")),
            "compactImageContext": bool(get_model_capabilities(key).get("compact_image_context")),
            "provider": "llama.cpp",
            "modelId": get_model_alias(key),
            "port": get_model_port(key),
            "contextWindow": get_model_context_limit(key),
            "targetDir": str(get_model_directory(key).relative_to(ROOT_DIR)),
        }
        for key in sorted(SUPPORTED_MODEL_KEYS)
    }


def model_supports_images(model_key: str) -> bool:
    return bool(get_model_capabilities(model_key).get("supports_images"))


def model_has_native_image_transport(model_key: str) -> bool:
    if not model_supports_images(model_key):
        return False
    if bool(get_model_capabilities(model_key).get("requires_mmproj")):
        patterns = get_model_mmproj_patterns(model_key)
        return bool(patterns and match_first_model_file(get_model_directory(model_key), patterns))
    return True


def model_prefers_compact_image_context(model_key: str) -> bool:
    return bool(get_model_capabilities(model_key).get("compact_image_context"))


def get_model_endpoint(model_name: str) -> str:
    return f"http://127.0.0.1:{get_model_port(model_name)}/v1/chat/completions"


def get_model_context_limit(model_key: str) -> int:
    config = get_registry_model_config(ROOT_DIR, model_key)
    if config and config.context_window:
        return config.context_window
    return MODEL_DEFAULT_CONTEXT.get(model_key, MODEL_DEFAULT_CONTEXT[DEFAULT_MODEL_KEY])


def get_chat_history_limit(model_key: str) -> int:
    return MODEL_HISTORY_LIMIT.get(model_key, MODEL_HISTORY_LIMIT[DEFAULT_MODEL_KEY])


def get_chat_max_tokens(model_key: str) -> int:
    return MODEL_CHAT_MAX_TOKENS.get(model_key, MODEL_CHAT_MAX_TOKENS[DEFAULT_MODEL_KEY])


def get_model_generation_options(model_key: str) -> Dict[str, object]:
    options = dict(MODEL_GENERATION_OPTIONS.get(model_key, MODEL_GENERATION_OPTIONS.get(DEFAULT_MODEL_KEY, {})))
    config = get_registry_model_config(ROOT_DIR, model_key)
    if config:
        if config.temperature is not None:
            options["temperature"] = config.temperature
        if config.top_p is not None:
            options["top_p"] = config.top_p
        if config.top_k is not None:
            options["top_k"] = config.top_k
    return options


def get_analyze_max_tokens(model_key: str) -> int:
    return MODEL_ANALYZE_MAX_TOKENS.get(model_key, MODEL_ANALYZE_MAX_TOKENS[DEFAULT_MODEL_KEY])


def get_chat_timeout_seconds(model_key: str) -> int:
    return MODEL_CHAT_TIMEOUT_SECONDS.get(model_key, MODEL_CHAT_TIMEOUT_SECONDS[DEFAULT_MODEL_KEY])


def get_analyze_timeout_seconds(model_key: str) -> int:
    return MODEL_ANALYZE_TIMEOUT_SECONDS.get(model_key, MODEL_ANALYZE_TIMEOUT_SECONDS[DEFAULT_MODEL_KEY])


def get_context_limits(model_key: str, single_file_focus: bool, prefer_compact: bool = False) -> Dict[str, int]:
    limits = MODEL_CONTEXT_LIMITS.get(model_key, MODEL_CONTEXT_LIMITS[DEFAULT_MODEL_KEY]).copy()
    if single_file_focus:
        limits["file_chars"] = limits["single_file_chars"]
        limits["total_chars"] = limits["single_total_chars"]
    if prefer_compact and model_prefers_compact_image_context(model_key):
        limits["max_files"] = min(limits.get("max_files", 2), 2)
        limits["file_chars"] = min(limits.get("file_chars", 3200), 3200)
        limits["total_chars"] = min(limits.get("total_chars", 9000), 9000)
        limits["full_max_files"] = 0
        limits["full_total_chars"] = 0
        limits["full_file_chars"] = 0
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
        STATE.model_key = DEFAULT_MODEL_KEY
        STATE.model_alias = DEFAULT_MODEL_ALIAS
        STATE.summary = ""
        STATE.tree = []
        STATE.files = []
        STATE.entrypoints = []
        STATE.tests = []
        STATE.pinned_files = []
        STATE.current_preview_path = None
        STATE.history = []
        STATE.memory_summary = ""
        STATE.memory_compacted_count = 0
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
    filenames = [
        item.get("rfilename", "")
        for item in siblings
        if isinstance(item, dict) and item.get("rfilename", "")
    ]
    if any(token in file_pattern for token in ["*", "?", "["]):
        candidates = [
            name for name in filenames
            if fnmatch.fnmatch(name.lower(), file_pattern.lower())
        ]
    else:
        candidates = [
            name for name in filenames
            if re.fullmatch(file_pattern, name)
        ]
    non_split = [name for name in candidates if not re.search(r"-\d{5}-of-\d{5}\.gguf$", name)]
    if non_split:
        candidates = non_split
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


def check_minimum_memory() -> Optional[str]:
    if os.name != "nt":
        return None
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
        return None
    try:
        total = int(result.stdout.strip())
    except ValueError:
        return None
    if total <= 0:
        return None
    if total < 32 * 1024 * 1024 * 1024:
        return (
            "Recommended system memory for larger local models is 32GB RAM or above. "
            f"Detected: {total / (1024 * 1024 * 1024):.1f} GB. "
            "Integrated graphics may reduce available system memory."
        )
    return None


def resolve_model_details(model_key: str) -> Tuple[Path, str]:
    return get_model_directory(model_key), get_model_alias(model_key)


def find_model_file(model_dir: Path, pattern: str = "*.gguf") -> Optional[Path]:
    matches = sorted(
        path
        for path in model_dir.glob("*.gguf")
        if fnmatch.fnmatch(path.name.lower(), pattern.lower())
    )
    return matches[0] if matches else None


def cleanup_image_upload_dir() -> None:
    if UPLOAD_DIR.exists():
        shutil.rmtree(UPLOAD_DIR, ignore_errors=True)
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    with FILE_UPLOADS_LOCK:
        FILE_UPLOADS.clear()


def decode_image_payload(data: str) -> bytes:
    raw = str(data or "").strip()
    if not raw:
        raise ValueError("Image data is required.")
    if raw.startswith("data:"):
        _, _, raw = raw.partition(",")
    try:
        return base64.b64decode(raw, validate=True)
    except Exception as exc:
        raise ValueError("Image data is not valid base64.") from exc


def normalize_uploaded_image(file_path: Path, mime_type: str) -> Dict[str, object]:
    if mime_type not in {"image/png", "image/jpeg"}:
        return {"normalized": False}
    powershell_script = r"""
Add-Type -AssemblyName System.Drawing
$ImagePath = $env:CODEWORKER_IMAGE_PATH
$MimeType = $env:CODEWORKER_IMAGE_MIME
$MaxEdge = [int]$env:CODEWORKER_IMAGE_MAX_EDGE
$TempPath = "$ImagePath.resize"
$source = $null
$target = $null
$graphics = $null
try {
    $source = [System.Drawing.Image]::FromFile($ImagePath)
    $width = [int]$source.Width
    $height = [int]$source.Height
    if ($width -le $MaxEdge -and $height -le $MaxEdge) {
        @{ normalized = $false; width = $width; height = $height } | ConvertTo-Json -Compress
        exit 0
    }
    $scale = [Math]::Min($MaxEdge / [double]$width, $MaxEdge / [double]$height)
    $newWidth = [Math]::Max(1, [int][Math]::Round($width * $scale))
    $newHeight = [Math]::Max(1, [int][Math]::Round($height * $scale))
    if (Test-Path $TempPath) {
        Remove-Item -LiteralPath $TempPath -Force -ErrorAction SilentlyContinue
    }
    $target = New-Object System.Drawing.Bitmap($newWidth, $newHeight)
    $graphics = [System.Drawing.Graphics]::FromImage($target)
    $graphics.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
    $graphics.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::HighQuality
    $graphics.PixelOffsetMode = [System.Drawing.Drawing2D.PixelOffsetMode]::HighQuality
    $graphics.DrawImage($source, 0, 0, $newWidth, $newHeight)
    if ($MimeType -eq 'image/jpeg') {
        $target.Save($TempPath, [System.Drawing.Imaging.ImageFormat]::Jpeg)
    } else {
        $target.Save($TempPath, [System.Drawing.Imaging.ImageFormat]::Png)
    }
}
finally {
    if ($graphics) { $graphics.Dispose() }
    if ($target) { $target.Dispose() }
    if ($source) { $source.Dispose() }
}
Move-Item -LiteralPath $TempPath -Destination $ImagePath -Force
@{ normalized = $true; width = $newWidth; height = $newHeight } | ConvertTo-Json -Compress
exit 0
"""
    try:
        env = os.environ.copy()
        env["CODEWORKER_IMAGE_PATH"] = str(file_path)
        env["CODEWORKER_IMAGE_MIME"] = mime_type
        env["CODEWORKER_IMAGE_MAX_EDGE"] = str(MAX_MODEL_IMAGE_EDGE)
        result = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                powershell_script,
            ],
            cwd=str(ROOT_DIR),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            timeout=60,
            env=env,
        )
    except Exception:
        return {"normalized": False}
    if result.returncode != 0:
        return {"normalized": False, "details": (result.stderr or result.stdout).strip()}
    try:
        payload = json.loads((result.stdout or "").strip() or "{}")
    except json.JSONDecodeError:
        return {"normalized": False}
    return {
        "normalized": bool(payload.get("normalized")),
        "width": int(payload.get("width", 0) or 0),
        "height": int(payload.get("height", 0) or 0),
    }


def get_upload_kind(extension: str, mime_type: str) -> str:
    lowered_ext = extension.lower()
    lowered_mime = mime_type.lower()
    if lowered_ext in IMAGE_UPLOAD_EXTENSIONS or lowered_mime.startswith("image/"):
        return "image"
    if lowered_ext in AUDIO_UPLOAD_EXTENSIONS or lowered_mime.startswith("audio/"):
        return "audio"
    if lowered_ext in VIDEO_UPLOAD_EXTENSIONS or lowered_mime.startswith("video/"):
        return "video"
    if lowered_ext in DOCUMENT_UPLOAD_EXTENSIONS:
        return "document"
    return "text"


def find_command(candidates: List[str]) -> Optional[str]:
    bundled = {
        "ffmpeg": ROOT_DIR / "runtime" / "ffmpeg" / "bin" / "ffmpeg.exe",
        "ffprobe": ROOT_DIR / "runtime" / "ffmpeg" / "bin" / "ffprobe.exe",
        "whisper": ROOT_DIR / "runtime" / "whisper" / "bin" / "whisper-cli.exe",
        "whisper-cli": ROOT_DIR / "runtime" / "whisper" / "bin" / "whisper-cli.exe",
    }
    for candidate in candidates:
        lowered = candidate.lower()
        bundled_path = bundled.get(lowered)
        if bundled_path and bundled_path.exists():
            return str(bundled_path)
        if lowered in {"whisper", "whisper-cli"}:
            for fallback in (
                ROOT_DIR / "runtime" / "whisper" / "whisper-cli.exe",
                ROOT_DIR / "runtime" / "whisper" / "build" / "bin" / "Release" / "whisper-cli.exe",
            ):
                if fallback.exists():
                    return str(fallback)
        path = shutil.which(candidate)
        if path:
            return path
    return None


def get_total_physical_memory_gb() -> Optional[float]:
    if platform.system().lower() == "windows":
        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]

        status = MEMORYSTATUSEX()
        status.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):  # type: ignore[attr-defined]
            return round(status.ullTotalPhys / (1024 ** 3), 2)
        return None
    try:
        pages = os.sysconf("SC_PHYS_PAGES")
        page_size = os.sysconf("SC_PAGE_SIZE")
        return round((pages * page_size) / (1024 ** 3), 2)
    except (AttributeError, ValueError, OSError):
        return None


def get_media_analysis_assessment() -> Dict[str, object]:
    ram_gb = get_total_physical_memory_gb()
    cpu_threads = os.cpu_count() or 0
    profile = "unknown"
    recommended_max_keyframes = 8
    if ram_gb is not None:
        if ram_gb < 24:
            profile = "limited"
            recommended_max_keyframes = 6
        elif ram_gb < 48:
            profile = "balanced-cpu-igpu"
            recommended_max_keyframes = 12
        else:
            profile = "large-memory"
            recommended_max_keyframes = 24
    if cpu_threads and cpu_threads < 8:
        recommended_max_keyframes = min(recommended_max_keyframes, 8)
    override = os.environ.get("CODEWORKER_VIDEO_MAX_KEYFRAMES", "").strip()
    if override:
        try:
            recommended_max_keyframes = max(1, min(60, int(override)))
            profile = f"{profile}:override"
        except ValueError:
            pass
    return {
        "profile": profile,
        "ramGb": ram_gb,
        "cpuThreads": cpu_threads,
        "recommendedMaxKeyframes": recommended_max_keyframes,
        "videoStrategy": "sampled-keyframes",
        "speechToText": get_stt_backend_status(),
    }


def ensure_ffmpeg_runtime() -> Tuple[Optional[str], Optional[str], str]:
    ffmpeg = find_command(["ffmpeg"])
    ffprobe = find_command(["ffprobe"])
    if ffmpeg and ffprobe:
        return ffmpeg, ffprobe, "ready"
    bootstrap = run_script("bootstrap.cmd", "-SkipModels", "-SkipWinPython", timeout_seconds=600)
    ffmpeg = find_command(["ffmpeg"])
    ffprobe = find_command(["ffprobe"])
    if ffmpeg and ffprobe:
        return ffmpeg, ffprobe, "installed"
    details = (bootstrap.stdout + bootstrap.stderr).strip()
    return None, None, details or "ffmpeg/ffprobe not found"


def get_stt_backend_status() -> Dict[str, object]:
    if os.environ.get("CODEWORKER_STT_DISABLED", "").strip().lower() in {"1", "true", "yes"}:
        return {"available": False, "backend": "disabled", "reason": "CODEWORKER_STT_DISABLED"}
    if os.environ.get("CODEWORKER_STT_COMMAND", "").strip():
        return {"available": True, "backend": "custom-command"}
    whisper_cpp = find_command(["whisper-cli"])
    whisper_cpp_model = get_whisper_cpp_model_path()
    if whisper_cpp and whisper_cpp_model:
        return {"available": True, "backend": "whisper.cpp", "path": whisper_cpp, "modelPath": str(whisper_cpp_model), "installHint": "bundled"}
    if importlib.util.find_spec("faster_whisper") is not None:
        return {"available": True, "backend": "faster-whisper"}
    if importlib.util.find_spec("whisper") is not None:
        return {"available": True, "backend": "openai-whisper"}
    whisper_cli = find_command(["whisper"])
    if whisper_cli:
        return {"available": True, "backend": "whisper-cli", "path": whisper_cli}
    return {
        "available": False,
        "backend": "none",
        "reason": "Install whisper.cpp/faster-whisper/openai-whisper or set CODEWORKER_STT_COMMAND.",
        "installHint": "Run scripts/bootstrap.cmd -SkipModels -SkipWinPython to install bundled whisper.cpp.",
    }


def get_whisper_cpp_model_path() -> Optional[Path]:
    configured = os.environ.get("CODEWORKER_WHISPER_CPP_MODEL", "").strip()
    if configured:
        path = Path(configured)
        return path if path.exists() else None
    model_dir = ROOT_DIR / "runtime" / "whisper" / "models"
    for name in ("ggml-base.bin", "ggml-base.en.bin", "ggml-small.bin", "ggml-tiny.bin", "ggml-tiny.en.bin"):
        path = model_dir / name
        if path.exists():
            return path
    return None


def get_stt_max_seconds() -> int:
    raw = os.environ.get("CODEWORKER_STT_MAX_SECONDS", "").strip()
    if not raw:
        return DEFAULT_STT_MAX_SECONDS
    try:
        return max(1, int(float(raw)))
    except ValueError:
        return DEFAULT_STT_MAX_SECONDS


def media_has_audio_stream(source: Path, ffprobe: str) -> bool:
    try:
        result = subprocess.run(
            [
                ffprobe,
                "-v",
                "error",
                "-select_streams",
                "a:0",
                "-show_entries",
                "stream=codec_type",
                "-of",
                "csv=p=0",
                str(source),
            ],
            cwd=str(ROOT_DIR),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
            check=False,
        )
    except Exception:
        return False
    return result.returncode == 0 and "audio" in (result.stdout or "").lower()


def extract_media_audio_to_wav(source: Path, upload_id: str, ffmpeg: str) -> Tuple[Optional[Path], str]:
    target_dir = UPLOAD_DIR / "audio"
    target_dir.mkdir(parents=True, exist_ok=True)
    wav_path = target_dir / f"{upload_id}.wav"
    result = subprocess.run(
        [
            ffmpeg,
            "-y",
            "-i",
            str(source),
            "-vn",
            "-ac",
            "1",
            "-ar",
            "16000",
            "-f",
            "wav",
            str(wav_path),
        ],
        cwd=str(ROOT_DIR),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=180,
        check=False,
    )
    if result.returncode != 0 or not wav_path.exists() or wav_path.stat().st_size <= 44:
        details = (result.stderr or result.stdout or "").strip().splitlines()
        return None, (details[-1][:240] if details else "audio-extract-failed")
    return wav_path, "ready"


def transcribe_wav_with_backend(wav_path: Path) -> Tuple[str, str]:
    language = os.environ.get("CODEWORKER_STT_LANGUAGE", "").strip()
    model_name = os.environ.get("CODEWORKER_STT_MODEL", "base").strip() or "base"
    custom_command = os.environ.get("CODEWORKER_STT_COMMAND", "").strip()
    if custom_command:
        output_dir = UPLOAD_DIR / "transcripts"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"{wav_path.stem}.txt"
        command = custom_command.format(
            input=str(wav_path),
            output=str(output_path),
            output_dir=str(output_dir),
            model=model_name,
            language=language,
        )
        result = subprocess.run(
            command,
            cwd=str(ROOT_DIR),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=max(60, get_stt_max_seconds() * 4),
            shell=True,
            check=False,
        )
        if output_path.exists():
            text = output_path.read_text(encoding="utf-8", errors="replace").strip()
            if text:
                return text, "custom-command"
        text = (result.stdout or "").strip()
        if result.returncode == 0 and text:
            return text, "custom-command:stdout"
        details = (result.stderr or result.stdout or "").strip().splitlines()
        raise RuntimeError(details[-1] if details else "custom STT command produced no transcript")

    whisper_cpp = find_command(["whisper-cli"])
    whisper_cpp_model = get_whisper_cpp_model_path()
    if whisper_cpp and whisper_cpp_model:
        output_dir = UPLOAD_DIR / "transcripts"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_prefix = output_dir / wav_path.stem
        command = [
            whisper_cpp,
            "-m",
            str(whisper_cpp_model),
            "-f",
            str(wav_path),
            "-otxt",
            "-of",
            str(output_prefix),
        ]
        if language:
            command.extend(["-l", language])
        result = subprocess.run(
            command,
            cwd=str(ROOT_DIR),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=max(60, get_stt_max_seconds() * 4),
            check=False,
        )
        output_path = output_prefix.with_suffix(".txt")
        if result.returncode == 0 and output_path.exists():
            text = output_path.read_text(encoding="utf-8", errors="replace").strip()
            if text:
                return text, "whisper.cpp"
        details = (result.stderr or result.stdout or "").strip().splitlines()
        raise RuntimeError(details[-1] if details else "whisper.cpp produced no transcript")

    if importlib.util.find_spec("faster_whisper") is not None:
        from faster_whisper import WhisperModel  # type: ignore

        model = WhisperModel(model_name, device="cpu", compute_type="int8")
        kwargs = {"beam_size": 1}
        if language:
            kwargs["language"] = language
        segments, _info = model.transcribe(str(wav_path), **kwargs)
        text = "\n".join(segment.text.strip() for segment in segments if segment.text.strip()).strip()
        if text:
            return text, "faster-whisper"
        raise RuntimeError("faster-whisper produced no transcript")

    if importlib.util.find_spec("whisper") is not None:
        import whisper  # type: ignore

        model = whisper.load_model(model_name)
        kwargs = {}
        if language:
            kwargs["language"] = language
        result = model.transcribe(str(wav_path), **kwargs)
        text = str(result.get("text", "")).strip()
        if text:
            return text, "openai-whisper"
        raise RuntimeError("openai-whisper produced no transcript")

    whisper_cli = find_command(["whisper"])
    if whisper_cli:
        output_dir = UPLOAD_DIR / "transcripts"
        output_dir.mkdir(parents=True, exist_ok=True)
        command = [
            whisper_cli,
            str(wav_path),
            "--model",
            model_name,
            "--output_format",
            "txt",
            "--output_dir",
            str(output_dir),
        ]
        if language:
            command.extend(["--language", language])
        result = subprocess.run(
            command,
            cwd=str(ROOT_DIR),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=max(60, get_stt_max_seconds() * 4),
            check=False,
        )
        output_path = output_dir / f"{wav_path.stem}.txt"
        if result.returncode == 0 and output_path.exists():
            text = output_path.read_text(encoding="utf-8", errors="replace").strip()
            if text:
                return text, "whisper-cli"
        details = (result.stderr or result.stdout or "").strip().splitlines()
        raise RuntimeError(details[-1] if details else "whisper CLI produced no transcript")

    raise RuntimeError("no STT backend available")


def transcribe_media_attachment(upload: Dict[str, object]) -> None:
    kind = str(upload.get("kind", ""))
    if kind not in {"audio", "video"}:
        return
    source = Path(str(upload.get("path", "")))
    if not source.exists():
        upload["transcriptStatus"] = "audio-transcript-unavailable:source-missing"
        if kind == "audio":
            upload["extractionStatus"] = upload["transcriptStatus"]
        return
    ffmpeg, ffprobe, ffmpeg_status = ensure_ffmpeg_runtime()
    if not ffmpeg or not ffprobe:
        upload["transcriptStatus"] = f"audio-transcript-unavailable:{ffmpeg_status}"
        if kind == "audio":
            upload["extractionStatus"] = upload["transcriptStatus"]
        return
    duration = get_video_duration_seconds(source, ffprobe)
    if duration is not None and not float(upload.get("durationSeconds", 0) or 0):
        upload["durationSeconds"] = round(duration, 3)
    max_seconds = get_stt_max_seconds()
    if duration is not None and duration > max_seconds:
        upload["transcriptStatus"] = f"audio-transcript-skipped:duration-too-long:{duration:.1f}s>{max_seconds}s"
        if kind == "audio":
            upload["extractionStatus"] = upload["transcriptStatus"]
        return
    if not media_has_audio_stream(source, ffprobe):
        upload["transcriptStatus"] = "audio-transcript-unavailable:no-audio-stream"
        if kind == "audio":
            upload["extractionStatus"] = upload["transcriptStatus"]
        return
    backend_status = get_stt_backend_status()
    if not backend_status.get("available"):
        reason = str(backend_status.get("reason", backend_status.get("backend", "unavailable")))
        upload["transcriptStatus"] = f"audio-transcript-unavailable:{reason}"
        if kind == "audio":
            upload["extractionStatus"] = upload["transcriptStatus"]
        return
    wav_path, audio_status = extract_media_audio_to_wav(source, str(upload.get("id", uuid.uuid4().hex)), ffmpeg)
    if wav_path is None:
        upload["transcriptStatus"] = f"audio-transcript-unavailable:{audio_status}"
        if kind == "audio":
            upload["extractionStatus"] = upload["transcriptStatus"]
        return
    try:
        transcript, backend = transcribe_wav_with_backend(wav_path)
    except Exception as exc:
        upload["transcriptStatus"] = f"audio-transcript-unavailable:{exc}"
        if kind == "audio":
            upload["extractionStatus"] = upload["transcriptStatus"]
        return
    transcript = transcript.strip()
    if not transcript:
        upload["transcriptStatus"] = "audio-transcript-unavailable:empty-transcript"
        if kind == "audio":
            upload["extractionStatus"] = upload["transcriptStatus"]
        return
    if len(transcript) > MAX_AUDIO_TRANSCRIPT_CHARS:
        transcript = transcript[:MAX_AUDIO_TRANSCRIPT_CHARS].rstrip() + "\n[transcript truncated]"
        status = f"audio-transcript-truncated:{backend}"
    else:
        status = f"audio-transcript-extracted:{backend}"
    upload["textPreview"] = transcript
    upload["textBlocks"] = [transcript]
    upload["transcriptStatus"] = status
    upload["transcriptChars"] = len(transcript)
    if kind == "audio":
        upload["extractionStatus"] = status


def convert_doc_to_docx(file_path: Path) -> Optional[Path]:
    soffice = find_command(["soffice", "libreoffice"])
    if not soffice:
        return None
    target_dir = UPLOAD_DIR / "converted"
    target_dir.mkdir(parents=True, exist_ok=True)
    before = {item.name for item in target_dir.glob("*.docx")}
    result = subprocess.run(
        [
            soffice,
            "--headless",
            "--convert-to",
            "docx",
            "--outdir",
            str(target_dir),
            str(file_path),
        ],
        cwd=str(ROOT_DIR),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
        check=False,
    )
    if result.returncode != 0:
        return None
    converted = [item for item in target_dir.glob("*.docx") if item.name not in before]
    if not converted:
        fallback = target_dir / f"{file_path.stem}.docx"
        return fallback if fallback.exists() else None
    return converted[0]


def extract_text_from_upload(file_path: Path, extension: str, mime_type: str) -> Tuple[str, str]:
    lowered_ext = extension.lower()
    if lowered_ext in TEXT_UPLOAD_EXTENSIONS or mime_type.startswith("text/"):
        content = file_path.read_text(encoding="utf-8", errors="replace")
        return content[:MAX_TEXT_ATTACHMENT_CHARS], "text-extracted" if len(content) <= MAX_TEXT_ATTACHMENT_CHARS else "text-truncated"
    if lowered_ext == ".pdf":
        parser_errors: List[str] = []
        try:
            from pypdf import PdfReader  # type: ignore
            reader = PdfReader(str(file_path))
            text = "\n".join(page.extract_text() or "" for page in reader.pages[:20]).strip()
            return text[:MAX_TEXT_ATTACHMENT_CHARS], "text-extracted" if text else "metadata-only"
        except Exception as exc:
            parser_errors.append(f"pypdf: {exc}")
        try:
            import pdfplumber  # type: ignore
            with pdfplumber.open(str(file_path)) as pdf:
                text = "\n".join(page.extract_text() or "" for page in pdf.pages[:20]).strip()
            return text[:MAX_TEXT_ATTACHMENT_CHARS], "text-extracted" if text else "metadata-only"
        except Exception as exc:
            parser_errors.append(f"pdfplumber: {exc}")
        return "", "parser-unavailable: " + " | ".join(parser_errors)
    if lowered_ext == ".doc":
        converted = convert_doc_to_docx(file_path)
        if converted is not None:
            text, status = extract_text_from_upload(converted, ".docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
            return text, f"converted-doc:{status}" if text else "legacy-doc-metadata-only"
        return "", "legacy-doc-metadata-only"
    if lowered_ext == ".docx":
        try:
            import docx  # type: ignore
            doc = docx.Document(str(file_path))
            text = "\n".join(paragraph.text for paragraph in doc.paragraphs).strip()
            return text[:MAX_TEXT_ATTACHMENT_CHARS], "text-extracted" if text else "metadata-only"
        except Exception as exc:
            return "", f"parser-unavailable: {exc}"
    return "", "metadata-only"


def save_uploaded_file(name: str, mime_type: str, data: str) -> Dict[str, object]:
    clean_name = Path(str(name or "").strip() or "attachment").name
    content_type = str(mime_type or "").strip().lower()
    guessed_extension = Path(clean_name).suffix.lower()
    extension = SUPPORTED_IMAGE_MIME_TYPES.get(content_type) or guessed_extension or mimetypes.guess_extension(content_type) or ".bin"
    if extension.lower() not in SUPPORTED_FILE_EXTENSIONS and not content_type.startswith(("text/", "image/", "audio/", "video/")):
        raise ValueError(f"Unsupported file format: {extension or content_type}")
    file_bytes = decode_image_payload(data)
    if not file_bytes:
        raise ValueError("Uploaded file is empty.")
    if len(file_bytes) > MAX_UPLOAD_BYTES:
        raise ValueError(f"Uploaded file is too large. Limit: {MAX_UPLOAD_BYTES // (1024 * 1024)} MB.")
    original_sha256 = hashlib.sha256(file_bytes).hexdigest()
    upload_id = uuid.uuid4().hex
    file_path = UPLOAD_DIR / f"{upload_id}{extension}"
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_bytes(file_bytes)
    kind = get_upload_kind(extension, content_type)
    normalization = normalize_uploaded_image(file_path, content_type) if kind == "image" else {"normalized": False}
    model_sha256 = hashlib.sha256(file_path.read_bytes()).hexdigest()
    text_preview, extraction_status = extract_text_from_upload(file_path, extension, content_type)
    if kind == "image" and extraction_status == "metadata-only":
        extraction_status = "vision-pending"
    if kind == "video" and extraction_status == "metadata-only":
        extraction_status = "video-keyframes-pending"
    if kind == "audio" and extraction_status == "metadata-only":
        extraction_status = "audio-transcript-unavailable"
    size_bytes = file_path.stat().st_size if file_path.exists() else len(file_bytes)
    payload = {
        "id": upload_id,
        "name": clean_name,
        "mimeType": content_type,
        "sizeBytes": size_bytes,
        "path": str(file_path),
        "kind": kind,
        "extension": extension,
        "normalizedForModel": bool(normalization.get("normalized")),
        "width": int(normalization.get("width", 0) or 0),
        "height": int(normalization.get("height", 0) or 0),
        "originalSha256": original_sha256,
        "sha256": model_sha256,
        "durationSeconds": 0,
        "keyframeCount": 0,
        "videoAnalysisMode": "",
        "videoFrameTimestamps": [],
        "transcriptStatus": "",
        "transcriptChars": 0,
        "textPreview": text_preview,
        "extractionStatus": extraction_status,
        "nativeParts": [{"type": "image_url"}] if kind == "image" else [],
        "textBlocks": [text_preview] if text_preview else [],
        "derivedFiles": [],
    }
    with FILE_UPLOADS_LOCK:
        FILE_UPLOADS[upload_id] = payload
    if kind == "video":
        payload["derivedFiles"] = derive_video_keyframes(payload)
        transcribe_media_attachment(payload)
    elif kind == "audio":
        transcribe_media_attachment(payload)
    return payload


def register_derived_file(name: str, mime_type: str, file_path: Path, kind: str, extraction_status: str) -> Dict[str, object]:
    upload_id = uuid.uuid4().hex
    extension = file_path.suffix.lower() or mimetypes.guess_extension(mime_type) or ".bin"
    stored_path = UPLOAD_DIR / f"{upload_id}{extension}"
    stored_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(file_path, stored_path)
    normalization = normalize_uploaded_image(stored_path, mime_type) if kind == "image" else {"normalized": False}
    model_sha256 = hashlib.sha256(stored_path.read_bytes()).hexdigest()
    text_preview = ""
    if kind == "text":
        text_preview, extraction_status = extract_text_from_upload(stored_path, extension, mime_type)
    payload = {
        "id": upload_id,
        "name": name,
        "mimeType": mime_type,
        "sizeBytes": stored_path.stat().st_size,
        "path": str(stored_path),
        "kind": kind,
        "extension": extension,
        "normalizedForModel": bool(normalization.get("normalized")),
        "width": int(normalization.get("width", 0) or 0),
        "height": int(normalization.get("height", 0) or 0),
        "originalSha256": model_sha256,
        "sha256": model_sha256,
        "durationSeconds": 0,
        "keyframeCount": 0,
        "videoAnalysisMode": "",
        "videoFrameTimestamps": [],
        "transcriptStatus": "",
        "transcriptChars": 0,
        "textPreview": text_preview,
        "extractionStatus": extraction_status,
        "nativeParts": [{"type": "image_url"}] if kind == "image" else [],
        "textBlocks": [text_preview] if text_preview else [],
        "derivedFiles": [],
    }
    with FILE_UPLOADS_LOCK:
        FILE_UPLOADS[upload_id] = payload
    return payload


def get_video_duration_seconds(source: Path, ffprobe: str) -> Optional[float]:
    try:
        result = subprocess.run(
            [
                ffprobe,
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(source),
            ],
            cwd=str(ROOT_DIR),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
            check=False,
        )
    except Exception:
        return None
    if result.returncode != 0:
        return None
    try:
        duration = float((result.stdout or "").strip())
    except ValueError:
        return None
    return duration if duration > 0 else None


def choose_video_keyframe_budget(duration_seconds: Optional[float], max_frames: Optional[int] = None) -> Tuple[int, str]:
    assessment = get_media_analysis_assessment()
    recommended = int(max_frames or assessment.get("recommendedMaxKeyframes", 8) or 8)
    if not duration_seconds:
        return min(recommended, 3), "unknown-duration-sample"
    if duration_seconds <= 30:
        return min(recommended, 8), "short-balanced"
    if duration_seconds <= 120:
        return min(recommended, 12), "balanced"
    if duration_seconds <= 300:
        return min(recommended, 16), "extended-sampled"
    return min(recommended, 24), "long-sampled"


def choose_video_timestamps(duration_seconds: Optional[float], max_frames: int) -> List[float]:
    if not duration_seconds:
        return [0.1]
    max_frames = max(1, max_frames)
    if max_frames > 3:
        start = 0.1
        upper_bound = max(0.1, duration_seconds - 0.05)
        if max_frames == 1:
            return [min(start, upper_bound)]
        step = (upper_bound - start) / max(1, max_frames - 1)
        timestamps: List[float] = []
        for index in range(max_frames):
            timestamp = min(upper_bound, max(0.0, start + step * index))
            if all(abs(timestamp - existing) > 0.15 for existing in timestamps):
                timestamps.append(timestamp)
        return timestamps or [0.1]
    candidates = [
        0.1,
        max(0.1, duration_seconds * 0.5),
        max(0.1, duration_seconds * 0.9),
    ]
    bounded: List[float] = []
    upper_bound = max(0.1, duration_seconds - 0.05)
    for value in candidates:
        timestamp = min(max(0.0, value), upper_bound)
        if all(abs(timestamp - existing) > 0.15 for existing in bounded):
            bounded.append(timestamp)
        if len(bounded) >= max_frames:
            break
    return bounded or [0.0]


def format_video_timestamp(seconds: float) -> str:
    return f"{max(0.0, seconds):.3f}"


def derive_video_keyframes(upload: Dict[str, object], max_frames: Optional[int] = None) -> List[Dict[str, object]]:
    ffmpeg, ffprobe, ffmpeg_status = ensure_ffmpeg_runtime()
    if not ffmpeg or not ffprobe:
        upload["extractionStatus"] = f"video-keyframes-unavailable:{ffmpeg_status}"
        return []
    source = Path(str(upload.get("path", "")))
    if not source.exists():
        upload["extractionStatus"] = "video-keyframes-unavailable:source-missing"
        return []
    duration = get_video_duration_seconds(source, ffprobe)
    if duration is not None:
        upload["durationSeconds"] = round(duration, 3)
    frame_budget, analysis_mode = choose_video_keyframe_budget(duration, max_frames)
    upload["videoAnalysisMode"] = analysis_mode
    frame_dir = UPLOAD_DIR / "video-frames" / str(upload.get("id", uuid.uuid4().hex))
    frame_dir.mkdir(parents=True, exist_ok=True)
    derived: List[Dict[str, object]] = []
    errors: List[str] = []
    timestamps = choose_video_timestamps(duration, frame_budget)
    upload["videoFrameTimestamps"] = [round(value, 3) for value in timestamps]
    for index, timestamp in enumerate(timestamps, start=1):
        frame_path = frame_dir / f"frame-{index}.jpg"
        result = subprocess.run(
            [
                ffmpeg,
                "-y",
                "-ss",
                format_video_timestamp(timestamp),
                "-i",
                str(source),
                "-frames:v",
                "1",
                "-vf",
                "scale='min(896,iw)':-2",
                "-q:v",
                "3",
                str(frame_path),
            ],
            cwd=str(ROOT_DIR),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=45,
            check=False,
        )
        if result.returncode != 0 or not frame_path.exists() or frame_path.stat().st_size <= 0:
            details = (result.stderr or result.stdout or "").strip().splitlines()
            if details:
                errors.append(details[-1][:240])
            else:
                errors.append(f"no-frame-at-{format_video_timestamp(timestamp)}")
            continue
        derived_upload = register_derived_file(
            f"{upload.get('name', 'video')} keyframe {index}",
            "image/jpeg",
            frame_path,
            "image",
            f"video-keyframe:{format_video_timestamp(timestamp)}s",
        )
        derived.append(build_history_attachment(derived_upload))
    upload["keyframeCount"] = len(derived)
    if derived:
        upload["extractionStatus"] = f"video-keyframes-extracted:{len(derived)}"
    else:
        reason = " | ".join(errors[:2]) if errors else "no-decodable-frames"
        upload["extractionStatus"] = f"video-keyframes-unavailable:{reason}"
    return derived


def save_uploaded_image(name: str, mime_type: str, data: str) -> Dict[str, object]:
    image = save_uploaded_file(name, mime_type, data)
    if image.get("kind") != "image":
        raise ValueError("Uploaded file is not an image.")
    return image


def get_uploaded_file(upload_id: str) -> Optional[Dict[str, object]]:
    if not upload_id:
        return None
    with FILE_UPLOADS_LOCK:
        upload = FILE_UPLOADS.get(upload_id)
        return dict(upload) if upload else None


def get_uploaded_image(image_id: str) -> Optional[Dict[str, object]]:
    return get_uploaded_file(image_id)


def get_uploaded_image_data_url(image: Dict[str, object]) -> str:
    file_path = Path(str(image.get("path", "")))
    if not file_path.exists():
        raise ValueError("Uploaded image file is no longer available.")
    encoded = base64.b64encode(file_path.read_bytes()).decode("ascii")
    return f"data:{image.get('mimeType', 'image/png')};base64,{encoded}"


def build_history_attachment(upload: Dict[str, object]) -> Dict[str, object]:
    return {
        "id": upload.get("id"),
        "kind": upload.get("kind"),
        "name": upload.get("name"),
        "mimeType": upload.get("mimeType"),
        "sizeBytes": upload.get("sizeBytes"),
        "width": upload.get("width", 0),
        "height": upload.get("height", 0),
        "sha256": upload.get("sha256", ""),
        "originalSha256": upload.get("originalSha256", ""),
        "normalizedForModel": upload.get("normalizedForModel", False),
        "durationSeconds": upload.get("durationSeconds", 0),
        "keyframeCount": upload.get("keyframeCount", 0),
        "videoAnalysisMode": upload.get("videoAnalysisMode", ""),
        "videoFrameTimestamps": upload.get("videoFrameTimestamps", []),
        "transcriptStatus": upload.get("transcriptStatus", ""),
        "transcriptChars": upload.get("transcriptChars", 0),
        "textPreview": upload.get("textPreview", ""),
        "extractionStatus": upload.get("extractionStatus", ""),
        "derivedFiles": upload.get("derivedFiles", []),
    }


def build_history_image_attachment(image: Dict[str, object]) -> Dict[str, object]:
    return build_history_attachment(image)


def query_models(port: int, timeout_sec: int = 2) -> Optional[Dict[str, object]]:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/v1/models", timeout=timeout_sec) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception:
        return None


def query_model_props(port: int, timeout_sec: int = 2) -> Optional[Dict[str, object]]:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/props", timeout=timeout_sec) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception:
        return None


def is_model_ready(model_alias: str, port: int) -> bool:
    payload = query_models(port)
    if not payload:
        return False
    data = payload.get("data", [])
    return any(isinstance(item, dict) and item.get("id") == model_alias for item in data)


def is_codeworker_model_command(commandline: str) -> bool:
    lowered = commandline.lower()
    return "codeworker" in lowered and ("launch_llama_server.py" in lowered or "llama-server.exe" in lowered)


def is_running_model_server_compatible(
    model_key: str,
    model_alias: str,
    port: int,
    model_file: Path,
    mmproj_file: Optional[Path],
) -> bool:
    if not is_model_ready(model_alias, port):
        return False
    props = query_model_props(port)
    if props:
        running_path = str(props.get("model_path", "")).lower()
        expected_model = str(model_file).lower()
        if running_path and expected_model and running_path != expected_model:
            return False
        if get_model_capabilities(model_key).get("requires_mmproj"):
            modalities = props.get("modalities", {})
            if isinstance(modalities, dict) and modalities.get("vision") is False:
                return False
    pid = get_listening_pid(port)
    if pid is None:
        return True
    commandline = get_process_commandline(pid)
    if not commandline or not is_codeworker_model_command(commandline):
        return True
    lowered = commandline.lower()
    expected_model = str(model_file).lower()
    if expected_model and expected_model not in lowered:
        return False
    if get_model_capabilities(model_key).get("requires_mmproj"):
        if mmproj_file is None:
            return False
        expected_mmproj = str(mmproj_file).lower()
        return "--mmproj" in lowered and expected_mmproj in lowered
    return True


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
    if result.returncode == 0:
        return True
    fallback = subprocess.run(
        ["netstat", "-ano"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        timeout=10,
    )
    return fallback.returncode == 0 and re.search(rf"^\s*TCP\s+127\.0\.0\.1:{port}\s+\S+\s+LISTENING\s+\d+\s*$", fallback.stdout, re.MULTILINE) is not None


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
    fallback = subprocess.run(
        ["netstat", "-ano"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        timeout=10,
    )
    if fallback.returncode == 0:
        match = re.search(rf"^\s*TCP\s+127\.0\.0\.1:{port}\s+\S+\s+LISTENING\s+(\d+)\s*$", fallback.stdout, re.MULTILINE)
        if match:
            return int(match.group(1))
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


def try_reclaim_codeworker_port(port: int, model_alias: str = "") -> Optional[str]:
    pid = get_listening_pid(port)
    if not pid:
        return None
    commandline = get_process_commandline(pid)
    if is_codeworker_model_command(commandline):
        if kill_process(pid):
            for _ in range(10):
                if not is_port_listening(port):
                    return f"Reclaimed CodeWorker model port {port} by stopping PID {pid}."
                threading.Event().wait(1)
            return f"Attempted to reclaim CodeWorker model port {port}, but it is still listening."
        return f"Failed to stop stale CodeWorker model server on PID {pid}."
    props = query_model_props(port)
    if model_alias and isinstance(props, dict) and props.get("model_alias") == model_alias:
        if kill_process(pid):
            for _ in range(10):
                if not is_port_listening(port):
                    return f"Reclaimed CodeWorker model port {port} by stopping PID {pid} with alias {model_alias}."
                threading.Event().wait(1)
            return f"Attempted to reclaim CodeWorker model port {port}, but it is still listening."
        return f"Failed to stop stale model server on PID {pid} with alias {model_alias}."
    return f"Port {port} is occupied by PID {pid}: {commandline or 'unknown process'}"


def ensure_runtime_and_model(model_key: str) -> Tuple[Path, str, Optional[Path]]:
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
    model_file = find_model_file(model_dir, get_model_file_pattern(model_key))
    if model_file is None:
        bootstrap = run_script("bootstrap.cmd", "-SkipRuntime", "-Models", model_key, timeout_seconds=1800)
        model_file = find_model_file(model_dir, get_model_file_pattern(model_key))
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
    mmproj_file: Optional[Path] = None
    mmproj_patterns = get_model_mmproj_patterns(model_key)
    if mmproj_patterns:
        mmproj_file = match_first_model_file(model_dir, mmproj_patterns)
        if mmproj_file is None:
            bootstrap = run_script("bootstrap.cmd", "-SkipRuntime", "-Models", model_key, timeout_seconds=1800)
            mmproj_file = match_first_model_file(model_dir, mmproj_patterns)
            if bootstrap.returncode != 0:
                raise RuntimeError(
                    json.dumps(
                        make_error(
                            "MODEL_MISSING",
                            "Failed to prepare multimodal projection file.",
                            bootstrap.stdout + bootstrap.stderr,
                            extra={"modelKey": model_key},
                        )
                    )
                )
        if mmproj_file is None:
            raise RuntimeError(
                json.dumps(
                    make_error(
                        "MODEL_MISSING",
                        "Failed to prepare multimodal projection file.",
                        f"Missing mmproj in {model_dir}; patterns={';'.join(mmproj_patterns)}",
                        extra={"modelKey": model_key},
                    )
                )
            )
        validate_model_file(mmproj_file)
    return model_file, model_alias, mmproj_file


def ensure_local_model_server(model_key: str, port: Optional[int] = None) -> Dict[str, object]:
    if model_key not in SUPPORTED_MODEL_KEYS:
        raise RuntimeError(json.dumps(make_error("MODEL_START_FAILED", "Unknown model.", model_key)))
    port = port or get_model_port(model_key)

    memory_warning = check_minimum_memory()
    if memory_warning:
        print(f"[WARN] {memory_warning}")
    model_file, model_alias, mmproj_file = ensure_runtime_and_model(model_key)
    llama_server = ROOT_DIR / "runtime" / "llama.cpp" / "llama-server.exe"

    if is_running_model_server_compatible(model_key, model_alias, port, model_file, mmproj_file):
        return {"modelAlias": model_alias, "logPath": None, "alreadyRunning": True}

    if is_model_ready(model_alias, port) or is_port_listening(port):
        reclaim_details = try_reclaim_codeworker_port(port, model_alias=model_alias)
        if is_running_model_server_compatible(model_key, model_alias, port, model_file, mmproj_file):
            return {"modelAlias": model_alias, "logPath": None, "alreadyRunning": True}
        if is_model_ready(model_alias, port) or is_port_listening(port):
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
    launch_args = [
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
    ]
    if mmproj_file is not None:
        launch_args.extend(["--mmproj", str(mmproj_file)])
    subprocess.Popen(
        launch_args,
        cwd=str(ROOT_DIR),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=DETACHED_FLAGS,
        close_fds=True,
    )

    for _ in range(60):
        if is_running_model_server_compatible(model_key, model_alias, port, model_file, mmproj_file):
            threading.Event().wait(2)
            if not is_running_model_server_compatible(model_key, model_alias, port, model_file, mmproj_file):
                continue
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
    file_patterns = model_config.get("filePatterns")
    if isinstance(file_patterns, list):
        resolved_patterns = [str(item).strip() for item in file_patterns if str(item).strip()]
    else:
        resolved_patterns = []
    file_pattern = str(model_config.get("filePattern", "")).strip()
    if file_pattern:
        resolved_patterns.insert(0, file_pattern)
    seen_patterns = set()
    required_patterns: List[str] = []
    for pattern in resolved_patterns:
        lowered = pattern.lower()
        if lowered in seen_patterns:
            continue
        seen_patterns.add(lowered)
        required_patterns.append(pattern)
    target_dir = ROOT_DIR / str(model_config.get("targetDir", "")).strip()
    if not repo or not required_patterns or not str(model_config.get("targetDir", "")).strip():
        raise RuntimeError(
            json.dumps(
                make_error(
                    "MODEL_INVALID",
                    "Model manifest is incomplete.",
                    f"repo={repo}, filePatterns={required_patterns}, targetDir={model_config.get('targetDir', '')}",
                    extra={"modelKey": model_key},
                )
            )
        )

    update_task(task_id, progress=8, step="解析模型來源", message="正在取得模型檔資訊")
    target_dir.mkdir(parents=True, exist_ok=True)
    resolved_filenames = [resolve_huggingface_filename(repo, pattern) for pattern in required_patterns]
    total_model_bytes = 0
    downloaded_paths: List[Path] = []

    for index, filename in enumerate(resolved_filenames):
        final_path = target_dir / Path(filename).name
        part_path = final_path.with_suffix(final_path.suffix + ".part")
        if part_path.exists():
            part_path.unlink()

        segment_start = 12 + int((index / max(len(resolved_filenames), 1)) * 80)
        segment_end = 12 + int(((index + 1) / max(len(resolved_filenames), 1)) * 80)
        update_task(task_id, progress=segment_start, step="準備下載", message=f"即將下載 {final_path.name}")
        download_url = f"https://huggingface.co/{repo}/resolve/main/{urllib.parse.quote(filename)}?download=true"
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
                            local_progress = segment_start + int((bytes_written / total_bytes) * max(segment_end - segment_start, 1))
                            local_progress = max(segment_start, min(local_progress, segment_end))
                            message = f"{final_path.name}: 已下載 {human_size(bytes_written)} / {human_size(total_bytes)}"
                        else:
                            local_progress = segment_start
                            message = f"{final_path.name}: 已下載 {human_size(bytes_written)}"
                        update_task(task_id, progress=local_progress, step="重新下載模型", message=message)

            if final_path.exists():
                final_path.unlink()
            os.replace(part_path, final_path)
            validate_model_file(final_path)
            downloaded_paths.append(final_path)
            total_model_bytes += final_path.stat().st_size
        except Exception:
            if part_path.exists():
                part_path.unlink()
            raise

    primary_path = target_dir / Path(resolve_huggingface_filename(repo, get_model_file_pattern(model_key))).name
    if not primary_path.exists():
        if not downloaded_paths:
            raise RuntimeError("Model download completed but no files were saved.")
        primary_path = downloaded_paths[0]
    return primary_path, total_model_bytes


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

    def should_ignore_project_path(path: Path) -> bool:
        try:
            relative = path.relative_to(project_root)
        except ValueError:
            return False
        parts = tuple(part.lower() for part in relative.parts)
        if not parts:
            return False
        if any(part in IGNORED_DIRS for part in parts):
            return True
        return any(parts[: len(prefix)] == prefix for prefix in GENERATED_PATH_PREFIXES)

    for root, dirs, files in os.walk(project_root):
        root_path = Path(root)
        dirs[:] = [
            item for item in dirs
            if not should_ignore_project_path(root_path / item)
        ]
        for filename in files:
            path = Path(root) / filename
            if should_ignore_project_path(path):
                continue
            suffix = path.suffix.lower()
            if suffix in IGNORED_EXTENSIONS:
                continue
            try:
                stat = path.stat()
            except OSError:
                continue
            if suffix not in SUPPORTED_FILE_EXTENSIONS and suffix:
                continue
            if suffix in TEXT_UPLOAD_EXTENSIONS and stat.st_size > 1_500_000:
                continue
            if suffix not in TEXT_UPLOAD_EXTENSIONS and stat.st_size > MAX_UPLOAD_BYTES:
                continue
            results.append(
                ProjectFile(
                    path=path.relative_to(project_root).as_posix(),
                    size=stat.st_size,
                    language=LANGUAGE_BY_EXTENSION.get(suffix, "Other"),
                )
            )
            if len(results) >= MAX_SCAN_FILES:
                return sort_project_files(results)
    return sort_project_files(results)


def sort_project_files(files: List[ProjectFile]) -> List[ProjectFile]:
    priority = {
        "Python": 0, "TypeScript": 1, "JavaScript": 1, "C#": 2, "Java": 2,
        "Markdown": 3, "JSON": 4, "YAML": 4,
    }
    return sorted(files, key=lambda item: (priority.get(item.language, 20), item.path.lower()))


def file_kind_from_path(path: str) -> str:
    suffix = Path(path).suffix.lower()
    if suffix in IMAGE_UPLOAD_EXTENSIONS:
        return "image"
    if suffix in AUDIO_UPLOAD_EXTENSIONS:
        return "audio"
    if suffix in VIDEO_UPLOAD_EXTENSIONS:
        return "video"
    if suffix in DOCUMENT_UPLOAD_EXTENSIONS:
        return "document"
    return "text"


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
    suffix = target.suffix.lower()
    if suffix in DOCUMENT_UPLOAD_EXTENSIONS:
        mime_type, _ = mimetypes.guess_type(str(target))
        extracted, status = extract_text_from_upload(target, suffix, mime_type or "")
        content = extracted or f"{relative_path}\n文件解析狀態: {status}\n目前只提供 metadata。"
    else:
        content = target.read_text(encoding="utf-8", errors="replace")
    return content[:max_chars] + ("\n... [truncated]" if len(content) > max_chars else "")


def read_file_full(project_root: Path, relative_path: str) -> str:
    target = (project_root / relative_path).resolve()
    try:
        target.relative_to(project_root)
    except ValueError as exc:
        raise ValueError("Invalid file path.") from exc
    suffix = target.suffix.lower()
    if suffix in DOCUMENT_UPLOAD_EXTENSIONS:
        mime_type, _ = mimetypes.guess_type(str(target))
        extracted, status = extract_text_from_upload(target, suffix, mime_type or "")
        return extracted or f"{relative_path}\n文件解析狀態: {status}\n目前只提供 metadata。"
    return target.read_text(encoding="utf-8", errors="replace")


def truncate_middle(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    if max_chars < 64:
        return text[:max_chars]
    keep_each_side = (max_chars - 24) // 2
    return f"{text[:keep_each_side]}\n... [truncated] ...\n{text[-keep_each_side:]}"


def fit_text_to_limit(text: str, max_chars: int) -> str:
    text = text.strip()
    if max_chars <= 0:
        return ""
    if len(text) <= max_chars:
        return text
    return truncate_middle(text, max_chars)


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


def build_line_chunk(title: str, content: str, start_line: int, end_line: int) -> str:
    snippet = slice_lines(content, start_line, end_line).strip()
    if not snippet:
        return ""
    lines = content.splitlines()
    line_count = max(1, len(lines))
    start = max(1, min(start_line, line_count))
    end = max(start, min(end_line, line_count))
    return f"{title} / lines {start}-{end}\n{snippet}"


def append_limited_chunk(chunks: List[str], chunk: str, max_chars: int) -> int:
    if not chunk or max_chars <= 0:
        return 0
    current = sum(len(item) for item in chunks) + max(0, len(chunks) - 1) * 2
    remaining = max_chars - current
    if remaining <= 0:
        return 0
    separator_cost = 2 if chunks else 0
    available = remaining - separator_cost
    if available <= 0:
        return 0
    if len(chunk) <= available:
        chunks.append(chunk)
        return len(chunk) + separator_cost
    if available >= 160:
        chunks.append(fit_text_to_limit(chunk, available))
        return available + separator_cost
    return 0


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


def build_member_index_chunk(content: str, relative_path: str, max_items: int = 80) -> str:
    if Path(relative_path).suffix.lower() != ".cs":
        return ""
    regions = detect_csharp_regions(content)
    if not regions:
        return ""
    lines = ["C# member index / detected members"]
    for region in regions[:max_items]:
        lines.append(f"- {region['name']}: lines {region['start_line']}-{region['end_line']}")
    if len(regions) > max_items:
        lines.append(f"- ... [truncated {len(regions) - max_items} more members]")
    return "\n".join(lines)


def build_general_file_excerpt(content: str, relative_path: str, message: str, max_chars: int) -> str:
    if not content.strip() or max_chars <= 0:
        return ""
    line_count = max(1, len(content.splitlines()))
    if len(content) <= max_chars:
        return build_line_chunk("Chunk 1", content, 1, line_count)

    chunks: List[str] = []
    seen_ranges = set()

    def add_range(title: str, start_line: int, end_line: int) -> None:
        start = max(1, start_line)
        end = min(line_count, end_line)
        if start > end:
            return
        marker = (start, end)
        if marker in seen_ranges:
            return
        seen_ranges.add(marker)
        append_limited_chunk(chunks, build_line_chunk(title, content, start, end), max_chars)

    add_range("Chunk 1 / file start", 1, min(line_count, 90))
    member_index = build_member_index_chunk(content, relative_path)
    if member_index:
        append_limited_chunk(chunks, member_index, max_chars)

    lowered_content = content.lower()
    for term in build_query_terms(message):
        index = lowered_content.find(term.lower())
        if index < 0:
            continue
        target_line = char_index_to_line(content, index)
        add_range(f"Chunk / keyword {term}", target_line - 25, target_line + 35)

    if line_count > 120:
        add_range("Chunk / file end", max(1, line_count - 70), line_count)

    if not chunks:
        return fit_text_to_limit(content, max_chars)
    return "\n\n".join(chunks)


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
        return build_general_file_excerpt(content, relative_path, message, max_chars=max_chars)

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
        raise ValueError("請先在檔案樹勾選至少一個檔案，模型才會根據這些檔案分析。")
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


def normalize_message_roles(messages: List[Dict[str, object]]) -> List[Dict[str, object]]:
    normalized: List[Dict[str, object]] = []
    for message in messages:
        role = str(message.get("role", "")).strip()
        content_obj = message.get("content", "")
        content: object
        if isinstance(content_obj, list):
            content = content_obj
        else:
            content = str(content_obj).strip()
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
        return 4
    if model_key == "qwen35":
        return 1
    return 0


def get_request_max_tokens(payload: Dict[str, object], default_value: int) -> int:
    raw = payload.get("maxTokens", payload.get("max_tokens", 0))
    try:
        requested = int(raw or 0)
    except (TypeError, ValueError):
        return default_value
    if requested <= 0:
        return default_value
    return max(16, min(default_value, requested))


def build_chat_system_prompt(model_key: str) -> str:
    return (
        "請只根據本輪實際提供給你的文字、圖片、文件抽取內容與 keyframes 回答。"
        "若使用者貼的是 URL/連結，而系統沒有提供網頁內容、影片 keyframes 或逐字稿，"
        "只能說明目前只看得到連結本身，不得根據網址、檔名或標題猜測影片內容。"
        "若附件只有 metadata 而沒有像素、音訊逐字稿或文字抽取內容，請明確說明限制，不要編造內容。"
    )


def strip_think_blocks(content: str) -> str:
    return re.sub(r"<think>\s*[\s\S]*?\s*</think>", "", str(content or ""), flags=re.IGNORECASE).strip()


def normalize_memory_line(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip(" -\t\r\n")


def append_unique_memory_line(target: List[str], text: str, max_items: int) -> None:
    line = normalize_memory_line(text)
    if not line:
        return
    line = truncate_middle(line, MAX_MEMORY_SUMMARY_LINE_CHARS)
    lowered = line.lower()
    existing = {item.lower() for item in target}
    if lowered in existing:
        return
    target.append(line)
    if len(target) > max_items:
        del target[0:len(target) - max_items]


def extract_memory_summary_sections(summary: str) -> Dict[str, List[str]]:
    sections = {"goals": [], "refs": [], "decisions": [], "attachments": []}
    current = ""
    heading_map = {
        "使用者目標": "goals",
        "已提到檔案": "refs",
        "已確認結論": "decisions",
        "附件": "attachments",
    }
    for raw_line in str(summary or "").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        matched_heading = next((value for key, value in heading_map.items() if line.startswith(key)), "")
        if matched_heading:
            current = matched_heading
            continue
        if current and line.startswith("- "):
            append_unique_memory_line(sections[current], line[2:], 12)
    return sections


def extract_referenced_names(content: str) -> List[str]:
    text = str(content or "")
    patterns = [
        r"\b[\w./\\-]+\.(?:py|cs|js|jsx|ts|tsx|json|yaml|yml|md|cmd|ps1|bat|html|css|scss|xml|toml|ini)\b",
        r"\b[A-Za-z_][\w]*(?:\.[A-Za-z_][\w]*)+\b",
        r"\b[A-Za-z_][\w]*(?:Interval|Timer|Speed|Manager|Controller|Service|Handler|Provider|Config)\b",
    ]
    refs: List[str] = []
    for pattern in patterns:
        for match in re.findall(pattern, text):
            append_unique_memory_line(refs, str(match).replace("\\", "/"), 20)
    return refs[:20]


def build_compressed_memory_summary(existing_summary: str, history_items: List[Dict[str, object]]) -> str:
    sections = extract_memory_summary_sections(existing_summary)
    for item in history_items:
        role = str(item.get("role", "")).strip()
        content = strip_think_blocks(str(item.get("content", "")).strip())
        if role == "user":
            attachments = item.get("attachments", [])
            if isinstance(attachments, list) and attachments:
                names = ", ".join(str(entry.get("name", "attachment")) for entry in attachments if isinstance(entry, dict))
                append_unique_memory_line(sections["attachments"], f"使用者上傳附件: {names}", 8)
            if content:
                append_unique_memory_line(sections["goals"], content, 10)
        elif role == "assistant" and content:
            append_unique_memory_line(sections["decisions"], content, 12)
        for ref in extract_referenced_names(content):
            append_unique_memory_line(sections["refs"], ref, 18)

    lines = [
        "使用者目標 / 待辦:",
        *[f"- {item}" for item in sections["goals"][-10:]],
        "",
        "已提到檔案 / 符號:",
        *[f"- {item}" for item in sections["refs"][-18:]],
        "",
        "已確認結論 / 建議:",
        *[f"- {item}" for item in sections["decisions"][-12:]],
    ]
    if sections["attachments"]:
        lines.extend(["", "附件 / 輸入狀態:", *[f"- {item}" for item in sections["attachments"][-8:]]])
    summary = "\n".join(line for line in lines if line is not None).strip()
    return fit_text_to_limit(summary, MAX_MEMORY_SUMMARY_CHARS)


def compact_session_memory_locked(model_key: str) -> None:
    raw_keep = max(0, min(MAX_CHAT_HISTORY_ITEMS, get_chat_history_limit(model_key) * 2))
    cutoff = max(0, len(STATE.history) - raw_keep)
    if cutoff <= STATE.memory_compacted_count + MEMORY_COMPACT_TRIGGER_ITEMS:
        return
    to_compact = STATE.history[STATE.memory_compacted_count:cutoff]
    if not to_compact:
        return
    STATE.memory_summary = build_compressed_memory_summary(STATE.memory_summary, to_compact)
    STATE.memory_compacted_count = cutoff


def build_answer_only_retry_messages(messages: List[Dict[str, object]]) -> List[Dict[str, object]]:
    retry_messages: List[Dict[str, object]] = []
    inserted = False
    for message in messages:
        item = dict(message)
        if not inserted and str(item.get("role", "")) == "system":
            item["content"] = f"{str(item.get('content', '')).strip()}\n\n{ANSWER_ONLY_SYSTEM_PROMPT}".strip()
            inserted = True
        retry_messages.append(item)
    if not inserted:
        retry_messages.insert(0, {"role": "system", "content": ANSWER_ONLY_SYSTEM_PROMPT})
    retry_messages.append({"role": "user", "content": ANSWER_ONLY_RETRY_PROMPT})
    return retry_messages


def is_continue_request(message: str) -> bool:
    lowered = str(message or "").strip().lower()
    if not lowered:
        return False
    return any(token in lowered for token in CONTINUE_TOKENS)


def build_history_continuation_message(message: str, history: List[Dict[str, object]]) -> Optional[str]:
    last_user = ""
    last_assistant = ""
    for item in reversed(history):
        role = str(item.get("role", ""))
        content = str(item.get("content", "")).strip()
        if not content:
            continue
        if role == "assistant" and not last_assistant:
            last_assistant = strip_think_blocks(content) or content
        elif role == "user" and not last_user:
            last_user = content
        if last_user and last_assistant:
            break
    if not last_assistant:
        return None
    tail = last_assistant[-6000:]
    parts = [
        "使用者要求延續上一輪回答。請直接接續，不要重新開場，不要重複前文。",
        f"本輪使用者要求：{message}",
    ]
    if last_user:
        parts.append(f"上一輪使用者問題：\n{last_user[-2000:]}")
    parts.append(f"上一輪回答末尾：\n{tail}")
    parts.append("請從上一輪回答中斷處繼續，若上一輪回答其實已完整，請只補充尚未完成的重點。")
    return "\n\n".join(parts)


def build_analyze_system_prompt(model_key: str) -> str:
    return ""


def build_raw_chat_user_message(context: str, message: str) -> str:
    if not context.strip():
        return f"USER QUESTION:\n{message}"
    normalized_context = context.strip()
    if normalized_context.startswith(("PINNED FILE CONTENT", "PROJECT CACHE CONTEXT", "PROJECT RAG CONTEXT")):
        return (
            f"{normalized_context}\n\n"
            f"USER QUESTION:\n{message}"
        )
    return (
        "PROJECT CONTEXT:\n"
        f"{normalized_context}\n\n"
        f"USER QUESTION:\n{message}"
    )


def build_raw_analyze_user_message(prompt: str, context: str) -> str:
    if not context.strip():
        return f"USER QUESTION:\n{prompt}"
    normalized_context = context.strip()
    if normalized_context.startswith(("PINNED FILE CONTENT", "PROJECT CACHE CONTEXT", "PROJECT RAG CONTEXT")):
        return (
            f"{normalized_context}\n\n"
            f"USER QUESTION:\n{prompt}"
        )
    return (
        "PROJECT CONTEXT:\n"
        f"{normalized_context}\n\n"
        f"USER QUESTION:\n{prompt}"
    )


def build_chat_user_content(context: str, message: str, image: Optional[Dict[str, object]] = None, images: Optional[List[Dict[str, object]]] = None) -> object:
    direct_images = list(images or ([] if image is None else [image]))
    if not direct_images:
        return build_raw_chat_user_message(context, message)
    text_sections: List[str] = []
    if context.strip():
        text_sections.append(f"PINNED FILE CONTENT:\n{context}")
    if message.strip():
        text_sections.append(f"USER QUESTION:\n{message}")
    else:
        text_sections.append("USER QUESTION:\n請根據附件圖片回答。")
    content: List[Dict[str, object]] = [{"type": "text", "text": "\n\n".join(text_sections).strip()}]
    for item in direct_images:
        content.append({"type": "image_url", "image_url": {"url": get_uploaded_image_data_url(item)}})
    return content


def build_attachment_prompt_block(attachments: List[Dict[str, object]], model_key: str, native_rejected: bool = False) -> str:
    if not attachments:
        return ""
    sections = ["\n\n[ATTACHMENTS]"]
    if native_rejected:
        sections.append(
            "重要限制：本輪附件的原生多模態輸入已被本地模型服務拒絕。"
            "若附件沒有可抽取文字，模型沒有收到圖片/影片/音訊的實際內容。"
            "不得描述、辨識、翻譯、推測或編造未收到的視覺/聽覺內容；"
            "只能根據下方 metadata 與文字抽取內容回答，必要時直接說明目前無法讀取實際內容。"
        )
    for index, upload in enumerate(attachments, start=1):
        kind = str(upload.get("kind", "file"))
        name = str(upload.get("name", "attachment"))
        mime_type = str(upload.get("mimeType", "unknown"))
        size = human_size(int(upload.get("sizeBytes", 0) or 0))
        status = str(upload.get("extractionStatus", "metadata-only"))
        sections.append(f"附件 {index}: {name} ({kind}, {mime_type}, {size}, extraction={status})")
        if kind == "image":
            width = int(upload.get("width", 0) or 0)
            height = int(upload.get("height", 0) or 0)
            if width > 0 and height > 0:
                sections.append(f"圖片尺寸: {width}x{height}")
            sha256 = str(upload.get("sha256", "")).strip()
            original_sha256 = str(upload.get("originalSha256", "")).strip()
            if sha256:
                sections.append(f"模型收到的圖片 SHA256: {sha256}")
            if original_sha256 and original_sha256 != sha256:
                sections.append(f"原始上傳圖片 SHA256: {original_sha256}")
        text_preview = str(upload.get("textPreview", "")).strip()
        if kind == "video":
            duration = float(upload.get("durationSeconds", 0) or 0)
            keyframes = int(upload.get("keyframeCount", 0) or 0)
            analysis_mode = str(upload.get("videoAnalysisMode", "")).strip()
            timestamps = upload.get("videoFrameTimestamps", [])
            transcript_status = str(upload.get("transcriptStatus", "")).strip()
            if duration > 0:
                sections.append(f"影片長度: {duration:.3f} 秒")
            if analysis_mode:
                sections.append(f"影片分析模式: {analysis_mode}")
            if keyframes > 0:
                if isinstance(timestamps, list) and timestamps:
                    compact_times = ", ".join(f"{float(value):.3f}s" for value in timestamps[:24] if isinstance(value, (int, float)))
                    if compact_times:
                        sections.append(f"keyframe 時間點: {compact_times}")
                sections.append(
                    f"影片已抽取 {keyframes} 張 keyframe，keyframes 會作為圖片附件提供。"
                    "請只根據這些 keyframes 與逐字稿描述影片；這不是完整逐格觀看。"
                )
            else:
                sections.append(
                    "這是影片附件，但目前沒有可用 keyframe 或逐字稿。"
                    "只能根據 metadata 說明限制，不得猜測影片畫面、角色、動作或聲音。"
                )
            if transcript_status:
                sections.append(f"音訊逐字稿狀態: {transcript_status}")
        elif kind == "audio":
            transcript_status = str(upload.get("transcriptStatus", upload.get("extractionStatus", ""))).strip()
            if transcript_status:
                sections.append(f"音訊逐字稿狀態: {transcript_status}")

        if text_preview:
            sections.append("附件文字內容/節錄:")
            sections.append(text_preview[:MAX_TEXT_ATTACHMENT_CHARS])
        elif kind == "image":
            if native_rejected:
                sections.append(
                    "這是圖片附件，但本輪沒有圖片像素內容可供模型閱讀。"
                    "請明確告知無法直接看見圖片內容，不要猜測圖片文字或畫面。"
                )
            else:
                sections.append(
                    "這是圖片附件。若目前模型與 llama.cpp server 沒有可用 vision projection，"
                    "請明確告知無法直接看見圖片內容，並請使用者提供文字描述或改用支援圖片的模型。"
                )
        elif kind == "audio":
            sections.append("這是音訊附件；目前沒有可用逐字稿。不得猜測音訊內容。")
        elif kind != "video":
            sections.append("此附件目前只提供 metadata，沒有可抽取的文字內容。")
    return "\n".join(sections).strip()


def expand_attachments_with_derived(attachments: List[Dict[str, object]]) -> List[Dict[str, object]]:
    expanded: List[Dict[str, object]] = []
    seen = set()
    for upload in attachments:
        upload_id = str(upload.get("id", ""))
        if upload_id and upload_id not in seen:
            expanded.append(upload)
            seen.add(upload_id)
        for derived in upload.get("derivedFiles", []) or []:
            if not isinstance(derived, dict):
                continue
            derived_id = str(derived.get("id", ""))
            if not derived_id or derived_id in seen:
                continue
            stored = get_uploaded_file(derived_id)
            if stored:
                expanded.append(stored)
                seen.add(derived_id)
    return expanded


def update_uploaded_file(upload_id: str, updates: Dict[str, object]) -> None:
    if not upload_id:
        return
    with FILE_UPLOADS_LOCK:
        if upload_id in FILE_UPLOADS:
            FILE_UPLOADS[upload_id].update(updates)


def prepare_attachments_for_model(model_key: str, attachments: List[Dict[str, object]]) -> List[Dict[str, object]]:
    return expand_attachments_with_derived(attachments)


def build_attachment_chat_content(
    context: str,
    message: str,
    attachments: List[Dict[str, object]],
    model_key: str,
    force_text_fallback: bool = False,
) -> Tuple[object, Dict[str, object]]:
    expanded = expand_attachments_with_derived(attachments)
    native_images = [] if force_text_fallback or not model_has_native_image_transport(model_key) else [item for item in expanded if item.get("kind") == "image"]
    native_ids = {str(item.get("id", "")) for item in native_images}
    text_attachments = [item for item in expanded if str(item.get("id", "")) not in native_ids]
    attachment_prompt = build_attachment_prompt_block(text_attachments, model_key, native_rejected=force_text_fallback)
    effective_message = message
    if attachment_prompt:
        effective_message = (effective_message + "\n\n" + attachment_prompt).strip()
    user_content = build_chat_user_content(context, effective_message, images=native_images)
    return user_content, {
        "nativeImages": len(native_images),
        "textAttachments": len(text_attachments),
        "fallback": force_text_fallback,
        "fallbackKinds": sorted({str(item.get("kind", "file")) for item in expanded}),
    }


def is_multimodal_transport_error(exc: Exception) -> bool:
    text = str(exc).lower()
    markers = (
        "image_url",
        "images",
        "image input",
        "multimodal",
        "mmproj",
        "projector",
        "vision",
        "clip",
        "unsupported content",
        "unsupported image",
        "invalid image",
        "content type",
        "not support image",
        "does not support image",
        "image data",
    )
    return any(marker in text for marker in markers)


def call_local_model_with_attachment_fallback(
    model_alias: str,
    model_key: str,
    context: str,
    message: str,
    attachments: List[Dict[str, object]],
    system_prompt: str,
    max_tokens: int,
    timeout_seconds: int,
    continue_on_length: int,
    history: Optional[List[Dict[str, object]]] = None,
    memory_summary: str = "",
) -> Tuple[str, Optional[Dict[str, object]], Dict[str, object]]:
    user_content, attachment_meta = build_attachment_chat_content(context, message, attachments, model_key, force_text_fallback=False)
    messages = build_raw_messages(model_key, user_content, system_prompt, history=history, memory_summary=memory_summary)
    try:
        reply = call_local_model(
            model_alias,
            messages,
            max_tokens=max_tokens,
            timeout_seconds=timeout_seconds,
            continue_on_length=continue_on_length,
            raw_mode=True,
        ).strip()
        return reply, None, attachment_meta
    except Exception as exc:
        if not attachment_meta.get("nativeImages") or not is_multimodal_transport_error(exc):
            raise
        fallback_content, fallback_meta = build_attachment_chat_content(context, message, attachments, model_key, force_text_fallback=True)
        fallback_messages = build_raw_messages(model_key, fallback_content, system_prompt, history=history, memory_summary=memory_summary)
        reply = call_local_model(
            model_alias,
            fallback_messages,
            max_tokens=max_tokens,
            timeout_seconds=timeout_seconds,
            continue_on_length=continue_on_length,
            raw_mode=True,
        ).strip()
        fallback_info = {
            "reason": str(exc),
            "fallbackKinds": fallback_meta.get("fallbackKinds", []),
            "retried": True,
        }
        return reply, fallback_info, fallback_meta


def stream_local_model_with_attachment_fallback(
    model_alias: str,
    model_key: str,
    context: str,
    message: str,
    attachments: List[Dict[str, object]],
    system_prompt: str,
    max_tokens: int,
    timeout_seconds: int,
    continue_on_length: int,
    history: Optional[List[Dict[str, object]]] = None,
    memory_summary: str = "",
):
    user_content, attachment_meta = build_attachment_chat_content(context, message, attachments, model_key, force_text_fallback=False)
    messages = build_raw_messages(model_key, user_content, system_prompt, history=history, memory_summary=memory_summary)
    emitted_model_output = False
    try:
        for event in stream_local_model_events(
            model_alias,
            messages,
            max_tokens=max_tokens,
            timeout_seconds=timeout_seconds,
            continue_on_length=continue_on_length,
        ):
            if event.get("type") in {"reasoning", "content"} and str(event.get("text", "")):
                emitted_model_output = True
            yield event
        return
    except Exception as exc:
        if emitted_model_output or not attachment_meta.get("nativeImages") or not is_multimodal_transport_error(exc):
            raise
        fallback_content, fallback_meta = build_attachment_chat_content(context, message, attachments, model_key, force_text_fallback=True)
        yield {
            "type": "attachment_fallback",
            "reason": str(exc),
            "fallbackKinds": fallback_meta.get("fallbackKinds", []),
            "retried": True,
        }
        fallback_messages = build_raw_messages(model_key, fallback_content, system_prompt, history=history, memory_summary=memory_summary)
        for event in stream_local_model_events(
            model_alias,
            fallback_messages,
            max_tokens=max_tokens,
            timeout_seconds=timeout_seconds,
            continue_on_length=continue_on_length,
        ):
            yield event


def build_history_messages(history: Optional[List[Dict[str, object]]], model_key: str) -> List[Dict[str, object]]:
    if not history:
        return []
    limit = max(0, min(MAX_CHAT_HISTORY_ITEMS, get_chat_history_limit(model_key) * 2))
    if limit <= 0:
        return []
    selected = list(history)[-limit:]
    collected: List[Dict[str, object]] = []
    total_chars = 0
    for item in reversed(selected):
        role = str(item.get("role", "")).strip()
        if role not in {"user", "assistant"}:
            continue
        content = strip_think_blocks(str(item.get("content", "")).strip())
        if role == "user" and not content:
            attachments = item.get("attachments", [])
            if isinstance(attachments, list) and attachments:
                names = ", ".join(str(entry.get("name", "attachment")) for entry in attachments if isinstance(entry, dict))
                content = f"[上一輪使用者上傳附件: {names}]"
        if not content:
            continue
        content = truncate_middle(content, MAX_CHAT_HISTORY_ITEM_CHARS)
        if total_chars + len(content) > MAX_CHAT_HISTORY_TOTAL_CHARS:
            continue
        total_chars += len(content)
        collected.append({"role": role, "content": content})
    collected.reverse()
    return collected


def build_raw_messages(
    model_key: str,
    user_content: object,
    system_prompt: str = "",
    history: Optional[List[Dict[str, object]]] = None,
    memory_summary: str = "",
) -> List[Dict[str, object]]:
    messages: List[Dict[str, object]] = []
    base_prompt = system_prompt.strip()
    history_messages = build_history_messages(history, model_key)
    compressed_memory = str(memory_summary or "").strip()
    if history_messages or compressed_memory:
        memory_note = (
            "你會收到壓縮記憶摘要與最近幾輪原文對話。"
            "請用它理解代名詞、上一題、延續問題與修改上下文；"
            "但若本輪 PROJECT RAG CONTEXT 或 PINNED FILE CONTENT 與歷史衝突，請以本輪提供的專案內容為準。"
        )
        base_prompt = f"{base_prompt}\n\n{memory_note}".strip()
    if compressed_memory:
        base_prompt = f"{base_prompt}\n\nCOMPRESSED CONVERSATION MEMORY:\n{compressed_memory}".strip()
    if model_key in {"gemma4", "qwen35"} and base_prompt:
        messages.append({"role": "system", "content": base_prompt})
    messages.extend(history_messages)
    messages.append({"role": "user", "content": user_content})
    return messages


def build_pinned_file_block(relative_path: str, excerpt: str, max_chars: int, mode_label: str = "完整內容") -> Tuple[str, str]:
    prefix = f"\n檔案: {relative_path} [{mode_label}]\nPINNED FILE CONTENT START\n```\n"
    suffix = "\n```\nPINNED FILE CONTENT END"
    content_budget = max_chars - len(prefix) - len(suffix)
    if content_budget < 160:
        return "", ""
    content = fit_text_to_limit(excerpt, content_budget)
    if not content:
        return "", ""
    return f"{prefix}{content}{suffix}", content


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


def build_context_coverage(
    model_key: str,
    selected_paths: List[str],
    files: List[Dict[str, object]],
    char_limit: int,
    used_chars: int,
) -> Dict[str, object]:
    truncated = any(bool(item.get("truncated")) for item in files)
    return {
        "modelKey": model_key,
        "selectedFiles": len(selected_paths),
        "filesSent": len(files),
        "fullCount": sum(1 for item in files if str(item.get("mode")) == "full"),
        "excerptCount": sum(1 for item in files if str(item.get("mode")) == "excerpt"),
        "truncated": truncated,
        "omittedFiles": max(0, len(selected_paths) - len(files)),
        "charLimit": char_limit,
        "usedChars": used_chars,
        "files": files,
    }


def build_project_context(
    project_root: Path,
    state: SessionState,
    message: str,
    prefer_compact: bool = False,
) -> Tuple[str, Dict[str, object]]:
    selected_paths = rank_paths_for_message(project_root, require_pinned_context(state), message)
    single_file_focus = len(selected_paths) == 1
    limits = get_context_limits(state.model_key, single_file_focus, prefer_compact=prefer_compact)
    selected_paths = selected_paths[: limits["max_files"]]
    header_lines = [
        "PINNED FILE CONTENT",
        "以下是已套用釘選檔案的實際內容，不只是檔名。",
        "檔案預覽不會自動加入上下文；只有下列 PINNED FILE CONTENT 區塊會提供給模型。",
        "若檔案標示為 [節錄模式]，代表模型只收到部分內容，不是完整原始碼。",
        "已套用釘選檔案:",
        *selected_paths,
    ]
    header = "\n".join(header_lines)
    full_max_files = limits.get("full_max_files", 0)
    full_total_chars = limits.get("full_total_chars", 0)
    full_file_chars = limits.get("full_file_chars", 0)
    if (
        state.model_key == "qwen35"
        and selected_paths
        and len(selected_paths) <= full_max_files
        and full_total_chars > 0
        and full_file_chars > 0
    ):
        full_chunks: List[str] = [header]
        full_files: List[Dict[str, object]] = []
        full_chars = len(header)
        can_use_full_mode = True
        for relative_path in selected_paths:
            try:
                content = read_file_full(project_root, relative_path)
            except (OSError, ValueError):
                can_use_full_mode = False
                break
            normalized_content = content.strip()
            if len(normalized_content) > full_file_chars:
                can_use_full_mode = False
                break
            separator_chars = 2 if full_chunks else 0
            remaining_chars = full_total_chars - full_chars - separator_chars
            block, sent_content = build_pinned_file_block(relative_path, content, remaining_chars, mode_label="完整內容")
            if not block or sent_content != normalized_content:
                can_use_full_mode = False
                break
            full_chunks.append(block)
            full_chars += len(block) + separator_chars
            full_files.append(
                {
                    "path": relative_path,
                    "mode": "full",
                    "truncated": False,
                    "charsSent": len(sent_content),
                    "charsTotal": len(normalized_content),
                }
            )
        if can_use_full_mode and len(full_files) == len(selected_paths):
            return "\n\n".join(full_chunks), build_context_coverage(
                state.model_key,
                selected_paths,
                full_files,
                full_total_chars,
                full_chars,
            )

    chunks = [header]
    total_limit = limits["total_chars"]
    total_chars = len(header)
    files_coverage: List[Dict[str, object]] = []
    for relative_path in selected_paths:
        try:
            content = read_file_full(project_root, relative_path)
            normalized_content = content.strip()
            excerpt = build_excerpt_for_message(
                project_root,
                relative_path,
                message,
                max_chars=limits["file_chars"],
                max_sections=3 if single_file_focus else 2,
            )
        except (OSError, ValueError):
            continue
        separator_chars = 2 if chunks else 0
        remaining_chars = total_limit - total_chars - separator_chars
        block, sent_content = build_pinned_file_block(relative_path, excerpt, remaining_chars, mode_label="節錄模式")
        if not block:
            if len(chunks) > 1:
                break
            continue
        chunks.append(block)
        total_chars += len(block) + separator_chars
        is_full_content = sent_content == normalized_content
        files_coverage.append(
            {
                "path": relative_path,
                "mode": "full" if is_full_content else "excerpt",
                "truncated": not is_full_content,
                "charsSent": len(sent_content),
                "charsTotal": len(normalized_content),
            }
        )
    return "\n\n".join(chunks), build_context_coverage(
        state.model_key,
        selected_paths,
        files_coverage,
        total_limit,
        total_chars,
    )


def load_cached_skeleton(project_root: Path) -> List[Dict[str, object]]:
    skeleton_path = rag_index_dir(DATA_DIR, project_root) / "skeleton.json"
    if not skeleton_path.exists():
        return []
    try:
        payload = json.loads(skeleton_path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, json.JSONDecodeError):
        return []
    return payload if isinstance(payload, list) else []


def ensure_project_index(project_root: Path) -> Tuple[Dict[str, object], bool]:
    db_path = rag_index_dir(DATA_DIR, project_root) / "index.sqlite"
    skeleton_path = rag_index_dir(DATA_DIR, project_root) / "skeleton.json"
    if db_path.exists() and skeleton_path.exists() and not index_is_stale(project_root, DATA_DIR):
        return {
            "projectHash": rag_index_dir(DATA_DIR, project_root).name,
            "indexDir": str(rag_index_dir(DATA_DIR, project_root)),
            "database": str(db_path),
            "files": len(load_cached_skeleton(project_root)),
            "chunks": 0,
        }, False
    return rebuild_index(project_root, DATA_DIR), True


def append_context_section(chunks: List[str], section: str, total_limit: int) -> bool:
    section = section.strip()
    if not section:
        return False
    separator = "\n\n" if chunks else ""
    current = sum(len(item) for item in chunks) + (2 * max(0, len(chunks) - 1))
    budget = total_limit - current - len(separator)
    if budget <= 80:
        return False
    if len(section) > budget:
        section = section[: max(0, budget - 24)].rstrip() + "\n... [truncated]"
    chunks.append(section)
    return True


def build_project_rag_context(
    project_root: Path,
    state: SessionState,
    prompt: str,
    model_key: str,
) -> Tuple[str, Dict[str, object]]:
    index_result, index_rebuilt = ensure_project_index(project_root)
    skeleton = load_cached_skeleton(project_root)
    search_result = search_index(project_root, DATA_DIR, prompt, limit=12)
    matches = search_result.get("matches", []) if isinstance(search_result, dict) else []
    total_limit = get_context_limits(model_key, single_file_focus=False).get("total_chars", MAX_TOTAL_CONTEXT)
    total_limit = max(9000, min(26000, int(total_limit)))
    chunks: List[str] = []
    files_sent: List[Dict[str, object]] = []

    append_context_section(
        chunks,
        "\n".join(
            [
                "PROJECT RAG CONTEXT",
                "未勾選 pinned files；本次使用 CodeWorker 的全專案搜尋快取與 RAG 檢索結果。",
                "這不是把整個專案原始碼完整丟給模型，而是使用快取的 skeleton、summary、symbols、imports 與相關 chunks。",
                "若使用者問「哪個檔案」、「哪一段」、「在哪裡」、「怎麼修改」、「如何調整」或類似定位/修改問題，請優先使用 RAG MATCHES 的檔案路徑、行號與程式碼片段回答。",
                f"專案路徑: {project_root}",
                f"快取狀態: {'本次重建' if index_rebuilt else '沿用既有快取'}",
                f"快取檔案數: {index_result.get('files', len(skeleton))}",
            ]
        ),
        total_limit,
    )

    if matches:
        match_lines = ["RAG MATCHES FOR USER REQUEST"]
        for item in matches[:12]:
            if not isinstance(item, dict):
                continue
            path = str(item.get("path", "")).strip()
            content = str(item.get("content", "")).strip()
            if not path or not content:
                continue
            line_start = int(item.get("lineStart", 1) or 1)
            line_end = int(item.get("lineEnd", line_start) or line_start)
            source = str(item.get("source", "rag"))
            match_lines.append(f"\n檔案: {path}:{line_start}-{line_end} [{source}]\n```\n{content[:1400]}\n```")
            files_sent.append({
                "path": path,
                "mode": "rag-chunk",
                "truncated": True,
                "charsSent": min(len(content), 1400),
                "charsTotal": len(content),
                "lineStart": line_start,
                "lineEnd": line_end,
                "source": source,
            })
        append_context_section(chunks, "\n".join(match_lines), total_limit)

    append_context_section(
        chunks,
        "\n".join(
            [
                "PROJECT SUMMARY",
                state.summary or build_summary(project_root, state.files, state.entrypoints, state.tests),
            ]
        ),
        total_limit,
    )

    skeleton_lines = ["CACHED PROJECT SKELETON"]
    skeleton_budget_count = 120
    for item in skeleton[:skeleton_budget_count]:
        if not isinstance(item, dict):
            continue
        path = str(item.get("path", "")).strip()
        if not path:
            continue
        symbols = item.get("symbols", [])
        imports = item.get("imports", [])
        summary = str(item.get("summary", "")).strip().replace("\n", " ")
        symbol_text = ", ".join(str(value) for value in symbols[:8]) if isinstance(symbols, list) else ""
        import_text = ", ".join(str(value) for value in imports[:6]) if isinstance(imports, list) else ""
        line = f"- {path}"
        if symbol_text:
            line += f" | symbols: {symbol_text}"
        if import_text:
            line += f" | imports: {import_text}"
        if summary:
            line += f" | summary: {summary[:360]}"
        skeleton_lines.append(line)
        files_sent.append({"path": path, "mode": "cached-summary", "truncated": True, "charsSent": min(len(line), 520), "charsTotal": int(item.get("size", 0) or len(summary))})
    append_context_section(chunks, "\n".join(skeleton_lines), total_limit)

    used_chars = sum(len(item) for item in chunks) + (2 * max(0, len(chunks) - 1))
    indexed_files = int(index_result.get("files", len(skeleton)) or len(skeleton))
    coverage = {
        "mode": "project-rag",
        "modelKey": model_key,
        "selectedFiles": max(len(state.files), indexed_files),
        "filesSent": len(files_sent),
        "fullCount": 0,
        "excerptCount": len(files_sent),
        "truncated": True,
        "omittedFiles": max(0, max(len(state.files), indexed_files) - len(files_sent)),
        "charLimit": total_limit,
        "usedChars": used_chars,
        "files": files_sent[:120],
        "indexRebuilt": index_rebuilt,
        "indexFiles": indexed_files,
        "indexChunks": int(index_result.get("chunks", 0) or 0),
        "indexDir": str(index_result.get("indexDir", "")),
    }
    return "\n\n".join(chunks), coverage


def build_project_cache_context(
    project_root: Path,
    state: SessionState,
    prompt: str,
    model_key: str,
) -> Tuple[str, Dict[str, object]]:
    return build_project_rag_context(project_root, state, prompt, model_key)


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
    model_key: str = DEFAULT_MODEL_KEY,
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
    model_key: str = DEFAULT_MODEL_KEY,
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


def prepare_messages_for_model(model_alias: str, messages: List[Dict[str, object]]) -> List[Dict[str, object]]:
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
    messages: List[Dict[str, object]],
    timeout_seconds: int = 180,
    max_tokens: int = 600,
    continue_on_length: int = 0,
    raw_mode: bool = False,
) -> str:
    endpoint = get_model_endpoint(model_alias)
    model_key = get_model_key_from_alias(model_alias)
    working_messages = list(messages)
    parts: List[str] = []
    remaining_continuations = max(0, continue_on_length)
    answer_only_retry_used = False

    def raise_model_empty_reply(finish_reason: str, reasoning_content: str = "") -> None:
        details_parts = []
        if finish_reason:
            details_parts.append(f"finish_reason={finish_reason}")
        if reasoning_content.strip():
            details_parts.append("reasoning_content_only=true")
        if answer_only_retry_used:
            details_parts.append("answer_only_retry_exhausted=true")
        details = "模型沒有產生可顯示的最終答案。"
        if details_parts:
            details = f"{details} {'; '.join(details_parts)}"
        raise ModelReplyError(
            make_error(
                "MODEL_EMPTY_REPLY",
                "模型沒有產生可顯示的最終答案。",
                details,
                extra={"modelKey": model_key},
            )
        )

    while True:
        prepared_messages = prepare_messages_for_model(model_alias, working_messages)
        request_payload = {
            "model": model_alias,
            "messages": prepared_messages,
            "stream": False,
            "max_tokens": max_tokens,
        }
        request_payload.update(get_model_generation_options(model_key))
        payload = json.dumps(request_payload, ensure_ascii=False).encode("utf-8")
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
                f"本地模型回應已等到目前上限仍未完成。模型可能仍在生成超長內容、主機效能不足，或本輪上下文需要縮小。timeout={timeout_seconds}s。若經常發生，請減少釘選檔案或縮小問題範圍後再試。"
            ) from exc
        except urllib.error.HTTPError as exc:
            details = ""
            try:
                details = exc.read().decode("utf-8", errors="replace")
            except Exception:
                details = str(exc)
            lowered_details = details.lower()
            if ("exceeds the available context size" in lowered_details) or ("context size has been exceeded" in lowered_details):
                raise RuntimeError(
                    "目前送給模型的專案上下文太大，超過這台機器目前可用的 context 上限。請縮小對話歷史、減少釘選檔案，或重新開啟專案後再試。"
                ) from exc
            raise RuntimeError(f"Failed to call local model endpoint: HTTP {exc.code}: {details}") from exc
        except urllib.error.URLError as exc:
            reason = getattr(exc, "reason", "")
            if isinstance(reason, (TimeoutError, socket.timeout)) or "timed out" in str(reason).lower():
                raise RuntimeError(
                    f"本地模型回應已等到目前上限仍未完成。模型可能仍在生成超長內容、主機效能不足，或本輪上下文需要縮小。timeout={timeout_seconds}s。若經常發生，請減少釘選檔案或縮小問題範圍後再試。"
                ) from exc
            raise RuntimeError(f"Failed to call local model endpoint: {exc}") from exc
        try:
            choice = body["choices"][0]
            message = choice.get("message") or {}
            raw_content = str(message.get("content") or "")
            reasoning_content = str(message.get("reasoning_content") or "")
            finish_reason = str(choice.get("finish_reason", "") or "")
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError("Unexpected model response format.") from exc
        if not raw_content.strip():
            if reasoning_content.strip() and not answer_only_retry_used:
                answer_only_retry_used = True
                working_messages = build_answer_only_retry_messages(working_messages)
                continue
            if reasoning_content.strip():
                parts.append(f"<think>\n{reasoning_content.strip()}\n</think>")
                break
            raise_model_empty_reply(finish_reason, reasoning_content)
        if reasoning_content.strip():
            parts.append(f"<think>\n{reasoning_content.strip()}\n</think>")
        parts.append(raw_content)
        if finish_reason != "length" or remaining_continuations <= 0:
            break
        remaining_continuations -= 1
        working_messages.append({"role": "assistant", "content": raw_content})
        working_messages.append({"role": "user", "content": "請直接從上一句繼續回答，不要重複前文，不要重新開場。"})
    return sanitize_model_reply(model_alias, "\n".join(part for part in parts if part.strip()), raw_mode=raw_mode)


def raise_local_model_http_error(exc: urllib.error.HTTPError) -> None:
    details = ""
    try:
        details = exc.read().decode("utf-8", errors="replace")
    except Exception:
        details = str(exc)
    lowered_details = details.lower()
    if ("exceeds the available context size" in lowered_details) or ("context size has been exceeded" in lowered_details):
        raise RuntimeError(
            "目前送給模型的專案上下文太大，超過這台機器目前可用的 context 上限。請縮小對話歷史、減少釘選檔案，或重新開啟專案後再試。"
        ) from exc
    raise RuntimeError(f"Failed to call local model endpoint: HTTP {exc.code}: {details}") from exc


def raise_local_model_url_error(exc: urllib.error.URLError, timeout_seconds: int) -> None:
    reason = getattr(exc, "reason", "")
    if isinstance(reason, (TimeoutError, socket.timeout)) or "timed out" in str(reason).lower():
        raise RuntimeError(
            f"本地模型回應已等到目前上限仍未完成。模型可能仍在生成超長內容、主機效能不足，或本輪上下文需要縮小。timeout={timeout_seconds}s。若經常發生，請減少釘選檔案或縮小問題範圍後再試。"
        ) from exc
    raise RuntimeError(f"Failed to call local model endpoint: {exc}") from exc


def stream_local_model_events(
    model_alias: str,
    messages: List[Dict[str, object]],
    timeout_seconds: int = 180,
    max_tokens: int = 600,
    continue_on_length: int = 0,
):
    endpoint = get_model_endpoint(model_alias)
    working_messages = list(messages)
    remaining_continuations = max(0, continue_on_length)
    answer_only_retry_used = False
    while True:
        prepared_messages = prepare_messages_for_model(model_alias, working_messages)
        request_payload = {
            "model": model_alias,
            "messages": prepared_messages,
            "stream": True,
            "max_tokens": max_tokens,
        }
        request_payload.update(get_model_generation_options(get_model_key_from_alias(model_alias)))
        payload = json.dumps(request_payload, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(
            endpoint,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        finish_reason = ""
        streamed_content: List[str] = []
        streamed_reasoning: List[str] = []
        try:
            with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
                for raw_line in response:
                    line = raw_line.decode("utf-8", errors="replace").strip()
                    if not line or not line.startswith("data:"):
                        continue
                    data = line[len("data:"):].strip()
                    if data == "[DONE]":
                        break
                    try:
                        payload_obj = json.loads(data)
                        choice = payload_obj.get("choices", [{}])[0]
                        finish_reason = str(choice.get("finish_reason", "") or finish_reason)
                        delta = choice.get("delta") or choice.get("message") or {}
                        reasoning = str(delta.get("reasoning_content") or "")
                        content = str(delta.get("content") or "")
                        if reasoning:
                            streamed_reasoning.append(reasoning)
                            yield {"type": "reasoning", "text": reasoning}
                        if content:
                            streamed_content.append(content)
                            yield {"type": "content", "text": content}
                    except Exception:
                        continue
        except (TimeoutError, socket.timeout) as exc:
            raise RuntimeError(
                f"本地模型回應已等到目前上限仍未完成。模型可能仍在生成超長內容、主機效能不足，或本輪上下文需要縮小。timeout={timeout_seconds}s。若經常發生，請減少釘選檔案或縮小問題範圍後再試。"
            ) from exc
        except urllib.error.HTTPError as exc:
            raise_local_model_http_error(exc)
        except urllib.error.URLError as exc:
            raise_local_model_url_error(exc, timeout_seconds)
        content_text = "".join(streamed_content).strip()
        reasoning_text = "".join(streamed_reasoning).strip()
        if not content_text and reasoning_text and not answer_only_retry_used:
            answer_only_retry_used = True
            yield {"type": "continuation", "text": "模型只輸出思考過程，已自動要求輸出最終答案。"}
            working_messages = build_answer_only_retry_messages(working_messages)
            continue
        if finish_reason != "length" or remaining_continuations <= 0:
            yield {"type": "finish", "finishReason": finish_reason}
            break
        remaining_continuations -= 1
        yield {"type": "continuation", "text": "內容過長，已自動從上一句繼續。"}
        working_messages.append({"role": "assistant", "content": content_text})
        working_messages.append({"role": "user", "content": "請直接從上一句繼續回答，不要重複前文，不要重新開場。"})


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
        existing_memory_summary = STATE.memory_summary
        existing_memory_compacted_count = STATE.memory_compacted_count
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
        STATE.memory_summary = existing_memory_summary if preserve_history else ""
        STATE.memory_compacted_count = existing_memory_compacted_count if preserve_history else 0
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
        if model_key not in SUPPORTED_MODEL_KEYS:
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
            "models": get_public_model_capabilities(),
            "summary": STATE.summary,
            "tree": STATE.tree,
            "entrypoints": STATE.entrypoints,
            "tests": STATE.tests,
            "pinnedFiles": STATE.pinned_files,
            "currentPreviewPath": STATE.current_preview_path,
            "history": STATE.history[-20:],
            "memorySummary": STATE.memory_summary,
            "memoryCompactedCount": STATE.memory_compacted_count,
            "pendingEdit": STATE.pending_edit,
            "uiState": STATE.ui_state,
            "mediaAssessment": get_media_analysis_assessment(),
        }


def get_models_payload() -> Dict[str, object]:
    models: Dict[str, object] = {}
    for key, capability in get_public_model_capabilities().items():
        model_dir = get_model_directory(key)
        config = get_registry_model_config(ROOT_DIR, key)
        patterns = config.file_patterns if config else [get_model_file_pattern(key)]
        primary = match_first_model_file(model_dir, patterns)
        mmproj = None
        if config and config.mmproj_patterns:
            mmproj = match_first_model_file(model_dir, config.mmproj_patterns)
        ready = False
        if primary:
            ready = is_running_model_server_compatible(key, get_model_alias(key), get_model_port(key), primary, mmproj)
        models[key] = {
            **capability,
            "installed": bool(primary and primary.exists()),
            "modelPath": str(primary) if primary else "",
            "mmprojPath": str(mmproj) if mmproj else "",
            "ready": ready,
            "nativeImageReady": bool(mmproj and ready and model_supports_images(key)),
        }
    return {"models": models, "defaultModelKey": DEFAULT_MODEL_KEY, "mediaAssessment": get_media_analysis_assessment()}


def write_sse_event(handler: BaseHTTPRequestHandler, event: str, payload: Dict[str, object]) -> None:
    data = json.dumps(payload, ensure_ascii=False)
    handler.wfile.write(f"event: {event}\ndata: {data}\n\n".encode("utf-8"))
    handler.wfile.flush()


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
        if parsed.path == "/api/models":
            json_response(self, {"ok": True, "data": get_models_payload()})
            return
        if parsed.path == "/api/media-assessment":
            json_response(self, {"ok": True, "data": get_media_analysis_assessment()})
            return
        if parsed.path == "/api/file":
            self.handle_file_request(parsed)
            return
        if parsed.path == "/api/file-tree":
            self.handle_file_tree(parsed)
            return
        if parsed.path.startswith("/api/tasks/"):
            self.handle_task_status(parsed.path)
            return
        if parsed.path.startswith("/api/agent/events/"):
            self.handle_agent_events(parsed.path)
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
        if parsed.path == "/api/chat/stream":
            self.handle_chat_stream()
            return
        if parsed.path == "/api/models/ensure":
            self.handle_model_ensure()
            return
        if parsed.path == "/api/index/rebuild":
            self.handle_index_rebuild()
            return
        if parsed.path == "/api/rag/search":
            self.handle_rag_search()
            return
        if parsed.path == "/api/agent/run":
            self.handle_agent_run()
            return
        if parsed.path == "/api/actions/confirm":
            self.handle_action_confirm()
            return
        if parsed.path.startswith("/api/actions/") and parsed.path.endswith("/confirm"):
            self.handle_action_confirm(parsed.path.rsplit("/", 2)[-2])
            return
        if parsed.path == "/api/uploads/image":
            self.handle_upload_file(require_image=True)
            return
        if parsed.path == "/api/uploads/file":
            self.handle_upload_file()
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
            model_key = str(payload.get("modelKey", DEFAULT_MODEL_KEY)).strip().lower()
            if model_key not in SUPPORTED_MODEL_KEYS:
                raise ValueError(f"Unsupported model. Use one of: {', '.join(sorted(SUPPORTED_MODEL_KEYS))}.")
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
            model_key = str(payload.get("modelKey", DEFAULT_MODEL_KEY)).strip().lower()
            if model_key not in SUPPORTED_MODEL_KEYS:
                raise ValueError(f"Unsupported model. Use one of: {', '.join(sorted(SUPPORTED_MODEL_KEYS))}.")
            task = start_background_task(TASK_REDOWNLOAD_MODEL, redownload_model_worker, model_key)
            json_response(self, {"ok": True, "data": {"taskId": task.id, "kind": task.kind}})
        except Exception as exc:
            error_response(self, make_error("MODEL_DOWNLOAD_FAILED", "Failed to start model redownload.", str(exc)))

    def handle_upload_file(self, require_image: bool = False) -> None:
        try:
            payload = self.read_json_body()
            upload = save_uploaded_file(
                str(payload.get("name", "")).strip(),
                str(payload.get("mimeType", "")).strip(),
                str(payload.get("data", "")),
            )
            if require_image and upload.get("kind") != "image":
                raise ValueError("Uploaded file is not an image.")
            json_response(self, {"ok": True, "data": upload})
        except ValueError as exc:
            error_response(self, make_error("FILE_UPLOAD_FAILED", "File upload failed.", str(exc)))
        except Exception as exc:
            error_response(self, make_error("FILE_UPLOAD_FAILED", "File upload failed.", str(exc)))

    def handle_model_ensure(self) -> None:
        try:
            payload = self.read_json_body()
            model_key = str(payload.get("modelKey", STATE.model_key or DEFAULT_MODEL_KEY)).strip().lower()
            if model_key not in SUPPORTED_MODEL_KEYS:
                raise ValueError("Unsupported model.")
            result = ensure_local_model_server(model_key, port=get_model_port(model_key))
            json_response(self, {"ok": True, "data": {"modelKey": model_key, **result}})
        except ValueError as exc:
            error_response(self, make_error("MODEL_INVALID", "Model validation failed.", str(exc)))
        except RuntimeError as exc:
            try:
                error_payload = json.loads(str(exc))
            except json.JSONDecodeError:
                error_payload = make_error("MODEL_START_FAILED", "Failed to ensure model.", str(exc))
            error_response(self, error_payload)
        except Exception as exc:
            error_response(self, make_error("MODEL_START_FAILED", "Failed to ensure model.", str(exc)))

    def get_ready_project_root(self) -> Path:
        with STATE_LOCK:
            if STATE.ui_state != "ready" or not STATE.project_path:
                raise ValueError("請先完成開啟專案。")
            return Path(STATE.project_path)

    def handle_index_rebuild(self) -> None:
        try:
            project_root = self.get_ready_project_root()
            result = rebuild_index(project_root, DATA_DIR)
            json_response(self, {"ok": True, "data": result})
        except ValueError as exc:
            error_response(self, make_error("PROJECT_NOT_READY", "Project is not ready.", str(exc)))
        except Exception as exc:
            error_response(self, make_error("INDEX_FAILED", "Rebuild index failed.", traceback.format_exc() or str(exc)))

    def handle_rag_search(self) -> None:
        try:
            payload = self.read_json_body()
            query = str(payload.get("query", "")).strip()
            if not query:
                raise ValueError("query is required.")
            project_root = self.get_ready_project_root()
            ensure_project_index(project_root)
            result = search_index(project_root, DATA_DIR, query, int(payload.get("limit", 8) or 8))
            json_response(self, {"ok": True, "data": result})
        except ValueError as exc:
            message = "Project is not ready." if str(exc) == "請先完成開啟專案。" else "RAG search failed."
            code = "PROJECT_NOT_READY" if str(exc) == "請先完成開啟專案。" else "RAG_SEARCH_FAILED"
            error_response(self, make_error(code, message, str(exc)))
        except Exception as exc:
            error_response(self, make_error("RAG_SEARCH_FAILED", "RAG search failed.", str(exc)))

    def handle_agent_run(self) -> None:
        try:
            payload = self.read_json_body()
            message = str(payload.get("message", "")).strip()
            if not message:
                raise ValueError("message is required.")
            project_root = self.get_ready_project_root()
            result = run_agent(project_root, DATA_DIR, message)
            run_id = uuid.uuid4().hex
            AGENT_RUNS[run_id] = result
            json_response(self, {"ok": True, "data": {"runId": run_id, **result}})
        except ValueError as exc:
            code = "PROJECT_NOT_READY" if str(exc) == "請先完成開啟專案。" else "AGENT_RUN_FAILED"
            message = "Project is not ready." if code == "PROJECT_NOT_READY" else "Agent run failed."
            error_response(self, make_error(code, message, str(exc)))
        except Exception as exc:
            error_response(self, make_error("AGENT_RUN_FAILED", "Agent run failed.", str(exc)))

    def handle_agent_events(self, path: str) -> None:
        run_id = path.rsplit("/", 1)[-1]
        result = AGENT_RUNS.get(run_id)
        if not result:
            error_response(self, make_error("AGENT_RUN_NOT_FOUND", "Agent run not found.", run_id), status=404)
            return
        json_response(self, {"ok": True, "data": result})

    def handle_action_confirm(self, action_id_from_path: str = "") -> None:
        try:
            payload = self.read_json_body()
            action_id = action_id_from_path or str(payload.get("actionId", "")).strip()
            approved = bool(payload.get("approved", False))
            if not action_id:
                raise ValueError("actionId is required.")
            project_root = self.get_ready_project_root()
            result = confirm_agent_action(project_root, action_id, approved, DATA_DIR)
            json_response(self, {"ok": True, "data": result})
        except ValueError as exc:
            error_response(self, make_error("ACTION_CONFIRM_FAILED", "Action confirmation failed.", str(exc)))
        except Exception as exc:
            error_response(self, make_error("ACTION_CONFIRM_FAILED", "Action confirmation failed.", str(exc)))

    def handle_file_tree(self, parsed: urllib.parse.ParseResult) -> None:
        try:
            query = urllib.parse.parse_qs(parsed.query)
            search = query.get("query", [""])[0].strip().lower()
            kind_filter = query.get("kind", [""])[0].strip().lower()
            offset = max(0, int(query.get("offset", ["0"])[0] or 0))
            limit = max(1, min(500, int(query.get("limit", ["200"])[0] or 200)))
            with STATE_LOCK:
                if STATE.ui_state != "ready" or not STATE.project_path:
                    raise ValueError("Project is not ready.")
                files = list(STATE.files)
            rows = []
            for item in files:
                kind = file_kind_from_path(item.path)
                if search and search not in item.path.lower() and search not in item.language.lower():
                    continue
                if kind_filter and kind_filter != kind:
                    continue
                rows.append({"path": item.path, "language": item.language, "kind": kind, "size": item.size})
            json_response(
                self,
                {
                    "ok": True,
                    "data": {
                        "items": rows[offset:offset + limit],
                        "total": len(rows),
                        "offset": offset,
                        "limit": limit,
                    },
                },
            )
        except ValueError as exc:
            error_response(self, make_error("PROJECT_NOT_READY", "Project is not ready.", str(exc)))
        except Exception as exc:
            error_response(self, make_error("FILE_TREE_FAILED", "File tree query failed.", str(exc)))

    def handle_analyze(self) -> None:
        try:
            payload = self.read_json_body()
            prompt = str(payload.get("prompt", DEFAULT_ANALYSIS_PROMPT)).strip() or DEFAULT_ANALYSIS_PROMPT
            requested_model_key = str(payload.get("modelKey", "")).strip().lower()
            with STATE_LOCK:
                if STATE.ui_state != "ready" or not STATE.project_path:
                    raise ValueError("請先完成開啟專案。")
                model_key = requested_model_key or STATE.model_key
                if model_key not in SUPPORTED_MODEL_KEYS:
                    raise ValueError("Unsupported model.")
                project_root = Path(STATE.project_path)
                snapshot = SessionState(
                    project_path=STATE.project_path,
                    model_key=model_key,
                    model_alias=get_model_alias(model_key),
                    summary=STATE.summary,
                    tree=list(STATE.tree),
                    files=list(STATE.files),
                    entrypoints=list(STATE.entrypoints),
                    tests=list(STATE.tests),
                    pinned_files=list(STATE.pinned_files),
                    current_preview_path=None,
                    history=list(STATE.history),
                    memory_summary=STATE.memory_summary,
                    memory_compacted_count=STATE.memory_compacted_count,
                    pending_edit=STATE.pending_edit,
                    ui_state=STATE.ui_state,
                )
            if snapshot.pinned_files:
                context, context_coverage = build_project_context(project_root, snapshot, prompt)
            else:
                context, context_coverage = build_project_cache_context(project_root, snapshot, prompt, model_key)
            with STATE_LOCK:
                current_model_key = STATE.model_key
            if requested_model_key and requested_model_key != current_model_key:
                ensure_local_model_server(model_key, port=get_model_port(model_key))
                with STATE_LOCK:
                    STATE.model_key = model_key
                    STATE.model_alias = get_model_alias(model_key)
            model_alias = get_model_alias(model_key)
            messages = build_raw_messages(
                model_key,
                build_raw_analyze_user_message(prompt, context),
                build_analyze_system_prompt(model_key),
            )
            reply = call_local_model(
                model_alias,
                messages,
                max_tokens=get_analyze_max_tokens(model_key),
                timeout_seconds=get_analyze_timeout_seconds(model_key),
                continue_on_length=0,
                raw_mode=True,
            ).strip()
            if not reply:
                raise ModelReplyError(
                    make_error(
                        "MODEL_EMPTY_REPLY",
                        "模型沒有產生可顯示的最終答案。",
                        "",
                        extra={"modelKey": model_key},
                    )
                )
            with STATE_LOCK:
                STATE.history.append({
                    "role": "assistant",
                    "content": reply,
                    "kind": "analysis",
                    "modelKey": model_key,
                    "modelName": str(get_model_capabilities(model_key).get("display_name", model_key)),
                    "contextUsed": bool(context.strip()),
                })
                compact_session_memory_locked(model_key)
            json_response(self, {"ok": True, "data": {"reply": reply, "modelKey": model_key, "modelName": str(get_model_capabilities(model_key).get("display_name", model_key)), "contextCoverage": context_coverage}})
        except ModelReplyError as exc:
            error_response(self, exc.error)
        except ValueError as exc:
            details = str(exc)
            if details == "請先完成開啟專案。":
                code = "PROJECT_NOT_READY"
                message = "Project is not ready."
            elif details.startswith("Unsupported model"):
                code = "MODEL_INVALID"
                message = "Model validation failed."
            else:
                code = "ANALYZE_FAILED"
                message = "Analyze failed."
            error_response(self, make_error(code, message, details))
        except Exception as exc:
            error_response(self, make_error("MODEL_START_FAILED", "Analyze failed.", str(exc)))

    def handle_chat(self) -> None:
        try:
            payload = self.read_json_body()
            message = str(payload.get("message", "")).strip()
            requested_model_key = str(payload.get("modelKey", "")).strip().lower()
            image_id = str(payload.get("imageId", "")).strip()
            attachment_ids = payload.get("attachmentIds", [])
            if not isinstance(attachment_ids, list):
                attachment_ids = []
            if image_id:
                attachment_ids = [image_id, *[str(item) for item in attachment_ids]]
            attachments = [get_uploaded_file(str(item).strip()) for item in attachment_ids if str(item).strip()]
            attachments = [item for item in attachments if item is not None]
            images = [item for item in attachments if item.get("kind") == "image"]
            if not message and not attachments:
                raise ValueError("message or image is required.")
            with STATE_LOCK:
                model_key = requested_model_key or STATE.model_key
                if model_key not in SUPPORTED_MODEL_KEYS:
                    raise ValueError("Unsupported model.")
                project_root = Path(STATE.project_path) if STATE.project_path else None
                snapshot = SessionState(
                    project_path=STATE.project_path,
                    model_key=model_key,
                    model_alias=get_model_alias(model_key),
                    summary=STATE.summary,
                    tree=list(STATE.tree),
                    files=list(STATE.files),
                    entrypoints=list(STATE.entrypoints),
                    tests=list(STATE.tests),
                    pinned_files=list(STATE.pinned_files),
                    current_preview_path=None,
                    history=list(STATE.history),
                    memory_summary=STATE.memory_summary,
                    memory_compacted_count=STATE.memory_compacted_count,
                    pending_edit=STATE.pending_edit,
                    ui_state=STATE.ui_state,
                )
                effective_message = message
                continuation_message = build_history_continuation_message(message, snapshot.history) if is_continue_request(message) else None
                if continuation_message:
                    effective_message = continuation_message
                    context = ""
                    context_coverage = {"mode": "history-continuation", "historyItems": len(snapshot.history)}
                elif project_root is not None and snapshot.pinned_files:
                    context, context_coverage = build_project_context(
                        project_root,
                        snapshot,
                        effective_message or "請根據附件回答。",
                        prefer_compact=bool(images) and model_prefers_compact_image_context(model_key),
                    )
                elif project_root is not None:
                    context, context_coverage = build_project_rag_context(project_root, snapshot, effective_message or "請根據附件回答。", model_key)
                else:
                    context = ""
                    context_coverage = None
                max_tokens = get_request_max_tokens(payload, get_chat_max_tokens(snapshot.model_key))
            if attachment_ids and not attachments:
                raise ValueError("Uploaded file not found. Please upload the file again.")
            ensure_local_model_server(model_key, port=get_model_port(model_key))
            model_alias = get_model_alias(model_key)
            attachments = prepare_attachments_for_model(snapshot.model_key, attachments)
            reply, fallback_info, _attachment_meta = call_local_model_with_attachment_fallback(
                model_alias,
                snapshot.model_key,
                context,
                effective_message,
                attachments,
                build_chat_system_prompt(snapshot.model_key),
                max_tokens=max_tokens,
                timeout_seconds=get_chat_timeout_seconds(snapshot.model_key),
                continue_on_length=get_continue_on_length(snapshot.model_key),
                history=[] if continuation_message else snapshot.history,
                memory_summary="" if continuation_message else snapshot.memory_summary,
            )
            if not reply:
                raise ModelReplyError(
                    make_error(
                        "MODEL_EMPTY_REPLY",
                        "模型沒有產生可顯示的最終答案。",
                        "",
                        extra={"modelKey": model_key},
                    )
                )
            with STATE_LOCK:
                STATE.model_key = model_key
                STATE.model_alias = model_alias
                user_record: Dict[str, object] = {"role": "user", "content": message, "kind": "chat", "contextUsed": bool(context.strip())}
                if attachments:
                    user_record["attachments"] = [build_history_attachment(item) for item in attachments]
                STATE.history.append(user_record)
                STATE.history.append({"role": "assistant", "content": reply, "kind": "chat", "modelKey": model_key, "modelName": str(get_model_capabilities(model_key).get("display_name", model_key)), "contextUsed": bool(context.strip())})
                compact_session_memory_locked(model_key)
            json_response(self, {"ok": True, "data": {"reply": reply, "modelKey": model_key, "contextCoverage": context_coverage, "attachmentFallback": fallback_info}})
        except ModelReplyError as exc:
            error_response(self, exc.error)
        except ValueError as exc:
            details = str(exc)
            if details == "請先完成開啟專案。":
                code = "PROJECT_NOT_READY"
                message = "Project is not ready."
            elif details.startswith("Selected model does not support image input"):
                code = "IMAGE_MODEL_UNSUPPORTED"
                message = "Selected model does not support image input."
            elif details.startswith("Uploaded image not found") or details.startswith("Uploaded file not found"):
                code = "FILE_UPLOAD_FAILED"
                message = "Uploaded file is not available."
            elif details.startswith("Unsupported model"):
                code = "MODEL_INVALID"
                message = "Model validation failed."
            elif details == "message or image is required.":
                code = "CHAT_EMPTY"
                message = "message or image is required."
            else:
                code = "CHAT_FAILED"
                message = "Chat failed."
            error_response(self, make_error(code, message, details))
        except Exception as exc:
            error_response(self, make_error("MODEL_START_FAILED", "Chat failed.", str(exc)))

    def handle_chat_stream(self) -> None:
        try:
            payload = self.read_json_body()
            message = str(payload.get("message", "")).strip()
            requested_model_key = str(payload.get("modelKey", "")).strip().lower()
            image_id = str(payload.get("imageId", "")).strip()
            attachment_ids = payload.get("attachmentIds", [])
            if not isinstance(attachment_ids, list):
                attachment_ids = []
            if image_id:
                attachment_ids = [image_id, *[str(item) for item in attachment_ids]]
            attachments = [get_uploaded_file(str(item).strip()) for item in attachment_ids if str(item).strip()]
            attachments = [item for item in attachments if item is not None]
            images = [item for item in attachments if item.get("kind") == "image"]
            if not message and not attachments:
                raise ValueError("message or image is required.")
            with STATE_LOCK:
                model_key = requested_model_key or STATE.model_key
                if model_key not in SUPPORTED_MODEL_KEYS:
                    raise ValueError("Unsupported model.")
                project_root = Path(STATE.project_path) if STATE.project_path else None
                snapshot = SessionState(
                    project_path=STATE.project_path,
                    model_key=model_key,
                    model_alias=get_model_alias(model_key),
                    summary=STATE.summary,
                    tree=list(STATE.tree),
                    files=list(STATE.files),
                    entrypoints=list(STATE.entrypoints),
                    tests=list(STATE.tests),
                    pinned_files=list(STATE.pinned_files),
                    current_preview_path=None,
                    history=list(STATE.history),
                    memory_summary=STATE.memory_summary,
                    memory_compacted_count=STATE.memory_compacted_count,
                    pending_edit=STATE.pending_edit,
                    ui_state=STATE.ui_state,
                )
                effective_message = message
                continuation_message = build_history_continuation_message(message, snapshot.history) if is_continue_request(message) else None
                if continuation_message:
                    effective_message = continuation_message
                    context = ""
                    context_coverage = {"mode": "history-continuation", "historyItems": len(snapshot.history)}
                elif project_root is not None and snapshot.pinned_files:
                    context, context_coverage = build_project_context(
                        project_root,
                        snapshot,
                        effective_message or "請根據附件回答。",
                        prefer_compact=bool(images) and model_prefers_compact_image_context(model_key),
                    )
                elif project_root is not None:
                    context, context_coverage = build_project_rag_context(project_root, snapshot, effective_message or "請根據附件回答。", model_key)
                else:
                    context = ""
                    context_coverage = None
                max_tokens = get_request_max_tokens(payload, get_chat_max_tokens(snapshot.model_key))
            if attachment_ids and not attachments:
                raise ValueError("Uploaded file not found. Please upload the file again.")
        except ValueError as exc:
            details = str(exc)
            code = "MODEL_INVALID" if details.startswith("Unsupported model") else "CHAT_FAILED"
            error_response(self, make_error(code, "Chat failed.", details))
            return
        except Exception as exc:
            error_response(self, make_error("CHAT_FAILED", "Chat failed.", str(exc)))
            return

        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Connection", "close")
        self.close_connection = True
        self.end_headers()

        reasoning_parts: List[str] = []
        content_parts: List[str] = []
        reasoning_open = False
        try:
            write_sse_event(self, "status", {"message": "啟動本地模型", "modelKey": model_key})
            ensure_local_model_server(model_key, port=get_model_port(model_key))
            model_alias = get_model_alias(model_key)
            attachments = prepare_attachments_for_model(snapshot.model_key, attachments)
            write_sse_event(self, "context", {"contextCoverage": context_coverage})
            write_sse_event(self, "model", {"modelKey": model_key, "modelName": str(get_model_capabilities(model_key).get("display_name", model_key))})
            for event in stream_local_model_with_attachment_fallback(
                model_alias,
                snapshot.model_key,
                context,
                effective_message,
                attachments,
                build_chat_system_prompt(snapshot.model_key),
                max_tokens=max_tokens,
                timeout_seconds=get_chat_timeout_seconds(snapshot.model_key),
                continue_on_length=get_continue_on_length(snapshot.model_key),
                history=[] if continuation_message else snapshot.history,
                memory_summary="" if continuation_message else snapshot.memory_summary,
            ):
                event_type = event.get("type", "content")
                text = str(event.get("text", ""))
                if event_type == "finish":
                    continue
                if event_type == "attachment_fallback":
                    write_sse_event(
                        self,
                        "attachment_fallback",
                        {
                            "reason": str(event.get("reason", "")),
                            "fallbackKinds": event.get("fallbackKinds", []),
                            "retried": bool(event.get("retried", False)),
                        },
                    )
                    continue
                if event_type == "continuation":
                    write_sse_event(self, "continuation", {"text": text or "內容過長，已自動續寫。"})
                    continue
                if not text:
                    continue
                if event_type == "reasoning":
                    reasoning_parts.append(text)
                    if not reasoning_open:
                        reasoning_open = True
                        write_sse_event(self, "reasoning_start", {"modelKey": model_key})
                    write_sse_event(self, "reasoning", {"text": text})
                else:
                    if reasoning_open:
                        reasoning_open = False
                        write_sse_event(self, "reasoning_end", {})
                    content_parts.append(text)
                    write_sse_event(self, "content", {"text": text})
            if reasoning_open:
                write_sse_event(self, "reasoning_end", {})
            reasoning = "".join(reasoning_parts).strip()
            content = "".join(content_parts).strip()
            reply_parts = []
            if reasoning:
                reply_parts.append(f"<think>\n{reasoning}\n</think>")
            if content:
                reply_parts.append(content)
            reply = "\n\n".join(reply_parts).strip()
            if not reply:
                raise ModelReplyError(make_error("MODEL_EMPTY_REPLY", "模型沒有產生可顯示的最終答案。", "", extra={"modelKey": model_key}))
            with STATE_LOCK:
                STATE.model_key = model_key
                STATE.model_alias = model_alias
                user_record: Dict[str, object] = {"role": "user", "content": message, "kind": "chat", "contextUsed": bool(context.strip())}
                if attachments:
                    user_record["attachments"] = [build_history_attachment(item) for item in attachments]
                STATE.history.append(user_record)
                STATE.history.append({"role": "assistant", "content": reply, "kind": "chat", "modelKey": model_key, "modelName": str(get_model_capabilities(model_key).get("display_name", model_key)), "contextUsed": bool(context.strip())})
                compact_session_memory_locked(model_key)
            write_sse_event(self, "done", {"reply": reply, "modelKey": model_key, "modelName": str(get_model_capabilities(model_key).get("display_name", model_key)), "contextCoverage": context_coverage})
        except ModelReplyError as exc:
            write_sse_event(self, "error", exc.error)
        except Exception as exc:
            write_sse_event(self, "error", make_error("MODEL_START_FAILED", "Chat failed.", str(exc), extra={"modelKey": model_key}))

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
                    memory_summary=STATE.memory_summary,
                    memory_compacted_count=STATE.memory_compacted_count,
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
                compact_session_memory_locked(STATE.model_key)
            setattr(self.server, "_pending_edit_internal", plan)
            json_response(self, {"ok": True, "data": {"plan": public_plan}})
        except ValueError as exc:
            details = str(exc)
            code = "PROJECT_NOT_READY" if details == "請先完成開啟專案。" else "PINNED_CONTEXT_REQUIRED"
            message = "Project is not ready." if code == "PROJECT_NOT_READY" else "請先勾選釘選檔案。"
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
            STATE.memory_summary = ""
            STATE.memory_compacted_count = 0
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
            target = (project_root / relative_path).resolve()
            kind = file_kind_from_path(relative_path)
            if kind == "image" and target.stat().st_size <= MAX_UPLOAD_BYTES:
                mime_type, _ = mimetypes.guess_type(str(target))
                data_url = f"data:{mime_type or 'application/octet-stream'};base64,{base64.b64encode(target.read_bytes()).decode('ascii')}"
                json_response(self, {"ok": True, "data": {"path": relative_path, "content": "", "kind": kind, "dataUrl": data_url}})
                return
            if kind == "document":
                content = read_file_full(project_root, relative_path)
                json_response(self, {"ok": True, "data": {"path": relative_path, "content": content, "kind": kind}})
                return
            if kind != "text":
                stat = target.stat()
                content = (
                    f"{relative_path}\n"
                    f"類型: {kind}\n"
                    f"大小: {human_size(stat.st_size)}\n"
                    "此檔案可被列入附件或 RAG metadata；目前檔案預覽不直接解析其二進位內容。"
                )
                json_response(self, {"ok": True, "data": {"path": relative_path, "content": content, "kind": kind}})
                return
            content = read_file_full(project_root, relative_path)
            json_response(self, {"ok": True, "data": {"path": relative_path, "content": content, "kind": kind}})
        except ValueError as exc:
            error_response(self, make_error("PROJECT_NOT_READY", "Cannot preview file.", str(exc)))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8764, type=int)
    args = parser.parse_args()
    cleanup_image_upload_dir()
    server = ThreadingHTTPServer((args.host, args.port), WebUIHandler)
    print(f"CodeWorker Web UI running at http://{args.host}:{args.port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
