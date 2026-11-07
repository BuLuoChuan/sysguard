#!/bin/bash
# 构建 SysGuard deb 包（架构无关 all，x86_64 与 ARM64 通用）。
# 纯 Python 脚本，无编译产物，产出单个 Architecture: all 包。
#
# 用法: ./build.sh [版本号]   默认 1.0.0
set -euo pipefail

SRC_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
VERSION="${1:-1.0.0}"
PKG="sysguard"
ARCH="all"
BUILD="$SRC_DIR/build"

echo "==> 清理旧构建目录"
rm -rf "$BUILD"
mkdir -p "$BUILD"

STAGE="$BUILD/${PKG}_${VERSION}_${ARCH}"
echo "==> 装配 ${ARCH} 包 -> $STAGE"

# 源码包（顶层为 python 包 sysguard）
install -d -m 0755 "$STAGE/usr/lib/sysguard"
cp -a "$SRC_DIR/lib/sysguard" "$STAGE/usr/lib/sysguard/"

# 清理可能的 __pycache__
find "$STAGE/usr/lib/sysguard" -name "__pycache__" -type d -prune -exec rm -rf {} +
# 规范化权限：目录 0755，源码文件 0644
find "$STAGE/usr/lib/sysguard" -type d -exec chmod 0755 {} +
find "$STAGE/usr/lib/sysguard" -type f -exec chmod 0644 {} +

# 启动脚本
install -d -m 0755 "$STAGE/usr/bin" "$STAGE/usr/sbin"
install -m 0755 "$SRC_DIR/bin/sysguard" "$STAGE/usr/bin/sysguard"
install -m 0755 "$SRC_DIR/bin/sysguard-cli" "$STAGE/usr/sbin/sysguard-cli"

# 桌面入口与 polkit 策略
install -d -m 0755 "$STAGE/usr/share/applications"
install -m 0644 "$SRC_DIR/data/sysguard.desktop" \
    "$STAGE/usr/share/applications/sysguard.desktop"
install -d -m 0755 "$STAGE/usr/share/polkit-1/actions"
install -m 0644 "$SRC_DIR/data/com.sysguard.policy" \
    "$STAGE/usr/share/polkit-1/actions/com.sysguard.policy"

# DEBIAN 控制文件
install -d -m 0755 "$STAGE/DEBIAN"
sed -e "s/__VERSION__/${VERSION}/g" \
    "$SRC_DIR/debian/control.template" > "$STAGE/DEBIAN/control"
# 确保 control 以换行结尾（dpkg-deb 对多行 Description 要求末尾换行）
printf '\n' >> "$STAGE/DEBIAN/control"
install -m 0755 "$SRC_DIR/debian/postinst" "$STAGE/DEBIAN/postinst"
install -m 0755 "$SRC_DIR/debian/prerm" "$STAGE/DEBIAN/prerm"
install -m 0755 "$SRC_DIR/debian/postrm" "$STAGE/DEBIAN/postrm"

echo "==> 构建 ${ARCH} deb"
TMPDIR="$BUILD" dpkg-deb --build --root-owner-group "$STAGE"

echo
echo "构建完成："
ls -l "$BUILD"/*.deb