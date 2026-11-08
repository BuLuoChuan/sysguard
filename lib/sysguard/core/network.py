# -*- coding: utf-8 -*-
"""网络优化与测试：接口信息 / 连通性 / 实时速率 / BBR / DNS。"""
from __future__ import annotations

import re
import time
import urllib.request

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


def routes() -> list[str]:
    """路由表（ip route）。"""
    rc, out, _ = shell.run(["ip", "route"], timeout=20)
    return [l for l in out.splitlines() if l.strip()] if rc == 0 else []


def wifi_interfaces() -> list[str]:
    """无线接口（wlan*/wl*）。"""
    rc, out, _ = shell.run(["ip", "-o", "link", "show"], timeout=15)
    ifaces = []
    if rc != 0:
        return ifaces
    for line in out.splitlines():
        m = re.match(r"\d+:\s+(\S+):", line)
        if m and m.group(1).startswith("wl"):
            ifaces.append(m.group(1))
    return ifaces


def wifi_powersave(iface):
    """返回 'on' / 'off' / 'unknown'。"""
    if not shell.which("iw"):
        return "unknown"
    rc, out, _ = shell.run(["iw", "dev", iface, "get", "power_save"], timeout=20)
    if rc != 0:
        return "unknown"
    low = out.lower()
    if "on" in low:
        return "on"
    if "off" in low:
        return "off"
    return "unknown"


def wifi_powersave_set(iface, on):
    rc, out, err = shell.pkexec(
        "wifi_powersave", [iface, "on" if on else "off"], timeout=60)
    return _parse(rc, out, err)


# ---------------------------------------------------------------------------
# 最大带宽测速（出口带宽峰值，非实时速率）
# ---------------------------------------------------------------------------

_SPEED_URL_DOWN = "https://speed.cloudflare.com/__down?bytes=200000000"
_SPEED_URL_UP = "https://speed.cloudflare.com/__up"
_SPEED_UA = {"User-Agent": "SysGuard/1.2"}


def max_bandwidth(duration: float = 5.0, timeout: int = 15) -> dict:
    """测本机可达到的最大下行/上行带宽（出口带宽峰值）。

    与 `realtime_rate()` 的实时采样不同：本函数通过向 Cloudflare 高速
    测速节点持续传输来逼近出口带宽上限。返回 {"down_bps": ..., "up_bps": ...}，
    单位为 bit/s；单项失败时为 None。
    """
    return {"down_bps": _max_down(duration, timeout),
            "up_bps": _max_up(duration, timeout)}


def _max_down(duration: float, timeout: int):
    try:
        req = urllib.request.Request(_SPEED_URL_DOWN, headers=_SPEED_UA)
        t0 = time.monotonic()
        total = 0
        with urllib.request.urlopen(req, timeout=timeout) as r:
            while time.monotonic() - t0 < duration:
                chunk = r.read(65536)
                if not chunk:
                    break
                total += len(chunk)
        dt = time.monotonic() - t0
        if dt <= 0 or total <= 0:
            return None
        return total * 8 / dt
    except Exception:
        return None


def _max_up(duration: float, timeout: int):
    chunk_size = 1024 * 1024  # 每次 POST 1MB
    payload = b"x" * chunk_size
    t0 = time.monotonic()
    sent = 0
    try:
        while time.monotonic() - t0 < duration:
            req = urllib.request.Request(
                _SPEED_URL_UP, data=payload, method="POST",
                headers={"User-Agent": "SysGuard/1.2",
                         "Content-Type": "application/octet-stream"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                r.read()
            sent += chunk_size
        dt = time.monotonic() - t0
        return sent * 8 / dt if dt > 0 and sent else None
    except Exception:
        return None