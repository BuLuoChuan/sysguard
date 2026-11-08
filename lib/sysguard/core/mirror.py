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
import socket
import time
import urllib.request

from . import shell

# ---------------------------------------------------------------------------
# 镜像表（base 为各发行版专属的源前缀，尾部不带斜杠）
# ---------------------------------------------------------------------------

# 支持的发行版（其余一律声明不支持）
SUPPORTED_FAMILIES = ("ubuntu", "debian", "fedora", "mint")

# 镜像表（base 为各发行版专属的源前缀，尾部不带斜杠）。
# 每项均为真实存在的官方/知名镜像站；mint 项额外带 ubuntu_base，
# 用于切换时同时设置其 Ubuntu 基础仓库。
MIRRORS = {
    "ubuntu": [
        {"id": "aliyun", "name": "阿里云", "base": "https://mirrors.aliyun.com/ubuntu"},
        {"id": "tuna", "name": "清华大学", "base": "https://mirrors.tuna.tsinghua.edu.cn/ubuntu"},
        {"id": "ustc", "name": "中科大", "base": "https://mirrors.ustc.edu.cn/ubuntu"},
        {"id": "tencent", "name": "腾讯云", "base": "https://mirrors.cloud.tencent.com/ubuntu"},
        {"id": "huawei", "name": "华为云", "base": "https://mirrors.huaweicloud.com/ubuntu"},
        {"id": "netease", "name": "网易163", "base": "https://mirrors.163.com/ubuntu"},
        {"id": "nju", "name": "南京大学", "base": "https://mirrors.nju.edu.cn/ubuntu"},
        {"id": "lzu", "name": "兰州大学", "base": "https://mirror.lzu.edu.cn/ubuntu"},
        {"id": "sjtu", "name": "上海交大", "base": "https://mirror.sjtu.edu.cn/ubuntu"},
        {"id": "zju", "name": "浙江大学", "base": "https://mirrors.zju.edu.cn/ubuntu"},
        {"id": "cqu", "name": "重庆大学", "base": "https://mirrors.cqu.edu.cn/ubuntu"},
        {"id": "bfsu", "name": "北京外国语", "base": "https://mirrors.bfsu.edu.cn/ubuntu"},
        {"id": "bit", "name": "北京理工", "base": "https://mirror.bit.edu.cn/ubuntu"},
        {"id": "hit", "name": "哈工大", "base": "https://mirrors.hit.edu.cn/ubuntu"},
        {"id": "hust", "name": "华中科大", "base": "https://mirrors.hust.edu.cn/ubuntu"},
        {"id": "sustech", "name": "南科大", "base": "https://mirrors.sustech.edu.cn/ubuntu"},
        {"id": "kernel", "name": "kernel.org", "base": "https://mirrors.kernel.org/ubuntu"},
        {"id": "official", "name": "官方(archive)", "base": "https://archive.ubuntu.com/ubuntu"},
    ],
    "debian": [
        {"id": "official", "name": "官方(deb.debian.org)", "base": "https://deb.debian.org/debian"},
        {"id": "aliyun", "name": "阿里云", "base": "https://mirrors.aliyun.com/debian"},
        {"id": "tuna", "name": "清华大学", "base": "https://mirrors.tuna.tsinghua.edu.cn/debian"},
        {"id": "ustc", "name": "中科大", "base": "https://mirrors.ustc.edu.cn/debian"},
        {"id": "tencent", "name": "腾讯云", "base": "https://mirrors.cloud.tencent.com/debian"},
        {"id": "huawei", "name": "华为云", "base": "https://mirrors.huaweicloud.com/debian"},
        {"id": "netease", "name": "网易163", "base": "https://mirrors.163.com/debian"},
        {"id": "nju", "name": "南京大学", "base": "https://mirrors.nju.edu.cn/debian"},
        {"id": "lzu", "name": "兰州大学", "base": "https://mirror.lzu.edu.cn/debian"},
        {"id": "sjtu", "name": "上海交大", "base": "https://mirror.sjtu.edu.cn/debian"},
        {"id": "zju", "name": "浙江大学", "base": "https://mirrors.zju.edu.cn/debian"},
        {"id": "bfsu", "name": "北京外国语", "base": "https://mirrors.bfsu.edu.cn/debian"},
        {"id": "hit", "name": "哈工大", "base": "https://mirrors.hit.edu.cn/debian"},
        {"id": "hust", "name": "华中科大", "base": "https://mirrors.hust.edu.cn/debian"},
        {"id": "kernel", "name": "kernel.org", "base": "https://mirrors.kernel.org/debian"},
    ],
    "fedora": [
        {"id": "tuna", "name": "清华大学", "base": "https://mirrors.tuna.tsinghua.edu.cn/fedora"},
        {"id": "ustc", "name": "中科大", "base": "https://mirrors.ustc.edu.cn/fedora"},
        {"id": "aliyun", "name": "阿里云", "base": "https://mirrors.aliyun.com/fedora"},
        {"id": "huawei", "name": "华为云", "base": "https://mirrors.huaweicloud.com/fedora"},
        {"id": "netease", "name": "网易163", "base": "https://mirrors.163.com/fedora"},
        {"id": "nju", "name": "南京大学", "base": "https://mirrors.nju.edu.cn/fedora"},
        {"id": "sjtu", "name": "上海交大", "base": "https://mirror.sjtu.edu.cn/fedora"},
        {"id": "bfsu", "name": "北京外国语", "base": "https://mirrors.bfsu.edu.cn/fedora"},
    ],
    "mint": [
        {"id": "official", "name": "官方(packages.linuxmint.com)",
         "base": "http://packages.linuxmint.com",
         "ubuntu_base": "http://archive.ubuntu.com/ubuntu"},
        {"id": "tuna", "name": "清华大学", "base": "https://mirrors.tuna.tsinghua.edu.cn/linuxmint",
         "ubuntu_base": "https://mirrors.tuna.tsinghua.edu.cn/ubuntu"},
        {"id": "ustc", "name": "中科大", "base": "https://mirrors.ustc.edu.cn/linuxmint",
         "ubuntu_base": "https://mirrors.ustc.edu.cn/ubuntu"},
        {"id": "aliyun", "name": "阿里云", "base": "https://mirrors.aliyun.com/linuxmint",
         "ubuntu_base": "https://mirrors.aliyun.com/ubuntu"},
        {"id": "nju", "name": "南京大学", "base": "https://mirrors.nju.edu.cn/linuxmint",
         "ubuntu_base": "https://mirrors.nju.edu.cn/ubuntu"},
        {"id": "sjtu", "name": "上海交大", "base": "https://mirror.sjtu.edu.cn/linuxmint",
         "ubuntu_base": "https://mirror.sjtu.edu.cn/ubuntu"},
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
    elif id_ == "linuxmint":
        family, pm = "mint", "apt"
    elif id_ == "debian":
        family, pm = "debian", "apt"
    elif id_ == "fedora":
        family, pm = "fedora", "dnf"
    elif id_ == "linuxmint" or "mint" in like:
        family, pm = "mint", "apt"
    elif id_ in ("centos", "rhel", "rocky", "almalinux") or any(
            x in like for x in ("rhel", "centos", "rocky", "almalinux")):
        # 不在支持列表内：pm 仍会给出，但 family 置空 -> available() 报不支持
        pm = "dnf" if _have("dnf") else ("yum" if _have("yum") else "yum")
    elif "opensuse" in id_ or "suse" in like:
        pm = "zypper"

    # 兜底：按可用包管理器推断（仅受支持家族会被重新映射）
    if pm is None:
        if _have("apt-get"):
            pm = "apt"
            if "debian" in name.lower():
                family = "debian"
            elif "mint" in name.lower() or "mint" in like:
                family = "mint"
            else:
                family = "ubuntu"
        elif _have("dnf"):
            pm, family = "dnf", "fedora"
        elif _have("yum"):
            pm = "yum"
        elif _have("zypper"):
            pm = "zypper"

    ubuntu_codename = d.get("UBUNTU_CODENAME") or codename
    return {"family": family, "pm": pm, "id": id_, "name": name,
            "codename": codename, "version": version,
            "ubuntu_codename": ubuntu_codename,
            "supported": family in SUPPORTED_FAMILIES}


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
    if fam in ("ubuntu", "debian", "mint") and code:
        return f"{base}/dists/{code}/Release"
    if fam == "fedora":
        ver = d["version"] or "40"
        return f"{base}/releases/{ver}/Everything/{_arch()}/os/repodata/repomd.xml"
    return None


def available() -> dict:
    d = detect()
    items = []
    for m in MIRRORS.get(d["family"], []):
        items.append({
            "id": m["id"], "name": m["name"], "base": m["base"],
            "test_url": _test_url(m, d),
        })
    return {"detect": d, "mirrors": items,
            "supported": d["family"] in SUPPORTED_FAMILIES}


def _url_host(url: str) -> str | None:
    try:
        from urllib.parse import urlparse
        return urlparse(url).hostname
    except Exception:
        return None


def _http_probe(url: str, host: str | None, cap_bytes: int, timeout: int = 8):
    """单次 HTTP 探测：返回 (ok, result)。result 含下载速度与 TCP 连接延时。"""
    lat_ms = None
    if host:
        try:
            t0 = time.monotonic()
            with socket.create_connection((host, 443), timeout=min(timeout, 5)):
                lat_ms = round((time.monotonic() - t0) * 1000, 1)
        except OSError:
            lat_ms = None
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "SysGuard/1.2"})
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
        speed_mbps = (total / 1e6) / dt if dt > 0 else 0.0
        return True, {"status": status, "bytes": total, "seconds": round(dt, 2),
                      "speed_mbps": round(speed_mbps, 2), "latency_ms": lat_ms}
    except Exception as e:  # 超时/连接失败/404 等
        return False, {"error": str(e), "latency_ms": lat_ms}


