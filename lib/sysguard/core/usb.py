# -*- coding: utf-8 -*-
"""USB 挂载/卸载/机械硬盘停转（复用 disk 层成熟逻辑）。"""
from __future__ import annotations

from . import disk


def list_usb(with_power=False):
    """列出 USB 设备（含温吞与挂载状态）。"""
    scan = disk.scan_disks(with_power=with_power)
    if not scan["ok"]:
        return scan
    usb = [d for d in scan["disks"] if d.get("is_usb")]
    return {"ok": True, "disks": usb}


def spindown(by_id):
    return disk.spindown(by_id)


def spinup(by_id):
    return disk.spinup(by_id)


def unmount(target):
    return disk.unmount(target)


def mount(dev):
    return disk.mount(dev)