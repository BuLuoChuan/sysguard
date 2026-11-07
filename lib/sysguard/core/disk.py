# -*- coding: utf-8 -*-
"""磁盘管理检修：分区/挂载/SMART 健康/温度/停转/坏道。

本模块为「纯逻辑层」，本身不直接以 root 执行；需要 root 的副作用操作
（sg_start / umount / 挂载 / smartctl / badblocks）一律经 `shell.pkexec`
转交特权入口 `sysguard-cli`，由入口内部再做命令白名单与设备守卫校验。
"""
from __future__ import annotations

import json
import os
import re
import time

from . import shell


SYSTEM_MOUNTPOINTS = {"/", "/boot", "/boot/efi"}

# 已知不支持 ATA 透传（hdparm）的 USB 桥接主控 idVendor:idProduct
HDARM_BLOCKLIST_USB = {("1058", "2626")}

# smartctl -n standby 在盘已待机时常见退出码（bit1=设备已待机、未唤醒）
SMART_STANDBY_EXIT_CODES = {2}

LSBLK_COLS = (
    "NAME,PATH,TYPE,ROTA,TRAN,MODEL,SERIAL,SIZE,FSTYPE,LABEL,UUID,"
    "MOUNTPOINTS,SUBSYSTEMS"
)


# ---------------------------------------------------------------------------
# 磁盘发现
# ---------------------------------------------------------------------------

def _byid_index():
    index = {}
    root = "/dev/disk/by-id"
    try:
        names = os.listdir(root)
    except OSError:
        return index
    for name in names:
        link = os.path.join(root, name)
        try:
            real = os.path.realpath(link)
        except OSError:
            continue
        index.setdefault(real, []).append(link)
    return index


def _pick_byid(candidates):
    if not candidates:
        return None
    prefixes = ("usb-", "ata-", "nvme-", "scsi-", "ieee1394-", "mmc-")
    filtered = [c for c in candidates
                if os.path.basename(c).startswith(prefixes)]
    pool = filtered or list(candidates)
    return sorted(pool)[0]


def _node_to_disk_name(node):
    base = os.path.basename(node)
    m = re.match(r"^(sd[a-z]+|nvme\d+n\d+|mmcblk\d+)", base)
    return m.group(1) if m else None


def _read_driver(disk_name):
    try:
        return os.path.basename(
            os.path.realpath(f"/sys/block/{disk_name}/device/driver"))
    except OSError:
        return None


def _walk_usb(disk_name):
    cur = os.path.realpath(f"/sys/block/{disk_name}/device")
    vendor = product = storage_driver = None
    for _ in range(12):
        v = shell.read_file(os.path.join(cur, "idVendor")).strip()
        p = shell.read_file(os.path.join(cur, "idProduct")).strip()
        if v and p and not vendor:
            vendor, product = v.lower(), p.lower()
        try:
            drv = os.path.basename(os.path.realpath(os.path.join(cur, "driver")))
        except OSError:
            drv = None
        if drv in ("usb-storage", "uas", "ums-cypress", "ums-realtek") \
                and not storage_driver:
            storage_driver = drv
        parent = os.path.dirname(cur)
        if parent == cur or not parent.startswith("/sys"):
            break
        cur = parent
    return vendor, product, storage_driver


def scan_disks(with_power=False, timeout=25):
    """扫描磁盘。with_power=True 时追加 SMART/电源信息（需 root）。"""
    rc, out, _ = shell.run(
        ["lsblk", "-Jb", "-o", LSBLK_COLS], timeout=15)
    if rc != 0:
        return {"ok": False, "error": "lsblk 失败", "disks": []}
    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        return {"ok": False, "error": "lsblk 输出解析失败", "disks": []}

    byids = _byid_index()
    disks = []

    for dev in data.get("blockdevices", []):
        if dev.get("type") != "disk":
            continue
        name = dev.get("name", "")
        path = dev.get("path") or f"/dev/{name}"
        rotational = bool(dev.get("rota", False))
        transport = dev.get("tran") or ""
        subsystems = dev.get("subsystems") or ""
        driver = _read_driver(name)

        vendor = product = storage_driver = None
        is_usb = transport == "usb" or "usb" in subsystems.split(":")
        if is_usb:
            vendor, product, storage_driver = _walk_usb(name)

        parts = []
        all_mps = []
        for child in dev.get("children", []) or []:
            if child.get("type") != "part":
                continue
            cpath = child.get("path") or f"/dev/{child.get('name')}"
            mps = [m for m in (child.get("mountpoints") or []) if m]
            all_mps.extend(mps)
            parts.append({
                "name": child.get("name"),
                "path": cpath,
                "fstype": child.get("fstype") or "",
                "label": child.get("label") or "",
                "uuid": child.get("uuid") or "",
                "mountpoints": mps,
                "by_id": _pick_byid(byids.get(os.path.realpath(cpath), [])),
            })
        if dev.get("mountpoints"):
            all_mps.extend([m for m in dev["mountpoints"] if m])

        disk = {
            "name": name,
            "path": path,
            "by_id": _pick_byid(byids.get(os.path.realpath(path), [])),
            "model": (dev.get("model") or "").strip() or None,
            "serial": (dev.get("serial") or "").strip() or None,
            "size_bytes": dev.get("size"),
            "rotational": rotational,
            "transport": transport,
            "driver": driver,
            "is_usb": is_usb,
            "usb_vendor": vendor,
            "usb_product": product,
            "usb_storage_driver": storage_driver,
            "partitions": parts,
            "mountpoints": sorted(set(all_mps)),
            "is_system_disk": bool(set(all_mps) & SYSTEM_MOUNTPOINTS),
            "power_state": "UNKNOWN",
            "temperature": None,
            "c0": None,
            "lcc": None,
            "smart_error": None,
        }

        if with_power:
            smart = probe_smart(path, timeout=timeout)
            disk.update(
                power_state=smart["power_state"],
                temperature=smart["temperature"],
                c0=smart["c0"],
                lcc=smart["lcc"],
                smart_error=smart["error"],
            )

        disks.append(disk)

    disks.sort(key=lambda d: d["name"])
    return {"ok": True, "disks": disks}


