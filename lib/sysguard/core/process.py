# -*- coding: utf-8 -*-
"""进程与服务管理：进程查看/搜索/终止；systemd 服务启停。"""
from __future__ import annotations

from . import shell


def list_processes(sort="mem") -> list[dict]:
    """列出进程。sort：cpu / mem。"""
    if sort == "cpu":
        order = "-pcpu"
    else:
        order = "-pmem"
    rc, out, _ = shell.run(
        ["ps", "-eo", "pid,ppid,user,rss,pcpu,pmem,etimes,comm,args",
         "--sort", order], timeout=30)
    rows = []
    if rc != 0:
        return rows
    lines = out.splitlines()[1:]
    for line in lines:
        parts = line.split(None, 8)
        if len(parts) < 8:
            continue
        try:
            pid = int(parts[0])
            ppid = int(parts[1])
        except ValueError:
            continue
        rows.append({
            "pid": pid,
            "ppid": ppid,
            "user": parts[2],
            "rss": int(parts[3]) * 1024,
            "cpu": float(parts[4]),
            "mem": float(parts[5]),
            "etime": parts[6],
            "comm": parts[7],
            "args": parts[8] if len(parts) >= 9 else parts[7],
        })
    return rows


def search(text: str) -> list[dict]:
    text = (text or "").strip().lower()
    if not text:
        return list_processes()
    result = []
    for p in list_processes():
        hay = f"{p['pid']} {p['user']} {p['comm']} {p['args']}".lower()
        if text in hay:
            result.append(p)
    return result


def kill(pid: int, signal: str = "TERM"):
    """经由特权入口终止进程。返回 (ok, msg)。"""
    rc, out, err = shell.pkexec("proc_kill", [str(pid), signal])
    if rc != 0:
        return False, (err or out).strip()
    return True, f"已向 PID {pid} 发送 {signal}"


def list_services() -> list[dict]:
    """systemd 单元列表（含状态与启停方式）。"""
    rc, out, _ = shell.run(
        ["systemctl", "list-units", "--type=service", "--all", "--no-pager",
         "--no-legend"], timeout=60)
    rows = []
    if rc != 0:
        return rows
    for line in out.splitlines():
        parts = line.split(None, 4)
        if len(parts) < 5:
            continue
        name = parts[0]
        if not name.endswith(".service"):
            continue
        rows.append({
            "unit": name,
            "load": parts[1],
            "active": parts[2],
            "sub": parts[3],
            "desc": parts[4],
        })
    rows.sort(key=lambda s: s["unit"])
    return rows


def service_action(unit: str, action: str):
    """经由特权入口启停服务。返回 (ok, msg)。"""
    rc, out, err = shell.pkexec("service_ctl", [action, unit])
    if rc != 0:
        return False, (err or out).strip()
    return True, (out or "操作成功").strip()