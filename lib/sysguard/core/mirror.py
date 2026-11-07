# -*- coding: utf-8 -*-
"""镜像源检测 / 测速 / 切换（apt 与 rpm 两大类）。

- `detect()` 依据 /etc/os-release 与可用的包管理器识别发行版与包管理器；
- `available()` 返回该发行版可用的镜像列表；
- `test_mirror()` 用标准库 urllib 对镜像索引文件测速（普通用户、只读、无第三方依赖）；
- `apply()` / `backup()` / `restore()` 通过 pkexec 转交特权入口执行写操作；
- 特权入口 `sysguard-cli mirror_set <id>` 会先自动备份再写入，支持一键还原。

安全约定：镜像写入的真实内容由本模块（受包内可信代码控制）生成，特权入口只接受
白名单镜像 id，绝不接受任意 URL 或 shell 字符串。
"""
from __future__ import annotations

import json
import os
import shutil
import time
import urllib.request

from . import shell

# ---------------------------------------------------------------------------
# 镜像表（base 为各发行版专属的源前缀，尾部不带斜杠）
# ---------------------------------------------------------------------------

MIRRORS = {
    "ubuntu": [
        {"id": "aliyun", "name": "阿里云", "base": "https://mirrors.aliyun.com/ubuntu"},
        {"id": "tuna", "name": "清华大学", "base": "https://mirrors.tuna.tsinghua.edu.cn/ubuntu"},
        {"id": "ustc", "name": "中科大", "base": "https://mirrors.ustc.edu.cn/ubuntu"},
        {"id": "tencent", "name": "腾讯云", "base": "https://mirrors.cloud.tencent.com/ubuntu"},
        {"id": "netease", "name": "网易163", "base": "https://mirrors.163.com/ubuntu"},
        {"id": "official", "name": "官方", "base": "https://archive.ubuntu.com/ubuntu"},
    ],
    "debian": [
        {"id": "aliyun", "name": "阿里云", "base": "https://mirrors.aliyun.com/debian"},
        {"id": "tuna", "name": "清华大学", "base": "https://mirrors.tuna.tsinghua.edu.cn/debian"},
        {"id": "ustc", "name": "中科大", "base": "https://mirrors.ustc.edu.cn/debian"},
        {"id": "netease", "name": "网易163", "base": "https://mirrors.163.com/debian"},
        {"id": "official", "name": "官方", "base": "https://deb.debian.org/debian"},
    ],
    "fedora": [
        {"id": "tuna", "name": "清华大学", "base": "https://mirrors.tuna.tsinghua.edu.cn/fedora"},
        {"id": "ustc", "name": "中科大", "base": "https://mirrors.ustc.edu.cn/fedora"},
        {"id": "aliyun", "name": "阿里云", "base": "https://mirrors.aliyun.com/fedora"},
    ],
    "el": [
        {"id": "tuna", "name": "清华大学", "base": "https://mirrors.tuna.tsinghua.edu.cn"},
        {"id": "ustc", "name": "中科大", "base": "https://mirrors.ustc.edu.cn"},
        {"id": "aliyun", "name": "阿里云", "base": "https://mirrors.aliyun.com"},
    ],
    "opensuse": [
        {"id": "tuna", "name": "清华大学", "base": "https://mirrors.tuna.tsinghua.edu.cn/opensuse"},
        {"id": "ustc", "name": "中科大", "base": "https://mirrors.ustc.edu.cn/opensuse"},
        {"id": "aliyun", "name": "阿里云", "base": "https://mirrors.aliyun.com/opensuse"},
        {"id": "official", "name": "官方", "base": "https://download.opensuse.org"},
    ],
}

BACKUP_DIR = "/var/backups/sysguard/mirror"


# ---------------------------------------------------------------------------
# 发行版 / 包管理器检测
# ---------------------------------------------------------------------------

def _os_release() -> dict:
    txt = shell.read_file("/etc/os-release")
    d = {}
    for line in txt.splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            d[k.strip()] = v.strip().strip('"').strip("'")
    return d


def _have(tool: str) -> bool:
    return shutil.which(tool) is not None