# ---------------------------------------------------------------------------
# SMART / 电源状态（smartctl -n standby 绝不唤醒盘）
# ---------------------------------------------------------------------------

_STANDBY_RE = re.compile(r"in STANDBY", re.IGNORECASE)
_ACTIVE_RE = re.compile(r"ACTIVE or IDLE|in IDLE|ACTIVE/IDLE", re.IGNORECASE)
_TEMP_INFO_RE = re.compile(r"Temperature:\s*(\d+)\s*Celsius", re.IGNORECASE)
_ATTR_RE = re.compile(
    r"^\s*(\d+)\s+([\w\-]+)\s+\S+\s+\d+\s+\d+\s+\d+\s+\S+\s+\S+\s+\S+\s+(.+?)\s*$"
)


def probe_smart(node, timeout=20):
    """探测电源状态 + 温度 + 192(C0)/193(LCC) 原始值。"""
    result = {
        "power_state": "UNKNOWN", "temperature": None, "c0": None,
        "lcc": None, "error": None, "raw": "", "rc": None,
    }
    rc, out, err = shell.run(
        ["smartctl", "-n", "standby", "-i", "-A", node], timeout=timeout)
    result["rc"] = rc
    result["raw"] = out
    text = out or ""

    if _STANDBY_RE.search(text):
        result["power_state"] = "STANDBY"
        return result
    if _ACTIVE_RE.search(text):
        result["power_state"] = "ACTIVE_IDLE"
    elif rc == 0:
        result["power_state"] = "ACTIVE_IDLE"
    elif rc not in SMART_STANDBY_EXIT_CODES:
        result["error"] = (err.strip() or text.strip() or f"smartctl 退出码 {rc}")[:500]

    m = _TEMP_INFO_RE.search(text)
    if m:
        result["temperature"] = int(m.group(1))

    for line in text.splitlines():
        m = _ATTR_RE.match(line)
        if not m:
            continue
        try:
            attr_id = int(m.group(1))
        except ValueError:
            continue
        name = m.group(2).lower()
        raw_match = re.search(r"\d+", m.group(3))
        raw_val = int(raw_match.group(0)) if raw_match else None
        if attr_id == 192 or "power_off_retract" in name:
            result["c0"] = raw_val
        elif attr_id == 193 or "load_cycle" in name:
            result["lcc"] = raw_val
        elif attr_id in (194, 190) and result["temperature"] is None:
            result["temperature"] = raw_val

    return result


# ---------------------------------------------------------------------------
# 需 root 的操作（转交特权入口）
# ---------------------------------------------------------------------------

def scan_with_power():
    """经特权入口扫描磁盘（含 SMART/温度，需 root）。返回 (ok, disks, error)。"""
    rc, out, err = shell.pkexec("disks_scan", [], timeout=120)
    ok, data, error = _parse_pkexec(rc, out, err)
    if not ok:
        return False, [], error
    return True, (data or {}).get("disks", []), None


def spindown(by_id: str):
    rc, out, err = shell.pkexec("spindown", [by_id], timeout=120)
    return _parse_pkexec(rc, out, err)


def spinup(by_id: str):
    rc, out, err = shell.pkexec("spinup", [by_id], timeout=120)
    return _parse_pkexec(rc, out, err)


def smart_report(dev: str):
    rc, out, err = shell.pkexec("smart", [dev], timeout=90)
    return _parse_pkexec(rc, out, err)


def badblocks_scan(dev: str):
    rc, out, err = shell.pkexec("badblocks_ro", [dev], timeout=900)
    return _parse_pkexec(rc, out, err)


def unmount(target: str):
    rc, out, err = shell.pkexec("unmount", [target], timeout=60)
    return _parse_pkexec(rc, out, err)


def mount(dev: str):
    rc, out, err = shell.pkexec("mount", [dev], timeout=60)
    return _parse_pkexec(rc, out, err)


def _parse_pkexec(rc, out, err):
    """解析特权入口返回的 JSON，转成统一 (ok, data, error)。"""
    msg = (out or "").strip()
    # 非 JSON（例如 pkexec 对话框被取消）时的兜底
    if not msg.lstrip().startswith("{"):
        if rc == 126:
            return False, None, "授权被取消或 pkexec 不可用"
        return False, None, (err or out or f"退出码 {rc}").strip()
    try:
        obj = json.loads(msg)
    except json.JSONDecodeError:
        return False, None, (err or out).strip()
    if obj.get("ok"):
        return True, obj.get("data"), None
    return False, obj.get("data"), obj.get("error", "未知错误")