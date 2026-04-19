import fnmatch
import json
import sys
from pathlib import Path


def emit(name: str, value: object) -> None:
    text = str(value or "")
    print(f'set "{name}={text}"')


def as_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


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
    emit("MODEL_FILE", first_match(target_dir, file_patterns))
    emit("MODEL_MMPROJ", first_match(target_dir, mmproj_patterns) if mmproj_patterns else "")
    emit("MODEL_FILE_PATTERNS", ";".join(file_patterns))
    emit("MODEL_MMPROJ_PATTERNS", ";".join(mmproj_patterns))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
