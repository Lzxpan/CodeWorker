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


def detect_auto_settings(root: Path, model_key: str, config: dict) -> tuple[int, list[str]]:
    try:
        sys.path.insert(0, str(root / "webui"))
        from core.hardware import classify_hardware, detect_hardware, recommend_model_settings  # type: ignore

        profile = classify_hardware(detect_hardware())
        settings = recommend_model_settings(profile, config)
        n_gpu_layers = int(settings.get("nGpuLayers") or 0)
        max_vram = float(profile.get("maxVramGb") or 0)
        total_ram = float(profile.get("totalRamGb") or 0)
        recommended_ram = float(config.get("recommendedRamGb") or 0)
        use_low_memory = bool(config.get("lowMemoryLlamaArgs")) and (
            0 <= max_vram < 4 or (recommended_ram > 0 and total_ram < recommended_ram)
        )
        raw_args = config.get("lowMemoryLlamaArgs") if use_low_memory else config.get("llamaArgs")
        return n_gpu_layers, parse_llama_args(raw_args)
    except Exception:
        return int(config.get("nGpuLayers") or 0), parse_llama_args(config.get("llamaArgs"))


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
    emit("MODEL_CONTEXT", config.get("contextWindow") or 4096)
    emit("MODEL_CACHE_TYPE_K", config.get("cacheTypeK") or "")
    emit("MODEL_CACHE_TYPE_V", config.get("cacheTypeV") or "")
    n_gpu_layers, llama_args = detect_auto_settings(root, model_key, config)
    emit("MODEL_N_GPU_LAYERS", n_gpu_layers)
    emit("MODEL_LLAMA_ARGS", " ".join(llama_args))
    emit("MODEL_FILE", first_match(target_dir, file_patterns))
    emit("MODEL_MMPROJ", first_match(target_dir, mmproj_patterns) if mmproj_patterns else "")
    emit("MODEL_FILE_PATTERNS", ";".join(file_patterns))
    emit("MODEL_MMPROJ_PATTERNS", ";".join(mmproj_patterns))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
