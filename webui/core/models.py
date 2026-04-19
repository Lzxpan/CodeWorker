import fnmatch
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional


@dataclass(frozen=True)
class ModelConfig:
    key: str
    enabled: bool
    provider: str
    service_provider: str
    repo: str
    target_dir: str
    display_name: str
    model_id: str
    alias: str
    port: int
    context_window: int
    cache_type_k: str
    cache_type_v: str
    file_pattern: str
    file_patterns: List[str]
    mmproj_patterns: List[str]
    supports_images: bool
    compact_image_context: bool
    temperature: Optional[float]
    top_p: Optional[float]
    top_k: Optional[int]


def load_manifest(root_dir: Path) -> Dict[str, object]:
    manifest_path = root_dir / "config" / "bootstrap.manifest.json"
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def _as_list(value: object) -> List[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def get_model_configs(root_dir: Path) -> Dict[str, ModelConfig]:
    manifest = load_manifest(root_dir)
    raw_models = manifest.get("models", {})
    if not isinstance(raw_models, dict):
        return {}
    configs: Dict[str, ModelConfig] = {}
    for key, raw in raw_models.items():
        if not isinstance(raw, dict):
            continue
        file_patterns = _as_list(raw.get("filePatterns"))
        file_pattern = str(raw.get("filePattern", "")).strip()
        if file_pattern and file_pattern not in file_patterns:
            file_patterns.insert(0, file_pattern)
        configs[str(key).lower()] = ModelConfig(
            key=str(key).lower(),
            enabled=bool(raw.get("enabled", False)),
            provider=str(raw.get("provider", "huggingface")).strip() or "huggingface",
            service_provider=str(raw.get("serviceProvider", "llama.cpp")).strip() or "llama.cpp",
            repo=str(raw.get("repo", "")).strip(),
            target_dir=str(raw.get("targetDir", "")).strip(),
            display_name=str(raw.get("displayName", key)).strip() or str(key),
            model_id=str(raw.get("modelId", raw.get("alias", key))).strip() or str(key),
            alias=str(raw.get("alias", f"{key}-local")).strip() or f"{key}-local",
            port=int(raw.get("port", 0) or 0),
            context_window=int(raw.get("contextWindow", raw.get("context", 4096)) or 4096),
            cache_type_k=str(raw.get("cacheTypeK", "")).strip(),
            cache_type_v=str(raw.get("cacheTypeV", "")).strip(),
            file_pattern=file_pattern,
            file_patterns=file_patterns,
            mmproj_patterns=_as_list(raw.get("mmprojPatterns")) or _as_list(raw.get("mmprojPattern")),
            supports_images=bool(raw.get("supportsImages", False)),
            compact_image_context=bool(raw.get("compactImageContext", False)),
            temperature=float(raw["temperature"]) if raw.get("temperature") is not None else None,
            top_p=float(raw["topP"]) if raw.get("topP") is not None else None,
            top_k=int(raw["topK"]) if raw.get("topK") is not None else None,
        )
    return configs


def get_model_config(root_dir: Path, model_key: str) -> Optional[ModelConfig]:
    return get_model_configs(root_dir).get(str(model_key or "").lower())


def public_model_capabilities(root_dir: Path) -> Dict[str, Dict[str, object]]:
    payload: Dict[str, Dict[str, object]] = {}
    for key, config in sorted(get_model_configs(root_dir).items()):
        if not config.enabled:
            continue
        payload[key] = {
            "displayName": config.display_name,
            "supportsImages": config.supports_images,
            "requiresMmproj": bool(config.mmproj_patterns),
            "compactImageContext": config.compact_image_context,
            "provider": config.service_provider,
            "modelId": config.model_id,
            "port": config.port,
            "contextWindow": config.context_window,
            "cacheTypeK": config.cache_type_k,
            "cacheTypeV": config.cache_type_v,
            "targetDir": config.target_dir,
            "generation": {
                "temperature": config.temperature,
                "topP": config.top_p,
                "topK": config.top_k,
            },
        }
    return payload


def match_first_model_file(model_dir: Path, patterns: List[str]) -> Optional[Path]:
    candidates = sorted(path for path in model_dir.glob("*.gguf") if path.is_file())
    if not patterns:
        return candidates[0] if candidates else None
    for pattern in patterns:
        matched = [
            path for path in candidates
            if fnmatch.fnmatch(path.name.lower(), pattern.lower())
        ]
        if matched:
            return matched[0]
    return None
