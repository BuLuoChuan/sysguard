# -*- coding: utf-8 -*-
"""安全执行外壳：所有系统命令统一经此出口。

- `run()`：读型/低危命令，普通用户身份执行，带超时；
- `pkexec()`：需 root 的写操作，转交特权入口 `sysguard-cli`；
- 禁止在此层拼接任意 shell 字符串直接给 root，root 操作一律走白名单入口。
"""
from __future__ import annotations

import subprocess

from ..config import PRIVILEGED_BIN


class CommandError(RuntimeError):
    """命令执行失败（非零退出码）。"""

    def __init__(self, rc, out, err):
        super().__init__(f"exit={rc}: {(err or out).strip()[:300]}")
        self.rc = rc
        self.out = out
        self.err = err


def run(argv, timeout=20, text=True):
    """执行命令，返回 (rc, stdout, stderr)。超时抛 TimeoutExpired。"""
    proc = subprocess.run(
        list(argv),
        capture_output=True,
        text=text,
        timeout=timeout,
    )
    return proc.returncode, proc.stdout, proc.stderr


def read_file(path: str) -> str:
    """读取文本文件；失败返回空串。"""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()
    except OSError:
        return ""


def which(tool: str) -> bool:
    """工具是否可用。"""
    return subprocess.run(["which", tool], capture_output=True).returncode == 0


def pkexec(subcommand: str, args: list[str], timeout=60):
    """以 root 身份执行白名单子命令。

    经 pkexec 触发图形授权框；参数只允许列表形式，避免 shell 注入。
    返回 (rc, stdout, stderr)。
    """
    argv = ["pkexec", PRIVILEGED_BIN, subcommand, *args]
    proc = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
    return proc.returncode, proc.stdout, proc.stderr


def human_bytes(n: float) -> str:
    """字节转可读单位。"""
    n = float(n)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB", "PiB"):
        if abs(n) < 1024.0:
            return f"{n:.1f} {unit}" if unit != "B" else f"{int(n)} B"
        n /= 1024.0
    return f"{n:.1f} EiB"


def percent(part: float, whole: float) -> float:
    """安全百分比。"""
    if not whole:
        return 0.0
    return round(part * 100.0 / whole, 1)