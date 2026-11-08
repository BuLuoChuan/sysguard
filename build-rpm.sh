#!/bin/bash
# 构建 SysGuard 的 noarch RPM 包。
# 纯 Python 脚本，架构无关，产出单个 noarch RPM，适用所有架构
# （x86_64 / aarch64 及其它受支持的 Linux）。
#
# 用法: ./build-rpm.sh [版本号]   默认 1.2.1
#
# 依赖:
#   - RPM/Fedora/openSUSE 等: 自带 rpmbuild（sudo dnf install rpm-build）
#   - Debian/Ubuntu 无 root 场景: 本脚本会自动探测 /tmp/rpmtools 下的便携
#     rpmbuild（通过 `apt-get download rpm rpm-common ...` + `dpkg-deb -x` 提取），
#     并为其指定真实 rpmrc/macros 与空的 _dbpath。
set -euo pipefail

SRC_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
VERSION="${1:-1.2.1}"
RPMBUILD="${RPMBUILD:-rpmbuild}"

TOPDIR="$SRC_DIR/build/rpmbuild"
OUT="$SRC_DIR/build"

ARGS=( -bb )

# 便携无 root 环境：仅当系统没有 rpm 配置、且存在提取的便携 rpmbuild 时启用。
# 注意：--rcfile/--macros 必须放在带空格的 --define 路径之前，否则会干扰参数解析。
if [ ! -f /usr/lib/rpm/rpmrc ] && [ -x /tmp/rpmtools/usr/bin/rpmbuild ]; then
    RPMBUILD=/tmp/rpmtools/usr/bin/rpmbuild
    export LD_LIBRARY_PATH="/tmp/rpmtools/usr/lib/x86_64-linux-gnu${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
    ARGS+=( --rcfile /tmp/rpmtools/usr/lib/rpm/rpmrc )
    ARGS+=( --macros /tmp/rpmtools/usr/lib/rpm/macros )
    ARGS+=( --define "_rpmconfigdir /tmp/rpmtools/usr/lib/rpm" )
    ARGS+=( --define "_dbpath /tmp/sysguard-rpmdb" )
    mkdir -p /tmp/sysguard-rpmdb
fi

ARGS+=( --define "_topdir $TOPDIR" )
ARGS+=( --define "sgroot $SRC_DIR" )

if ! command -v "$RPMBUILD" >/dev/null 2>&1 && [ ! -x "$RPMBUILD" ]; then
    echo "错误：未找到 rpmbuild（$RPMBUILD）。" >&2
    echo "RPM/Fedora 系请执行：sudo dnf install rpm-build" >&2
    echo "Debian/Ubuntu 请执行：sudo apt install rpm" >&2
    exit 1
fi

echo "==> 清理并准备 rpmbuild 顶层目录"
rm -rf "$TOPDIR"
mkdir -p "$TOPDIR"/{BUILD,BUILDROOT,RPMS,SOURCES,SPECS,SRPMS}

echo "==> 构建 noarch RPM"
"$RPMBUILD" "${ARGS[@]}" "$SRC_DIR/rpm/sysguard.spec"

echo "==> 复制产物到 $OUT"
mkdir -p "$OUT"
find "$TOPDIR/RPMS" -name '*.rpm' -exec cp -f {} "$OUT/" \;

echo
echo "构建完成："
ls -l "$OUT"/*.rpm