# -*- coding: utf-8 -*-
"""系统信息监控：CPU / 内存 / 磁盘 / 网络 / 温度 / 负载 / 运行时间。"""
from __future__ import annotations

import os
import time

from . import shell


def os_info() -> dict:
    """读取 /etc/os-release 概览。"""
    info = {}
    txt = shell.read_file("/etc/os-release")
    for line in txt.splitlines():
        if "=" in line and not line.startswith("#"):
            k, _, v = line.partition("=")
            info[k.strip()] = v.strip().strip('"')
    return {
        "pretty": info.get("PRETTY_NAME", "Linux"),
        "name": info.get("NAME", ""),
        "version": info.get("VERSION", ""),
        "id": info.get("ID", ""),
    }


def _kernel() -> str:
    return shell.read_file("/proc/sys/kernel/osrelease").strip()


def _arch() -> str:
    rc, out, _ = shell.run(["uname", "-m"])
    return out.strip() if rc == 0 else "unknown"


def uptime_seconds() -> float:
    txt = shell.read_file("/proc/uptime")
    try:
        return float(txt.split()[0])
    except (ValueError, IndexError):
        return 0.0


def load_average() -> dict:
    txt = shell.read_file("/proc/loadavg")
    parts = txt.split()
    if len(parts) < 3:
        return {"1": 0.0, "5": 0.0, "15": 0.0}
    return {
        "1": float(parts[0]),
        "5": float(parts[1]),
        "15": float(parts[2]),
    }


def cpu_info() -> dict:
    """CPU 型号/核心数与实时占用率（两次采样差分）。"""
    model = ""
    cores = 0
    for line in shell.read_file("/proc/cpuinfo").splitlines():
        if line.startswith("model name") and not model:
            model = line.split(":", 1)[1].strip()
        if line.startswith("processor"):
            cores += 1
    if cores == 0:
        rc, out, _ = shell.run(["nproc"])
        try:
            cores = int(out.strip())
        except ValueError:
            cores = 1

    def _sample():
        total, idle = 0, 0
        with open("/proc/stat") as f:
            for line in f:
                if line.startswith("cpu "):
                    vals = list(map(int, line.split()[1:]))
                    total = sum(vals)
                    idle = vals[3] + vals[4]  # idle + iowait
                    break
        return total, idle

    t1, i1 = _sample()
    time.sleep(0.2)
    t2, i2 = _sample()
    usage = 0.0
    if t2 > t1:
        usage = shell.percent((t2 - t1) - (i2 - i1), t2 - t1)
    return {
        "model": model,
        "cores": cores,
        "usage": usage,
        "kernel": _kernel(),
        "arch": _arch(),
    }


def memory_info() -> dict:
    """来自 /proc/meminfo 的内存统计（字节）。"""
    def gb(key):
        txt = shell.read_file("/proc/meminfo")
        for line in txt.splitlines():
            if line.startswith(key + ":"):
                try:
                    return int(line.split()[1]) * 1024
                except (ValueError, IndexError):
                    return 0
        return 0

    total = gb("MemTotal")
    available = gb("MemAvailable")
    free = gb("MemFree")
    buffers = gb("Buffers")
    cached = gb("Cached")
    used = total - available if available else total - free - buffers - cached
    return {
        "total": total,
        "used": max(used, 0),
        "available": available,
        "free": free,
        "buffers": buffers,
        "cached": cached,
        "percent": shell.percent(total - available, total),
    }


def swap_info() -> dict:
    txt = shell.read_file("/proc/swaps")
    total = used = 0
    for line in txt.splitlines()[1:]:
        parts = line.split()
        if len(parts) >= 3:
            try:
                total += int(parts[2]) * 1024
                used += int(parts[3]) * 1024
            except ValueError:
                continue
    return {
        "total": total,
        "used": used,
        "percent": shell.percent(used, total),
    }


def disk_usage() -> list[dict]:
    """挂载的文件系统使用率。"""
    rc, out, _ = shell.run(["df", "-B1", "-x", "tmpfs", "-x", "devtmpfs",
                            "-x", "squashfs", "-x", "overlay"])
    rows = []
    if rc != 0:
        return rows
    for line in out.splitlines()[1:]:
        parts = line.split()
        if len(parts) < 6:
            continue
        try:
            size = int(parts[1])
            used = int(parts[2])
        except ValueError:
            continue
        rows.append({
            "filesystem": parts[0],
            "mountpoint": parts[5],
            "size": size,
            "used": used,
            "available": int(parts[3]) if parts[3].isdigit() else 0,
            "percent": shell.percent(used, size),
        })
    return rows


def _net_delta():
    rx = tx = 0
    try:
        with open("/proc/net/dev") as f:
            for line in f:
                if ":" in line:
                    fields = line.split(":")[1].split()
                    if len(fields) >= 9:
                        rx += int(fields[0])
                        tx += int(fields[8])
    except OSError:
        pass
    return rx, tx


def network_rate() -> dict:
    """瞬时收发速率（字节/秒）。"""
    r1, t1 = _net_delta()
    time.sleep(0.5)
    r2, t2 = _net_delta()
    return {
        "rx_rate": int((r2 - r1) / 0.5),
        "tx_rate": int((t2 - t1) / 0.5),
        "rx_total": r2,
        "tx_total": t2,
    }


def temperature() -> dict:
    """读取 thermal_zone 温度（最高值 + 列表）。"""
    zones = []
    base = "/sys/class/thermal"
    if os.path.isdir(base):
        for name in sorted(os.listdir(base)):
            if name.startswith("thermal_zone"):
                raw = shell.read_file(os.path.join(base, name, "temp")).strip()
                if raw and raw.lstrip("-").isdigit():
                    zones.append({
                        "name": name,
                        "type": shell.read_file(
                            os.path.join(base, name, "type")).strip(),
                        "celsius": int(raw) / 1000.0,
                    })
    highest = max((z["celsius"] for z in zones), default=0.0)
    return {"zones": zones, "max": highest}


def dashboard() -> dict:
    """一次性汇总仪表盘数据。"""
    return {
        "os": os_info(),
        "cpu": cpu_info(),
        "memory": memory_info(),
        "swap": swap_info(),
        "disks": disk_usage(),
        "network": network_rate(),
        "temperature": temperature(),
        "load": load_average(),
        "uptime": uptime_seconds(),
    }