import json
import hashlib
import os
import platform
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List


@dataclass(frozen=True)
class HardwareInfo:
    total_ram_gb: float
    cpu_cores: int
    cpu_threads: int
    gpus: List[Dict[str, object]] = field(default_factory=list)
    has_nvidia_smi: bool = False
    has_vulkan: bool = False
    os_name: str = ""
    arch: str = ""
    cpu_model: str = ""
    machine_type: str = "pc"


def _run_powershell(command: str) -> str:
    try:
        completed = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            timeout=15,
        )
    except Exception:
        return ""
    if completed.returncode != 0:
        return ""
    return completed.stdout.strip()


def _vendor_from_name(name: str) -> str:
    lowered = name.lower()
    if "nvidia" in lowered or "geforce" in lowered or "quadro" in lowered or "rtx" in lowered:
        return "nvidia"
    if "amd" in lowered or "radeon" in lowered:
        return "amd"
    if "intel" in lowered or "arc" in lowered or "iris" in lowered:
        return "intel"
    return "unknown"


def _detect_windows_hardware() -> HardwareInfo:
    computer_raw = _run_powershell(
        "Get-CimInstance Win32_ComputerSystem | "
        "Select-Object TotalPhysicalMemory,NumberOfLogicalProcessors | ConvertTo-Json -Compress"
    )
    cpu_raw = _run_powershell(
        "Get-CimInstance Win32_Processor | "
        "Select-Object Name,NumberOfCores,NumberOfLogicalProcessors | ConvertTo-Json -Compress"
    )
    gpu_raw = _run_powershell(
        "Get-CimInstance Win32_VideoController | "
        "Select-Object Name,AdapterRAM,DriverVersion | ConvertTo-Json -Compress"
    )

    total_ram_gb = 0.0
    cpu_threads = os.cpu_count() or 1
    cpu_cores = max(1, cpu_threads // 2)
    cpu_model = ""
    try:
        computer = json.loads(computer_raw) if computer_raw else {}
        if isinstance(computer, list):
            computer = computer[0] if computer else {}
        total_ram_gb = round(float(computer.get("TotalPhysicalMemory", 0)) / (1024 ** 3), 1)
        cpu_threads = int(computer.get("NumberOfLogicalProcessors") or cpu_threads)
    except Exception:
        pass
    try:
        cpus = json.loads(cpu_raw) if cpu_raw else {}
        if isinstance(cpus, dict):
            cpus = [cpus]
        if cpus:
            cpu_cores = sum(int(item.get("NumberOfCores") or 0) for item in cpus) or cpu_cores
            cpu_threads = sum(int(item.get("NumberOfLogicalProcessors") or 0) for item in cpus) or cpu_threads
            cpu_model = str(cpus[0].get("Name", "") or "").strip()
    except Exception:
        pass

    gpus: List[Dict[str, object]] = []
    try:
        raw_gpus = json.loads(gpu_raw) if gpu_raw else []
        if isinstance(raw_gpus, dict):
            raw_gpus = [raw_gpus]
        for gpu in raw_gpus:
            name = str(gpu.get("Name", "")).strip()
            if not name:
                continue
            adapter_ram = float(gpu.get("AdapterRAM") or 0)
            gpus.append({
                "name": name,
                "vendor": _vendor_from_name(name),
                "vramGb": round(adapter_ram / (1024 ** 3), 1) if adapter_ram > 0 else 0.0,
                "driverVersion": str(gpu.get("DriverVersion", "")).strip(),
            })
    except Exception:
        pass

    return HardwareInfo(
        total_ram_gb=total_ram_gb,
        cpu_cores=cpu_cores,
        cpu_threads=cpu_threads,
        gpus=gpus,
        has_nvidia_smi=shutil.which("nvidia-smi") is not None,
        has_vulkan=_detect_vulkan(gpus),
        os_name="Windows",
        arch=platform.machine(),
        cpu_model=cpu_model,
        machine_type="pc",
    )


def _run_command(command: List[str], timeout: int = 8) -> str:
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            timeout=timeout,
        )
    except Exception:
        return ""
    if completed.returncode != 0:
        return ""
    return completed.stdout.strip()


