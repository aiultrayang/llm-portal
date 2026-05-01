"""GPU monitoring API endpoints."""

import subprocess
import re
from typing import List, Dict, Any
from fastapi import APIRouter

router = APIRouter(prefix="/api/system", tags=["system"])


def parse_nvidia_smi() -> List[Dict[str, Any]]:
    """Parse nvidia-smi output to get GPU information."""
    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu",
                "index,name,utilization.gpu,utilization.memory,memory.used,memory.total,temperature.gpu",
                "--format",
                "csv,noheader,nounits"
            ],
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode != 0:
            return []

        gpus = []
        for line in result.stdout.strip().split('\n'):
            if not line.strip():
                continue

            parts = [p.strip() for p in line.split(',')]
            if len(parts) >= 7:
                gpu_index = int(parts[0])
                name = parts[1]
                gpu_util = float(parts[2]) if parts[2] != 'N/A' else 0
                mem_bandwidth_util = float(parts[3]) if parts[3] != 'N/A' else 0  # 显存带宽利用率
                mem_used_mib = float(parts[4]) if parts[4] != 'N/A' else 0
                mem_total_mib = float(parts[5]) if parts[5] != 'N/A' else 1
                temp = float(parts[6]) if parts[6] != 'N/A' else 0

                # 计算显存占用百分比（实际显存占用）
                mem_util_percent = (mem_used_mib / mem_total_mib * 100) if mem_total_mib > 0 else 0

                gpus.append({
                    "index": gpu_index,
                    "name": name,
                    "utilization": round(gpu_util, 1),  # GPU计算利用率
                    "memoryUtilization": round(mem_util_percent, 1),  # 显存占用百分比
                    "memoryBandwidthUtil": round(mem_bandwidth_util, 1),  # 显存带宽利用率
                    "memoryUsed": round(mem_used_mib / 1024, 2),  # GB
                    "memoryTotal": round(mem_total_mib / 1024, 2),  # GB
                    "temperature": round(temp, 1)
                })

        return gpus
    except Exception as e:
        print(f"Error parsing nvidia-smi: {e}")
        return []


@router.get("/gpu")
async def get_gpu_status() -> Dict[str, Any]:
    """Get GPU status for all GPUs."""
    gpus = parse_nvidia_smi()

    # Calculate totals
    total_memory_used = sum(g.get("memoryUsed", 0) for g in gpus)
    total_memory_total = sum(g.get("memoryTotal", 0) for g in gpus)
    avg_utilization = sum(g.get("utilization", 0) for g in gpus) / len(gpus) if gpus else 0
    max_temperature = max((g.get("temperature", 0) for g in gpus), default=0)

    return {
        "gpus": gpus,
        "summary": {
            "gpuCount": len(gpus),
            "totalMemoryUsed": round(total_memory_used, 2),
            "totalMemoryTotal": round(total_memory_total, 2),
            "avgUtilization": round(avg_utilization, 1),
            "maxTemperature": round(max_temperature, 1)
        }
    }


@router.get("/gpu/{gpu_index}")
async def get_single_gpu_status(gpu_index: int) -> Dict[str, Any]:
    """Get GPU status for a specific GPU."""
    gpus = parse_nvidia_smi()

    for gpu in gpus:
        if gpu.get("index") == gpu_index:
            return gpu

    return {"error": f"GPU {gpu_index} not found"}


@router.get("/memory")
async def get_memory_status() -> Dict[str, Any]:
    """Get system memory status."""
    try:
        with open('/proc/meminfo', 'r') as f:
            meminfo = f.read()

        def get_mem_value(key: str) -> int:
            match = re.search(rf'{key}:\s+(\d+)', meminfo)
            return int(match.group(1)) if match else 0

        total = get_mem_value('MemTotal') / (1024 * 1024)  # Convert to GB
        free = get_mem_value('MemFree') / (1024 * 1024)
        available = get_mem_value('MemAvailable') / (1024 * 1024)
        used = total - available

        return {
            "total": round(total, 2),
            "used": round(used, 2),
            "free": round(free, 2),
            "available": round(available, 2),
            "utilization": round(used / total * 100, 1) if total > 0 else 0
        }
    except Exception as e:
        return {
            "total": 0,
            "used": 0,
            "free": 0,
            "available": 0,
            "utilization": 0,
            "error": str(e)
        }
