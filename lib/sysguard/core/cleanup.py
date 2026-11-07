# -*- coding: utf-8 -*-
"""垃圾清理：apt 缓存 / 旧内核 / journal / 临时文件 / 缩略图（先估空间）。"""
from __future__ import annotations

import os
import re

from . import shell

APT_CACHE = "/var/cache/apt/archives"
APT_LISTS = "/var/lib/apt/lists"


def _parse_size(text):
    """把 '123', '4.2M', '1.5G' 解析成字节。"""
    m = re.search(r"(\d+\.?\d*)\s*([KMG]?)", text, re.IGNORECASE)
    if not m:
        return 0
    try:
        num = float(m.group(1))
    except ValueError:
        return 0
    unit = (m.group(2) or "").upper()
    mult = {"": 1, "K": 1024, "M": 1024 ** 2, "G": 1024 ** 3}.get(unit, 1)
    return int(num * mult)


def _du(path):
    rc, out, _ = shell.run(["du", "-sb", path], timeout=60)
    if rc != 0:
        return 0
    try:
        return int(out.split()[0])
    except (ValueError, IndexError):
        return 0


def apt_cache_size():
    return _du(APT_CACHE)


def apt_list_size():
    return _du(APT_LISTS)


def autoremove_summary():
    """apt autoremove 干跑，给出可释放体积与包数。"""
    rc, out, _ = shell.run(["apt-get", "-s", "autoremove"], timeout=60)
    if rc != 0:
        return {"packages": 0, "freed_bytes": 0, "packages_list": []}
    pkgs = re.findall(r"^Remv\s+(\S+)", out, re.MULTILINE)
    freed = 0
    m = re.search(r"(\d+(?:\.\d+)?)\s*([KMG]?)\s*\w*?\s*disk space will be freed",
                  out, re.IGNORECASE)
    if m:
        freed = _parse_size(m.group(1) + m.group(2))
    return {"packages": len(pkgs), "freed_bytes": freed, "packages_list": pkgs}


def old_kernels():
    """列出可卸载的旧内核镜像版本（排除当前运行内核）。"""
    running = shell.read_file("/proc/sys/kernel/osrelease").strip()
    rc, out, _ = shell.run(
        ["dpkg-query", "-W", "-f=${Package}\n", "linux-image-[0-9]*"],
        timeout=30)
    kernels = []
    if rc != 0:
        return kernels
    for pkg in out.splitlines():
        pkg = pkg.strip()
        if not pkg:
            continue
        ver = pkg.replace("linux-image-", "")
        if ver == running:
            continue
        if ver.endswith(("-generic", "-rt", "-lowlatency")):
            # 去掉 ABI 后缀，只保留版本前缀比较；仍按完整 ver 返回
            pass
        kernels.append(ver)
    return sorted(set(kernels))


def journal_size():
    rc, out, _ = shell.run(["journalctl", "--disk-usage"], timeout=30)
    if rc != 0:
        return 0
    m = re.search(r"(\d+\.?\d*)\s*([KMG])", out, re.IGNORECASE)
    if not m:
        return 0
    return _parse_size(m.group(1) + m.group(2))


def tmp_size():
    return _du("/tmp")


def _home_users():
    try:
        return [u for u in os.listdir("/home")
                if os.path.isdir(os.path.join("/home", u))]
    except OSError:
        return []


def thumbnails_size():
    total = 0
    for user in _home_users():
        total += _du(f"/home/{user}/.cache/thumbnails")
    return total


def measure():
    """汇总各可清理项的空间估算（字节）。"""
    return {
        "apt_cache": apt_cache_size(),
        "apt_lists": apt_list_size(),
        "autoremove": autoremove_summary(),
        "old_kernels": old_kernels(),
        "journal": journal_size(),
        "tmp": tmp_size(),
        "thumbnails": thumbnails_size(),
    }


# ---------------------------------------------------------------------------
# 实际清理（转交特权入口）
# ---------------------------------------------------------------------------

def _parse(rc, out, err):
    import json
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


def clean_apt_cache():
    rc, out, err = shell.pkexec("apt_clean", [], timeout=300)
    ok, _, err2 = _parse(rc, out, err)
    return ok, err2 or "已清理 apt 缓存"


def clean_apt_autoclean():
    rc, out, err = shell.pkexec("apt_autoclean", [], timeout=300)
    ok, _, err2 = _parse(rc, out, err)
    return ok, err2 or "已完成 autoclean"


def clean_autoremove():
    rc, out, err = shell.pkexec("apt_autoremove", [], timeout=600)
    ok, _, err2 = _parse(rc, out, err)
    return ok, err2 or "已清理不再需要的软件包"


def clean_journal(size="100M"):
    rc, out, err = shell.pkexec("journal_vacuum", [size], timeout=300)
    ok, _, err2 = _parse(rc, out, err)
    return ok, err2 or "已清理日志"


def clean_tmp():
    rc, out, err = shell.pkexec("purge_tmp", [], timeout=300)
    ok, _, err2 = _parse(rc, out, err)
    return ok, err2 or "已清理临时文件"


def clean_thumbnails():
    rc, out, err = shell.pkexec("purge_thumbnails", [], timeout=300)
    ok, _, err2 = _parse(rc, out, err)
    return ok, err2 or "已清理缩略图缓存"


def remove_kernel(version):
    rc, out, err = shell.pkexec("kernel_remove", [version], timeout=600)
    ok, _, err2 = _parse(rc, out, err)
    return ok, err2 or "已卸载内核"