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
            "health": None,
            "smart_attrs": [],
        }

        if with_power:
            smart = probe_smart(path, timeout=timeout)
            disk.update(
                power_state=smart["power_state"],
                temperature=smart["temperature"],
                c0=smart["c0"],
                lcc=smart["lcc"],
                smart_error=smart["error"],
                health=smart["health"],
                smart_attrs=smart["attrs"],
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
        "health": None, "attrs": [],
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

    result["health"], result["attrs"] = analyze_smart(text)
    return result


# ---------------------------------------------------------------------------
# SMART 属性解析（中文专有名词 + 黄/红分级）
# ---------------------------------------------------------------------------

# ATA/SATA SMART 属性 ID -> 中文专有名词
SMART_ATTR_CN = {
    1: "原始读错误率", 2: "读吞吐性能", 3: "磁盘起转时间",
    4: "启动/停止次数", 5: "重分配扇区数", 7: "寻道错误率",
    8: "寻道时间性能", 9: "通电时间", 10: "起转重试次数",
    11: "校准重试次数", 12: "通电周期数", 13: "软读错误率",
    183: "运行时坏块总数", 184: "端到端错误数", 187: "上报不可纠正错误",
    188: "命令超时", 189: "磁头飞行高度写入", 190: "气流温度",
    191: "冲击感应错误率", 192: "断电回撤次数", 193: "加载/卸载循环次数",
    194: "温度", 195: "硬件 ECC 恢复次数", 196: "重分配事件次数",
    197: "当前待决扇区", 198: "离线不可纠正扇区", 199: "UDMA CRC 错误",
    200: "多区域错误率", 201: "软读错误率(2)", 202: "数据地址标记错误",
    240: "磁头飞行时间", 241: "累计写入量", 242: "累计读取量",
    254: "自由落体传感器",
}

# raw 值 > 0 即视为「红色异常」的关键属性（坏扇区/不可纠正类）
SMART_BAD_ATTRS = {5, 183, 187, 197, 198}
# raw 值 > 0 视为「黄色警告」的属性（可修复/环境类）
SMART_WARN_ATTRS = {10, 188, 196, 199, 202}

_ATTR_LINE_RE = re.compile(
    r"^\s*(\d+)\s+([\w\-_]+)\s+(0x[0-9a-fA-F]+)\s+(\d+)\s+(\d+)\s+(\d+)\s+"
    r"([\w\-]+)\s+([\w\-]+)\s+(\S+)\s+(.*)$")


def _first_int(s):
    m = re.search(r"\d+", s or "")
    try:
        return int(m.group(0)) if m else None
    except ValueError:
        return None


def _attr_status(attr_id, value, threshold, when_failed, raw):
    if when_failed not in ("-", "", "0"):
        return "bad"
    if attr_id in SMART_BAD_ATTRS and _first_int(raw) and _first_int(raw) > 0:
        return "bad"
    if attr_id in SMART_WARN_ATTRS and _first_int(raw) and _first_int(raw) > 0:
        return "warn"
    if threshold and value <= threshold:
        return "warn"
    return "ok"


def _analyze_ata(report):
    attrs = []
    in_table = False
    for line in report.splitlines():
        if "ATTRIBUTE_NAME" in line and "WHEN_FAILED" in line:
            in_table = True
            continue
        if not in_table:
            continue
        m = _ATTR_LINE_RE.match(line.strip())
        if not m:
            continue
        try:
            attr_id = int(m.group(1))
            value = int(m.group(4))
            worst = int(m.group(5))
            threshold = int(m.group(6))
        except ValueError:
            continue
        when_failed = m.group(9)
        raw = m.group(10).strip()
        attrs.append({
            "id": attr_id,
            "name": m.group(2),
            "name_cn": SMART_ATTR_CN.get(attr_id, m.group(2)),
            "value": value,
            "worst": worst,
            "threshold": threshold,
            "when_failed": when_failed,
            "raw": raw,
            "status": _attr_status(attr_id, value, threshold, when_failed, raw),
        })
    return attrs


def _analyze_nvme(report):
    """NVMe 关键健康项 -> 与 ATA 结构对齐的属性列表（中文专有名词）。"""
    attrs = []
    for line in report.splitlines():
        if ":" not in line:
            continue
        key, _, val = line.partition(":")
        key_s = key.strip()
        val_s = val.strip()
        if "Critical Warning" in key_s:
            attrs.append(_nvme_attr("Critical Warning", "严重警告", val_s, "bad"))
        elif key_s == "Temperature":
            num = _first_int(val_s)
            attrs.append({"id": "temp", "name": "Temperature", "name_cn": "温度",
                          "value": num, "worst": num, "threshold": 0,
                          "when_failed": "-", "raw": val_s, "status": "ok"})
        elif key_s == "Available Spare":
            pct = _first_int(val_s)
            st = "bad" if pct is not None and pct < 10 else ("warn" if pct is not None and pct < 50 else "ok")
            attrs.append({"id": "spare", "name": "Available Spare",
                          "name_cn": "可用备用空间", "value": pct, "worst": pct,
                          "threshold": 0, "when_failed": "-", "raw": val_s,
                          "status": st})
        elif key_s == "Percentage Used":
            pct = _first_int(val_s)
            st = "warn" if pct is not None and pct >= 90 else "ok"
            attrs.append({"id": "used", "name": "Percentage Used",
                          "name_cn": "已使用寿命", "value": pct, "worst": pct,
                          "threshold": 0, "when_failed": "-", "raw": val_s,
                          "status": st})
        elif "Media and Data Integrity Errors" in key_s:
            n = _first_int(val_s) or 0
            attrs.append({"id": "integrity", "name": "Media Errors",
                          "name_cn": "介质与数据完整性错误", "value": n, "worst": n,
                          "threshold": 0, "when_failed": "-", "raw": val_s,
                          "status": "bad" if n > 0 else "ok"})
    return attrs


def _nvme_attr(name, name_cn, raw, status):
    return {"id": name.lower().replace(" ", "_"), "name": name, "name_cn": name_cn,
            "value": _first_int(raw), "worst": _first_int(raw), "threshold": 0,
            "when_failed": "-", "raw": raw, "status": status}


def _overall_health(attrs):
    if not attrs:
        return None
    if any(a["status"] == "bad" for a in attrs):
        return "bad"
    if any(a["status"] == "warn" for a in attrs):
        return "warn"
    return "ok"


def analyze_smart(report):
    """解析 SMART 输出，返回 (health, attrs)。health 为 ok/warn/bad/None。"""
    text = report or ""
    attrs = _analyze_ata(text)
    if not attrs:
        attrs = _analyze_nvme(text)
    return _overall_health(attrs), attrs

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