def test_mirror(mirror_id: str, cap_bytes: int = 2 * 1024 * 1024, timeout: int = 8):
    d = detect()
    mirror = _find_mirror(mirror_id)
    if not mirror:
        return False, {"error": "未知镜像 id"}
    url = _test_url(mirror, d)
    if not url:
        return False, {"error": "该发行版暂不支持测速"}
    ok, res = _http_probe(url, _url_host(url), cap_bytes, timeout)
    if not ok:
        return False, {"url": url, "error": res.get("error")}
    res["url"] = url
    return True, res


def test_latency(mirror_id: str, samples: int = 4, timeout: int = 5):
    """测延时：对镜像站点做多次 TCP 握手（443 端口），取平均/最值。"""
    d = detect()
    mirror = _find_mirror(mirror_id)
    if not mirror:
        return False, {"error": "未知镜像 id"}
    url = _test_url(mirror, d)
    host = _url_host(url) if url else None
    if not host:
        return False, {"error": "该发行版暂不支持测速"}
    times = []
    for _ in range(samples):
        try:
            t0 = time.monotonic()
            with socket.create_connection((host, 443), timeout=timeout):
                times.append(round((time.monotonic() - t0) * 1000, 1))
        except OSError:
            times.append(None)
    ok_times = [t for t in times if t is not None]
    if not ok_times:
        return False, {"error": "无法连接到镜像站点"}
    return True, {"host": host, "samples": samples, "success": len(ok_times),
                  "avg_ms": round(sum(ok_times) / len(ok_times), 1),
                  "min_ms": round(min(ok_times), 1),
                  "max_ms": round(max(ok_times), 1)}


