# -*- coding: utf-8 -*-
"""安全（火绒式，不做防病毒）：ufw / 端口审计 / 可疑进程 / 文件粉碎 / 自启审计。"""
from __future__ import annotations

import json
import re

from . import shell
from . import process as _process
from . import optimize as _optimize


def ufw_status():
    """ufw 是否启用（解析 ufw status 输出）。"""
    rc, out, err = shell.run(["ufw", "status", "verbose"], timeout=30)
    if rc != 0:
        return {"installed": False, "active": False, "raw": (err or out).strip()}
    active = bool(re.search(r"^Status:\s*active", out, re.MULTILINE))
    return {"installed": True, "active": active, "raw": out.strip()}


def listening_ports():
    """监听中的 TCP/UDP 端口与对应进程。"""
    rc, out, _ = shell.run(
        ["ss", "-tulpn"], timeout=30)
    rows = []
    if rc != 0:
        return rows
    for line in out.splitlines()[1:]:
        m = re.match(r"(\S+)\s+\S+\s+\S+\s+(\S+)\s+\S+\s+users:\(\((.+)\)\)", line)
        if not m:
            continue
        proto = m.group(1).upper()
        local = m.group(2)
        proc = m.group(3).strip()
        # 提取本地地址:端口
        if ":" not in local:
            continue
        addr, port = local.rsplit(":", 1)
        rows.append({
            "proto": proto,
            "address": addr,
            "port": port,
            "process": proc,
        })
    return rows


def suspicious_processes():
    """高 CPU 或高内存进程（阈值：CPU>50% 或 内存>30%）。"""
    result = []
    for p in _process.list_processes(sort="cpu"):
        if p["cpu"] > 50 or p["mem"] > 30:
            result.append(p)
        if len(result) >= 20:
            break
    return result


def autostart_services():
    return _optimize.enabled_services()


def _ufw(action, argc):
    rc, out, err = shell.pkexec(action, argc, timeout=60)
    return _parse(rc, out, err)


def ufw_enable():
    return _ufw("ufw_enable", [])


def ufw_disable():
    return _ufw("ufw_disable", [])


def ufw_allow(spec):
    return _ufw("ufw_allow", [spec])


def ufw_deny(spec):
    return _ufw("ufw_deny", [spec])


def ufw_reset():
    return _ufw("ufw_reset", [])


def shred(path):
    rc, out, err = shell.pkexec("shred", [path], timeout=600)
    return _parse(rc, out, err)


def _parse(rc, out, err):
    msg = (out or "").strip()
    if not msg.lstrip().startswith("{"):
        return False, (err or out or f"退出码 {rc}").strip()
    try:
        obj = json.loads(msg)
    except json.JSONDecodeError:
        return False, (err or out).strip()
    if obj.get("ok"):
        return True, obj.get("data")
    return False, obj.get("error", "未知错误")