def detect() -> dict:
    d = _os_release()
    id_ = (d.get("ID") or "").lower()
    like = (d.get("ID_LIKE") or "").lower()
    name = d.get("PRETTY_NAME") or d.get("NAME") or id_
    codename = d.get("VERSION_CODENAME") or ""
    version = d.get("VERSION_ID") or ""

    family = pm = None
    if id_ == "ubuntu":
        family, pm = "ubuntu", "apt"
    elif id_ == "debian":
        family, pm = "debian", "apt"
    elif id_ == "fedora":
        family, pm = "fedora", "dnf"
    elif id_ in ("centos", "rhel", "rocky", "almalinux") or any(
            x in like for x in ("rhel", "centos", "rocky", "almalinux")):
        family = "el"
        pm = "dnf" if _have("dnf") else ("yum" if _have("yum") else "yum")
    elif "opensuse" in id_ or "suse" in like:
        family, pm = "opensuse", "zypper"

    # 兜底：按可用包管理器推断
    if pm is None:
        if _have("apt-get"):
            family, pm = (family or ("debian" if "debian" in name.lower() else "ubuntu")), "apt"
        elif _have("dnf"):
            family, pm = family or "fedora", "dnf"
        elif _have("yum"):
            family, pm = family or "el", "yum"
        elif _have("zypper"):
            family, pm = family or "opensuse", "zypper"

    return {"family": family, "pm": pm, "id": id_, "name": name,
            "codename": codename, "version": version}


def _arch() -> str:
    m = os.uname().machine
    return {"x86_64": "x86_64", "amd64": "x86_64",
            "aarch64": "aarch64", "arm64": "aarch64"}.get(m, m)


def _find_mirror(mirror_id: str):
    d = detect()
    for m in MIRRORS.get(d["family"], []):
        if m["id"] == mirror_id:
            return m
    return None


# ---------------------------------------------------------------------------
# 测速 URL 与镜像列表
# ---------------------------------------------------------------------------

def _test_url(mirror: dict, d: dict) -> str | None:
    base = mirror["base"].rstrip("/")
    fam = d["family"]
    code = d["codename"]
    if fam in ("ubuntu", "debian") and code:
        return f"{base}/dists/{code}/Release"
    if fam == "fedora":
        ver = d["version"] or "40"
        return f"{base}/releases/{ver}/Everything/{_arch()}/os/repodata/repomd.xml"
    if fam == "el":
        sub = _el_subpath(d)
        ver = (d["version"] or "9").split(".")[0]
        return f"{base}/{sub}/{ver}/BaseOS/{_arch()}/os/repodata/repomd.xml"
    if fam == "opensuse":
        return f"{base}/{_oss_path(d)}/repodata/repomd.xml"
    return None


def available() -> dict:
    d = detect()
    items = []
    for m in MIRRORS.get(d["family"], []):
        items.append({
            "id": m["id"], "name": m["name"], "base": m["base"],
            "test_url": _test_url(m, d),
        })
    return {"detect": d, "mirrors": items}


def test_mirror(mirror_id: str, cap_bytes: int = 2 * 1024 * 1024, timeout: int = 8):
    d = detect()
    mirror = _find_mirror(mirror_id)
    if not mirror:
        return False, {"error": "未知镜像 id"}
    url = _test_url(mirror, d)
    if not url:
        return False, {"error": "该发行版暂不支持测速"}

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "SysGuard/1.0"})
        t0 = time.monotonic()
        with urllib.request.urlopen(req, timeout=timeout) as r:
            status = r.status
            total = 0
            while total < cap_bytes:
                chunk = r.read(65536)
                if not chunk:
                    break
                total += len(chunk)
        dt = time.monotonic() - t0
        speed_bps = total / dt if dt > 0 else 0.0
        return True, {"url": url, "status": status, "bytes": total,
                      "seconds": round(dt, 2), "speed_mbps": round(speed_bps / 1e6, 2)}
    except Exception as e:  # 超时/连接失败/404 等
        return False, {"url": url, "error": str(e)}


# ---------------------------------------------------------------------------
# 当前源（只读）
# ---------------------------------------------------------------------------

def current() -> dict:
    d = detect()
    if d["pm"] == "apt":
        hosts = set()
        txt = shell.read_file("/etc/apt/sources.list")
        for line in txt.splitlines():
            line = line.strip()
            if line.startswith("deb ") and "://" in line:
                hosts.add(line.split()[1].split("/")[2])
        files = []
        try:
            for fn in sorted(os.listdir("/etc/apt/sources.list.d")):
                if fn.endswith((".list", ".sources")):
                    files.append(fn)
        except OSError:
            pass
        return {"pm": "apt", "hosts": sorted(hosts), "files": files}
    if d["pm"] in ("dnf", "yum"):
        return {"pm": d["pm"], "repos": _repo_baseurls("/etc/yum.repos.d")}
    if d["pm"] == "zypper":
        return {"pm": "zypper", "repos": _repo_baseurls("/etc/zypp/repos.d")}
    return {"pm": None}


