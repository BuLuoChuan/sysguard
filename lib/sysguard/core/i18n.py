# -*- coding: utf-8 -*-
"""中文环境检测：中文字体、输入法（fcitx/ibus）、系统中文 locale（只读给出建议）。"""
from __future__ import annotations

import re

from . import shell


CJK_FONTS = ("Noto Sans CJK SC", "WenQuanYi", "Source Han Sans SC",
             "Noto Sans SC", "PingFang")


def cjk_fonts() -> list[str]:
    """已安装的中文字体（fc-list 匹配）。"""
    if not shell.which("fc-list"):
        return []
    rc, out, _ = shell.run(["fc-list", ":lang=zh", "family"], timeout=30)
    if rc != 0:
        return []
    fams = set()
    for line in out.splitlines():
        fam = line.split(",")[0].strip()
        if fam:
            fams.add(fam)
    return sorted(fams)


def input_methods() -> list[dict]:
    """输入法框架安装与运行状态。"""
    ims = []
    for name in ("fcitx5", "fcitx", "ibus"):
        ims.append({
            "name": name,
            "installed": shell.which(name),
            "running": _is_running(name),
        })
    return ims


def _is_running(name):
    rc, out, _ = shell.run(["pgrep", "-x", name], timeout=10)
    return rc == 0


def env_lang() -> str:
    import os
    return os.environ.get("LANG", os.environ.get("LC_ALL", ""))


def locale_status() -> dict:
    """系统 locale 与中文语言包状态。"""
    lang = env_lang()
    zh = lang.lower().startswith("zh")
    # 已生成的 locale 列表
    rc, out, _ = shell.run(["locale", "-a"], timeout=20)
    locales = set()
    if rc == 0:
        locales = {l.strip() for l in out.splitlines() if l.strip()}
    zh_locales = sorted(l for l in locales if l.lower().startswith("zh"))
    return {
        "lang": lang,
        "is_zh": zh,
        "zh_locales_available": zh_locales,
    }


def summary() -> dict:
    """中文环境总体检测。"""
    return {
        "fonts": cjk_fonts(),
        "input_methods": input_methods(),
        "locale": locale_status(),
    }


# 安装/配置指令（仅展示，本软件不代为执行）
def install_hints() -> dict:
    """返回各缺项的安装建议文本。"""
    hints = {
        "fonts": (
            "Debian/Ubuntu：\n"
            "  sudo apt install fonts-noto-cjk fonts-noto-cjk-extra\n"
            "Fedora/RHEL：\n"
            "  sudo dnf install google-noto-sans-cjk-fonts google-noto-serif-cjk-fonts"
        ),
        "fcitx5": (
            "Debian/Ubuntu：\n"
            "  sudo apt install fcitx5 fcitx5-chinese-addons fcitx5-config-qt\n"
            "Fedora/RHEL：\n"
            "  sudo dnf install fcitx5 fcitx5-chinese-addons"
        ),
        "ibus": (
            "Debian/Ubuntu：\n"
            "  sudo apt install ibus ibus-libpinyin\n"
            "Fedora/RHEL：\n"
            "  sudo dnf install ibus ibus-libpinyin"
        ),
        "locale": (
            "Debian/Ubuntu 生成并启用中文 locale：\n"
            "  sudo dpkg-reconfigure locales   # 勾选 zh_CN.UTF-8\n"
            "  sudo localectl set-locale LANG=zh_CN.UTF-8\n"
            "Fedora/RHEL：\n"
            "  sudo localectl set-locale LANG=zh_CN.UTF-8\n"
            "设置后重新登录生效。"
        ),
    }
    return hints


def switch_locale(lang="zh"):
    """一键切换系统语言环境（zh/en），经 pkexec 特权入口执行。返回 (ok, msg)。"""
    import json
    if lang not in ("zh", "en"):
        return False, "非法语言参数"
    rc, out, err = shell.pkexec("i18n_set", [lang], timeout=180)
    msg = (out or "").strip()
    if not msg.lstrip().startswith("{"):
        if rc == 126:
            return False, "授权被取消或 pkexec 不可用"
        return False, (err or out or f"退出码 {rc}").strip()
    try:
        obj = json.loads(msg)
    except json.JSONDecodeError:
        return False, (err or out).strip()
    if obj.get("ok"):
        data = obj.get("data") or {}
        note = "（已写入 /etc/locale.conf 兜底）" if data.get("fallback") else ""
        return True, f"已切换为 {data.get('lang', lang)}{note}，重新登录后生效"
    return False, obj.get("error", "未知错误")