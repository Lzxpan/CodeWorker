import fnmatch
import json
import sys
from pathlib import Path


def emit(name: str, value: object) -> None:
    text = "" if value is None else str(value)
    print(f'set "{name}={text}"')


def as_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def parse_llama_args(raw_args: object) -> list[str]:
    args = as_list(raw_args)
    return [arg for arg in args if arg.startswith("--")]


def load_hardware_profiles(root: Path) -> dict:
    path = root / "data" / "hardware-model-profiles.json"
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return raw if isinstance(raw, dict) else {}


def detect_auto_settings(root: Path, model_key: str, config: dict, model_file: str = "") -> dict:
    try:
        sys.path.insert(0, str(root / "webui"))
        from core.hardware import build_optimization_plan, classify_hardware, detect_hardware  # type: ignore

        profile = classify_hardware(detect_hardware())
        runtime_path = (
            root
            / "runtime"
            / "llama.cpp"
            / "llama-server.exe"
        )
        return build_optimization_plan(
            profile,
            model_key,
            config,
            stored_profiles=load_hardware_profiles(root),
            model_file_path=model_file,
            runtime_path=runtime_path,
        )
    except Exception:
        return {
            "contextWindow": int(config.get("contextWindow") or 4096),
            "nGpuLayers": int(config.get("nGpuLayers") or 0),
            "cacheTypeK": config.get("cacheTypeK") or "",
            "cacheTypeV": config.get("cacheTypeV") or "",
            "llamaArgs": parse_llama_args(config.get("llamaArgs")),
        }


def first_match(model_dir: Path, patterns: list[str]) -> str:
    if not model_dir.exists():
        return ""
    candidates = sorted(path for path in model_dir.glob("*.gguf") if path.is_file())
    if not patterns:
        return str(candidates[0]) if candidates else ""
    for pattern in patterns:
        matches = [
            path for path in candidates
            if fnmatch.fnmatch(path.name.lower(), pattern.lower())
        ]
        if matches:
            return str(matches[0])
    return ""


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    model_key = (sys.argv[1] if len(sys.argv) > 1 else "gemma4").lower()
    manifest_path = root / "config" / "bootstrap.manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    models = manifest.get("models", {})
    config = models.get(model_key)
    if not isinstance(config, dict) or not config.get("enabled", False):
        print(f'[ERROR_CODE] MODEL_START_FAILED')
        print(f'[ERROR_MESSAGE] Unknown model.')
        print(f'[ERROR_DETAILS] {model_key}')
        return 1

    target_dir = root / str(config.get("targetDir", "")).strip()
    file_patterns = as_list(config.get("filePatterns"))
    file_pattern = str(config.get("filePattern", "")).strip()
    if file_pattern and file_pattern not in file_patterns:
        file_patterns.insert(0, file_pattern)
    mmproj_patterns = as_list(config.get("mmprojPatterns")) or as_list(config.get("mmprojPattern"))

    emit("MODEL_DIR", target_dir)
    emit("MODEL_ALIAS", config.get("alias") or f"{model_key}-local")
    emit("MODEL_PORT", config.get("port") or 8082)
    model_file = first_match(target_dir, file_patterns)
    mmproj_file = first_match(target_dir, mmproj_patterns) if mmproj_patterns else ""
    auto_settings = detect_auto_settings(root, model_key, config, model_file)
    emit("MODEL_CONTEXT", auto_settings.get("contextWindow") or config.get("contextWindow") or 4096)
    emit("MODEL_CACHE_TYPE_K", auto_settings.get("cacheTypeK") or config.get("cacheTypeK") or "")
    emit("MODEL_CACHE_TYPE_V", auto_settings.get("cacheTypeV") or config.get("cacheTypeV") or "")
    llama_args = parse_llama_args(auto_settings.get("llamaArgs"))
    emit("MODEL_N_GPU_LAYERS", auto_settings.get("nGpuLayers") or 0)
    emit("MODEL_LLAMA_ARGS", " ".join(llama_args))
    emit("MODEL_FILE", model_file)
    emit("MODEL_MMPROJ", mmproj_file)
    emit("MODEL_FILE_PATTERNS", ";".join(file_patterns))
    emit("MODEL_MMPROJ_PATTERNS", ";".join(mmproj_patterns))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
