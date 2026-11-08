# -*- coding: utf-8 -*-
"""软件包修复与依赖自愈（适配 Debian/Ubuntu 的 dpkg/apt）。"""
from __future__ import annotations

import json

from . import shell


def _parse(rc, out, err):
    msg = (out or "").strip()
    if not msg.lstrip().startswith("{"):
        return False, None, (err or out or f"退出码 {rc}").strip()
    try:
        obj = json.loads(msg)
    except json.JSONDecodeError:
        return False, None, (err or out).strip()
    if obj.get("ok"):
        return True, obj.get("data"), None
    return False, obj.get("data"), obj.get("error", "未知错误")


def status() -> dict:
    """只读状态：损坏/半装包、被 hold 锁定的包。"""
    rc, out, _ = shell.run(["dpkg", "--audit"], timeout=60)
    broken = [l.strip() for l in out.splitlines() if l.strip()]
    rc, out, _ = shell.run(["apt-mark", "showhold"], timeout=30)
    held = [l.strip() for l in out.splitlines() if l.strip()]
    return {"broken": broken, "held": held}


def fix_broken():
    """修复损坏/半装依赖（dpkg --configure -a + apt --fix-broken）。"""
    rc, out, err = shell.pkexec("pkg_fix", [], timeout=600)
    return _parse(rc, out, err)


def orphans():
    """可自动移除的孤儿包（经特权入口预演 autoremove）。"""
    rc, out, err = shell.pkexec("pkg_orphans", [], timeout=300)
    return _parse(rc, out, err)


def hold(pkg: str):
    """锁定软件包版本（禁止自动升级/移除）。"""
    rc, out, err = shell.pkexec("apt_mark", ["hold", pkg], timeout=120)
    return _parse(rc, out, err)


def unhold(pkg: str):
    """解除版本锁定。"""
    rc, out, err = shell.pkexec("apt_mark", ["unhold", pkg], timeout=120)
    return _parse(rc, out, err)