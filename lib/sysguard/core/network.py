# -*- coding: utf-8 -*-
"""网络优化与测试：接口信息 / 连通性 / 实时速率 / BBR / DNS。"""
from __future__ import annotations

import re
import time

from . import shell


def interfaces() -> list[dict]:
    """接口列表（名称/状态/IP/MAC）。"""
    rc, out, _ = shell.run(["ip", "-o", "addr", "show"], timeout=15)
    rows = []
    if rc != 0:
        return rows
    cur = {}
    for line in out.splitlines():
        m = re.match(r"\d+:\s+(\S+)\s+inet(6)?\s+([\d.af:]+)/(\d+)", line)
        if m:
            iface = m.group(1)
            fam = "inet6" if m.group(2) else "inet"
            addr = m.group(3)
            if iface not in cur:
                cur[iface] = {"name": iface, "inet": "", "inet6": ""}
            cur[iface][fam] = addr
    # 补充链路状态
    rc, out2, _ = shell.run(["ip", "-o", "link", "show"], timeout=15)
    state = {}
    mac = {}
    if rc == 0:
        for line in out2.splitlines():
            m = re.match(r"\d+:\s+(\S+):\s+<[^>]*>.*state\s+(\S+)", line)
            if m:
                state[m.group(1)] = m.group(2)
            mm = re.search(r"link/\w+\s+([0-9a-f:]{17})", line)
            if mm:
                mac[m.group(1) if m else ""] = mm.group(1)
    for name in cur:
        cur[name]["state"] = state.get(name, "unknown")
        cur[name]["mac"] = mac.get(name, "")
    return sorted(cur.values(), key=lambda i: i["name"])


def ping(host: str, count: int = 4, timeout: int = 10):
    """连通性/延迟测试。返回 (ok, 结果dict)。"""
    if not re.match(r"^[\w.\-]+$", host):
        return False, {"error": "主机名非法"}
    rc, out, err = shell.run(
        ["ping", "-c", str(count), "-W", "2", host], timeout=timeout + 5)
    if rc != 0:
        return False, {"error": (err or out).strip() or "ping 失败"}
    # 提取 min/avg/max/mdev
    m = re.search(r"(\d+\.\d+)/(\d+\.\d+)/(\d+\.\d+)/(\d+\.\d+)\s+ms", out)
    rtt = None
    if m:
        rtt = {"min": float(m.group(1)), "avg": float(m.group(2)),
               "max": float(m.group(3)), "mdev": float(m.group(4))}
    loss = re.search(r"(\d+)% packet loss", out)
    return True, {"host": host, "rtt": rtt,
                  "loss": int(loss.group(1)) if loss else None,
                  "raw": out.strip()}


def realtime_rate(seconds: float = 1.0):
    """采样 /proc/net/dev 计算实时速率。"""
    def counters():
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

    r1, t1 = counters()
    time.sleep(seconds)
    r2, t2 = counters()
    return {
        "rx_rate": int((r2 - r1) / seconds),
        "tx_rate": int((t2 - t1) / seconds),
    }


def dns_servers() -> list[str]:
    txt = shell.read_file("/etc/resolv.conf")
    servers = []
    for line in txt.splitlines():
        if line.startswith("nameserver"):
            servers.append(line.split()[1])
    return servers


def bbr_status() -> dict:
    """当前 TCP 拥塞控制与 qdisc。"""
    cca = shell.read_file("/proc/sys/net/ipv4/tcp_congestion_control").strip()
    qdisc = shell.read_file("/proc/sys/net/core/default_qdisc").strip()
    return {
        "congestion_control": cca,
        "default_qdisc": qdisc,
        "bbr": "bbr" in cca,
    }


def bbr_set(on: bool):
    rc, out, err = shell.pkexec("bbr", ["on" if on else "off"], timeout=30)
    return _parse(rc, out, err)


def _parse(rc, out, err):
    import json
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