def _repo_baseurls(directory: str) -> list:
    out = []
    try:
        names = sorted(os.listdir(directory))
    except OSError:
        return out
    for fn in names:
        if not fn.endswith(".repo"):
            continue
        txt = shell.read_file(os.path.join(directory, fn))
        cur_name = None
        for line in txt.splitlines():
            line = line.strip()
            if line.startswith("[") and line.endswith("]"):
                cur_name = line[1:-1]
            elif line.lower().startswith(("baseurl=", "mirrorlist=")):
                out.append({"repo": cur_name or fn, "url": line.split("=", 1)[1]})
    return out


# ---------------------------------------------------------------------------
# 生成源内容（运行于 root，仅由特权入口调用）
# ---------------------------------------------------------------------------

def _el_subpath(d: dict) -> str:
    return {"rocky": "rocky", "almalinux": "almalinux",
            "centos": "centos-stream"}.get(d["id"], "centos-stream")


def _oss_path(d: dict) -> str:
    if "tumbleweed" in d["id"]:
        return "tumbleweed/repo/oss"
    return "distribution/leap/$releasever/repo/oss"


def _apt_content(mirror: dict, d: dict) -> str:
    base = mirror["base"].rstrip("/")
    code = d["codename"]
    if d["family"] == "ubuntu":
        comps = "main restricted universe multiverse"
        return "\n".join(
            f"deb {base} {code}{s} {comps}"
            for s in ("", "-updates", "-backports", "-security")) + "\n"
    # debian
    comps = "main contrib non-free"
    lines = [
        f"deb {base} {code} {comps}",
        f"deb {base} {code}-updates {comps}",
        f"deb {base} {code}-backports {comps}",
        f"deb https://deb.debian.org/debian-security {code}-security {comps}",
    ]
    return "\n".join(lines) + "\n"


def _dnf_content(mirror: dict, d: dict) -> str:
    base = mirror["base"].rstrip("/")
    ver = d["version"] or "$releasever"
    arch = _arch()
    return (
        "[sysguard-fedora]\n"
        f"name=Fedora {ver} - {arch}\n"
        f"baseurl={base}/releases/$releasever/Everything/$basearch/os/\n"
        "gpgcheck=0\nenabled=1\n\n"
        "[sysguard-fedora-updates]\n"
        f"name=Fedora {ver} - {arch} - Updates\n"
        f"baseurl={base}/updates/$releasever/Everything/$basearch/\n"
        "gpgcheck=0\nenabled=1\n"
    )


def _el_content(mirror: dict, d: dict) -> str:
    base = f"{mirror['base'].rstrip('/')}/{_el_subpath(d)}"
    return (
        "[sysguard-base]\nname=BaseOS\n"
        f"baseurl={base}/$releasever/BaseOS/$basearch/os/\n"
        "gpgcheck=0\nenabled=1\n\n"
        "[sysguard-appstream]\nname=AppStream\n"
        f"baseurl={base}/$releasever/AppStream/$basearch/os/\n"
        "gpgcheck=0\nenabled=1\n"
    )


def _zypper_content(mirror: dict, d: dict) -> str:
    base = f"{mirror['base'].rstrip('/')}/{_oss_path(d)}"
    return (
        "[sysguard-oss]\nname=openSUSE OSS\n"
        f"baseurl={base}\n"
        "gpgcheck=0\nenabled=1\n"
    )


def build_sources(mirror_id: str) -> tuple[bool, list | str]:
    """返回 (ok, entries)。entries 为 [(绝对路径, 内容)] 或错误字符串。"""
    d = detect()
    mirror = _find_mirror(mirror_id)
    if not mirror:
        return False, "未知镜像 id"
    fam = d["family"]
    if fam in ("ubuntu", "debian"):
        if not d["codename"]:
            return False, "无法确定发行版代号（codename）"
        return True, [("/etc/apt/sources.list", _apt_content(mirror, d))]
    if fam == "fedora":
        return True, [("/etc/yum.repos.d/sysguard-mirror.repo", _dnf_content(mirror, d))]
    if fam == "el":
        return True, [("/etc/yum.repos.d/sysguard-mirror.repo", _el_content(mirror, d))]
    if fam == "opensuse":
        return True, [("/etc/zypp/repos.d/sysguard-oss.repo", _zypper_content(mirror, d))]
    return False, "当前发行版暂不支持自动切换镜像源"


