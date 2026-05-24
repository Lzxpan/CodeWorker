import json
import os
import platform
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from typing import Dict, List


@dataclass(frozen=True)
class HardwareInfo:
    total_ram_gb: float
    cpu_cores: int
    cpu_threads: int
    gpus: List[Dict[str, object]] = field(default_factory=list)
    has_nvidia_smi: bool = False
    has_vulkan: bool = False


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
        "Select-Object NumberOfCores,NumberOfLogicalProcessors | ConvertTo-Json -Compress"
    )
    gpu_raw = _run_powershell(
        "Get-CimInstance Win32_VideoController | "
        "Select-Object Name,AdapterRAM,DriverVersion | ConvertTo-Json -Compress"
    )

    total_ram_gb = 0.0
    cpu_threads = os.cpu_count() or 1
    cpu_cores = max(1, cpu_threads // 2)
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
    )


def _detect_vulkan(gpus: List[Dict[str, object]]) -> bool:
    if shutil.which("vulkaninfo") is not None:
        return True
    return any(str(gpu.get("vendor", "")) in {"amd", "intel", "nvidia"} for gpu in gpus)


def detect_hardware() -> HardwareInfo:
    if platform.system().lower() == "windows":
        return _detect_windows_hardware()
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
    )


def classify_hardware(info: HardwareInfo) -> Dict[str, object]:
    max_vram = max((float(gpu.get("vramGb") or 0) for gpu in info.gpus), default=0.0)
    vendors = sorted({str(gpu.get("vendor", "unknown")) for gpu in info.gpus if gpu.get("vendor")})
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
        "hasNvidiaSmi": info.has_nvidia_smi,
        "hasVulkan": info.has_vulkan,
    }


def select_runtime_backend(profile: Dict[str, object]) -> str:
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


def recommend_model_settings(profile: Dict[str, object], model_config: Dict[str, object]) -> Dict[str, object]:
    context_options = _model_context_options(model_config)
    profile_name = str(profile.get("profile") or "low")
    max_vram_gb = float(profile.get("maxVramGb") or 0)
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


def choose_recommended_model_key(profile: Dict[str, object], model_configs: Dict[str, Dict[str, object]]) -> str:
    priority_by_profile = {
        "extreme": ("glm46", "qwen36a3b", "qwen3coder30b", "gemma4", "qwen25coder14b", "deepseekcoderlite"),
        "high": ("qwen36a3b", "qwen3coder30b", "glm46", "gemma4", "qwen25coder14b", "deepseekcoderlite"),
        "standard": ("qwen25coder14b", "deepseekcoderlite", "gemma4", "qwen35"),
        "low": ("deepseekcoderlite", "qwen25coder14b", "qwen35", "gemma4"),
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
