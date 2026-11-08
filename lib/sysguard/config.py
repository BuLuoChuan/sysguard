# -*- coding: utf-8 -*-
"""全局常量与工具映射。"""
from . import __version__, __app_name__, __app_name_cn__

APP_VERSION = __version__
APP_NAME = __app_name__
APP_NAME_CN = __app_name_cn__
PACKAGE = "sysguard"

# 特权入口（被 pkexec 调用）
PRIVILEGED_BIN = "/usr/sbin/sysguard-cli"

# 本工具需要用到、但可能缺失的外部命令（用于 GUI 里给出安装提示）
DEP_MAP = {
    "systemctl": "systemd",
    "lsblk": "util-linux",
    "sudo": "sudo",
    "pkexec": "policykit-1",
    "df": "coreutils",
    "free": "procps",
    "nproc": "coreutils",
    "ps": "procps",
    "ss": "iproute2",
    "ip": "iproute2",
    "udisksctl": "udisks2",
    "sg_start": "sg3-utils",
    "hdparm": "hdparm",
    "smartctl": "smartmontools",
    "badblocks": "e2fsprogs",
    "mount": "util-linux",
    "umount": "util-linux",
    "sysctl": "procps",
    "ufw": "ufw",
    "shred": "coreutils",
    "journalctl": "systemd",
    "localectl": "systemd",
    "locale-gen": "locales",
}

# 颜色主题（ttk 样式名，避免依赖第三方主题包）
THEME = {
    "bg": "#f5f6f7",
    "card_bg": "#ffffff",
    "accent": "#2f6fed",
    "ok": "#1e8e3e",
    "warn": "#f9a825",
    "danger": "#d93025",
}