def _detect_darwin_hardware() -> HardwareInfo:
    def sysctl_value(name: str) -> str:
        return _run_command(["sysctl", "-n", name])

    total_ram_gb = 0.0
    try:
        total_ram_gb = round(float(sysctl_value("hw.memsize") or 0) / (1024 ** 3), 1)
    except Exception:
        total_ram_gb = 0.0
    try:
        cpu_cores = int(sysctl_value("hw.physicalcpu") or 0) or max(1, (os.cpu_count() or 1) // 2)
    except Exception:
        cpu_cores = max(1, (os.cpu_count() or 1) // 2)
    try:
        cpu_threads = int(sysctl_value("hw.logicalcpu") or 0) or (os.cpu_count() or 1)
    except Exception:
        cpu_threads = os.cpu_count() or 1
    cpu_model = sysctl_value("machdep.cpu.brand_string") or "Apple Silicon"
    machine_model = sysctl_value("hw.model")
    machine_type = "mac-mini" if "mini" in machine_model.lower() else "apple-silicon"
    gpus = [{"name": cpu_model, "vendor": "apple", "vramGb": 0.0, "driverVersion": ""}]
    return HardwareInfo(
        total_ram_gb=total_ram_gb,
        cpu_cores=cpu_cores,
        cpu_threads=cpu_threads,
        gpus=gpus,
        has_nvidia_smi=False,
        has_vulkan=False,
        os_name="Darwin",
        arch=platform.machine(),
        cpu_model=cpu_model,
        machine_type=machine_type,
    )


def _detect_vulkan(gpus: List[Dict[str, object]]) -> bool:
    if shutil.which("vulkaninfo") is not None:
        return True
    return any(str(gpu.get("vendor", "")) in {"amd", "intel", "nvidia"} for gpu in gpus)


def detect_hardware() -> HardwareInfo:
    system = platform.system()
    if system.lower() == "windows":
        return _detect_windows_hardware()
    if system.lower() == "darwin":
        return _detect_darwin_hardware()
    total_ram_gb = 0.0
    try:
        if hasattr(os, "sysconf"):
            pages = os.sysconf("SC_PHYS_PAGES")
            page_size = os.sysconf("SC_PAGE_SIZE")
            total_ram_gb = round((pages * page_size) / (1024 ** 3), 1)
    except Exception:
        total_ram_gb = 0.0
    cpu_threads = os.cpu_count() or 1
    return HardwareInfo(
        total_ram_gb=total_ram_gb,
        cpu_cores=max(1, cpu_threads // 2),
        cpu_threads=cpu_threads,
        gpus=[],
        has_nvidia_smi=shutil.which("nvidia-smi") is not None,
        has_vulkan=shutil.which("vulkaninfo") is not None,
        os_name=system,
        arch=platform.machine(),
        cpu_model=platform.processor(),
        machine_type="pc",
    )


def _bucket(value: float, buckets: List[int]) -> int:
    for bucket in buckets:
        if value <= bucket:
            return bucket
    return buckets[-1]


def _vram_class(vendor: str, bucket: int) -> str:
    if bucket >= 64:
        suffix = "64gb-plus"
    elif bucket >= 48:
        suffix = "48gb-plus"
    else:
        suffix = f"{bucket}gb"
    return f"{vendor}-vram-{suffix}"


def classify_hardware(info: HardwareInfo) -> Dict[str, object]:
    max_vram = max((float(gpu.get("vramGb") or 0) for gpu in info.gpus), default=0.0)
    vendors = sorted({str(gpu.get("vendor", "unknown")) for gpu in info.gpus if gpu.get("vendor")})
    ram_bucket = _bucket(float(info.total_ram_gb or 0), [16, 32, 64, 96, 128, 192, 256, 512])
    vram_bucket = _bucket(float(max_vram or 0), [0, 4, 8, 16, 24, 36, 48, 64])
    os_name = info.os_name or platform.system()
    arch = info.arch or platform.machine()
    machine_type = info.machine_type or "pc"
    primary_vendor = vendors[0] if vendors else ""
    if os_name.lower() == "darwin" or primary_vendor == "apple" or "apple" in str(info.cpu_model).lower():
        hardware_class = "apple-silicon-unified"
    elif not vendors or max_vram <= 0:
        hardware_class = "cpu-only"
    elif max_vram < 4 and primary_vendor in {"amd", "intel"}:
        hardware_class = "igpu-shared-memory"
    elif "nvidia" in vendors:
        hardware_class = _vram_class("nvidia", vram_bucket)
    elif "amd" in vendors:
        hardware_class = _vram_class("amd", vram_bucket)
    elif "intel" in vendors:
        hardware_class = _vram_class("intel", vram_bucket)
    else:
        hardware_class = "gpu-unknown"
    if info.total_ram_gb >= 192 or max_vram >= 48:
        profile = "extreme"
    elif info.total_ram_gb >= 64 and (max_vram >= 12 or info.has_nvidia_smi):
        profile = "high"
    elif info.total_ram_gb >= 30:
        profile = "standard"
    else:
        profile = "low"
    return {
        "profile": profile,
        "totalRamGb": info.total_ram_gb,
        "cpuCores": info.cpu_cores,
        "cpuThreads": info.cpu_threads,
        "gpus": [dict(gpu) for gpu in info.gpus],
        "gpuVendors": vendors,
        "maxVramGb": max_vram,
        "ramBucketGb": ram_bucket,
        "vramBucketGb": vram_bucket,
        "hardwareClass": hardware_class,
        "hasNvidiaSmi": info.has_nvidia_smi,
        "hasVulkan": info.has_vulkan,
        "osName": os_name,
        "arch": arch,
        "cpuModel": info.cpu_model,
        "machineType": machine_type,
    }


def select_runtime_backend(profile: Dict[str, object]) -> str:
    if str(profile.get("hardwareClass") or "") == "apple-silicon-unified" or str(profile.get("osName") or "").lower() == "darwin":
        return "metal"
    if str(profile.get("hardwareClass") or "") == "igpu-shared-memory":
        return "cpu"
    vendors = set(profile.get("gpuVendors") or [])
    if profile.get("hasNvidiaSmi") or "nvidia" in vendors:
        return "cuda"
    if profile.get("hasVulkan") and vendors.intersection({"amd", "intel", "nvidia"}):
        return "vulkan"
    return "cpu"


def _model_context_options(model_config: Dict[str, object]) -> List[int]:
    raw = model_config.get("contextOptions") or []
    values: List[int] = []
    if isinstance(raw, list):
        for item in raw:
            try:
                values.append(int(item))
            except (TypeError, ValueError):
                continue
    configured = model_config.get("contextWindow")
    try:
        values.append(int(configured))
    except (TypeError, ValueError):
        pass
    return sorted({value for value in values if value > 0}) or [4096]


def _base_model_settings(profile: Dict[str, object], model_config: Dict[str, object]) -> Dict[str, object]:
    context_options = _model_context_options(model_config)
    profile_name = str(profile.get("profile") or "low")
    max_vram_gb = float(profile.get("maxVramGb") or 0)
    hardware_class = str(profile.get("hardwareClass") or "")
    if profile_name == "extreme":
        context = context_options[-1]
    elif profile_name == "high":
        context = max([value for value in context_options if value <= 131072] or [context_options[0]])
    elif profile_name == "standard":
        context = max([value for value in context_options if value <= 65536] or [context_options[0]])
    else:
        context = max([value for value in context_options if value <= 32768] or [context_options[0]])
    try:
        low_vram_context = int(model_config.get("lowVramContextWindow") or 0)
    except (TypeError, ValueError):
        low_vram_context = 0
    if 0 < max_vram_gb <= 8 and low_vram_context > 0:
        context = min(context, low_vram_context)
    if hardware_class in {"cpu-only", "igpu-shared-memory"}:
        context = min(context, max([value for value in context_options if value <= 32768] or [context_options[0]]))

    backend = select_runtime_backend(profile)
    cpu_threads = int(profile.get("cpuThreads") or os.cpu_count() or 4)
    if backend == "cpu":
        gpu_layers = 0
    elif backend == "vulkan" and 0 <= max_vram_gb < 4 and float(model_config.get("minRamGb") or 0) >= 48:
        gpu_layers = 0
    elif profile_name == "extreme":
        gpu_layers = -1
    elif profile_name == "high":
        gpu_layers = 999
    else:
        gpu_layers = 32

    return {
        "contextWindow": context,
        "runtimeBackend": backend,
        "nGpuLayers": gpu_layers,
        "threads": max(1, min(cpu_threads, 16)),
        "cacheTypeK": str(model_config.get("cacheTypeK") or ""),
        "cacheTypeV": str(model_config.get("cacheTypeV") or ""),
    }


def _as_arg_list(raw_args: object) -> List[str]:
    if isinstance(raw_args, list):
        return parse_llama_server_args([str(item) for item in raw_args])
    return []


def _use_low_memory_args(profile: Dict[str, object], model_config: Dict[str, object]) -> bool:
    if not model_config.get("lowMemoryLlamaArgs"):
        return False
    max_vram = float(profile.get("maxVramGb") or 0)
    total_ram = float(profile.get("totalRamGb") or 0)
    recommended_ram = float(model_config.get("recommendedRamGb") or 0)
    return 0 <= max_vram < 4 or (recommended_ram > 0 and total_ram < recommended_ram)


def _constrained_cpu_like(profile: Dict[str, object], model_config: Dict[str, object], settings: Dict[str, object] = None) -> bool:
    hardware_class = str(profile.get("hardwareClass") or "")
    total_ram = float(profile.get("totalRamGb") or 0)
    recommended_ram = float(model_config.get("recommendedRamGb") or 0)
    min_ram = float(model_config.get("minRamGb") or 0)
    backend = str((settings or {}).get("runtimeBackend") or select_runtime_backend(profile))
    return backend == "cpu" and hardware_class in {"cpu-only", "igpu-shared-memory"} and (
        (min_ram > 0 and total_ram <= min_ram + 2) or (recommended_ram > 0 and total_ram < recommended_ram)
    )


def _with_constrained_cpu_args(args: List[str], profile: Dict[str, object], model_config: Dict[str, object], settings: Dict[str, object] = None) -> List[str]:
    updated = list(args)
    if not _constrained_cpu_like(profile, model_config, settings=settings):
        return updated
    existing_names = {arg.split("=", 1)[0] for arg in updated}
    if "--no-repack" not in existing_names:
        updated.append("--no-repack")
    if "--batch-size" not in existing_names:
        updated.append("--batch-size=128")
    if "--ubatch-size" not in existing_names:
        updated.append("--ubatch-size=32")
    return updated


def selected_llama_args(profile: Dict[str, object], model_config: Dict[str, object]) -> List[str]:
    raw = model_config.get("lowMemoryLlamaArgs") if _use_low_memory_args(profile, model_config) else model_config.get("llamaArgs")
    args = _as_arg_list(raw)
    return _with_constrained_cpu_args(args, profile, model_config)


def _parse_plan_llama_args(args: List[str]) -> Dict[str, object]:
    parsed: Dict[str, object] = {
        "batchSize": 0,
        "ubatchSize": 0,
        "nCpuMoe": 0,
        "flashAttn": False,
        "jinja": False,
        "mlock": False,
        "noRepack": False,
    }
    for raw in args:
        name, _, value = raw.partition("=")
        if name == "--batch-size":
            parsed["batchSize"] = int(value or 0)
        elif name == "--ubatch-size":
            parsed["ubatchSize"] = int(value or 0)
        elif name == "--n-cpu-moe":
            parsed["nCpuMoe"] = int(value or 0)
        elif name == "--flash-attn":
            parsed["flashAttn"] = True
        elif name == "--jinja":
            parsed["jinja"] = True
        elif name == "--mlock":
            parsed["mlock"] = True
        elif name == "--no-repack":
            parsed["noRepack"] = True
    return parsed


def _model_file_signature(model_file_path: object) -> Dict[str, object]:
    path_text = str(model_file_path or "").strip()
    if not path_text:
        return {"modelFilePath": "", "modelFileSize": 0, "modelFileHash": ""}
    path = Path(path_text)
    try:
        size = path.stat().st_size if path.exists() else 0
    except OSError:
        size = 0
    digest = ""
    if size > 0:
        try:
            hasher = hashlib.sha256()
            with path.open("rb") as handle:
                first = handle.read(1024 * 1024)
                hasher.update(first)
                if size > 1024 * 1024:
                    handle.seek(max(0, size - 1024 * 1024))
                    hasher.update(handle.read(1024 * 1024))
            digest = hasher.hexdigest()
        except OSError:
            digest = ""
    return {"modelFilePath": path_text, "modelFileSize": size, "modelFileHash": digest}


def build_profile_fingerprint(
    profile: Dict[str, object],
    model_key: str,
    model_config: Dict[str, object],
    settings: Dict[str, object],
    model_file_path: object = "",
    runtime_path: object = "",
) -> Dict[str, object]:
    gpus = profile.get("gpus") if isinstance(profile.get("gpus"), list) else []
    primary_gpu = gpus[0] if gpus and isinstance(gpus[0], dict) else {}
    signature = _model_file_signature(model_file_path)
    return {
        "modelKey": str(model_key or ""),
        "osName": str(profile.get("osName") or ""),
        "arch": str(profile.get("arch") or ""),
        "cpuFamily": str(profile.get("cpuModel") or "").split("@", 1)[0].strip(),
        "ramBucketGb": int(profile.get("ramBucketGb") or 0),
        "hardwareClass": str(profile.get("hardwareClass") or ""),
        "gpuVendor": str(primary_gpu.get("vendor") or ""),
        "gpuName": str(primary_gpu.get("name") or ""),
        "gpuDriverVersion": str(primary_gpu.get("driverVersion") or ""),
        "vramBucketGb": int(profile.get("vramBucketGb") or 0),
        "runtimeBackend": str(settings.get("runtimeBackend") or ""),
        "runtimePath": str(runtime_path or ""),
        "contextWindow": int(settings.get("contextWindow") or 0),
        "cacheTypeK": str(settings.get("cacheTypeK") or model_config.get("cacheTypeK") or ""),
        "cacheTypeV": str(settings.get("cacheTypeV") or model_config.get("cacheTypeV") or ""),
        "quant": str(model_config.get("defaultQuant") or ""),
        **signature,
    }


def _stored_profiles_list(stored_profiles: object) -> List[Dict[str, object]]:
    if isinstance(stored_profiles, dict):
        raw = stored_profiles.get("profiles")
    else:
        raw = stored_profiles
    return [item for item in raw if isinstance(item, dict)] if isinstance(raw, list) else []


def _same_profile_value(left: Dict[str, object], right: Dict[str, object], key: str) -> bool:
    return str(left.get(key) or "") == str(right.get(key) or "")


def match_hardware_model_profile(stored_profiles: object, fingerprint: Dict[str, object]) -> Dict[str, object]:
    candidates = [
        item for item in _stored_profiles_list(stored_profiles)
        if isinstance(item.get("fingerprint"), dict)
        and str(item["fingerprint"].get("modelKey") or "") == str(fingerprint.get("modelKey") or "")
    ]
    exact_keys = (
        "osName", "arch", "cpuFamily", "ramBucketGb", "hardwareClass", "gpuVendor", "gpuName",
        "gpuDriverVersion", "vramBucketGb", "runtimeBackend", "runtimePath", "contextWindow",
        "cacheTypeK", "cacheTypeV", "quant", "modelFileSize", "modelFileHash",
    )
    compatible_keys = (
        "osName", "arch", "ramBucketGb", "hardwareClass", "gpuVendor", "vramBucketGb",
        "runtimeBackend", "contextWindow", "cacheTypeK", "cacheTypeV", "quant", "modelFileSize",
    )
    for candidate in candidates:
        stored = candidate["fingerprint"]
        if all(_same_profile_value(stored, fingerprint, key) for key in exact_keys):
            return {"level": "exact", "source": "measured-local", "profile": candidate}
    for candidate in candidates:
        stored = candidate["fingerprint"]
        if all(_same_profile_value(stored, fingerprint, key) for key in compatible_keys):
            return {"level": "compatible", "source": "measured-local", "profile": candidate}
    return {"level": "preset", "source": "preset-unverified", "profile": None}


def _fit_level(profile: Dict[str, object], model_config: Dict[str, object]) -> str:
    total_ram = float(profile.get("totalRamGb") or 0)
    min_ram = float(model_config.get("minRamGb") or 0)
    recommended_ram = float(model_config.get("recommendedRamGb") or 0)
    if min_ram and total_ram < min_ram:
        return "below-minimum"
    if recommended_ram and total_ram < recommended_ram:
        return "constrained"
    return "recommended"


def build_optimization_plan(
    profile: Dict[str, object],
    model_key: str,
    model_config: Dict[str, object],
    stored_profiles: object = None,
    model_file_path: object = "",
    runtime_path: object = "",
) -> Dict[str, object]:
    settings = _base_model_settings(profile, model_config)
    llama_args = selected_llama_args(profile, model_config)
    parsed_args = _parse_plan_llama_args(llama_args)
    warnings: List[str] = []
    fit_level = _fit_level(profile, model_config)
    if fit_level == "below-minimum":
        warnings.append("Detected system RAM is below the model minimum; startup may fail or swap heavily.")
    elif fit_level == "constrained":
        warnings.append("Detected system RAM is below the recommended model memory; use conservative context and batch settings.")
    if str(profile.get("hardwareClass") or "") == "apple-silicon-unified":
        warnings.append("Apple Silicon preset uses Metal when a matching llama.cpp Metal runtime is installed; otherwise it is a preset reference.")
    if str(profile.get("hardwareClass") or "") == "igpu-shared-memory":
        warnings.append("Integrated/shared-memory GPU detected; CPU-safe settings are used unless a measured local profile proves GPU offload is stable.")
    elif str(settings.get("runtimeBackend")) == "vulkan" and float(profile.get("maxVramGb") or 0) < 4:
        warnings.append("Low dedicated VRAM detected; large models may run more reliably with CPU-heavy settings.")

    fingerprint = build_profile_fingerprint(profile, model_key, model_config, settings, model_file_path, runtime_path)
    match = match_hardware_model_profile(stored_profiles, fingerprint)
    measured_performance: Dict[str, object] = {}
    if match.get("profile"):
        stored_profile = match["profile"]
        stored_settings = stored_profile.get("settings") if isinstance(stored_profile, dict) else {}
        if isinstance(stored_settings, dict):
            for key in ("contextWindow", "runtimeBackend", "nGpuLayers", "threads", "cacheTypeK", "cacheTypeV"):
                if key in stored_settings:
                    settings[key] = stored_settings[key]
            llama_args = _as_arg_list(stored_settings.get("llamaArgs"))
            if llama_args:
                llama_args = _with_constrained_cpu_args(llama_args, profile, model_config, settings=settings)
                parsed_args = _parse_plan_llama_args(llama_args)
        measured = stored_profile.get("performance") if isinstance(stored_profile, dict) else {}
        measured_performance = dict(measured) if isinstance(measured, dict) else {}
        if match.get("level") == "compatible":
            warnings.append("Using a compatible measured profile; retest if performance or stability changed.")

    source = "measured-local" if match.get("level") in {"exact", "compatible"} else "preset-unverified"
    reason = (
        f"{profile.get('hardwareClass') or profile.get('profile')} profile, "
        f"{settings.get('runtimeBackend')} backend, "
        f"{int(settings.get('contextWindow') or 0) // 1024}k context, "
        f"{source} settings."
    )
    return {
        **settings,
        **parsed_args,
        "llamaArgs": llama_args,
        "fitLevel": fit_level,
        "warnings": warnings,
        "reason": reason,
        "source": source,
        "profileMatch": {
            "level": str(match.get("level") or "preset"),
            "source": source,
            "matchedAt": str((match.get("profile") or {}).get("measuredAt") or "") if isinstance(match.get("profile"), dict) else "",
        },
        "measuredPerformance": measured_performance,
        "fingerprint": fingerprint,
    }


def recommend_model_settings(profile: Dict[str, object], model_config: Dict[str, object]) -> Dict[str, object]:
    return build_optimization_plan(profile, "", model_config)


def choose_recommended_model_key(profile: Dict[str, object], model_configs: Dict[str, Dict[str, object]]) -> str:
    priority_by_profile = {
        "extreme": ("glm46", "qwen36a3b", "qwen36uncensored", "qwen3coder30b", "gemma4", "qwen25coder14b", "deepseekcoderlite", "gemma4e4buncensored"),
        "high": ("qwen36a3b", "qwen36uncensored", "qwen3coder30b", "glm46", "gemma4", "qwen25coder14b", "deepseekcoderlite", "gemma4e4buncensored"),
        "standard": ("qwen25coder14b", "qwen36uncensored", "deepseekcoderlite", "gemma4e4buncensored", "gemma4", "qwen35"),
        "low": ("deepseekcoderlite", "qwen25coder14b", "qwen35", "gemma4e4buncensored", "qwen36uncensored", "gemma4"),
    }
    order = priority_by_profile.get(str(profile.get("profile") or "low"), priority_by_profile["low"])
    for key in order:
        if key in model_configs:
            return key
    return next(iter(model_configs.keys()), "")


def parse_llama_server_args(raw_args: List[str]) -> List[str]:
    args: List[str] = []
    for value in raw_args:
        text = str(value).strip()
        if not text:
            continue
        if not re.match(r"^--[A-Za-z0-9][A-Za-z0-9_-]*(=.*)?$", text):
            continue
        args.append(text)
    return args
