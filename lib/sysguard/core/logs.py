# -*- coding: utf-8 -*-
"""错误日志聚合与一键诊断报告。"""
from __future__ import annotations

import datetime

from . import shell


def journal_errors(limit: int = 100) -> list[str]:
    """journal 优先级 err 及以上的最近日志。"""
    rc, out, _ = shell.run(
        ["journalctl", "-p", "err", "-n", str(limit), "--no-pager"], timeout=60)
    if rc != 0:
        return []
    return [l for l in out.splitlines() if l.strip()]


def dmesg_errors() -> list[str]:
    """内核错误日志（dmesg -l err）。"""
    rc, out, _ = shell.run(["dmesg", "-l", "err"], timeout=30)
    if rc != 0:
        return []
    return [l for l in out.splitlines() if l.strip()]


def reboot_required() -> bool:
    """是否存在需要重启的待生效更新。"""
    rc, out, _ = shell.run(
        ["test", "-f", "/var/run/reboot-required"], timeout=10)
    return rc == 0


def _run_cmd(*argv):
    rc, out, _ = shell.run(list(argv), timeout=30)
    return out.strip() if rc == 0 else "（无法获取）"


def diagnostics() -> str:
    """聚合系统信息生成可分享的诊断报告。"""
    L = []

    def section(title):
        L.append("\n" + "=" * 52)
        L.append(title)
        L.append("=" * 52)

    section("系统信息")
    L.append(_run_cmd("uname", "-a"))
    L.append(shell.read_file("/etc/os-release").strip())

    section("CPU")
    rc, out, _ = shell.run(["lscpu"], timeout=30)
    for line in out.splitlines():
        if line.startswith(("Model name", "Architecture", "CPU(s)", "Thread")):
            L.append(line.strip())

    section("内存")
    L.append(_run_cmd("free", "-h"))

    section("磁盘")
    L.append(_run_cmd("df", "-h"))

    section("网络接口")
    L.append(_run_cmd("ip", "-br", "addr"))

    section("系统日志错误（最近 20 条）")
    errs = journal_errors(20)
    L.extend(errs if errs else ["（无，或当前用户无权读取系统日志）"])

    section("内核错误（最近 20 条）")
    derrs = dmesg_errors()[:20]
    L.extend(derrs if derrs else ["（无，或需 root 读取）"])

    section("待重启更新")
    L.append("是（存在 /var/run/reboot-required）" if reboot_required() else "否")

    section(f"生成时间 {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    return "\n".join(L)