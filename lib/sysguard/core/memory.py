# -*- coding: utf-8 -*-
"""内存压缩与 swap 管理：zram/zswap 检测、vm.swappiness 读写。"""
from __future__ import annotations

import os

from . import shell
from . import sysinfo


def swappiness_get() -> int:
    txt = shell.read_file("/proc/sys/vm/swappiness").strip()
    try:
        return int(txt)
    except ValueError:
        return 60


def swappiness_set(value: int):
    import json
    rc, out, err = shell.pkexec("swappiness", [str(value)], timeout=30)
    msg = (out or "").strip()
    if not msg.lstrip().startswith("{"):
        return False, (err or out or f"退出码 {rc}").strip()
    try:
        obj = json.loads(msg)
    except json.JSONDecodeError:
        return False, (err or out).strip()
    if obj.get("ok"):
        return True, f"swappiness 已设为 {value}"
    return False, obj.get("error", "未知错误")


def zram_status() -> dict:
    """检测 zram 设备与压缩统计。"""
    devices = []
    base = "/sys/block"
    if os.path.isdir(base):
        for name in os.listdir(base):
            if not name.startswith("zram"):
                continue
            d = base + "/" + name
            devices.append({
                "name": name,
                "size": _read_int(d + "/size") or
                        _read_int(d + "/disksize"),
                "compr_data": _read_int(d + "/compr_data_size"),
                "orig_data": _read_int(d + "/orig_data_size"),
            })
    enabled = bool(devices)
    return {"enabled": enabled, "devices": devices}


def zswap_status() -> dict:
    """检测 zswap（内核参数 enable/compressor/pool）。"""
    p = "/sys/module/zswap/parameters"
    if not os.path.isdir(p):
        return {"enabled": False}
    enabled = _read_str(p + "/enabled") in ("Y", "1", "y")
    return {
        "enabled": enabled,
        "compressor": _read_str(p + "/compressor"),
        "zpool": _read_str(p + "/zpool"),
        "max_pool_percent": _read_str(p + "/max_pool_percent"),
    }


def _read_int(path):
    try:
        with open(path) as f:
            return int(f.read().strip())
    except (OSError, ValueError):
        return None


def _read_str(path):
    try:
        with open(path) as f:
            return f.read().strip()
    except OSError:
        return ""


def summary():
    """内存/交换概览（供页面展示）。"""
    return {
        "memory": sysinfo.memory_info(),
        "swap": sysinfo.swap_info(),
        "swappiness": swappiness_get(),
        "zram": zram_status(),
        "zswap": zswap_status(),
    }