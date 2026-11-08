# -*- coding: utf-8 -*-
"""电源与电池健康、能效模式切换。"""
from __future__ import annotations

import re

from . import shell

PROFILES = ("performance", "balanced", "power-saver")
PROFILE_LABELS = {"performance": "高性能", "balanced": "平衡", "power-saver": "省电"}


def has_daemon() -> bool:
    return shell.which("powerprofilesctl")


def current_profile() -> str:
    rc, out, _ = shell.run(["powerprofilesctl", "get"], timeout=20)
    return out.strip() if rc == 0 else ""


def profiles_status() -> list[dict]:
    cur = current_profile()
    return [{"profile": p, "label": PROFILE_LABELS[p], "current": p == cur}
            for p in PROFILES]


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
        return True, "已切换"
    return False, obj.get("error", "未知错误")


def set_profile(profile):
    rc, out, err = shell.pkexec("power_profile", [profile], timeout=60)
    return _parse(rc, out, err)


def ac_state() -> str:
    txt = shell.read_file("/sys/class/power_supply/AC/online").strip()
    if txt == "1":
        return "已接电源"
    if txt == "0":
        return "电池供电"
    return ""


def _wh(text):
    m = re.search(r"([\d.]+)\s*Wh", text or "")
    return float(m.group(1)) if m else None


def battery_info() -> dict:
    """电池健康摘要（upower）。"""
    result = {"present": False, "percentage": None, "state": "",
              "health": None, "model": "", "energy_full": "",
              "energy_design": ""}
    rc, out, _ = shell.run(["upower", "-e"], timeout=20)
    if rc != 0:
        return result
    batt = ""
    for line in out.splitlines():
        if "battery" in line.lower():
            batt = line.strip()
            break
    if not batt:
        return result
    rc, out, _ = shell.run(["upower", "-i", batt], timeout=20)
    if rc != 0:
        return result
    result["present"] = True
    for line in out.splitlines():
        line = line.strip()
        if line.startswith("percentage:"):
            try:
                result["percentage"] = int(line.split()[-1].rstrip("%"))
            except ValueError:
                pass
        elif line.startswith("state:"):
            result["state"] = line.split(":", 1)[1].strip()
        elif line.startswith("model:"):
            result["model"] = line.split(":", 1)[1].strip()
        elif line.startswith("energy-full:"):
            result["energy_full"] = line.split(":", 1)[1].strip()
        elif line.startswith("energy-full-design:"):
            result["energy_design"] = line.split(":", 1)[1].strip()
    full = _wh(result["energy_full"])
    design = _wh(result["energy_design"])
    if full and design:
        result["health"] = round(full * 100.0 / design, 1)
    return result