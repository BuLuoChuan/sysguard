# -*- coding: utf-8 -*-
"""系统优化：开机自启项审计、内核清理、电源/交换建议。"""
from __future__ import annotations

import re

from . import shell
from . import cleanup
from . import memory
from . import sysinfo


def delayed_services() -> list[str]:
    """由系统管家设置的开机延时启动单元（sysguard-delay-*.timer）。"""
    rc, out, _ = shell.run(
        ["systemctl", "list-unit-files", "--state=enabled", "--no-pager",
         "--no-legend", "sysguard-delay-*.timer"], timeout=20)
    names = []
    if rc != 0:
        return names
    for line in out.splitlines():
        parts = line.split()
        if parts:
            names.append(parts[0])
    return names


def _unit_description(unit):
    rc, out, _ = shell.run(
        ["systemctl", "show", "--property=Description", unit], timeout=15)
    if rc != 0:
        return ""
    for line in out.splitlines():
        if line.startswith("Description="):
            return line.split("=", 1)[1].strip()
    return ""


def enabled_services() -> list[dict]:
    """systemd 已启用（开机自启）单元，含说明与延时标记。"""
    rc, out, _ = shell.run(
        ["systemctl", "list-unit-files", "--state=enabled", "--no-pager",
         "--no-legend"], timeout=30)
    rows = []
    if rc != 0:
        return rows
    delayed = {n for n in delayed_services()}
    for line in out.splitlines():
        parts = line.split()
        if len(parts) < 2:
            continue
        unit = parts[0]
        base = unit.replace(".service", "")
        rows.append({
            "unit": unit,
            "state": parts[1],
            "description": _unit_description(unit),
            "delayed": f"sysguard-delay-{base}.timer" in delayed,
        })
    rows.sort(key=lambda r: r["unit"])
    return rows


def _pk(rc, out, err):
    import json
    msg = (out or "").strip()
    if not msg.lstrip().startswith("{"):
        return False, (err or out or f"退出码 {rc}").strip()
    try:
        obj = json.loads(msg)
    except json.JSONDecodeError:
        return False, (err or out).strip()
    if obj.get("ok"):
        return True, "操作成功"
    return False, obj.get("error", "未知错误")


def enable_service(unit):
    rc, out, err = shell.pkexec("service_ctl", ["enable", unit], timeout=60)
    return _pk(rc, out, err)


def disable_service(unit):
    rc, out, err = shell.pkexec("service_ctl", ["disable", unit], timeout=60)
    return _pk(rc, out, err)


def delay_start(unit, seconds):
    """设置开机延时 seconds 秒后启动该服务（0 表示取消延时恢复自启）。"""
    rc, out, err = shell.pkexec("service_delay", [unit, str(seconds)], timeout=120)
    return _pk(rc, out, err)


def cancel_delay(unit):
    return delay_start(unit, 0)


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


def power_hints(lang="zh") -> list[str]:
    """电源与交换优化建议（只读建议，支持 zh / en）。"""
    hints = []
    swap = sysinfo.swap_info()
    mem = sysinfo.memory_info()
    sw = memory.swappiness_get()
    zs = memory.zswap_status()
    zr = memory.zram_status()

    if lang == "en":
        if swap["total"] > 0 and swap["percent"] > 80:
            hints.append("Swap usage is high; add RAM or lower vm.swappiness.")
        if mem["percent"] > 90:
            hints.append("Memory usage exceeds 90%; close heavy processes or "
                         "check memory compression.")
        if sw > 60:
            hints.append(f"vm.swappiness={sw} is high; 10~30 is recommended "
                         "for desktop use.")
        if not zs["enabled"] and not zr["enabled"]:
            hints.append("zram/zswap is not enabled; enable compression to "
                         "relieve memory pressure.")
        return hints

    if swap["total"] > 0 and swap["percent"] > 80:
        hints.append("交换分区占用较高，建议增加物理内存或降低 vm.swappiness。")
    if mem["percent"] > 90:
        hints.append("内存占用超过 90%，建议关闭占用较高的进程或查看内存压缩。")
    if sw > 60:
        hints.append(f"vm.swappiness={sw} 偏高，桌面场景建议设为 10~30。")
    if not zs["enabled"] and not zr["enabled"]:
        hints.append("未启用 zram/zswap，内存紧张时可启用压缩缓解。")
    return hints


def summary(lang="zh"):
    return {
        "enabled_services": enabled_services(),
        "kernels": installed_kernels(),
        "hints": power_hints(lang=lang),
        "swappiness": memory.swappiness_get(),
        "zram": memory.zram_status(),
        "zswap": memory.zswap_status(),
    }