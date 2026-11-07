#!/bin/sh
# SysGuard 源码安装脚本（也支持卸载）。
# 将本项目源码安装到系统标准位置，文件布局与 deb/rpm 完全一致。
# 用法:
#   sudo ./install.sh                 # 安装
#   sudo ./install.sh --uninstall     # 卸载
set -eu

SRC_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
LIBDIR=/usr/lib/sysguard
BINDIR=/usr/bin
SBINDIR=/usr/sbin
APPDIR=/usr/share/applications
POLKITDIR=/usr/share/polkit-1/actions

MODE=install
[ "${1:-}" = "--uninstall" ] && MODE=uninstall

if [ "$(id -u)" -ne 0 ]; then
    echo "请以 root 运行：sudo ./install.sh [--uninstall]" >&2
    exit 1
fi

if [ "$MODE" = uninstall ]; then
    echo "==> 卸载 SysGuard"
    rm -rf "$LIBDIR/sysguard"
    rmdir "$LIBDIR" 2>/dev/null || true
    rm -f "$BINDIR/sysguard" "$SBINDIR/sysguard-cli"
    rm -f "$APPDIR/sysguard.desktop" "$POLKITDIR/com.sysguard.policy"
    if command -v update-desktop-database >/dev/null 2>&1; then
        update-desktop-database "$APPDIR" >/dev/null 2>&1 || true
    fi
    echo "已卸载"
    exit 0
fi

echo "==> 安装 SysGuard 到系统路径"
install -d -m 0755 "$LIBDIR"
rm -rf "$LIBDIR/sysguard"
cp -a "$SRC_ROOT/lib/sysguard" "$LIBDIR/"
find "$LIBDIR/sysguard" -name __pycache__ -type d -prune -exec rm -rf {} +
find "$LIBDIR/sysguard" -type d -exec chmod 0755 {} +
find "$LIBDIR/sysguard" -type f -exec chmod 0644 {} +

install -d -m 0755 "$BINDIR" "$SBINDIR" "$APPDIR" "$POLKITDIR"
install -m 0755 "$SRC_ROOT/bin/sysguard" "$BINDIR/sysguard"
install -m 0755 "$SRC_ROOT/bin/sysguard-cli" "$SBINDIR/sysguard-cli"
install -m 0644 "$SRC_ROOT/data/sysguard.desktop" "$APPDIR/sysguard.desktop"
install -m 0644 "$SRC_ROOT/data/com.sysguard.policy" "$POLKITDIR/com.sysguard.policy"

if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$APPDIR" >/dev/null 2>&1 || true
fi

echo "安装完成。启动：sysguard（或应用菜单「系统管家 / SysGuard」）"