def _managed_sources() -> list[str]:
    """需要备份的源文件/目录。"""
    d = detect()
    if d["pm"] == "apt":
        return ["/etc/apt/sources.list", "/etc/apt/sources.list.d"]
    if d["pm"] in ("dnf", "yum"):
        return ["/etc/yum.repos.d"]
    if d["pm"] == "zypper":
        return ["/etc/zypp/repos.d"]
    return []


def _disable_existing(entries: list) -> None:
    """写入我们的源后，禁用其它可能冲突的源文件（备份已在此之前完成）。"""
    targets = set(os.path.dirname(p) for p, _ in entries)
    for t in targets:
        if not os.path.isdir(t):
            continue
        for fn in os.listdir(t):
            if fn.startswith("sysguard"):
                continue
            full = os.path.join(t, fn)
            if os.path.isfile(full) and not fn.endswith(".sysguardbak"):
                try:
                    os.rename(full, full + ".sysguardbak")
                except OSError:
                    pass


def backup_sources() -> tuple[bool, str]:
    paths = _managed_sources()
    if not paths:
        return False, "当前发行版无可备份的源"
    try:
        if os.path.isdir(BACKUP_DIR):
            shutil.rmtree(BACKUP_DIR)
        os.makedirs(BACKUP_DIR, exist_ok=True)
        for p in paths:
            base = os.path.basename(p.rstrip("/"))
            dst = os.path.join(BACKUP_DIR, base)
            if os.path.isdir(p):
                # 排除之前已有的 .sysguardbak 残留，只备份真实源
                shutil.copytree(p, dst, ignore=shutil.ignore_patterns("*.sysguardbak"))
            elif os.path.isfile(p):
                shutil.copy2(p, dst)
        return True, BACKUP_DIR
    except OSError as e:
        return False, f"备份失败：{e}"


def restore_sources() -> tuple[bool, str]:
    if not os.path.isdir(BACKUP_DIR):
        return False, "没有可用的备份"
    d = detect()
    try:
        for name in os.listdir(BACKUP_DIR):
            src = os.path.join(BACKUP_DIR, name)
            if name == "sources.list":
                shutil.copy2(src, "/etc/apt/sources.list")
            elif name == "sources.list.d":
                _reset_dir("/etc/apt/sources.list.d")
                for fn in os.listdir(src):
                    shutil.copy2(os.path.join(src, fn),
                                 os.path.join("/etc/apt/sources.list.d", fn))
            elif name == "yum.repos.d":
                _reset_dir("/etc/yum.repos.d")
                for fn in os.listdir(src):
                    shutil.copy2(os.path.join(src, fn),
                                 os.path.join("/etc/yum.repos.d", fn))
            elif name == "zypp.repos.d":
                _reset_dir("/etc/zypp/repos.d")
                for fn in os.listdir(src):
                    shutil.copy2(os.path.join(src, fn),
                                 os.path.join("/etc/zypp/repos.d", fn))
        return True, "已从备份恢复"
    except OSError as e:
        return False, f"恢复失败：{e}"


def _reset_dir(path: str) -> None:
    if os.path.isdir(path):
        shutil.rmtree(path)
    os.makedirs(path, exist_ok=True)


def write_sources(mirror_id: str) -> tuple[bool, str]:
    """特权入口 mirror_set 的主体：备份 → 写入 → 禁用冲突源。"""
    ok, entries = build_sources(mirror_id)
    if not ok:
        return False, entries
    bok, bmsg = backup_sources()
    if not bok:
        return False, bmsg
    try:
        for path, content in entries:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
        _disable_existing(entries)
        return True, mirror_id
    except OSError as e:
        return False, f"写入失败：{e}"


# ---------------------------------------------------------------------------
# GUI 端封装（普通用户，经 pkexec）
# ---------------------------------------------------------------------------

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


def apply(mirror_id: str):
    rc, out, err = shell.pkexec("mirror_set", [mirror_id], timeout=120)
    return _parse(rc, out, err)


def backup():
    rc, out, err = shell.pkexec("mirror_backup", [], timeout=60)
    return _parse(rc, out, err)


def restore():
    rc, out, err = shell.pkexec("mirror_restore", [], timeout=60)
    return _parse(rc, out, err)