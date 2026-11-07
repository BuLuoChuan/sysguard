# -*- coding: utf-8 -*-
"""系统优化：开机自启项审计、内核清理、电源/交换建议。"""
from __future__ import annotations

import re

from . import shell
from . import cleanup
from . import memory
from . import sysinfo


def enabled_services() -> list[dict]:
    """systemd 已启用（开机自启）单元。"""
    rc, out, _ = shell.run(
        ["systemctl", "list-unit-files", "--state=enabled", "--no-pager",
         "--no-legend"], timeout=30)
    rows = []
    if rc != 0:
        return rows
    for line in out.splitlines():
        parts = line.split()
        if len(parts) < 2:
            continue
        rows.append({"unit": parts[0], "state": parts[1]})
    rows.sort(key=lambda r: r["unit"])
    return rows


def disable_service(unit):
    return shell.pkexec("service_ctl", ["disable", unit], timeout=60)


def installed_kernels():
    """已安装内核镜像（含是否正在运行）。"""
    running = shell.read_file("/proc/sys/kernel/osrelease").strip()
    rc, out, _ = shell.run(
        ["dpkg-query", "-W", "-f=${Package}\t${Status}\n",
         "linux-image-*"], timeout=30)
    rows = []
    if rc != 0:
        return rows
    for line in out.splitlines():
        if "\t" not in line:
            continue
        pkg, status = line.split("\t", 1)
        ver = pkg.replace("linux-image-", "")
        if not re.match(r"^\d", ver):
            continue
        rows.append({
            "package": pkg,
            "version": ver,
            "running": ver == running,
            "installed": "installed" in status,
        })
    rows.sort(key=lambda r: r["version"], reverse=True)
    return rows


def remove_kernel(version):
    return cleanup.remove_kernel(version)


def power_hints() -> list[str]:
    """电源与交换优化建议（只读建议）。"""
    hints = []
    swap = sysinfo.swap_info()
    if swap["total"] > 0 and swap["percent"] > 80:
        hints.append("交换分区占用较高，建议增加物理内存或降低 vm.swappiness。")
    mem = sysinfo.memory_info()
    if mem["percent"] > 90:
        hints.append("内存占用超过 90%，建议关闭占用较高的进程或查看内存压缩。")
    sw = memory.swappiness_get()
    if sw > 60:
        hints.append(f"vm.swappiness={sw} 偏高，桌面场景建议设为 10~30。")
    zs = memory.zswap_status()
    zr = memory.zram_status()
    if not zs["enabled"] and not zr["enabled"]:
        hints.append("未启用 zram/zswap，内存紧张时可启用压缩缓解。")
    return hints


def summary():
    return {
        "enabled_services": enabled_services(),
        "kernels": installed_kernels(),
        "hints": power_hints(),
        "swappiness": memory.swappiness_get(),
        "zram": memory.zram_status(),
        "zswap": memory.zswap_status(),
    }