def _score(speed_mbps, latency_ms):
    """综合评分：单位延时的吞吐量，速度越高、延时越低则分越高。

    速度(网速)与延时按此公式耦合：score = speed * (100 / latency)。
    失败或无法测速时返回 -1（排序时排最后）。
    """
    if speed_mbps is None:
        return -1.0
    lat = latency_ms if latency_ms and latency_ms > 0 else 999.0
    return round(speed_mbps * (100.0 / max(lat, 1.0)), 3)


def test_all(cap_bytes: int = 2 * 1024 * 1024, timeout: int = 8):
    """一键测试当前发行版全部镜像的网速与延时，并按综合评分降序排序。

    返回 (ok, {"detect": d, "results": [...]})，results 已按 score 从高到低
    排列（测速失败的排在最后）。每个结果项含 mirror、ok、speed_mbps、
    latency_ms、score、error。
    """
    d = detect()
    results = []
    for m in MIRRORS.get(d["family"], []):
        url = _test_url(m, d)
        if not url:
            results.append({"mirror": m, "ok": False, "speed_mbps": None,
                            "latency_ms": None, "score": -1.0,
                            "error": "不支持该发行版"})
            continue
        ok, res = _http_probe(url, _url_host(url), cap_bytes, timeout)
        speed = res["speed_mbps"] if ok else None
        lat = res.get("latency_ms") if ok else None
        results.append({
            "mirror": m,
            "ok": ok,
            "speed_mbps": speed,
            "latency_ms": lat,
            "score": _score(speed, lat),
            "error": None if ok else res.get("error"),
        })
    # 成功在前并按评分降序，失败按 score=-1 沉底；整体稳定性排序
    results.sort(key=lambda r: (r["ok"], r["score"]), reverse=True)
    return True, {"detect": d, "results": results}


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


def _mint_content(mirror: dict, d: dict) -> str:
    """Linux Mint 源：mint 发行版仓库 + 同站 Ubuntu 基础仓库。"""
    base = mirror["base"].rstrip("/")
    code = d["codename"]               # mint 代号（xia/wilma 等）
    ucode = d.get("ubuntu_codename") or code
    ub = mirror.get("ubuntu_base") or base.replace("/linuxmint", "/ubuntu")
    comp = "main restricted universe multiverse"
    lines = [
        f"deb {base} {code} main upstream import backport",
        f"deb {ub} {ucode} {comp}",
        f"deb {ub} {ucode}-updates {comp}",
        f"deb {ub} {ucode}-security {comp}",
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
    if fam == "mint":
        if not d["codename"]:
            return False, "无法确定发行版代号（codename）"
        return True, [("/etc/apt/sources.list.d/sysguard-mint.list",
                       _mint_content(mirror, d))]
    if fam == "fedora":
        return True, [("/etc/yum.repos.d/sysguard-mirror.repo", _dnf_content(mirror, d))]
    return False, "当前发行版暂不支持自动切换镜像源（仅支持 Ubuntu/Debian/Fedora/Linux Mint 及其衍生版）"


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