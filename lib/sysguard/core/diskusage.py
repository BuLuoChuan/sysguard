# -*- coding: utf-8 -*-
"""磁盘空间深度分析：挂载点、大目录、大文件、inode。"""
from __future__ import annotations

from . import shell


def list_mounts() -> list[dict]:
    """真实文件系统挂载点（排除虚拟/内存文件系统）。"""
    rc, out, _ = shell.run(
        ["df", "-h", "-x", "tmpfs", "-x", "devtmpfs",
         "-x", "squashfs", "-x", "overlay"], timeout=30)
    rows = []
    if rc != 0:
        return rows
    for line in out.splitlines()[1:]:
        parts = line.split()
        if len(parts) < 6:
            continue
        rows.append({"fs": parts[0], "size": parts[1], "used": parts[2],
                     "avail": parts[3], "pct": parts[4], "mount": parts[5]})
    return rows


def top_dirs(path: str, limit: int = 15) -> list[dict]:
    """指定目录下占用最大的子目录（du，跳过其它文件系统）。"""
    if not path.startswith("/"):
        return []
    rc, out, _ = shell.run(
        ["du", "-x", "-h", "--max-depth=1", path], timeout=180)
    if rc != 0:
        return []
    rows = []
    for line in out.splitlines():
        parts = line.split(None, 1)
        if len(parts) != 2:
            continue
        rows.append({"size": parts[0], "path": parts[1]})
        if len(rows) >= limit:
            break
    return rows


def top_files(path: str, min_mb: int = 100, limit: int = 20) -> list[dict]:
    """指定目录下的大文件（find，跳过其它文件系统，按大小降序）。"""
    if not path.startswith("/"):
        return []
    rc, out, _ = shell.run(
        ["find", path, "-xdev", "-type", "f", "-size", f"+{min_mb}M",
         "-printf", "%s\\t%p\\n"], timeout=240)
    if rc != 0:
        return []
    rows = []
    for line in out.splitlines():
        if "\t" not in line:
            continue
        size_s, p = line.split("\t", 1)
        try:
            size = int(size_s)
        except ValueError:
            continue
        rows.append({"size": size, "path": p})
    rows.sort(key=lambda r: r["size"], reverse=True)
    return rows[:limit]


def inode_usage() -> list[dict]:
    """inode 使用率（小文件过多也会耗尽 inode）。"""
    rc, out, _ = shell.run(["df", "-i", "-h"], timeout=30)
    rows = []
    if rc != 0:
        return rows
    for line in out.splitlines()[1:]:
        parts = line.split()
        if len(parts) < 6:
            continue
        rows.append({"fs": parts[0], "inodes": parts[1], "iused": parts[2],
                     "ifree": parts[3], "ipct": parts[4], "mount": parts[5]})
    return rows