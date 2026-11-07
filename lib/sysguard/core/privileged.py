# -*- coding: utf-8 -*-
"""特权入口 `sysguard-cli`：以 root 身份执行白名单子命令。

GUI 通过 `pkexec /usr/sbin/sysguard-cli <子命令> [参数...]` 调用本文件。
安全原则：
  1. 命令白名单：只允许出现在 COMMANDS 中的子命令，其他一律拒绝；
  2. 无 shell：所有外部命令一律 subprocess 列表参数，绝不 shell=True；
  3. 参数强校验：PID/端口/百分比/单元名/路径均做类型与格式校验；
  4. 磁盘守卫：任何会改变硬件状态的操作，先经 `guard_disk` 校验，
     绝不触碰 SSD、系统盘，且身份按 /dev/disk/by-id 白名单确认。
  5. 停转/唤醒的完整验证（STANDBY 或 LCC 增长且 C0 不变）在此完成。

输出：单行 JSON（{"ok": bool, "data": ..., "error": str}），供 GUI 解析。
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time

from . import disk as _disk
from . import mirror as _mirror


# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------

SYSTEM_DISK_NAMES = {"sda", "nvme0n1", "nvme1n1"}
SYSTEM_MOUNTPOINTS = {"/", "/boot", "/boot/efi"}

ALLOWED_SIGNALS = {"TERM", "KILL", "INT", "HUP", "STOP", "CONT"}
ALLOWED_SERVICE_ACTIONS = {
    "start", "stop", "restart", "enable", "disable", "mask", "unmask", "status",
}
UNIT_NAME_RE = re.compile(r"^[\w:@.\-\\]+$")
PORT_RE = re.compile(r"^(\d{1,5})(?:/(tcp|udp))?$")
SIZE_RE = re.compile(r"^\d+[KMGkmg]?$")

SHRED_ALLOWED_PREFIXES = ("/home/", "/media/", "/mnt/", "/tmp/", "/var/tmp/")
SHRED_DENIED_EXACT = {"/", "/boot", "/etc", "/usr", "/bin", "/sbin", "/lib",
                      "/lib64", "/var", "/root", "/proc", "/sys", "/dev"}


# ---------------------------------------------------------------------------
# 基础输出
# ---------------------------------------------------------------------------

def _run(argv, timeout=120):
    proc = subprocess.run([str(a) for a in argv], capture_output=True,
                          text=True, timeout=timeout)
    return proc.returncode, proc.stdout or "", proc.stderr or ""


def _emit(obj):
    sys.stdout.write(json.dumps(obj, ensure_ascii=False, indent=2) + "\n")
    sys.stdout.flush()
    return 0


def _ok(data=None):
    return _emit({"ok": True, "data": data})


def _err(msg):
    return _emit({"ok": False, "error": str(msg)})


# ---------------------------------------------------------------------------
# 磁盘守卫
# ---------------------------------------------------------------------------

def _resolve_whole_disk(byid_path):
    """by-id -> /dev/sdX 整盘节点。解析失败返回 None。"""
    real = os.path.realpath(byid_path)
    name = _disk._node_to_disk_name(real)
    if not name:
        return None
    return f"/dev/{name}", name


def _lsblk_map():
    """返回 {磁盘名: {rota, mountpoints}}（含分区挂载回填）。"""
    rc, out, _ = _run(
        ["lsblk", "-Jb", "-o", "NAME,PATH,TYPE,ROTA,MOUNTPOINTS"], timeout=20)
    if rc != 0:
        return {}
    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        return {}
    m = {}
    for dev in data.get("blockdevices", []):
        if dev.get("type") != "disk":
            continue
        name = dev.get("name")
        mps = set(x for x in (dev.get("mountpoints") or []) if x)
        for c in dev.get("children", []) or []:
            mps.update(x for x in (c.get("mountpoints") or []) if x)
        m[name] = {"rota": bool(dev.get("rota", False)), "mountpoints": mps}
    return m


def guard_disk(byid_path, require_rotational=True):
    """返回 (ok, reason)。绝不触碰 SSD 与系统盘，身份须 by-id 可确认。"""
    if not byid_path or not byid_path.startswith("/dev/disk/by-id/"):
        return False, f"非法设备标识（须为 /dev/disk/by-id/...）：{byid_path!r}"
    resolved = _resolve_whole_disk(byid_path)
    if not resolved:
        return False, "无法从 by-id 解析到整盘设备节点"
    node, name = resolved

    if name in SYSTEM_DISK_NAMES:
        return False, f"拒绝操作：{name} 为系统盘或受保护设备"

    m = _lsblk_map().get(name)
    if m is None:
        return False, f"设备 {name} 未在 lsblk 中找到或已离线"

    for sysmp in SYSTEM_MOUNTPOINTS:
        if sysmp in m["mountpoints"]:
            return False, f"拒绝操作：{name} 含有系统挂载点 {sysmp}"

    if require_rotational and not m["rota"]:
        return False, f"拒绝操作：{name} 为固态盘（SSD），不支持停转"

    return True, node


# ---------------------------------------------------------------------------
# 停转 / 唤醒（完整验证在此，root 环境）
# ---------------------------------------------------------------------------

def _spindown_full(node):
    """对整盘执行 sg_start --stop 并验证结果。返回结果 dict。"""
    result = {"ok": False, "node": node, "final_state": "UNKNOWN",
              "logs": [], "effect": None, "error": None}
    pre = _disk.probe_smart(node, timeout=20)
    pre_lcc, pre_c0 = pre.get("lcc"), pre.get("c0")

    _run(["sync"], timeout=20)

    rc, out, err = _run(["sg_start", "--stop", "--", node], timeout=60)
    result["logs"].append(f"sg_start --stop rc={rc} {err.strip()}".strip())
    if rc != 0:
        result["error"] = f"sg_start 失败：{err.strip() or rc}"
        return result

    # 轮询验证
    post = _disk.probe_smart(node, timeout=20)
    deadline = time.monotonic() + 8
    while post["power_state"] != "STANDBY" and time.monotonic() < deadline:
        time.sleep(1)
        post = _disk.probe_smart(node, timeout=10)
    result["final_state"] = post["power_state"]
    post_lcc, post_c0 = post.get("lcc"), post.get("c0")

    if post["power_state"] == "STANDBY":
        result["ok"] = True
        result["effect"] = "true_standby"
        return result

    lcc_grew = (pre_lcc is not None and post_lcc is not None
                and post_lcc > pre_lcc)
    c0_safe = pre_c0 is None or post_c0 is None or post_c0 == pre_c0
    if lcc_grew and c0_safe:
        result["ok"] = True
        result["effect"] = "head_unload_only"
        result["logs"].append(
            f"桥接未报 STANDBY，但 LCC {pre_lcc}->{post_lcc} 增长且 C0 不变，"
            "判定磁头已安全卸载")
        return result

    result["error"] = (f"停转后未验证到 STANDBY 且无磁头卸载迹象 "
                       f"(LCC {pre_lcc}->{post_lcc}, C0 {pre_c0}->{post_c0})")
    return result


# ---------------------------------------------------------------------------
# 各子命令处理
# ---------------------------------------------------------------------------

def cmd_disks_scan(args):
    if args:
        return _err("disks_scan 不接受参数")
    scan = _disk.scan_disks(with_power=True)
    if not scan["ok"]:
        return _err(scan.get("error", "扫描失败"))
    return _ok({"disks": scan["disks"]})


def cmd_proc_kill(args):
    if len(args) not in (1, 2):
        return _err("用法：proc_kill <PID> [SIGNAME]")
    try:
        pid = int(args[0])
    except ValueError:
        return _err("PID 必须是整数")
    if pid <= 1:
        return _err("拒绝：PID 必须大于 1")
    sig = args[1] if len(args) == 2 else "TERM"
    if sig not in ALLOWED_SIGNALS:
        return _err(f"不允许的信号：{sig}")
    rc, out, err = _run(["kill", f"-{sig}", str(pid)], timeout=10)
    if rc != 0:
        return _err(err.strip() or f"kill 失败：{rc}")
    return _ok({"pid": pid, "signal": sig})


def cmd_service(args):
    if len(args) != 2:
        return _err("用法：service_ctl <动作> <单元>")
    action, unit = args
    if action not in ALLOWED_SERVICE_ACTIONS:
        return _err(f"不允许的动作：{action}")
    if not UNIT_NAME_RE.match(unit) or ".." in unit:
        return _err(f"非法的 systemd 单元名：{unit!r}")
    argv = ["systemctl", action, unit]
    if action == "disable":
        argv.append("--now")
    rc, out, err = _run(argv, timeout=120)
    if rc != 0:
        return _err(err.strip() or f"systemctl 失败：{rc}")
    return _ok({"action": action, "unit": unit, "out": out.strip()})


def cmd_unmount(args):
    if len(args) != 1:
        return _err("用法：unmount <挂载点或设备>")
    target = args[0]
    if not target.startswith("/"):
        return _err("挂载点/设备必须是绝对路径")
    rc, out, err = _run(["umount", target], timeout=60)
    if rc != 0:
        return _err(err.strip() or f"卸载失败：{rc}")
    return _ok({"target": target})


def cmd_mount(args):
    if len(args) != 1:
        return _err("用法：mount <设备>")
    dev = args[0]
    if not dev.startswith("/dev/"):
        return _err("设备必须是 /dev/... 路径")
    rc, out, err = _run(["udisksctl", "mount", "-b", dev], timeout=60)
    if rc != 0:
        return _err(err.strip() or f"挂载失败：{rc}")
    m = re.search(r"at (/\S+)", out)
    return _ok({"device": dev, "mountpoint": m.group(1) if m else None})


def cmd_spindown(args):
    if len(args) != 1:
        return _err("用法：spindown <by-id>")
    ok, reason = guard_disk(args[0], require_rotational=True)
    if not ok:
        return _err(reason)
    result = _spindown_full(reason)  # reason 在此为整盘节点 /dev/sdX
    if not result["ok"]:
        return _err(result["error"])
    return _ok({"node": result["node"], "final_state": result["final_state"],
                "effect": result["effect"], "logs": result["logs"]})


def cmd_spinup(args):
    if len(args) != 1:
        return _err("用法：spinup <by-id>")
    ok, reason = guard_disk(args[0], require_rotational=False)
    if not ok:
        return _err(reason)
    node = reason
    rc, out, err = _run(["sg_start", "--start", "--", node], timeout=60)
    if rc != 0:
        return _err(err.strip() or f"唤醒失败：{rc}")
    return _ok({"node": node, "action": "start"})


def cmd_smart(args):
    if len(args) != 1:
        return _err("用法：smart <块设备路径>")
    dev = args[0]
    if not dev.startswith("/dev/"):
        return _err("设备必须是 /dev/... 路径")
    rc, out, err = _run(["smartctl", "-a", dev], timeout=90)
    if rc != 0:
        return _err(err.strip() or out.strip() or "smartctl 失败")
    return _ok({"device": dev, "report": out})


def cmd_badblocks_ro(args):
    if len(args) != 1:
        return _err("用法：badblocks_ro <块设备路径>")
    dev = args[0]
    if not dev.startswith("/dev/"):
        return _err("设备必须是 /dev/... 路径")
    rc, out, err = _run(
        ["badblocks", "-b", "4096", "-c", "64", "-s", "-v", dev], timeout=600)
    if rc not in (0, 1):
        return _err(err.strip() or f"badblocks 失败：{rc}")
    return _ok({"device": dev, "badblocks": out.strip(), "rc": rc})


def cmd_bbr(args):
    if len(args) != 1 or args[0] not in ("on", "off"):
        return _err("用法：bbr <on|off>")
    on = args[0] == "on"
    cca = "bbr" if on else "cubic"
    qdisc = "fq" if on else "fq_codel"
    rc1, _, e1 = _run(["sysctl", "-w", f"net.core.default_qdisc={qdisc}"])
    rc2, _, e2 = _run(["sysctl", "-w", f"net.ipv4.tcp_congestion_control={cca}"])
    if rc1 or rc2:
        return _err((e1 or e2).strip() or "设置 BBR 失败")
    try:
        os.makedirs("/etc/sysctl.d", exist_ok=True)
        with open("/etc/sysctl.d/99-sysguard-bbr.conf", "w") as f:
            f.write(f"net.core.default_qdisc={qdisc}\n")
            f.write(f"net.ipv4.tcp_congestion_control={cca}\n")
    except OSError as e:
        return _err(f"写入持久化配置失败：{e}")
    return _ok({"bbr": on, "congestion_control": cca})


def cmd_swappiness(args):
    if len(args) != 1:
        return _err("用法：swappiness <0-100>")
    try:
        val = int(args[0])
    except ValueError:
        return _err("swappiness 必须是整数")
    if not (0 <= val <= 100):
        return _err("swappiness 必须在 0..100 之间")
    rc, out, err = _run(["sysctl", "-w", f"vm.swappiness={val}"], timeout=30)
    if rc != 0:
        return _err(err.strip() or "写入 swappiness 失败")
    try:
        with open("/etc/sysctl.d/99-sysguard-swap.conf", "w") as f:
            f.write(f"vm.swappiness={val}\n")
    except OSError as e:
        return _err(f"写入持久化配置失败：{e}")
    return _ok({"swappiness": val})


def cmd_apt_clean(args):
    if args:
        return _err("apt_clean 不接受参数")
    rc, out, err = _run(["apt-get", "clean"], timeout=300)
    if rc != 0:
        return _err(err.strip() or f"apt-get clean 失败：{rc}")
    return _ok({"done": True})


def cmd_apt_autoclean(args):
    if args:
        return _err("apt_autoclean 不接受参数")
    rc, out, err = _run(["apt-get", "autoclean"], timeout=300)
    if rc != 0:
        return _err(err.strip() or f"apt-get autoclean 失败：{rc}")
    return _ok({"done": True})


def cmd_apt_autoremove(args):
    if args:
        return _err("apt_autoremove 不接受参数")
    rc, out, err = _run(["apt-get", "autoremove", "--purge", "-y"], timeout=600)
    if rc != 0:
        return _err(err.strip() or f"apt-get autoremove 失败：{rc}")
    return _ok({"done": True})


def cmd_journal_vacuum(args):
    if len(args) != 1:
        return _err("用法：journal_vacuum <大小>，如 100M / 200K / 1G")
    size = args[0]
    if not SIZE_RE.match(size):
        return _err("大小格式非法：须为数字 + 可选 K/M/G")
    rc, out, err = _run(["journalctl", "--vacuum-size", size], timeout=300)
    if rc != 0:
        return _err(err.strip() or f"日志清理失败：{rc}")
    return _ok({"vacuumed_to": out.strip()})


def _safe_rmtree_children(target):
    if not target.startswith("/") or target in SHRED_DENIED_EXACT:
        return 0
    freed = 0
    try:
        entries = os.listdir(target)
    except OSError:
        return 0
    for ent in entries:
        if ent in (".", ".."):
            continue
        freed += _safe_rmtree(os.path.join(target, ent))
    return freed


def _safe_rmtree(path):
    import shutil
    if os.path.islink(path):
        try:
            os.unlink(path)
        except OSError:
            pass
        return 0
    if not os.path.isdir(path):
        try:
            return os.path.getsize(path)
        except OSError:
            return 0
    total = 0
    try:
        for ent in os.listdir(path):
            total += _safe_rmtree(os.path.join(path, ent))
        os.rmdir(path)
    except OSError:
        pass
    return total


def cmd_purge_tmp(args):
    if args:
        return _err("purge_tmp 不接受参数")
    freed = _safe_rmtree_children("/tmp")
    return _ok({"freed_bytes": freed})


def cmd_purge_thumbnails(args):
    if args:
        return _err("purge_thumbnails 不接受参数")
    freed = 0
    try:
        for user in os.listdir("/home"):
            tp = os.path.join("/home", user, ".cache", "thumbnails")
            if os.path.isdir(tp):
                freed += _safe_rmtree_children(tp)
    except OSError:
        pass
    return _ok({"freed_bytes": freed})


def cmd_kernel_remove(args):
    if len(args) != 1:
        return _err("用法：kernel_remove <完整内核版本前缀>")
    ver = args[0]
    if not re.match(r"^[\w.\-\+]+$", ver):
        return _err("非法的内核版本字符串")
    cur = os.uname().release
    if ver in cur or cur.startswith(ver) or ver.startswith(cur):
        return _err("拒绝：不能卸载当前运行内核")
    rc, out, err = _run(
        ["apt-get", "remove", "--purge", "-y",
         f"linux-image-{ver}", f"linux-headers-{ver}"], timeout=600)
    if rc != 0:
        return _err(err.strip() or f"卸载内核失败：{rc}")
    return _ok({"removed": ver})


def cmd_ufw_enable(args):
    if args:
        return _err("ufw_enable 不接受参数")
    rc, out, err = _run(["ufw", "--force", "enable"], timeout=120)
    if rc != 0:
        return _err(err.strip() or f"ufw 启用失败：{rc}")
    return _ok({"enabled": True})


def cmd_ufw_disable(args):
    if args:
        return _err("ufw_disable 不接受参数")
    rc, out, err = _run(["ufw", "--force", "disable"], timeout=120)
    if rc != 0:
        return _err(err.strip() or f"ufw 停用失败：{rc}")
    return _ok({"enabled": False})


def cmd_ufw_allow(args):
    if len(args) != 1:
        return _err("用法：ufw_allow <端口[/tcp|udp]>")
    spec = args[0]
    m = PORT_RE.match(spec)
    if not m:
        return _err("端口格式非法：如 22 或 443/tcp")
    argv = ["ufw", "allow",
            f"{m.group(1)}/{m.group(2)}" if m.group(2) else m.group(1)]
    rc, out, err = _run(argv, timeout=60)
    if rc != 0:
        return _err(err.strip() or f"ufw allow 失败：{rc}")
    return _ok({"rule": spec, "action": "allow"})


def cmd_ufw_deny(args):
    if len(args) != 1:
        return _err("用法：ufw_deny <端口[/tcp|udp]>")
    spec = args[0]
    m = PORT_RE.match(spec)
    if not m:
        return _err("端口格式非法：如 22 或 443/tcp")
    argv = ["ufw", "deny",
            f"{m.group(1)}/{m.group(2)}" if m.group(2) else m.group(1)]
    rc, out, err = _run(argv, timeout=60)
    if rc != 0:
        return _err(err.strip() or f"ufw deny 失败：{rc}")
    return _ok({"rule": spec, "action": "deny"})


def cmd_ufw_reset(args):
    if args:
        return _err("ufw_reset 不接受参数")
    rc, out, err = _run(["ufw", "--force", "reset"], timeout=60)
    if rc != 0:
        return _err(err.strip() or f"ufw reset 失败：{rc}")
    return _ok({"reset": True})


def cmd_shred(args):
    if len(args) != 1:
        return _err("用法：shred <绝对路径>")
    path = args[0]
    if not path.startswith("/") or ".." in path.split("/"):
        return _err("路径非法")
    if path in SHRED_DENIED_EXACT:
        return _err("拒绝：禁止粉碎系统关键路径")
    if not any(path.startswith(p) for p in SHRED_ALLOWED_PREFIXES):
        return _err("拒绝：仅允许粉碎 /home、/media、/mnt、/tmp 下的文件")
    if not os.path.exists(path):
        return _err("目标不存在")
    if os.path.isdir(path):
        return _err("拒绝：不允许粉碎目录（请逐个文件操作）")
    rc, out, err = _run(["shred", "-u", "-z", "-n", "3", path], timeout=600)
    if rc != 0:
        return _err(err.strip() or f"shred 失败：{rc}")
    return _ok({"shredded": path})


# ---------------------------------------------------------------------------
# 命令表
# ---------------------------------------------------------------------------

def cmd_mirror_set(args):
    if len(args) != 1:
        return _err("用法：mirror_set <镜像id>")
    mirror_id = args[0]
    if not re.match(r"^[a-z0-9\-]+$", mirror_id):
        return _err("镜像 id 非法")
    ok, msg = _mirror.write_sources(mirror_id)
    if not ok:
        return _err(msg)
    return _ok({"mirror": msg})


def cmd_mirror_backup(args):
    if args:
        return _err("mirror_backup 不接受参数")
    ok, msg = _mirror.backup_sources()
    if not ok:
        return _err(msg)
    return _ok({"backup_dir": msg})


def cmd_mirror_restore(args):
    if args:
        return _err("mirror_restore 不接受参数")
    ok, msg = _mirror.restore_sources()
    if not ok:
        return _err(msg)
    return _ok({"done": True})


COMMANDS = {
    "disks_scan": cmd_disks_scan,
    "proc_kill": cmd_proc_kill,
    "service_ctl": cmd_service,
    "unmount": cmd_unmount,
    "mount": cmd_mount,
    "spindown": cmd_spindown,
    "spinup": cmd_spinup,
    "smart": cmd_smart,
    "badblocks_ro": cmd_badblocks_ro,
    "bbr": cmd_bbr,
    "swappiness": cmd_swappiness,
    "apt_clean": cmd_apt_clean,
    "apt_autoclean": cmd_apt_autoclean,
    "apt_autoremove": cmd_apt_autoremove,
    "journal_vacuum": cmd_journal_vacuum,
    "purge_tmp": cmd_purge_tmp,
    "purge_thumbnails": cmd_purge_thumbnails,
    "kernel_remove": cmd_kernel_remove,
    "ufw_enable": cmd_ufw_enable,
    "ufw_disable": cmd_ufw_disable,
    "ufw_allow": cmd_ufw_allow,
    "ufw_deny": cmd_ufw_deny,
    "ufw_reset": cmd_ufw_reset,
    "shred": cmd_shred,
    "mirror_set": cmd_mirror_set,
    "mirror_backup": cmd_mirror_backup,
    "mirror_restore": cmd_mirror_restore,
}


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        return _err("缺少子命令")
    sub = args[0]
    handler = COMMANDS.get(sub)
    if handler is None:
        return _err(f"未知子命令：{sub}")
    try:
        return handler(args[1:])
    except subprocess.TimeoutExpired:
        return _err("命令执行超时")
    except Exception as e:
        return _err(f"内部错误：{e}")


if __name__ == "__main__":
    sys.exit(main())