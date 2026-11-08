# -*- coding: utf-8 -*-
"""启动性能分析（systemd-analyze）。"""
from __future__ import annotations

from . import shell


def boot_time() -> str:
    """总启动时间（kernel + userspace）。"""
    rc, out, _ = shell.run(["systemd-analyze", "time"], timeout=60)
    return out.strip() if rc == 0 else ""


def blame(top_n: int = 15) -> list[dict]:
    """启动耗时 Top 服务单元。"""
    rc, out, _ = shell.run(["systemd-analyze", "blame"], timeout=120)
    rows = []
    if rc != 0:
        return rows
    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split(None, 1)
        if len(parts) != 2:
            continue
        rows.append({"time": parts[0], "unit": parts[1]})
        if len(rows) >= top_n:
            break
    return rows


def critical_chain() -> str:
    """关键启动链路（哪个环节最拖时间）。"""
    rc, out, _ = shell.run(["systemd-analyze", "critical-chain"], timeout=120)
    return out.strip() if rc == 0 else ""